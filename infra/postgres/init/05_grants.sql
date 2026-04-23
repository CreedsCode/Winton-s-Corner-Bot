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
