---
fip: 3
title: Profile
author: Dercio (@creedscode)
status: Draft
type: Standards
category: Content
created: 2026-04-22
requires: FIP-1
---

# FIP-3 - Profile

## Abstract

This FIP defines the Profile content type: a per-person, key-value document that travels across the contexts a person belongs to. Profiles are how cross-community identity manifests in the UI: one bio, one set of pronouns, one social-link list, visible everywhere the person is present.

This FIP is the first Content-category FIP and serves as the template for subsequent content types.

## Motivation

The protocol's value proposition is cross-community identity. Without a unified profile, a user appearing in three different communities is three separate strangers - same identity, no shared context.

A profile is also identity-adjacent in a way that pure content (workshop codes, PUG listings) is not. It describes the person rather than being authored *by* the person about something else. This FIP nevertheless models profiles as a content type to keep the protocol uniform: one pattern, one set of RLS conventions, one extension mechanism.

Profiles are also the natural extension point for community-specific fields. A dating community wants `looking_for`; an OW community wants `battletag`. A subsequent FIP can extend this one without changing the core schema.

## Specification

### Schema

```sql
create table profile_fields (
  id                    uuid primary key default gen_random_uuid(),
  author_identity_id    uuid not null references identities,
  origin_context_id     uuid not null references contexts,
  visibility            text not null default 'public',
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  
  -- FIP-3 specific
  scope_context_id      uuid references contexts,    -- null = global
  key                   text not null,
  value                 jsonb not null,
  
);

create unique index profile_fields_scoped_unique
  on profile_fields (author_identity_id, scope_context_id, key)
  where scope_context_id is not null;

create unique index profile_fields_global_unique
  on profile_fields (author_identity_id, key)
  where scope_context_id is null;

create index profile_fields_by_person
  on profile_fields (author_identity_id, scope_context_id);

-- Automatically refresh updated_at on PATCH/UPDATE.
-- This function is defined once here; subsequent content FIPs reuse it.
create or replace function api.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profile_fields_updated_at
  before update on profile_fields
  for each row execute function api.set_updated_at();
```

`updated_at` is maintained automatically by the `profile_fields_updated_at` trigger. Implementations MUST NOT rely on callers to supply or increment `updated_at`; the trigger is normative because the resolution query in §Resolution sorts on it.

The base contract columns (`author_identity_id`, `origin_context_id`, `visibility`, `created_at`) follow SPEC.md §5.1.

### Field semantics

- **`author_identity_id`** - the identity that wrote this field. Only the author can edit or delete it.
- **`origin_context_id`** - the context the user was active in when setting the field. Recorded for provenance; does not affect visibility.
- **`scope_context_id`** - the context within which this field is *visible*. `null` means the field is global (visible in every context the person is a member of).
- **`key`** - the field name. MUST be from the registered field set (see §Standard fields) or namespaced by an extending FIP.
- **`value`** - the field value. Type depends on the field; see §Standard fields.
- **`visibility`** - `public` (anyone), `members_only` (only members of `scope_context_id`, or any shared context if global), `unlisted` (only the author, useful for drafts).

### Resolution

A person's complete profile, as rendered in a given context, is the result of:

```sql
select key, value, visibility, scope_context_id, updated_at
from profile_fields
where author_identity_id in (
    -- all identities belonging to the person
    select id from identities where person_id = <target_person_id>
  )
  and (
    scope_context_id is null                       -- global fields
    or scope_context_id = <viewing_context_id>     -- this-context fields
  )
  and (
    visibility = 'public'
    or (visibility = 'members_only' and viewer_shares_context_with_author)
  )
order by updated_at desc;
```

When multiple identities of the same person have set the same `(scope, key)`, the most recently updated one wins. Implementations MAY surface conflicts in the UI but SHOULD pick one for display purposes.

### Standard fields

This FIP defines the following field keys. Implementations MUST recognize and render fields with these keys when present. Implementations MAY allow users to set fields with other keys; such fields are namespace-reserved by extending FIPs.

| Key | Type | Description |
|---|---|---|
| `bio` | string, max 500 chars | Free-text self-description |
| `pronouns` | string, max 32 chars | Self-reported pronouns |
| `display_name` | string, max 64 chars | Preferred name (overrides identity handle for display) |
| `avatar_url` | string, URL | Custom avatar (overrides identity avatar) |
| `links` | array of `{ label: string, url: string }`, max 10 entries | Social/external links |
| `timezone` | string, IANA tz name | Self-reported timezone (e.g. `Europe/Berlin`) |
| `languages` | array of strings, ISO 639-1 codes | Languages the person speaks |

All standard fields default to `public` visibility unless the user specifies otherwise.

### URL validation for `links` and `avatar_url`

Implementations MUST validate URLs against the following rules before storing:

- Protocol MUST be `https://`
- MUST NOT resolve to private/loopback/link-local addresses (SSRF prevention)
- Length MUST be ≤ 2048 characters
- MUST parse as a syntactically valid URL per RFC 3986

Implementations SHOULD additionally screen URLs against common malware/phishing blocklists where available.

### Extension mechanism

Other FIPs MAY define additional profile fields. An extending FIP MUST:

1. Declare `requires: FIP-3` in its header
2. Reserve a key namespace by either:
   - **Field-by-field**: claim specific keys (`battletag`, `peak_rank`)
   - **Prefix-based**: claim a prefix (`ow.battletag`, `ow.peak_rank`)
3. Define type, validation, default visibility, and rendering hints for each field

Implementations MAY support any subset of profile FIPs. Fields belonging to unsupported FIPs MUST be preserved on round-trip (the row is not deleted) but MAY be hidden in the UI.

### RLS policies

Authentication via SPEC.md §6.1 JWT claims. Standard policies:

```sql
alter table profile_fields enable row level security;

-- Read: anyone can read public fields; members can read members_only fields
create policy read_public on profile_fields for select
  using (visibility = 'public');

create policy read_members_only on profile_fields for select
  using (
    visibility = 'members_only'
    and (
      -- global field, viewer shares any context with author
      scope_context_id is null
      and exists (
        select 1 from memberships m1
        join memberships m2 on m1.context_id = m2.context_id
        where m1.identity_id = author_identity_id
          and m2.identity_id::text = any(
            select jsonb_array_elements_text(
              current_setting('request.jwt.claims', true)::jsonb->'identities'
            )
          )
      )
      -- scoped field, viewer is in that context
      or scope_context_id::text = any(
        select jsonb_array_elements_text(
          current_setting('request.jwt.claims', true)::jsonb->'contexts'
        )
      )
    )
  );

-- Write: only as one of your own identities
create policy insert_own on profile_fields for insert
  with check (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

create policy update_own on profile_fields for update
  using (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

create policy delete_own on profile_fields for delete
  using (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );
```

### API surface

Standard PostgREST conventions apply (SPEC.md §7). Common queries:

```
GET /profile_fields?author_identity_id=eq.<id>          # one identity's fields
GET /profile_fields?scope_context_id=is.null            # global fields only
PATCH /profile_fields?id=eq.<row_id>                    # update one field
DELETE /profile_fields?id=eq.<row_id>                   # remove one field
POST /profile_fields                                    # add a field
```

Implementations MAY expose a convenience endpoint that returns a person's resolved profile (joining across identities, applying scope and visibility filters):

```
GET /persons/<person_id>/profile?context=<context_id>
```

This is non-normative but RECOMMENDED for frontend ergonomics.

## Rationale

### Why key-value rather than fixed columns

Fixed columns lock the schema. Every new field - community-specific or not - would require a migration. Key-value lets the *protocol* stay stable while *fields* evolve through FIPs. The cost is slightly more complex queries, which is fine for a profile (small N per person).

### Why scope as a column rather than separate tables

Per-context profiles could be a separate table (`global_profile`, `context_profile`). Single table with nullable `scope_context_id` is simpler to query, simpler to RLS, and cleaner for "show me everything this person has set."

### Why most-recent-wins for conflicts

A person with two identities (Discord + Twitch) might set `bio` from each. The protocol could merge, prompt the user to reconcile, or pick one. Picking the most recent is the simplest rule that doesn't lose data - older versions remain in the table and could be surfaced by the UI as edit history.

### Why standard fields rather than fully open-vocabulary

A small standard set ensures basic interoperability. Without it, every implementation displays profiles differently and there's no baseline. Seven fields is enough to be useful, not so many that the FIP becomes an ontology debate.

### Why `display_name` overrides `identity.handle`

Discord usernames are sometimes not what the person wants displayed (legacy `username#1234` artifacts, anonymized handles). `display_name` lets users present their preferred name without needing to change their Discord account.

### Why two partial indexes instead of one UNIQUE constraint

PostgreSQL's UNIQUE treats NULL as distinct from every other NULL, so `(author, NULL, 'bio')` could be inserted twice. Splitting into two partial indexes — one for scoped fields, one for global — enforces uniqueness correctly in both cases.

### Why `members_only` rather than per-context ACLs

Per-context ACLs (this field visible to Monke and Twitch-OW but not to Book Club) would let users fine-tune visibility, but the UX cost is enormous and the privacy gain modest. Three tiers (public / members_only / unlisted) is a reasonable point on the simplicity-vs-control curve.

## Backwards Compatibility

This is the first profile FIP. Nothing to break.

Extending FIPs (e.g. an Overwatch profile fields FIP) build on this without modification.

## Reference Implementation

To be linked when the platform's profile UI is built. The reference schema lives at `db/migrations/003_profiles.sql` (or equivalent) in the protocol monorepo.

## Security Considerations

**XSS via field values.** `bio` and other text fields are user-controlled. Implementations MUST treat all values as untrusted on render: HTML-escape, sanitize markdown, or apply a strict allow-list for formatting. Storing raw HTML in `value` is permissible only if the rendering layer treats it as text.

**SSRF via URL fields.** `avatar_url` and `links[].url` could point to internal infrastructure if not validated. The §URL validation rules above are normative, not advisory.

**Person enumeration.** Public profile fields can be enumerated to map identity-to-person relationships. This is a fundamental property of any cross-community profile system; users who want unlinked identities should not link them. Implementations SHOULD make the linking behavior obvious in the UI.

**Visibility race conditions.** A user changes `bio` from `public` to `members_only`. A web cache may continue serving the public version. Implementations SHOULD set short cache TTLs on profile data and invalidate caches on visibility changes where possible.

**Field bloat.** A malicious user could add thousands of profile fields to consume storage. Implementations SHOULD enforce a per-person field count limit (recommended: ≤ 100 across all FIPs and scopes combined).

**Cross-identity field merging.** When a person merges two identities, profile fields from both are now visible together. This may surface inconsistencies (different bios on Discord vs Twitch identity). Implementations SHOULD prompt the user to reconcile during the link flow.

## Copyright

CC0 1.0 Universal.