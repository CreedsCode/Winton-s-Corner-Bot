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

-- ── Seeded workshop codes (migrated from workshop-snippets_snippets.js) ───────

INSERT INTO api.workshop_codes
  (author_identity_id, origin_context_id, visibility, title, description, code, game, category)
VALUES (
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0001-000000000000',
  'public',
  'Skip team assembly phase',
  'Skips the hero selection time',
  $$rule("Skip team assembly phase")
{
  event
  {
    Ongoing - Global;
  }

  conditions
  {
    Is Assembling Heroes == True;
  }

  actions
  {
    Set Match Time(0);
  }
}$$,
  'overwatch_2', 'utility'
);

INSERT INTO api.workshop_codes
  (author_identity_id, origin_context_id, visibility, title, description, code, game, category)
VALUES (
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0001-000000000000',
  'public',
  'Skip setup phase',
  'Skips the setup time',
  $$rule("Skip setup phase")
{
  event
  {
    Ongoing - Global;
  }

  conditions
  {
    Is In Setup == True;
  }

  actions
  {
    Set Match Time(0);
  }
}$$,
  'overwatch_2', 'utility'
);

INSERT INTO api.workshop_codes
  (author_identity_id, origin_context_id, visibility, title, description, code, game, category)
VALUES (
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0001-000000000000',
  'public',
  'Ultimate ability is free',
  'Automatically ready up the ultimate ability when players try to use it',
  $$rule("Ultimate ability is free")
{
  event
  {
    Ongoing - Each Player;
    All;
    All;
  }

  conditions
  {
    Is Button Held(Event Player, Button(Ultimate)) == True;
  }

  actions
  {
    Set Ultimate Charge(Event Player, 100);
  }
}$$,
  'overwatch_2', 'gameplay'
);

INSERT INTO api.workshop_codes
  (author_identity_id, origin_context_id, visibility, title, description, code, game, category)
VALUES (
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0001-000000000000',
  'public',
  'Teleport self to point',
  'Teleport yourself to point using interact + crouch + primary fire',
  $$rule("Teleport self to objective")
{
  event
  {
    Ongoing - Each Player;
    All;
    All;
  }

  conditions
  {
    Is Button Held(Event Player, Button(Interact)) == True;
    Is Button Held(Event Player, Button(Crouch)) == True;
    Is Button Held(Event Player, Button(Primary Fire)) == True;
  }

  actions
  {
    Teleport(Event Player, Objective Position(0));
  }
}$$,
  'overwatch_2', 'utility'
);
