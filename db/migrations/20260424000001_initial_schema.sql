-- migrate:up

-- ── 01: Extensions ───────────────────────────────────────────────────────────
-- pgcrypto provides gen_random_uuid() and cryptographic helpers.
-- pgjwt is no longer needed: JWT signing is handled by auth-shim (PyJWT).
-- PostgREST only verifies tokens using PGRST_JWT_SECRET; it does not sign them.
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ── 02: Roles ────────────────────────────────────────────────────────────────

-- anon: unauthenticated requests (no login, no inherit)
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOINHERIT;
  END IF;
END $$;

-- authenticated: logged-in users (no login, no inherit)
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOINHERIT;
  END IF;
END $$;

-- authenticator: the single login role PostgREST uses to connect.
-- NOINHERIT is critical — it must not automatically get anon/authenticated privileges.
-- PostgREST switches via SET ROLE on each request based on the JWT 'role' claim.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
    CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'changeme';
  END IF;
END $$;

-- AUTHENTICATOR_PASSWORD is injected as a PostgreSQL GUC via the connection
-- string's `options` parameter: ?options=-c%20app.authenticator_password%3D<value>
-- The migrate service's entrypoint builds this URL at runtime (see docker-compose.yml).
-- Requirement: the password must not contain URL-special characters (?, &, #, %, space).
DO $$
BEGIN
  EXECUTE format('ALTER ROLE authenticator PASSWORD %L',
                 current_setting('app.authenticator_password'));
END $$;

GRANT anon          TO authenticator;
GRANT authenticated TO authenticator;


-- ── 03: Schema ───────────────────────────────────────────────────────────────
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
  copy_count          integer     not null default 0,

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

-- ── Copy count tracking ───────────────────────────────────────────────────────

-- Stores one row per copy event; used only by api.record_copy (SECURITY DEFINER).
-- No app-role grants — unreachable except through the RPC.
CREATE TABLE api.workshop_code_copy_events (
  id          uuid        primary key default gen_random_uuid(),
  code_id     uuid        not null references api.workshop_codes on delete cascade,
  identity_id uuid        references api.identities,  -- null for anon
  client_key  text        not null,  -- identity uuid OR 'ip:<x.x.x.x>'
  copied_at   timestamptz not null default now()
);

CREATE INDEX workshop_code_copy_events_dedup
  ON api.workshop_code_copy_events (code_id, client_key, copied_at desc);

-- RPC called by the frontend after a clipboard copy.
-- SECURITY DEFINER runs as the schema owner (postgres), bypassing RLS so it can
-- write workshop_code_copy_events without exposing that table to app roles.
-- Returns true when the count was incremented, false when rate-limited.
CREATE OR REPLACE FUNCTION api.record_copy(p_code_id uuid)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  v_claims    jsonb;
  v_key       text;
  v_identity  uuid;
  v_headers   jsonb;
BEGIN
  v_claims  := current_setting('request.jwt.claims', true)::jsonb;
  v_headers := current_setting('request.headers',    true)::jsonb;

  IF v_claims IS NOT NULL AND v_claims->>'active_identity' IS NOT NULL THEN
    v_identity := (v_claims->>'active_identity')::uuid;
    v_key      := v_claims->>'active_identity';
  ELSE
    v_key := 'ip:' || coalesce(
      v_headers->>'x-real-ip',
      split_part(v_headers->>'x-forwarded-for', ',', 1),
      'unknown'
    );
  END IF;

  -- Already copied this code within the last 10 minutes?
  IF EXISTS (
    SELECT 1 FROM api.workshop_code_copy_events
    WHERE code_id    = p_code_id
      AND client_key = v_key
      AND copied_at  > now() - interval '10 minutes'
  ) THEN
    RETURN false;
  END IF;

  INSERT INTO api.workshop_code_copy_events (code_id, identity_id, client_key)
  VALUES (p_code_id, v_identity, v_key);

  UPDATE api.workshop_codes
  SET copy_count = copy_count + 1
  WHERE id = p_code_id;

  RETURN true;
END;
$$;

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


-- ── 04: RLS ──────────────────────────────────────────────────────────────────
-- Row Level Security policies for all api tables.
-- auth-shim writes persons/identities/memberships as postgres superuser (bypasses RLS).
-- PostgREST requests run as anon or authenticated; RLS enforces row visibility.

ALTER TABLE api.persons       ENABLE ROW LEVEL SECURITY;
ALTER TABLE api.identities    ENABLE ROW LEVEL SECURITY;
ALTER TABLE api.contexts      ENABLE ROW LEVEL SECURITY;
ALTER TABLE api.memberships   ENABLE ROW LEVEL SECURITY;
ALTER TABLE api.profile_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE api.workshop_codes ENABLE ROW LEVEL SECURITY;
-- No app-role grants on this table; all access via api.record_copy (SECURITY DEFINER).
ALTER TABLE api.workshop_code_copy_events ENABLE ROW LEVEL SECURITY;

-- ── persons ──────────────────────────────────────────────────────────────────

-- Authenticated users can only see their own person row.
CREATE POLICY select_own_person ON api.persons
  FOR SELECT TO authenticated
  USING (
    id::text = current_setting('request.jwt.claims', true)::jsonb->>'person_id'
  );

-- ── identities ───────────────────────────────────────────────────────────────

-- Authenticated: see own identities (for profile management).
CREATE POLICY select_own_identity ON api.identities
  FOR SELECT TO authenticated
  USING (
    id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

-- Anon: see all identities (needed to render author info on public feeds).
CREATE POLICY select_identity_anon ON api.identities
  FOR SELECT TO anon
  USING (true);

-- ── contexts ─────────────────────────────────────────────────────────────────

-- Anyone can read non-deleted contexts.
CREATE POLICY select_context ON api.contexts
  FOR SELECT
  USING (deleted_at IS NULL);

-- ── memberships ───────────────────────────────────────────────────────────────

-- Authenticated: see memberships for own identities only.
CREATE POLICY select_own_memberships ON api.memberships
  FOR SELECT TO authenticated
  USING (
    identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

-- ── profile_fields (FIP-3 §RLS policies) ─────────────────────────────────────

-- Anyone can read public fields.
CREATE POLICY read_public ON api.profile_fields
  FOR SELECT
  USING (visibility = 'public');

-- Authenticated can read members_only fields when they share a context with the author
-- (global field) or when they are in the scope context (scoped field).
CREATE POLICY read_members_only ON api.profile_fields
  FOR SELECT
  USING (
    visibility = 'members_only'
    and (
      -- global field: viewer shares any context with author
      (
        scope_context_id is null
        and exists (
          select 1
          from   api.memberships m1
          join   api.memberships m2 on m1.context_id = m2.context_id
          where  m1.identity_id = author_identity_id
            and  m2.identity_id::text = any(
                   select jsonb_array_elements_text(
                     current_setting('request.jwt.claims', true)::jsonb->'identities'
                   )
                 )
        )
      )
      -- scoped field: viewer is a member of the scope context
      or scope_context_id::text = any(
           select jsonb_array_elements_text(
             current_setting('request.jwt.claims', true)::jsonb->'contexts'
           )
         )
    )
  );

-- Only own identities can insert.
CREATE POLICY insert_own ON api.profile_fields
  FOR INSERT
  WITH CHECK (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

-- Only own identities can update.
CREATE POLICY update_own ON api.profile_fields
  FOR UPDATE
  USING (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

-- Only own identities can delete.
CREATE POLICY delete_own ON api.profile_fields
  FOR DELETE
  USING (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

-- ── workshop_codes (FIP-4 §RLS policies) ─────────────────────────────────────

-- Public and unlisted codes are readable by anyone (unlisted = accessible by direct URL).
CREATE POLICY read_public ON api.workshop_codes
  FOR SELECT
  USING (visibility in ('public', 'unlisted'));

-- context_only codes are readable only by members of the origin context.
CREATE POLICY read_context_only ON api.workshop_codes
  FOR SELECT
  USING (
    visibility = 'context_only'
    and origin_context_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'contexts'
      )
    )
  );

-- Insert: must be one of your own identities AND in the origin context.
CREATE POLICY insert_authored ON api.workshop_codes
  FOR INSERT
  WITH CHECK (
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

-- Update: author can update their own codes.
CREATE POLICY update_own ON api.workshop_codes
  FOR UPDATE
  USING (
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
  );

-- Delete: author, context mod/owner, or platform admin.
CREATE POLICY delete_own_or_mod ON api.workshop_codes
  FOR DELETE
  USING (
    -- author can delete own
    author_identity_id::text = any(
      select jsonb_array_elements_text(
        current_setting('request.jwt.claims', true)::jsonb->'identities'
      )
    )
    -- context mod or owner can delete from their context
    or exists (
      select 1
      from   api.memberships m
      where  m.context_id = origin_context_id
        and  m.identity_id::text = any(
               select jsonb_array_elements_text(
                 current_setting('request.jwt.claims', true)::jsonb->'identities'
               )
             )
        and  m.role in ('mod', 'owner')
    )
    -- platform admin can delete anything
    or current_setting('request.jwt.claims', true)::jsonb->>'platform_role'
       in ('platform_mod', 'platform_admin')
  );


-- ── 05: Grants ───────────────────────────────────────────────────────────────
-- Grants for anon and authenticated roles.
-- authenticator connects to PG and switches role per JWT; it needs no direct grants.
-- auth-shim connects as postgres (superuser) and bypasses everything.

GRANT USAGE ON SCHEMA api TO anon, authenticated;

-- ── Read-only tables (auth-shim writes these as superuser) ───────────────────

GRANT SELECT ON api.providers    TO anon, authenticated;
GRANT SELECT ON api.persons      TO authenticated;
GRANT SELECT ON api.identities   TO authenticated, anon;
GRANT SELECT ON api.contexts     TO authenticated, anon;
GRANT SELECT ON api.memberships  TO authenticated;

-- ── Content tables (RLS enforces row-level access) ───────────────────────────

GRANT SELECT, INSERT, UPDATE, DELETE ON api.profile_fields  TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON api.workshop_codes  TO authenticated;

-- anon can read workshop_codes (RLS limits to public/unlisted rows)
GRANT SELECT ON api.workshop_codes TO anon;

-- RPC: anyone can call record_copy (rate-limiting is enforced inside the function)
GRANT EXECUTE ON FUNCTION api.record_copy(uuid) TO anon, authenticated;


-- ── 06: Seed ─────────────────────────────────────────────────────────────────
-- Seed data: providers, synthetic platform identity, Monke context, 4 workshop codes.
-- Fixed UUIDs are used so the frontend can hardcode the Monke context ID.
--
-- Monke context ID:   00000000-0000-0000-0001-000000000000
-- Platform person ID: 00000000-0000-0000-0000-000000000001
-- Platform identity:  00000000-0000-0000-0000-000000000002

-- ── Providers ────────────────────────────────────────────────────────────────

INSERT INTO api.providers (slug, name, config) VALUES
  ('discord', 'Discord', '{
    "authorize_url": "https://discord.com/oauth2/authorize",
    "token_url":     "https://discord.com/api/oauth2/token",
    "api_base":      "https://discord.com/api/v10",
    "cdn_base":      "https://cdn.discordapp.com"
  }'::jsonb),
  ('platform', 'Platform', '{}'::jsonb);

-- ── Platform service identity (synthetic author for seeded content) ───────────

INSERT INTO api.persons (id, display_name, platform_role)
VALUES ('00000000-0000-0000-0000-000000000001', 'Platform', 'platform_admin');

INSERT INTO api.identities (id, person_id, provider, provider_user_id, handle)
VALUES ('00000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        'platform', 'platform-service', 'platform');

UPDATE api.persons
SET primary_identity_id = '00000000-0000-0000-0000-000000000002'
WHERE id = '00000000-0000-0000-0000-000000000001';

-- ── Monke context ─────────────────────────────────────────────────────────────

INSERT INTO api.contexts (id, provider, provider_context_id, slug, name, verified, owner_identity_id)
VALUES ('00000000-0000-0000-0001-000000000000',
        'discord', '1425571463192121354',
        'monke', 'Monke', true, null);


-- migrate:down

-- Revoke role memberships before dropping roles
REVOKE anon          FROM authenticator;
REVOKE authenticated FROM authenticator;

-- Drop the api schema and all objects within it (tables, functions,
-- triggers, indexes, policies, grants on schema objects)
DROP SCHEMA IF EXISTS api CASCADE;

-- Drop extension
DROP EXTENSION IF EXISTS pgcrypto;

-- Roles must have no owned objects after schema drop; DROP ROLE is then safe
DROP ROLE IF EXISTS authenticator;
DROP ROLE IF EXISTS authenticated;
DROP ROLE IF EXISTS anon;
