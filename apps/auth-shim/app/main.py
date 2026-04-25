import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

load_dotenv()

app = FastAPI()

DISCORD_CLIENT_ID     = os.environ["DISCORD_CLIENT_ID"]
DISCORD_CLIENT_SECRET = os.environ["DISCORD_CLIENT_SECRET"]
DISCORD_REDIRECT_URI  = os.environ["DISCORD_REDIRECT_URI"]
JWT_SECRET            = os.environ["JWT_SECRET"]
DATABASE_URL          = os.environ["DATABASE_URL"]
FRONTEND_URL          = os.environ.get("FRONTEND_URL", "").rstrip("/")

DISCORD_AUTH_URL  = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_BASE  = "https://discord.com/api/v10"

# Monke guild (only context in v1).
MONKE_GUILD_ID = "1425571463192121354"


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )
    return auth[7:]


@app.get("/auth/health")
async def health():
    return {"status": "ok"}


@app.get("/auth/discord")
async def discord_login():
    """Initiate Discord OAuth2 flow. Generates CSRF state stored in a short-lived cookie."""
    state = secrets.token_urlsafe(32)
    params = (
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify+guilds"
        f"&state={state}"
    )
    response = RedirectResponse(DISCORD_AUTH_URL + params)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=300,
        secure=False,  # set to True in production behind TLS
    )
    return response


@app.get("/auth/discord/callback")
async def discord_callback(request: Request, code: str, state: str):
    """
    OAuth2 callback. Validates CSRF state, exchanges code for token, fetches
    Discord identity + guilds, upserts person/identity/membership in the DB,
    and redirects to the frontend with a signed JWT in the URL fragment.
    """
    # CSRF validation
    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or cookie_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    async with httpx.AsyncClient() as client:
        # Exchange authorization code for Discord access token
        token_resp = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id":     DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Discord token exchange failed")
        tok              = token_resp.json()
        access_token     = tok["access_token"]
        refresh_token    = tok.get("refresh_token")
        expires_in       = tok.get("expires_in", 604800)  # Discord default: 7 days
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Fetch authenticated user's identity (FIP-2 §fetchIdentity)
        user_resp = await client.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Discord user")
        user = user_resp.json()

        # Fetch guild list for context membership sync (FIP-2 §suggestContexts)
        guilds_resp = await client.get(
            f"{DISCORD_API_BASE}/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if guilds_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Discord guilds")
        guilds = guilds_resp.json()

    discord_id = user["id"]
    handle = user["username"]
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{discord_id}/{user['avatar']}.png"
        if user.get("avatar")
        else None
    )

    # auth-shim connects as the postgres superuser so it bypasses RLS for
    # person/identity/membership management (these are read-only from the API).
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Look up existing discord identity
        row = await conn.fetchrow(
            "SELECT id, person_id FROM api.identities "
            "WHERE provider = 'discord' AND provider_user_id = $1",
            discord_id,
        )

        if row:
            # Returning user: refresh handle and avatar
            identity_id = row["id"]
            person_id = row["person_id"]
            await conn.execute(
                "UPDATE api.identities SET handle = $1, avatar_url = $2 WHERE id = $3",
                handle, avatar_url, identity_id,
            )
        else:
            # New user: create person-of-one, then identity linked to it
            person_id = await conn.fetchval(
                "INSERT INTO api.persons (platform_role) VALUES ('user') RETURNING id"
            )
            identity_id = await conn.fetchval(
                "INSERT INTO api.identities "
                "  (person_id, provider, provider_user_id, handle, avatar_url) "
                "VALUES ($1, 'discord', $2, $3, $4) RETURNING id",
                person_id, discord_id, handle, avatar_url,
            )
            await conn.execute(
                "UPDATE api.persons SET primary_identity_id = $1 WHERE id = $2",
                identity_id, person_id,
            )

        # Store/refresh Discord OAuth tokens for out-of-band re-verification
        await conn.execute(
            "INSERT INTO api.discord_tokens "
            "  (identity_id, access_token, refresh_token, token_expires_at) "
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (identity_id) DO UPDATE SET "
            "  access_token     = EXCLUDED.access_token, "
            "  refresh_token    = EXCLUDED.refresh_token, "
            "  token_expires_at = EXCLUDED.token_expires_at, "
            "  updated_at       = now()",
            identity_id, access_token, refresh_token, token_expires_at,
        )

        # Sync Monke membership (v1: Monke is the only context)
        guild_ids = {g["id"] for g in guilds}
        if MONKE_GUILD_ID in guild_ids:
            await conn.execute(
                "INSERT INTO api.memberships "
                "  (identity_id, context_id, role, established_by) "
                "SELECT $1, id, 'member', 'provider_verify' "
                "FROM   api.contexts "
                "WHERE  provider_context_id = $2 "
                "ON CONFLICT DO NOTHING",
                identity_id, MONKE_GUILD_ID,
            )

        # Fetch all context memberships for JWT claims
        membership_rows = await conn.fetch(
            "SELECT context_id::text FROM api.memberships WHERE identity_id = $1",
            identity_id,
        )
        context_ids = [r["context_id"] for r in membership_rows]

    finally:
        await conn.close()

    now = int(time.time())
    payload = {
        "role":            "authenticated",  # PostgreSQL role for PostgREST SET ROLE
        "person_id":       str(person_id),
        "active_identity": str(identity_id),
        "identities":      [str(identity_id)],
        "contexts":        context_ids,
        "iat":             now,
        "exp":             now + 3600,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # Redirect to the frontend app entry point; JS reads the fragment and saves the token.
    return RedirectResponse(f"{FRONTEND_URL}/app/#token={token}")


@app.get("/auth/me")
async def auth_me(request: Request):
    """Verify a Bearer token and return its decoded claims."""
    token = _extract_bearer(request)
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return JSONResponse(claims)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/auth/refresh")
async def auth_refresh(request: Request):
    """
    Re-issue a JWT with a fresh exp and up-to-date contexts claim.
    Accepts tokens that have been expired for up to 7 days (checked via iat).
    """
    token = _extract_bearer(request)
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token signature")

    iat = claims.get("iat", 0)
    if int(time.time()) - iat > 7 * 24 * 3600:
        raise HTTPException(status_code=401, detail="Token too old to refresh")

    identities = claims.get("identities", [])
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT context_id::text FROM api.memberships "
            "WHERE identity_id::text = ANY($1)",
            identities,
        )
        context_ids = [r["context_id"] for r in rows]
    finally:
        await conn.close()

    now = int(time.time())
    new_payload = {
        **claims,
        "contexts": context_ids,
        "iat":      now,
        "exp":      now + 3600,
    }
    new_token = jwt.encode(new_payload, JWT_SECRET, algorithm="HS256")
    return {"token": new_token}
