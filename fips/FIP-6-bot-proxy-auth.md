---
fip: 6
title: Bot-Proxy Authentication
author: Dercio (@creedscode)
status: Draft
type: Standards
category: Bot
created: 2026-04-22
requires: FIP-1, FIP-5
---

# FIP-6 - Bot-Proxy Authentication

## Abstract

This FIP defines how a context's registered bot can submit content and perform actions on behalf of a user without that user completing a full OAuth flow per action. It specifies the API key authentication, the `acting_as` claim model, the trust tiers for different action types, and the constraints (scopes, rate limits, audit) that prevent abuse.

## Motivation

The cleanest user experience for community content submission is direct: a member types `/submit_workshop <code>` in their community's Discord, the bot relays it to the platform, and it appears immediately. Forcing a full user-OAuth dance per submission destroys this UX.

But naively trusting bots to assert "user X did Y" creates obvious attack vectors: a malicious bot operator forging submissions, a compromised bot key spamming on behalf of unwilling users, a community abusing membership claims to inflate engagement.

This FIP defines a trust-tiered model: low-stakes community-scoped actions accept bot-proxy auth with appropriate constraints; sensitive identity-affecting actions require full user OAuth regardless. Each action type is assigned a tier, and the platform refuses to perform actions above a bot's authority.

## Specification

### Token issuance endpoint

```
POST /auth/bot/token
Authorization: Bearer <api_key>
Content-Type: application/json

{
  "acting_as": "123456789@discord",      // canonical identity address
  "scope": ["workshop_codes:write"]      // requested action scopes
}

Server actions:
1. Validate API key: not revoked, hash matches stored hash
2. Look up the context the key belongs to
3. Look up identity by canonical address
4. Verify identity is a member of the context (membership row exists)
5. If verifyMembership is supported (FIP-2), optionally re-verify
   against provider for actions of tier >= verified (see §Trust tiers)
6. Verify all requested scopes are subset of key's granted scopes
7. Issue short-lived JWT (TTL ≤ 5 minutes)

Response (200 OK):
{
  "token": "eyJhbGc...",
  "expires_in": 300,
  "scopes": ["workshop_codes:write"]
}

Error responses:
401 - invalid/revoked API key
403 - identity not a member of key's context
403 - scope not granted to this key
403 - verifyMembership failed (when required)
429 - rate limit exceeded
```

### JWT claims for bot-proxy tokens

A bot-proxy JWT MUST have the same shape as a user JWT (SPEC.md §6.1) plus:

```json
{
  "role":              "member",
  "person_id":         "<uuid>",
  "active_identity":   "<uuid of acting_as>",
  "identities":        ["<uuid of acting_as>"],     // single identity, not the full set
  "contexts":          ["<uuid of bot's context>"],  // single context, not the user's full set
  "exp":               <unix ts, ≤ now + 300>,
  
  "bot_proxy": {
    "issued_via_key":  "<api_key.id>",
    "scopes":          ["workshop_codes:write"]
  }
}
```

Critical differences from user JWTs:

- `identities` is the single acting identity, NOT the person's full identity set
- `contexts` is the single context the bot has authority for, NOT the user's full context list
- `bot_proxy` claim is present, allowing RLS or app code to distinguish

This narrowing prevents privilege escalation: a bot can act as user X within its own context, but cannot act as user X across other contexts X belongs to via other identities.

### Scopes

Bot-proxy tokens are scope-restricted. Defined scopes:

| Scope | Permits |
|---|---|
| `workshop_codes:write` | INSERT into workshop_codes (own context, acting identity) |
| `workshop_codes:delete:own` | DELETE workshop_codes authored by acting identity |
| `pug_listings:write` | (when defined by future FIP) |
| `profile:read` | Read public profile fields (no auth needed in practice but useful for explicitness) |

Scopes a bot key has NOT been granted MUST be rejected at token issuance. The key's scopes are stored in `api_keys.scopes` (FIP-5).

Scopes NEVER permitted for bot-proxy auth:

- Profile field writes (`profile:write`) - identity-affecting
- Identity linking (`identities:link`) - irreversible
- Context settings changes (`contexts:write`) - community-affecting
- Member moderation (`memberships:write`) - community-affecting
- Cross-context actions of any kind

These actions require full user OAuth without exception.

### Trust tiers

Each action type has a trust tier indicating the minimum auth strength required:

**Tier 1 - Bot-proxy with cached membership.**
Bot key + `acting_as` + identity has a membership row in the bot's context. No live re-verification.
- Suitable for: read operations, low-stakes writes, ephemeral content
- Examples: posting a workshop code, marking interest in a PUG

**Tier 2 - Bot-proxy with live membership re-verification.**
Tier 1 + platform calls `verifyMembership` (FIP-2 §verifyMembership) at token issuance time. Catches users who left the community since their membership was cached.
- Suitable for: moderate-stakes writes, content that affects others
- Examples: organizing a PUG, submitting a tournament bracket entry

**Tier 3 - Short-lived user-confirmed token.**
Bot generates a one-time link (e.g. `https://platform.pro/bot/confirm?token=...`); user clicks and confirms in browser; platform issues normal user JWT scoped to a single action.
- Suitable for: actions where user intent must be unambiguous
- Examples: linking a Twitch identity initiated from Discord, accepting a tournament invitation

**Tier 4 - Full user OAuth.**
Standard authentication flow. No bot involvement.
- Required for: profile changes, identity linking, account-level settings

Implementations MUST NOT permit a bot-proxy token to perform an action above its tier. The action-to-tier mapping for FIP-defined content types is specified in their respective FIPs.

For workshop_codes (FIP-4):
- Submit: Tier 1
- Delete own: Tier 1
- Delete as mod: Tier 2 (requires re-verification of mod role)

### Rate limits

Per-key rate limits MUST be enforced. Recommended defaults:

| Limit | Threshold | Window |
|---|---|---|
| Token issuance | 60 / minute | rolling |
| Token issuance burst | 10 / second | rolling |
| Distinct `acting_as` identities | 1000 / hour | rolling |

Implementations MUST track rate-limit consumption per `api_key_id` (not per IP) and return `429 Too Many Requests` with `Retry-After` header when exceeded.

Rate limits SHOULD be configurable per-context with platform-admin override, since legitimate bot operators with large communities may need higher caps.

### Audit logging

Every token issuance MUST be logged:

```sql
create table bot_proxy_audit (
  id              uuid primary key default gen_random_uuid(),
  api_key_id      uuid not null references api_keys,
  context_id      uuid not null references contexts,
  acting_identity uuid not null references identities,
  scopes          text[] not null,
  issued_at       timestamptz not null default now(),
  client_ip       inet,                              -- optional, privacy-considered
  user_agent      text,                              -- optional
  outcome         text not null                      -- 'issued' | 'denied:scope' | 'denied:membership' | etc.
);

create index bot_proxy_audit_by_key on bot_proxy_audit (api_key_id, issued_at desc);
create index bot_proxy_audit_by_identity on bot_proxy_audit (acting_identity, issued_at desc);
```

Context owners MUST be able to view their context's audit log:

```
GET /contexts/<id>/bot_audit?since=<ts>&limit=100
Authorization: Bearer <jwt>     # owner or mod
```

This is the single most important deterrent against bot operator abuse: the community itself can detect "bot is issuing tokens for users who never typed a command."

### Acting-as identity restrictions

The `acting_as` identity MUST satisfy:

1. Be a member of the bot's context (membership row exists)
2. NOT be platform-banned
3. Match the format of a canonical address (SPEC.md §3.1)

Implementations MAY additionally:

- Block `acting_as` for identities with an active "do not impersonate" flag set by the user
- Require the identity's account age to be ≥ N days before allowing bot-proxy submissions

A user opt-out is RECOMMENDED:

```
PATCH /me/bot_proxy_consent
Authorization: Bearer <jwt>     # acting as the user themselves

{ "consent": false }            // refuse all bot-proxy actions for this person
```

When consent is false, all `acting_as` requests for any of the person's identities MUST fail with 403.

### Token revocation

Bot-proxy tokens are short-lived (≤ 5 min) and not individually revocable in normal operation - they expire fast enough that revocation lists are unnecessary.

However, in incident response (key leak, bot compromise), implementations MUST support immediate cancellation of all outstanding bot-proxy tokens issued by a given key. Cleanest implementation: include a `key_generation` counter in the JWT and increment it on revocation; PostgREST validates the counter matches the current value for the key.

### Server-to-server use without acting_as

A bot MAY also perform actions as itself rather than as a user, e.g. "the Monke bot announces that the weekly tournament is starting." For these cases, omit `acting_as`:

```
POST /auth/bot/token
Authorization: Bearer <api_key>

{ "scope": ["announcements:write"] }
```

Token is issued for a synthetic platform identity representing the bot, format `bot:<context_slug>@platform`. Such actions MUST be visually distinguished in UIs (different badge, no human avatar) so users can tell when content is bot-authored vs user-authored-via-bot.

This use case is OPTIONAL; implementations MAY refuse bot-self tokens entirely.

## Rationale

### Why short-lived tokens (≤ 5 min)

Bot-proxy tokens are issued continuously and cached by the bot for the duration of a user's interaction. 5 minutes is long enough for a multi-step command flow (user types `/submit`, bot prompts for confirmation, user confirms, bot submits) but short enough that token theft has limited blast radius.

User OAuth tokens can be longer-lived because the user is present during issuance and can revoke explicitly.

### Why narrow contexts/identities in JWT to single values

A bot's authority is per-context. If a user is also in 3 other contexts via 2 other identities, a bot-proxy token must NOT be able to leverage those memberships. Narrowing the JWT enforces this at the RLS layer without requiring app-side checks.

### Why scopes rather than role-based tiers

Scopes compose better than roles. A bot might be permitted to submit workshop codes but not delete them; one scope each. Roles ("write-bot", "mod-bot") would couple unrelated permissions and require new roles for every combination.

### Why permanent scope blacklist for sensitive actions

The principle: bot-proxy auth is a UX optimization for actions that are recoverable. Identity changes are not recoverable in the same way (linking an identity has external implications, profile changes affect cross-community presentation). Forcing user OAuth for these is a small cost for a large safety win.

### Why audit logs are owner-visible

Centralized audit (only platform admins can see) doesn't give community owners the agency to detect their own bot's misbehavior. Decentralized audit (only the user can see their own actions) doesn't help a community detect systemic issues. Owner-visible is the right granularity: the community polices its own bot.

### Why consent opt-out

Some users may strongly prefer to perform all actions personally. Bot-proxy is convenient but reduces user agency. An opt-out respects that preference without removing the feature for others.

## Backwards Compatibility

This is the first bot-proxy FIP. Nothing to break.

The existing reference Discord bot in `apps/discord-bot` does not currently use bot-proxy auth (no platform exists yet). It will adopt this FIP when integrated.

## Reference Implementation

To be linked when the auth shim's `/auth/bot/token` endpoint is built. Reference implementation lives at `apps/auth-shim/bot-proxy.ts` (or equivalent).

## Security Considerations

**API key leakage is the dominant risk.** Most threats reduce to "attacker has the key." Mitigations:

- Hashed storage (FIP-5)
- Easy rotation (FIP-5)
- Rate limits cap blast radius
- Audit logs make abuse detectable
- Scope restrictions cap the worst case

**Bot operator gone rogue.** A malicious bot operator could submit fake content under their members' names. Detected by audit log review (members notice "I never submitted this"). Mitigated structurally because the worst case is "spam in their own community," not "platform-wide compromise."

**Token replay.** Bot-proxy tokens are bearer tokens. An attacker who intercepts one can use it until expiry. Mitigations: HTTPS-only, short TTL, optional `key_generation` for incident response.

**Acting-as enumeration.** A bot could probe `acting_as` for arbitrary identity addresses to learn which users are members of its context. Mitigation: rate limit by `acting_as` lookup attempts independent of token issuance success.

**Membership claim race.** Between token issuance (T0) and action execution (T1), the user could leave the context. The token is still valid. For low-stakes actions this is acceptable; for higher-stakes actions, RLS policies that re-check membership at action time provide defense in depth.

**Consent bypass via identity linking.** A user opts out of bot-proxy via their primary identity. They later link a new identity. Does the opt-out cascade? Yes: consent is per-person, applied to all linked identities. Implementations MUST enforce this.

**Synthetic bot identity confusion.** A bot acting as itself (`bot:monke@platform`) should be visually distinguishable from a user. Implementations MUST render bot-authored content with clear "from <community> bot" indication, never as if a human authored it.

**Cross-context privilege escalation prevented.** The narrowed JWT (single identity, single context) is the structural defense. RLS policies referencing JWT claims will naturally fail to grant cross-context access. Implementations MUST verify this property in tests.

## Copyright

CC0 1.0 Universal.