---
fip: 2
title: Discord Provider Adapter
author: Dercio (@creedscode)
status: Draft
type: Standards
category: Auth
created: 2026-04-22
requires: FIP-1
---

# FIP-2 - Discord Provider Adapter

## Abstract

This FIP defines the Discord provider adapter: how a conformant implementation authenticates users via Discord OAuth2, fetches identity profiles, suggests contexts, and verifies membership in Discord guilds. It locks in the OAuth scopes, API endpoints, and native-role mapping for Discord.

## Motivation

`SPEC.md` §4 defines the abstract provider adapter interface (`fetchIdentity`, `suggestContexts`, `verifyMembership`) but is provider-agnostic. Without a concrete adapter FIP, two implementations could both claim "Discord support" while disagreeing on what scopes to request, what counts as `mod` vs `member`, or how to handle vanity URLs.

This FIP makes Discord support unambiguous and interoperable.

## Specification

### Provider registration

Implementations MUST register the Discord provider with `slug = 'discord'` and the following config:

```yaml
slug: discord
name: Discord
config:
  authorize_url: https://discord.com/oauth2/authorize
  token_url: https://discord.com/api/oauth2/token
  api_base: https://discord.com/api/v10
  cdn_base: https://cdn.discordapp.com
```

### OAuth scopes

The Discord adapter MUST request the following scopes during the authorization request:

- `identify` - required for `fetchIdentity`
- `guilds` - required for `suggestContexts` and for guild-membership-based join flows

Implementations MAY request additional scopes (`email`, `guilds.members.read`) but MUST NOT depend on optional scopes for any normative behavior in this FIP.

### Authorization flow

```
GET /auth/discord/login
  → 302 to https://discord.com/oauth2/authorize?
       client_id=<id>
       &redirect_uri=<configured>
       &response_type=code
       &scope=identify%20guilds
       &state=<csrf-token>

GET /auth/discord/callback?code=<code>&state=<csrf-token>
  → POST https://discord.com/api/oauth2/token
       grant_type=authorization_code
       code=<code>
       redirect_uri=<configured>
  → returns { access_token, refresh_token, expires_in }
```

The CSRF `state` parameter MUST be validated on callback. Mismatched or missing state MUST result in authentication failure.

### `fetchIdentity` implementation

```
GET https://discord.com/api/v10/users/@me
Authorization: Bearer <access_token>
```

Returns Discord user object. Map to identity:

```
{
  provider_user_id: <user.id>,                 // Discord snowflake, as text
  handle:           <user.username>,
  avatar_url:       avatar ? cdn_url : null
}
```

Where `cdn_url` is constructed as:

```
https://cdn.discordapp.com/avatars/<user.id>/<user.avatar>.png
```

For users without a custom avatar, `avatar_url` MUST be `null`. Implementations MAY render a Discord default avatar at the UI layer but MUST NOT store one as the canonical avatar.

### `suggestContexts` implementation

```
GET https://discord.com/api/v10/users/@me/guilds
Authorization: Bearer <access_token>
```

Returns array of guild objects. Map each to a context suggestion:

```
{
  provider_context_id: <guild.id>,             // Discord snowflake, as text
  name:                <guild.name>,
  icon_url:            icon ? icon_cdn_url : null,
  native_role_hint:    derive_from_permissions(guild.permissions, guild.owner)
}
```

`icon_cdn_url`:
```
https://cdn.discordapp.com/icons/<guild.id>/<guild.icon>.png
```

`native_role_hint` is included as a hint only and MUST NOT be used to establish memberships without a join flow (see SPEC.md §4.3). Derivation:

- `guild.owner == true` → `owner`
- `guild.permissions & 0x20 (MANAGE_GUILD)` → `mod`
- otherwise → `member`

### `verifyMembership` implementation

The `verifyMembership` call requires a privileged check that the user is *currently* a member of the specified guild. Two implementations are acceptable:

**Method A - User token check (preferred for join flows):**
```
GET https://discord.com/api/v10/users/@me/guilds/<guild_id>/member
Authorization: Bearer <user_access_token>
```

Returns the user's guild member object on success, or 404 if not a member. Requires `guilds.members.read` scope; implementations using Method A MUST request this scope.

**Method B - Bot token check (for ongoing verification):**
```
GET https://discord.com/api/v10/guilds/<guild_id>/members/<user_id>
Authorization: Bot <bot_token>
```

Requires the platform's bot to be present in the target guild. Used for background membership re-verification and for join flows where the user is not actively in an OAuth session.

Map result to verification verdict:

```
{
  present: <true if member object returned, false on 404>,
  native_role: derive_from_member(member_object)
}
```

Native role derivation (highest wins per SPEC.md §2.1):

- Guild owner (`guild.owner_id == user.id`, requires guild fetch) → `owner`
- Member has any role with `MANAGE_GUILD` permission bit → `mod`
- Otherwise → `member`

### Vanity URLs and slugs

Discord guilds MAY have a `vanity_url_code` (e.g. `discord.gg/monke`). Implementations MAY use this as the default `slug` value when registering a context. Slugs are not addresses (SPEC.md §3.2); the canonical context address always uses the snowflake.

Vanity URL changes on Discord MUST NOT cascade to context slug changes automatically; slug edits are explicit operations on the platform side.

### Token refresh

Discord access tokens expire (typically 7 days). Implementations supporting long-lived sessions MUST store the `refresh_token` and refresh proactively before expiry:

```
POST https://discord.com/api/oauth2/token
grant_type=refresh_token
refresh_token=<stored>
```

Refresh failures (revoked grant, deleted account) MUST invalidate the user's session and require re-authentication.

### Rate limits

Discord enforces rate limits per route. Implementations MUST respect `X-RateLimit-Remaining` and `Retry-After` headers. Implementations SHOULD batch `verifyMembership` checks where possible (per-guild bot endpoints support fewer requests than per-user OAuth endpoints).

For background re-verification jobs, implementations SHOULD cache positive results for at least 5 minutes and negative results for at least 1 minute.

## Rationale

### Why Discord API v10

v10 is the current stable version as of this FIP. Earlier versions are deprecated. v11+ may be adopted via amendment or supersession FIP when released.

### Why request `guilds` scope by default

The `suggestContexts` capability is core to the Discord adapter's usefulness - without it, every user has to know guild snowflakes by heart. Requesting `guilds` adds a single line to the OAuth consent screen and dramatically improves the registration UX.

`guilds.members.read` is *not* requested by default because it is a more sensitive scope and Method B (bot token) is sufficient for most verification needs.

### Why two `verifyMembership` methods

Method A is optimal during active OAuth sessions (the user just authenticated, no extra API call needed beyond the membership check itself). Method B is required for background verification when no user token is available. Implementations choose per situation.

### Why `provider_user_id` as text, not bigint

Discord snowflakes are 64-bit integers, but JavaScript loses precision past 2^53. SPEC.md §3.1 already mandates text storage; this FIP reaffirms it for clarity.

### Why not store Discord email

Email correlation across providers is a privacy hazard and not needed for any protocol functionality. Implementations that want email for transactional purposes (notifications) SHOULD request `email` scope explicitly and store it on `persons`, not `identities`.

## Backwards Compatibility

This is the first provider adapter FIP. Nothing to break.

Future FIPs that add Discord-specific features (e.g. role-based labels synced from Discord roles) MUST declare this FIP in their `requires:` header.

## Reference Implementation

To be linked when the auth shim is built (Phase 3 of the implementation roadmap). The reference implementation will live at `apps/auth-shim/providers/discord.ts` (or equivalent) in the protocol monorepo.

## Security Considerations

**OAuth state parameter.** CSRF protection via `state` is mandatory, not optional. Without it, attackers can trick users into linking the attacker's Discord account to the victim's session.

**Bot token storage.** Method B requires a long-lived bot token on the platform. This token has broad guild-read permissions and MUST be stored as a secret (environment variable, secret manager), never in source control or logs.

**Scope creep.** Requesting more scopes than necessary increases the consent friction for users and the data exposure if tokens leak. Stick to the minimum: `identify`, `guilds`, and `guilds.members.read` only if Method A is used.

**Avatar URL injection.** Discord-supplied user avatar hashes are constrained, but implementations MUST validate hashes match `^[a-f0-9_]+$` before constructing CDN URLs to prevent URL manipulation attacks.

**Vanity URL squatting.** If implementations auto-suggest slugs from `vanity_url_code`, two guilds claiming the same vanity (rare but possible during Discord boost transitions) could conflict. Slug uniqueness is enforced at the platform level, so first registration wins; subsequent registrations require manual slug selection.

**Membership verification timing.** A user's guild membership at OAuth time may differ from their membership at action time (they left the guild between login and posting). For sensitive actions, implementations SHOULD re-verify via Method B rather than trust the JWT's cached `contexts` claim.

## Copyright

CC0 1.0 Universal.