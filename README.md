# Winton's Corner

*A federated community platform — Discord bot, auth layer, REST API, and web presence for the [Monke](https://winton.pro) Overwatch 2 community.*

[![Spec](https://img.shields.io/badge/spec-v0.1.0_draft-orange)](spec/SPEC.md)
[![FIPs](https://img.shields.io/badge/FIPs-6_drafts-blue)](fips/)

---

## What this is

Winton's Corner is a monorepo implementing a federated content protocol for community platforms. The reference deployment is the **Monke** Overwatch 2 Discord community at [winton.pro](https://winton.pro).

The platform lets communities share content — starting with Overwatch Workshop codes — with full provenance: every piece of content knows which identity posted it and which community it came from. Identity is provider-agnostic (Discord today, Twitch and Matrix on the roadmap). Content attribution is structural, not cosmetic.

The protocol is defined in [`spec/SPEC.md`](spec/SPEC.md). Changes are governed by [Federation Improvement Proposals](fips/).

---

## Services

| Service | Path | What it does |
|---|---|---|
| `nginx` | `apps/web-presence` | Static frontend + reverse proxy for `/auth/` and `/api/` |
| `auth-shim` | `apps/auth-shim` | Discord OAuth2 → JWT issuance (FastAPI + asyncpg) |
| `postgres` | `infra/postgres` | PostgreSQL with RLS; two databases: `wintondb` (API) and `botdb` (bot) |
| `postgrest` | (upstream image) | Auto-generated REST API from `wintondb.api` schema |
| `discord-bot` | `apps/discord-bot` | Overwatch leaderboard, voice channels, invite analytics (Python, discord.py) |

**Request flow:**

```
Browser / Bot
    │
    ▼
 nginx (:80)
    ├── /auth/*   → auth-shim  (OAuth, JWT refresh)
    ├── /api/*    → postgrest  (data, RLS-enforced)
    └── /*        → static frontend
```

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A Discord application ([create one](https://discord.com/developers/applications)) with OAuth2 redirect set

### 1. Configure

```bash
cp .env.example .env
```

Edit `.env` — the required values are:

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Superuser password for the PostgreSQL instance |
| `JWT_SECRET` | Shared secret between auth-shim and PostgREST (≥ 32 chars) |
| `AUTHENTICATOR_PASSWORD` | Password for the `authenticator` PostgREST role |
| `DISCORD_CLIENT_ID` | OAuth2 application client ID |
| `DISCORD_CLIENT_SECRET` | OAuth2 application client secret |
| `DISCORD_REDIRECT_URI` | Must match the redirect URL registered in Discord (e.g. `http://localhost/auth/discord/callback`) |
| `FRONTEND_URL` | Base URL of the frontend (e.g. `http://localhost`) |

### 2. Start

```bash
docker compose up -d
```

PostgreSQL initializes on first boot. If you're upgrading from a previous volume, wipe it first:

```bash
docker compose down -v && docker compose up -d
```

### 3. Verify

```bash
curl http://localhost/api/contexts     # should return []
curl http://localhost/auth/me          # should return {"role":"web_anon"}
```

The frontend is at `http://localhost`. The web app is at `http://localhost/app/`.

---

## Configuration Reference

Full variable list from `.env.example`:

```bash
# Postgres superuser (used only for bootstrapping)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=changeme_strong_password

# API database (auth-shim + PostgREST)
API_DB_NAME=wintondb
API_DATABASE_URL=postgresql://postgres:...@postgres:5432/wintondb

# Bot database (discord-bot)
BOT_DB_NAME=botdb
BOT_DATABASE_URL=postgresql://postgres:...@postgres:5432/botdb

# JWT (shared between auth-shim and PostgREST — must be ≥32 chars)
JWT_SECRET=changeme_at_least_32_chars_long_secret_here

# PostgREST (uses authenticator role, not superuser)
AUTHENTICATOR_PASSWORD=changeme_authenticator_pass
PGRST_DB_URI=postgres://authenticator:...@postgres:5432/wintondb
PGRST_DB_SCHEMA=api
PGRST_DB_ANON_ROLE=anon
PGRST_DB_MAX_ROWS=1000

# Discord OAuth
DISCORD_CLIENT_ID=your_discord_client_id
DISCORD_CLIENT_SECRET=your_discord_client_secret
DISCORD_REDIRECT_URI=http://localhost/auth/discord/callback
FRONTEND_URL=http://localhost
```

---

## Discord Bot

The bot is not yet wired into the main `docker-compose.yml` (see TODO comment). To run it standalone:

```bash
cd apps/discord-bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # set TOKEN, BOT_DEV_GUILDS, MONGO_URI
python src/main.py
```

The bot requires `Manage Server` and `Manage Channels` permissions to track invites and manage voice channels.

---

## Repo Structure

```
.
├── apps/
│   ├── auth-shim/      # FastAPI OAuth + JWT service
│   ├── discord-bot/    # Python Discord bot
│   └── web-presence/   # Nginx config + static frontend
├── infra/
│   └── postgres/       # Dockerfile + init scripts for PostgreSQL
├── fips/               # Federation Improvement Proposals
├── spec/
│   └── SPEC.md         # The protocol specification (v0.1.0)
└── docker-compose.yml
```

---

## Protocol

The platform implements a federated content protocol designed for community platforms. Key concepts:

- **Identity** — a single account on a single provider (`123456789@discord`)
- **Context** — a community on a provider (a Discord guild, Twitch channel)
- **Person** — a bundle of linked identities controlled by one human
- **Membership** — a provable relation between an identity and a context, carrying a role (`member`, `mod`, `owner`)

Authorization uses JWT claims enforced by PostgreSQL row-level security. Bypassing the application layer does not bypass authorization.

Read [`spec/SPEC.md`](spec/SPEC.md) for the full protocol definition.

### FIPs

| FIP | Title | Category | Status |
|---|---|---|---|
| [FIP-1](fips/FIP-1-fip-process.md) | FIP Process | Process | Draft |
| [FIP-2](fips/FIP-2-discord-adapter.md) | Discord Provider Adapter | Auth | Draft |
| [FIP-3](fips/FIP-3-profile.md) | Profile | Content | Draft |
| [FIP-4](fips/FIP-4-workshop-codes.md) | Workshop Codes | Content | Draft |
| [FIP-5](fips/FIP-5-context-registration.md) | Context Registration | Auth | Draft |
| [FIP-6](fips/FIP-6-bot-proxy-auth.md) | Bot-Proxy Authentication | Bot | Draft |

New FIPs start as GitHub Discussions. See [FIP-1](fips/FIP-1-fip-process.md) for the full lifecycle.

---

## Contributing

1. Read [`spec/SPEC.md`](spec/SPEC.md) and [`fips/README.md`](fips/README.md) to understand the protocol
2. For protocol changes, open a GitHub Discussion before drafting a FIP
3. For platform changes, open an issue or PR against this repo

**Editor:** Dercio (`@creedscode`)
