# SPEC.md

**Version:** v0.1.0 (pre-stable - breaking changes without notice)
**Status:** Draft

A federated content protocol for community platforms, with provider-agnostic identity and structural content attribution.

---

## 1. Overview

This specification defines a protocol by which community platforms can:

- Authenticate users via one or more identity providers (Discord, Twitch, Matrix, …)
- Express community membership as a relation between identities and contexts
- Allow users to link multiple identities into a single person
- Expose content with structural attribution to its author and originating context
- Federate content across communities while preserving provenance

The protocol is provider-agnostic. Discord is the reference provider, not the privileged one.

A **conformant implementation** satisfies every MUST requirement in this document. Implementations MAY extend, but MUST NOT narrow, the contracts defined here.

---

## 2. Core concepts

The protocol distinguishes four entities. Conflating any two is the most common implementation mistake.

**Identity** - a single account on a single provider, provably controlled by whoever holds the credentials. `123456789@discord` is one identity; `dercio@twitch` is another. Identities are the unit of *authentication*.

**Context** - a community on a provider: a Discord guild, a Twitch channel's community, a Matrix room. Contexts are the unit of *belonging* and the unit of *content origin*. Contexts are not identities; they do not author content directly.

**Membership** - a relation stating that an identity belongs to a context, qualified by a **role** (see §2.1). Memberships are mutable and verified against the upstream provider at authentication time.

**Person** - a bundle of one or more identities controlled by the same human. Persons are the unit of *reputation* and *cross-provider continuity*. A new identity always begins as a person of one; persons grow by explicit linking, never by inference.

### 2.1 Membership roles

Memberships carry a protocol-defined role from a fixed vocabulary:

- `member` - baseline presence in the context
- `mod` - can moderate content and members within the context
- `owner` - full control of the context, including delegation of `mod`

Roles are mapped from provider-native signals at authentication time. The mapping is defined per-provider (see §4.2). When a provider signals multiple roles simultaneously (e.g. a Discord guild owner who also has `MANAGE_GUILD`), the **highest** role wins: `owner > mod > member`.

Communities MAY define additional **labels** (see §2.2) for local display and local-permission purposes, but labels are not part of the federation contract.

### 2.2 Labels (optional)

A **label** is a context-defined tag attached to a membership. Labels are:

- **Community-defined** - each context invents its own vocabulary
- **Display-oriented** - typically used to render badges in that context
- **Not federated** - other implementations are not required to recognize or render labels
- **Optionally permission-granting** - a label MAY be configured to elevate its holder to `mod` within the defining context (see §6.3)

Labels are not required for conformance. An implementation MAY omit the labels system entirely.

### 2.3 Platform roles

Platform roles are orthogonal to context membership. They allow moderation and administration across contexts without requiring explicit membership.

- `user` - default
- `platform_mod` - can moderate across all contexts
- `platform_admin` - full platform control

Platform roles live on the `persons` table, not on memberships.

---

## 3. Address format

Identities and contexts share a single canonical address format:

```
<provider_local_id>@<provider_slug>
```

Examples of canonical addresses:

- `123456789@discord` - a Discord user by snowflake
- `1425571463192121354@discord` - a Discord guild by snowflake
- `44322889@twitch` - a Twitch user by numeric ID
- `@dercio:matrix.org@matrix` - a Matrix user (native MXID preserved before final `@`)

URL-friendly slugs (`/c/monke`, `/u/dercio`) resolve to canonical addresses - see §3.2.

### 3.1 Parsing

Implementations MUST split on the **last** `@` only. Provider local IDs MAY contain `@` (as in Matrix MXIDs).

Provider slugs MUST be lowercase alphanumeric with no separators. Reserved slugs: `discord`, `twitch`, `matrix`, `platform` (reserved for native platform identities such as service accounts).

### 3.2 Canonical addresses and slugs

The **canonical address** of an identity or context uses the provider-native ID as the local part. For Discord, this is the snowflake; for Twitch, the numeric user ID; for Matrix, the full MXID.

```
1425571463192121354@discord    ← canonical address of the Monke guild
123456789@discord              ← canonical address of a Discord user
```

Canonical addresses are the only form used in:

- JWT claims
- Federation messages between deployments
- Foreign keys and internal references
- Equality comparisons

Contexts and identities MAY additionally have a **slug** (e.g. `monke`, `dercio`) stored on the record. Slugs exist solely as URL sugar for human-facing paths:

```
/c/monke        → resolves to 1425571463192121354@discord
/u/dercio       → resolves to 123456789@discord
```

Slugs are not addresses. They MUST NOT appear in JWT claims or federation payloads. A slug change MUST NOT invalidate any canonical address. Slug uniqueness is per-provider; `monke@discord` and `monke@twitch` are unrelated.

---

## 4. Provider model

A **provider** is an identity source. Its sole mandatory responsibility is authenticating a user and returning a stable, provider-unique identifier plus basic profile information.

Providers do **not** own the concept of membership. Membership is a protocol-level relation that is established explicitly through a join flow (§4.3), and providers optionally assist by supplying verification endpoints.

This separation means:

- A conformant provider adapter is small: OAuth + profile fetch
- Providers like Twitch, whose native model doesn't map cleanly to "guilds the user is in," can still be first-class
- Context membership is always explicit and provable, never silently inferred from a provider's claims

### 4.1 Provider adapter interface

Every provider implementation MUST expose:

```
fetchIdentity(access_token) → { provider_user_id, handle, avatar_url? }
```

Every provider implementation MAY additionally expose:

```
suggestContexts(access_token) → [{ provider_context_id, name, icon_url? }]
   // hint only - communities the user is likely to want to join.
   // used to populate join-flow UI, not to create memberships.

verifyMembership(access_token, provider_context_id) → { present: bool, native_role?: string }
   // used during the join flow to prove the user belongs to the
   // provider-side community backing this context.
```

`suggestContexts` is purely a UX affordance - for example, Discord can suggest "guilds you're in" so the user doesn't have to paste IDs. No membership is created from a suggestion alone.

`verifyMembership` is the provider's contribution to join-flow proofs (§4.3). Providers without a meaningful membership check (e.g. bare OAuth identity providers) MAY omit it; those contexts then rely on alternative proof mechanisms.

### 4.2 Role mapping

When `verifyMembership` returns a `native_role`, provider FIPs MUST document how it maps to the protocol roles defined in §2.1. Reference mappings:

| Provider | Native signal | Protocol role |
|---|---|---|
| Discord | Guild owner | `owner` |
| Discord | `MANAGE_GUILD` permission | `mod` |
| Discord | Guild member | `member` |
| Twitch | Channel broadcaster | `owner` |
| Twitch | Channel moderator | `mod` |
| Twitch | Follower / VIP / subscriber | `member` |
| Matrix | Power level ≥ 100 | `owner` |
| Matrix | Power level ≥ 50 | `mod` |
| Matrix | Room member | `member` |

Highest role wins when multiple signals apply.

### 4.3 Join flow

A membership is established when an identity produces an accepted **proof** of belonging to a context. The protocol defines the join flow; context owners configure which proof mechanisms their context accepts.

A join flow proceeds as:

1. An authenticated identity initiates a join against a context
2. The platform selects a proof mechanism acceptable to that context
3. The mechanism produces a verdict: `accepted` (with optional `native_role`) or `rejected`
4. On acceptance, a `memberships` row is created with the derived role

Protocol-defined proof mechanisms:

- **`provider_verify`** - Platform calls the provider's `verifyMembership` against the context's backing provider-side community. Strongest when the provider supports it (Discord Bot API membership check, Twitch channel follow check, Matrix `/joined_rooms`). This is the default and preferred mechanism.

- **`provider_oauth_rescope`** - The user performs a fresh OAuth with provider scopes sufficient for `verifyMembership`. Used when the user's active token lacks scope (e.g. they logged in without `guilds` scope and now want to join a Discord-backed context).

- **`context_invite`** - Context owner issues a time-scoped, single-use invite code. User presents the code to join. Used when `provider_verify` is unavailable or when a context wants explicit admission control independent of provider state.

- **`bot_assertion`** - The context's registered bot asserts the user has joined. Used for flows where Discord's "user typed /join in our server" is the signal, not an API check. Carries weaker trust than `provider_verify` - see the Bot-category FIP for constraints.

Context owners MUST configure at least one accepted proof mechanism when registering a context. Implementations MAY add mechanisms beyond the above; the four listed MUST be recognized by any conformant implementation that supports the underlying preconditions (e.g. a deployment without a bot infrastructure MAY omit `bot_assertion`).

Memberships established through any mechanism are equally valid at the data-model level. They differ only in the trust record stamped at creation time, which implementations MAY expose via an `established_by` field on memberships for audit purposes.

### 4.4 Identity-only flows

A deployment MAY expose contexts that require no membership proof beyond authenticated identity ("anyone with a verified Discord account can participate"). These contexts set their accepted proof mechanisms to include an identity-only option, effectively treating any authenticated identity as a member on first interaction.

This is useful for platform-native or cross-community contexts (e.g. a shared "workshop code library" that any authenticated user can post to, regardless of which Discord guild they belong to). Identity-only contexts SHOULD be clearly distinguished in UI from verified-membership contexts, since the trust signal differs.

---

## 5. Data model

Normative tables. Implementations MAY add columns; MUST NOT remove or rename the columns defined here.

```sql
providers (
  slug          text primary key,
  name          text not null,
  config        jsonb
)

persons (
  id                    uuid primary key,
  primary_identity_id   uuid,                        -- references identities, nullable pre-first-login
  display_name          text,
  platform_role         text not null default 'user', -- see §2.3
  created_at            timestamptz not null default now()
)

identities (
  id                  uuid primary key,
  person_id           uuid not null references persons,
  provider            text not null references providers,
  provider_user_id    text not null,
  handle              text not null,
  avatar_url          text,
  created_at          timestamptz not null default now(),
  unique (provider, provider_user_id)
)

contexts (
  id                    uuid primary key,
  provider              text not null references providers,
  provider_context_id   text not null,
  slug                  text unique,
  name                  text not null,
  icon_url              text,
  owner_identity_id     uuid references identities,
  verified              boolean not null default false,
  created_at            timestamptz not null default now(),
  unique (provider, provider_context_id)
)

memberships (
  identity_id     uuid not null references identities,
  context_id      uuid not null references contexts,
  role            text not null default 'member',     -- 'member' | 'mod' | 'owner'
  joined_at       timestamptz not null default now(),
  verified_at     timestamptz,
  established_by  text,                                -- proof mechanism: see §4.3
  primary key (identity_id, context_id)
)

-- Optional (§2.2)
context_labels (
  id            uuid primary key,
  context_id    uuid not null references contexts,
  slug          text not null,
  name          text not null,
  color         text,
  grants_mod    boolean not null default false,
  unique (context_id, slug)
)

membership_labels (
  identity_id   uuid not null,
  context_id    uuid not null,
  label_id      uuid not null references context_labels,
  granted_by    uuid references identities,
  granted_at    timestamptz not null default now(),
  primary key (identity_id, context_id, label_id),
  foreign key (identity_id, context_id) references memberships (identity_id, context_id)
)
```

### 5.1 Content base contract

Every content-type table MUST include the following columns:

```sql
id                    uuid primary key,
author_identity_id    uuid not null references identities,
origin_context_id     uuid not null references contexts,
visibility            text not null default 'public',  -- 'public' | 'context_only'
created_at            timestamptz not null default now()
```

These four columns make federation work: every piece of content has a knowable author, a knowable origin, and structural visibility.

Content authorship is attributed to the **identity** that submitted the content, not the person. This preserves provenance: "this was posted from your Discord account, not your Twitch one." Aggregation by person is derivable via `identities.person_id`.

Content types beyond the base contract are defined per-type in Content-category FIPs.

---

## 6. Authorization model

The protocol uses JWT-bearer authorization with PostgreSQL row-level security as the enforcement layer.

### 6.1 JWT claims

A conformant token MUST include:

```json
{
  "role":              "member",
  "person_id":         "<uuid>",
  "active_identity":   "<uuid>",
  "identities":        ["<uuid>", "..."],
  "contexts":          ["<uuid>", "..."],
  "exp":               1714304800
}
```

- `role` MUST be `member` for authenticated users or `web_anon` for unauthenticated. Implementations MAY add additional roles (`platform_mod`, `platform_admin`) but MUST treat unknown roles as `web_anon`.
- `identities` is the full set of identities belonging to the active person.
- `contexts` is the union of contexts across all listed identities.
- `active_identity` is the identity used for this session; it is the default `author_identity_id` for new content written during the session.

Tokens SHOULD have short lifetimes (≤ 1 hour for interactive sessions, ≤ 5 minutes for bot-proxy tokens). Implementations SHOULD provide a refresh endpoint that reissues tokens without a full OAuth round-trip.

### 6.2 RLS contract

Implementations MUST enforce authorization in the database via row-level security. Bypassing the application layer (e.g. direct SQL via leaked credentials) MUST NOT bypass authorization.

RLS policies are expected to read JWT claims via `current_setting('request.jwt.claims', true)::jsonb` (PostgREST convention). Standard policy templates are defined in the Content Type Conventions FIP.

### 6.3 Label-granted moderation

If a deployment supports labels (§2.2), holding a label where `context_labels.grants_mod = true` SHOULD be treated equivalently to `memberships.role = 'mod'` for authorization purposes **within that context only**. Implementations MAY implement this by syncing an effective role onto memberships or by expanding RLS policies to check labels directly.

---

## 7. API conventions

The protocol does not mandate a specific HTTP API shape but RECOMMENDS PostgREST conventions:

- Resource paths match table names: `/workshop_codes`, `/identities`
- Filters use PostgREST operators: `?author_identity_id=eq.<uuid>`
- Embedded resources via `?select=*,author:identities(*)`
- Pagination via `Range` header and `Prefer: count=exact`

Two endpoint categories are protocol-defined and MUST exist outside the PostgREST-generated surface:

- `GET /auth/<provider>/login` - initiates OAuth
- `GET /auth/<provider>/callback` - completes OAuth, issues JWT

Implementations SHOULD additionally expose:

- `POST /auth/refresh` - reissue JWT from existing session without re-OAuth
- `GET /auth/me` - decoded JWT claims for the frontend
- `POST /auth/bot/token` - bot-proxy token issuance (see Bot-category FIP)
- `POST /contexts/register` - community self-registration

---

## 8. Content type pattern

Adding a new content type to a conformant implementation requires:

1. A **Content-category FIP** defining the type
2. A SQL table satisfying the content base contract (§5.1)
3. RLS policies covering: read (public + own-context), insert (as self, into known context), update (as self), delete (as self)
4. A response schema documented in the FIP

Implementations MAY support a content type without implementing every field defined in its FIP, but MUST NOT silently drop unknown fields when round-tripping content. Forward compatibility is preserved by storing unknown fields verbatim (e.g. in a `metadata jsonb` column when one is defined for the type).

The spec itself defines no specific content types. Workshop codes, PUG listings, and similar are defined in their own FIPs.

---

## 9. Versioning and references

This specification uses semantic versioning.

This document is **v0.1.0** - pre-stable. Breaking changes are expected without notice.

**v1.0.0** will be tagged when:

- Two independent implementations exist
- At least three providers have working adapters
- The bot-proxy auth flow has been deployed in production by at least one third party

Pre-v1, the spec evolves freely. Post-v1, breaking changes require a major version bump and a 90-day migration window.

### 9.1 FIP citation convention

FIPs are cited in the form `FIP-N - Title`, e.g. `FIP-1 - FIP Process`. Numbers are assigned in order of submission. References in this spec to FIPs that have not yet been written use the category name (e.g. "the relevant Bot-category FIP") and SHOULD be upgraded to the `FIP-N - Title` form once the FIP is drafted.

---

## 10. Glossary

- **Address** - the `<id>@<provider>` form of an identity or context
- **Conformant** - an implementation satisfying all MUST requirements
- **Federation** - the property that content authored on one deployment is meaningfully attributable to its origin even when consumed elsewhere
- **FIP** - Federation Improvement Proposal. Cited in the form `FIP-N - Title` (e.g. `FIP-1 - FIP Process`). FIPs are numbered in order of submission, not in order of dependency or importance. See the FIP process document for lifecycle and template.
- **Label** - a context-local tag on a membership, not part of the federation contract
- **Person** - a bundle of linked identities controlled by one human
- **Provenance** - the structural record of who authored a piece of content and where it originated
- **Provider** - an identity source (Discord, Twitch, Matrix)
- **Reference implementation** - the canonical example; useful but not normative
- **Role** - a protocol-defined membership qualifier: `member`, `mod`, `owner`

---

## Changelog

- **v0.1.0** - Initial draft. Four core concepts, address format, provider model, data model with labels, JWT + RLS authorization.