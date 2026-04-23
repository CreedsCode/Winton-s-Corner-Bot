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