-- Spec-compliant schema (api schema only — PostgREST exposes api, not auth).
-- All FIP base tables live here. auth-shim writes persons/identities/memberships
-- as the postgres superuser, bypassing RLS. PostgREST enforces RLS for app roles.

CREATE SCHEMA IF NOT EXISTS api;

-- ── Core identity tables ─────────────────────────────────────────────────────

CREATE TABLE api.providers (
  slug    text primary key,
  name    text not null,
  config  jsonb
);

-- persons: one row per human, may bundle multiple identities
CREATE TABLE api.persons (
  id                  uuid        primary key default gen_random_uuid(),
  primary_identity_id uuid,       -- FK to identities, added after that table is created
  display_name        text,
  platform_role       text        not null default 'user',
  created_at          timestamptz not null default now()
);

CREATE TABLE api.identities (
  id                uuid        primary key default gen_random_uuid(),
  person_id         uuid        not null references api.persons,
  provider          text        not null references api.providers,
  provider_user_id  text        not null,
  handle            text        not null,
  avatar_url        text,
  created_at        timestamptz not null default now(),
  unique (provider, provider_user_id)
);

-- Add the FK that couldn't be created until identities existed
ALTER TABLE api.persons
  ADD CONSTRAINT persons_primary_identity_fk
  FOREIGN KEY (primary_identity_id) REFERENCES api.identities;

CREATE TABLE api.contexts (
  id                    uuid        primary key default gen_random_uuid(),
  provider              text        not null references api.providers,
  provider_context_id   text        not null,
  slug                  text        unique,
  name                  text        not null,
  icon_url              text,
  owner_identity_id     uuid        references api.identities,
  verified              boolean     not null default false,
  created_at            timestamptz not null default now(),
  deleted_at            timestamptz,
  unique (provider, provider_context_id)
);

CREATE TABLE api.memberships (
  identity_id     uuid        not null references api.identities,
  context_id      uuid        not null references api.contexts,
  role            text        not null default 'member',
  joined_at       timestamptz not null default now(),
  verified_at     timestamptz,
  established_by  text,
  primary key (identity_id, context_id)
);

-- ── Content tables (FIP-3: profile_fields, FIP-4: workshop_codes) ─────────────

CREATE TABLE api.profile_fields (
  id                  uuid        primary key default gen_random_uuid(),
  author_identity_id  uuid        not null references api.identities,
  origin_context_id   uuid        not null references api.contexts,
  visibility          text        not null default 'public',
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  scope_context_id    uuid        references api.contexts,
  key                 text        not null,
  value               jsonb       not null
);
-- Two partial indexes enforce uniqueness correctly:
-- standard UNIQUE treats NULLs as distinct, so (author, NULL, 'bio') could be
-- inserted twice without these explicit partial indexes.
CREATE UNIQUE INDEX profile_fields_scoped_unique
  ON api.profile_fields (author_identity_id, scope_context_id, key)
  WHERE scope_context_id IS NOT NULL;

CREATE UNIQUE INDEX profile_fields_global_unique
  ON api.profile_fields (author_identity_id, key)
  WHERE scope_context_id IS NULL;

CREATE INDEX profile_fields_by_person
  ON api.profile_fields (author_identity_id, scope_context_id);

CREATE TABLE api.workshop_codes (
  id                  uuid        primary key default gen_random_uuid(),
  author_identity_id  uuid        not null references api.identities,
  origin_context_id   uuid        not null references api.contexts,
  visibility          text        not null default 'public',
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  title               text        not null,
  description         text,
  code                text        not null,
  tags                text[]      not null default '{}',

  constraint title_length       check (char_length(title) between 1 and 120),
  constraint description_length check (description is null or char_length(description) <= 2000),
  constraint code_length        check (char_length(code) between 4 and 8),
  constraint tags_count         check (cardinality(tags) <= 5)
);

CREATE INDEX workshop_codes_by_origin
  ON api.workshop_codes (origin_context_id, created_at desc);
CREATE INDEX workshop_codes_by_author
  ON api.workshop_codes (author_identity_id, created_at desc);
CREATE INDEX workshop_codes_by_tags
  ON api.workshop_codes USING gin (tags);

-- ── updated_at triggers ───────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION api.set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER profile_fields_updated_at
  BEFORE UPDATE ON api.profile_fields
  FOR EACH ROW EXECUTE FUNCTION api.set_updated_at();

CREATE TRIGGER workshop_codes_updated_at
  BEFORE UPDATE ON api.workshop_codes
  FOR EACH ROW EXECUTE FUNCTION api.set_updated_at();
