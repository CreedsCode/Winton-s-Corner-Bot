---
fip: 4
title: Workshop Codes
author: Dercio (@creedscode)
status: Draft
type: Standards
category: Content
created: 2026-04-22
requires: FIP-1, FIP-3
---

# FIP-4 - Workshop Codes

## Abstract

This FIP defines the Workshop Codes content type: shareable Overwatch Workshop scripts authored by community members, attributed to the originating context, and discoverable across the federated platform.

It is the first non-profile content type and validates that the FIP-3 content pattern generalizes beyond identity metadata.

## Motivation

Overwatch Workshop snippets are a natural unit of community-generated content: small, reusable, copy-paste-friendly, and often invented in one community before spreading. Today they live scattered across Discord pins, Reddit threads, and ad-hoc websites. The platform's value proposition is to give them a structured home with attribution, search, and federation.

Workshop Codes serves as the validation case for the content base contract: if a content type fundamentally different from profile (multiple per author, no per-key uniqueness, content-as-the-payload rather than metadata) fits cleanly into the pattern, the pattern works.

## Specification

### Schema

```sql
create table workshop_codes (
  id                    uuid primary key default gen_random_uuid(),
  author_identity_id    uuid not null references identities,
  origin_context_id     uuid not null references contexts,
  visibility            text not null default 'public',
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  
  -- FIP-4 specific
  title                 text not null,
  description           text,
  code                  text not null,
  game                  text not null default 'overwatch_2',
  category              text,
  tags                  text[] not null default '{}',
  constraint title_length check (char_length(title) between 1 and 120),
  constraint description_length check (description is null or char_length(description) <= 2000),
  constraint code_length check (char_length(code) between 1 and 50000),
  constraint tags_count check (cardinality(tags) <= 10)
);

create index workshop_codes_by_origin
  on workshop_codes (origin_context_id, created_at desc);

create index workshop_codes_by_author
  on workshop_codes (author_identity_id, created_at desc);

create index workshop_codes_by_tags
  on workshop_codes using gin (tags);

-- Automatically refresh updated_at on PATCH/UPDATE (api.set_updated_at defined in FIP-3).
create trigger workshop_codes_updated_at
  before update on workshop_codes
  for each row execute function api.set_updated_at();
```

`updated_at` is maintained automatically by the `workshop_codes_updated_at` trigger. Implementations MUST NOT rely on callers to supply `updated_at` on update.

### Field semantics

- **`title`** - short human-readable name. Required, 1–120 chars.
- **`description`** - what the code does, when to use it. Optional, ≤ 2000 chars.
- **`code`** - the actual Workshop script text. Required, ≤ 50000 chars (Overwatch's published cap is around 32KB; the higher limit allows for future game updates and other Workshop-like games).
- **`game`** - game identifier. Default `overwatch_2`. Reserved values: `overwatch_2`, `overwatch_classic`. Other games MAY be added by amendment FIP.
- **`category`** - optional grouping (`gamemode`, `practice`, `meme`, `competitive`, etc.). Free-form for now; future FIP MAY define a controlled vocabulary.
- **`tags`** - searchable labels. Up to 10. Lowercase, alphanumeric + hyphens. Implementations MUST normalize tags to lowercase on insert.

### Visibility values

- **`public`** - visible to anyone, including anonymous viewers
- **`context_only`** - visible only to members of `origin_context_id`
- **`unlisted`** - accessible by direct URL but not in feeds or search

`members_only` (defined in FIP-3) is not used for workshop codes; `context_only` is the equivalent semantic.

> Copy-event tracking for analytics is out of scope for this FIP. A future FIP MAY define an events/telemetry content type that captures copy events (and other interactions) as first-class data, without coupling aggregate counters to the workshop_codes row.

### RLS policies

```sql
alter table workshop_codes enable row level security;

-- Read: public, or context_only with viewer in that context, or unlisted (anyone with URL)
create policy read_public on workshop_codes for select
  using (visibility in ('public', 'unlisted'));

create policy read_context_only on workshop_codes for select
  using (
    visibility = 'context_only'
    and origin_context_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'contexts'
      )
    )
  );

-- Write: must be one of your identities, must be in the origin context
create policy insert_authored on workshop_codes for insert
  with check (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
    and origin_context_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'contexts'
      )
    )
  );

create policy update_own on workshop_codes for update
  using (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

create policy delete_own_or_mod on workshop_codes for delete
  using (
    -- author can delete
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
    -- or context mod/owner can delete from their context
    or exists (
      select 1 from memberships m
      where m.context_id = origin_context_id
        and m.identity_id::text = any(
          select jsonb_array_elements_text(
            current_setting('request.jwt.claims', true)::jsonb->'identities'
          )
        )
        and m.role in ('mod', 'owner')
    )
    -- or platform admin
    or current_setting('request.jwt.claims', true)::jsonb->>'platform_role'
       in ('platform_mod', 'platform_admin')
  );
```

### API surface

Standard PostgREST. Notable queries:

```
GET /workshop_codes?order=created_at.desc&limit=20             # latest feed
GET /workshop_codes?origin_context_id=eq.<id>                  # one context's codes
GET /workshop_codes?author_identity_id=eq.<id>                 # one author's codes
GET /workshop_codes?tags=cs.{practice,gamemode}                # codes with specific tags
GET /workshop_codes?title=ilike.*skip*                         # search by title
GET /workshop_codes?select=*,author:identities(handle,avatar_url),context:contexts(name,slug)
                                                                # with embedded author + context
POST /workshop_codes                                            # create
PATCH /workshop_codes?id=eq.<id>                                # update own
DELETE /workshop_codes?id=eq.<id>                               # delete own or as mod
```

### Cross-content rendering

When a UI displays a workshop code, it SHOULD show:

- Title, description, code text
- Author handle and avatar (from `identities` via `author_identity_id`)
- Origin context name and icon (from `contexts` via `origin_context_id`), as a community badge
- Created/updated timestamps
- A copy-to-clipboard control

The community badge is non-negotiable: provenance is what the federation contract pays for, and rendering it everywhere makes attribution a structural property of the UI rather than an opt-in.

## Rationale

### Why a separate table per content type

Single mega-table approaches (one `content` table with `type` discriminator and `data jsonb`) reduce code duplication but lose type safety, complicate indexing, and make RLS harder to reason about. Per-type tables are slightly more boilerplate but align with how Postgres is designed to be used.

### Why `code` as text rather than a structured AST

Workshop scripts are small, copy-paste artifacts. The platform's job is to store and surface them, not to parse or validate them. Keeping `code` as opaque text means we don't need to track Workshop syntax updates and we support any Workshop-like game.

### Why no language/locale on title/description

Most Workshop content is in English, with a long tail of other languages. A future FIP could add multilingual fields if community demand warrants. Doing it now is over-engineering.

### Why mods can delete from their context but not edit

Edit access for mods would create attribution confusion ("did the author write this or did a mod rewrite it?"). Delete is binary and unambiguous. If a mod thinks the code is wrong, they delete and the author can repost with corrections.

### Why include `game` field at all

Future-proofing. The protocol may eventually host content for Marvel Rivals, Deadlock, or successor games with their own Workshop equivalents. A single `game` field lets the same content type table serve multiple games without schema changes.

## Backwards Compatibility

This is the first workshop-codes FIP. Nothing to break.

The current `apps/web-presence/public/tools/workshop-snippets.html` static page in the protocol monorepo is a precursor to this FIP. It will be replaced by a dynamic frontend reading from `/workshop_codes`. Existing snippets in `workshop-snippets_snippets.js` SHOULD be migrated as authored by the platform's service identity into the Monke context.

## Reference Implementation

To be linked when the platform's workshop UI is built. The reference schema lives at `db/migrations/004_workshop_codes.sql` in the protocol monorepo.

## Security Considerations

**Code injection.** Workshop scripts are not executed by the platform - they are inert text users copy into Overwatch's Workshop editor. No XSS risk from `code` content as long as it's escaped on render. Implementations MUST escape on display.

**Prompt injection in description.** A workshop code's `description` could contain text designed to manipulate AI assistants or bots that summarize content. Implementations whose features include LLM summarization SHOULD treat all user-supplied content as untrusted input.

**Spam at scale.** A flood of low-quality submissions degrades the platform. Mitigations: rate-limit submissions per identity (recommended: ≤ 10/hour), require contexts to have non-trivial member counts before listing globally, expose mod tooling for bulk deletion.

**Tag pollution.** Free-form tags can be abused (`#freerobux`, etc.). Implementations SHOULD normalize aggressively, hide tag clouds for new submissions until they're moderated, and offer mod tooling to remove tags from arbitrary content.

**Visibility downgrade race.** A code created `public`, copied by many, then changed to `unlisted` doesn't retroactively un-copy. This is correct behavior but worth documenting in UI ("changing visibility doesn't affect copies already made").

**Cascade deletes on context removal.** If a context is deleted, what happens to its workshop codes? Default: codes remain, with `origin_context_id` pointing to a soft-deleted context (the context record is preserved with a `deleted_at` timestamp). This preserves attribution even after community shutdown.

## Copyright

CC0 1.0 Universal.