---
fip: 5
title: Context Registration
author: Dercio (@creedscode)
status: Draft
type: Standards
category: Auth
created: 2026-04-22
requires: FIP-1, FIP-2
---

# FIP-5 - Context Registration

## Abstract

This FIP defines how a community owner self-registers their community as a context on the platform: how ownership is proven, how a slug is claimed, what is issued in return, and how registration can be transferred or revoked.

This is the mechanism that turns a single-deployment platform into a multi-tenant one without giving up control over who can register or what they can do once registered.

## Motivation

The protocol's value compounds with each new context. Onboarding requires either an admin manually creating context rows (doesn't scale) or a self-service flow with proper verification (scales, but needs to be designed carefully).

A naive "anyone can register any context" flow creates several problems: squatting (registering `monke@discord` before the real Monke owner), impersonation (claiming to own a community you don't), and resource abuse (registering thousands of fake contexts to spam-feed). This FIP defines the verification model that prevents all three.

## Specification

### Registration flow

```
1. User authenticates via the relevant provider (FIP-2 for Discord)
2. Platform fetches user's contexts via suggestContexts
3. User selects a context to register (must be one suggestContexts returned)
4. Platform calls verifyMembership for that context, requiring native_role = 'owner'
5. If verification passes, platform creates the contexts row, generates an API key, and returns it to the user once
6. The user is recorded as the owner_identity_id and granted owner membership
```

### API endpoints

```
GET /contexts/registerable
Authorization: Bearer <jwt>

  Returns: list of contexts the user could register, drawn from
  suggestContexts results filtered to native_role = 'owner' and
  not already registered.

  Response:
  [
    {
      "provider": "discord",
      "provider_context_id": "1425571463192121354",
      "name": "Monke",
      "icon_url": "https://...",
      "already_registered": false
    }
  ]
```

```
POST /contexts/register
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "provider": "discord",
  "provider_context_id": "1425571463192121354",
  "slug": "monke",                   // optional, see §Slug claim
  "display_name": "Monke"            // optional, defaults to provider name
}

  Server actions:
  1. Verify the user has native_role 'owner' on this context via
     verifyMembership (FIP-2 §verifyMembership)
  2. Verify the context is not already registered
  3. If slug provided, verify it is available and well-formed
  4. Create contexts row with verified=true
  5. Insert membership for the registering identity with role='owner'
  6. Generate API key (see §API key issuance)
  7. Return context details + API key (this is the only time the
     full key is exposed)

  Response (201 Created):
  {
    "context": {
      "id": "uuid",
      "address": "1425571463192121354@discord",
      "slug": "monke",
      "name": "Monke",
      "verified": true
    },
    "api_key": "fip_live_abc123...xyz",
    "api_key_id": "uuid",
    "warning": "Store this key securely. It will not be shown again."
  }
```

### Slug claim

Slugs are global per-provider (SPEC.md §3.2). On registration:

- If `slug` omitted, no slug is set; context is reachable only by canonical address
- If `slug` provided:
  - MUST match `^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$` (lowercase, alphanumeric + hyphens, 3–32 chars, no leading/trailing hyphen)
  - MUST NOT be a reserved word (see §Reserved slugs)
  - MUST be unused by any other context with the same provider
  - First-come, first-served

Slugs MAY be changed later via:

```
PATCH /contexts/<id>
Authorization: Bearer <jwt>     # must be owner

{ "slug": "new-slug" }
```

Old slugs are not retained or aliased; URL changes are the owner's responsibility to communicate.

### Reserved slugs

The following slugs MUST NOT be assigned via registration:

- `admin`, `api`, `auth`, `app`, `assets`, `static`, `public`, `private`
- `system`, `platform`, `official`, `support`, `help`, `about`
- `login`, `logout`, `register`, `signup`, `signin`
- `discord`, `twitch`, `matrix` (provider names - confusing if a context shares the name)
- `null`, `undefined`, `none`, `default`

Implementations MAY extend this list. Reserved slugs MAY be assigned manually by platform admins for legitimate uses.

### API key issuance

Each registered context receives one API key on registration. Keys:

- Are formatted `fip_<env>_<base64-random>` where `<env>` is `live` or `test`
- Have ≥ 256 bits of entropy in the random portion
- Are hashed (SHA-256 or stronger) before storage; the platform NEVER stores plaintext
- Are returned in full exactly once, at issuance
- Are scoped to a single context - a Monke key cannot act for any other context

Schema additions:

```sql
create table api_keys (
  id                  uuid primary key default gen_random_uuid(),
  context_id          uuid not null references contexts on delete cascade,
  key_prefix          text not null,                    -- first 12 chars for identification
  key_hash            text not null unique,             -- SHA-256 of full key
  label               text,                              -- user-set name ("monke-bot-prod")
  created_by          uuid not null references identities,
  created_at          timestamptz not null default now(),
  last_used_at        timestamptz,
  revoked_at          timestamptz,
  
  -- scoped capabilities (see FIP-6)
  scopes              text[] not null default '{}'
);

create index api_keys_by_context on api_keys (context_id);
create index api_keys_by_hash on api_keys (key_hash);
```

### Key rotation

Owners can issue additional keys and revoke existing ones:

```
GET /contexts/<id>/api_keys                            # list (no plaintext, only metadata)
POST /contexts/<id>/api_keys                           # issue new key
DELETE /contexts/<id>/api_keys/<key_id>                # revoke
```

A revoked key MUST be rejected immediately on subsequent requests. Implementations SHOULD additionally support a `last_used_at` display so owners can audit which keys are still in use.

A context MAY have multiple active keys simultaneously (useful for zero-downtime rotation: issue new key, deploy with new key, revoke old key).

### Owner transfer

Context ownership MAY be transferred:

```
POST /contexts/<id>/transfer_ownership
Authorization: Bearer <jwt>     # must be current owner

{
  "new_owner_identity_id": "uuid"
}
```

Server requires:

1. Caller is current `owner_identity_id`
2. Target identity is a member of the context with role `mod` or `owner`
3. Target identity belongs to a person with verified email (if applicable) - implementations MAY require additional confirmation (email link, second factor)

After transfer:
- Old owner's membership role is downgraded to `mod`
- New owner's membership role is set to `owner`
- `contexts.owner_identity_id` is updated
- Existing API keys remain valid but a notification SHOULD be sent to the new owner so they can rotate if desired

### Registration revocation

A context's registration MAY be revoked by:

- The platform (for ToS violations, abuse, etc.)
- The context owner (voluntary deregistration)

Revocation:
- Soft-deletes the context (`contexts.deleted_at` set)
- Revokes all API keys
- Preserves all content for attribution; `origin_context_id` references remain valid
- The slug becomes available for re-claim after a 90-day cool-down

```
DELETE /contexts/<id>
Authorization: Bearer <jwt>     # must be owner or platform admin
```

### Re-verification

A context's verified status SHOULD be re-checked periodically (recommended: weekly) by re-running `verifyMembership` for the owner. If the owner has lost `owner` role on the provider side (e.g. transferred their Discord guild), the platform context SHOULD be flagged for review.

Loss of provider-side ownership does NOT automatically revoke the context registration - community ownership at the platform level is independent of provider-side roles. But a flagged status alerts platform admins to potential conflicts.

## Rationale

### Why require provider-side ownership for registration

The simplest verification that scales without manual review. Anyone with `MANAGE_GUILD` on a Discord guild can credibly claim to represent that community. Lower bars (any member can register) invite squatting; higher bars (manual review) don't scale.

### Why one key per context, with rotation

Multiple keys per context enables zero-downtime rotation, multiple bots per community (a content bot + an analytics bot), and key-level audit ("which key submitted this?"). One key would be simpler but would force key sharing across deployments.

### Why hash keys before storage

Standard practice. Database compromise should not equal credential compromise. The plaintext-once pattern is borrowed from GitHub personal access tokens, Stripe API keys, and similar.

### Why slugs are first-come-first-served

The simplest fair rule. Disputes (community A registers `pro-ow`, community B feels they have a better claim) are resolved by community A choosing to release the slug or platform admin intervention. Trying to encode a "rightful claim" algorithm is fraught.

### Why preserve content on registration revocation

Attribution outlives institutions. A community shutting down or losing platform access shouldn't erase the contributions of its members. Showing "from [Defunct Community]" with a soft-deleted indicator is more honest than orphaning the content.

### Why re-verification is non-blocking

Discord ownership changes (someone sells/transfers a server) are normal. Auto-revoking the platform context on provider-side ownership change would be hostile to legitimate transfers. Flagging for review is the right balance.

## Backwards Compatibility

This is the first context registration FIP. Existing pre-registered contexts (initially: just `monke@discord`) MAY be grandfathered with `verified=true` and a synthetic API key issuance, as long as the owner subsequently rotates.

## Reference Implementation

To be linked when the auth shim's registration endpoints are built. Reference implementation lives at `apps/auth-shim/contexts/register.ts` (or equivalent).

## Security Considerations

**Squatting via stolen credentials.** If an attacker compromises a Discord guild owner's account, they can register the community on the platform. Mitigations: out-of-band ownership disputes can be resolved by platform admins; revocation + re-registration is supported.

**API key leakage.** Leaked keys allow forged activity from the affected context. Mitigations: revocation is one click; `last_used_at` lets owners detect unused-key revocation safely; rate limits per key (FIP-6) cap blast radius.

**Slug enumeration.** Public registration lets attackers probe which slugs are available before legitimate owners arrive. Largely unmitigable; first-come-first-served is the defense.

**Re-verification race.** A user who has lost provider-side ownership but still holds platform-side ownership could continue acting as owner until re-verification flags them. This is intentional - platform ownership is independent - but the lag MUST be visible to platform admins.

**Slug recycling.** After 90-day cool-down, a previous slug becomes available. A community could register a slug previously held by a known community to deceive users. Implementations SHOULD display "registered <date>" prominently for newly registered contexts to make recycling visible.

**Owner transfer hijacking.** A compromised current owner could transfer ownership to an attacker-controlled identity. Mitigations: transfer requires explicit confirmation (out-of-band: email link); platform admins can roll back recent transfers within a grace period.

**Provider API outages.** If `verifyMembership` is unavailable at registration time, the platform MUST NOT register the context. Falling back to cached suggestions or trusting user assertions invites squatting. Better to fail closed.

## Copyright

CC0 1.0 Universal.