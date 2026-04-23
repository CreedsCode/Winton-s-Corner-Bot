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

