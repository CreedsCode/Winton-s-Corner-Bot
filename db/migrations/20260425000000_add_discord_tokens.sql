-- migrate:up

-- Stores Discord OAuth tokens per identity so out-of-band re-verification
-- (e.g. nightly Monke membership checks) can call Discord APIs without
-- requiring the user to re-authenticate.
--
-- No GRANT to anon/authenticated — this table is only ever read/written by
-- the auth-shim running as the postgres superuser. It is intentionally
-- invisible to PostgREST and the frontend.
CREATE TABLE api.discord_tokens (
  identity_id      uuid        primary key references api.identities on delete cascade,
  access_token     text        not null,
  refresh_token    text,
  token_expires_at timestamptz not null,
  updated_at       timestamptz not null default now()
);


-- migrate:down
-- Intentionally a no-op: dropping this table destroys live OAuth tokens and
-- forces every user to re-login. Roll back the auth-shim code instead; the
-- table is harmless if its columns are never written.
