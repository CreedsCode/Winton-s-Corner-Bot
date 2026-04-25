-- migrate:up
-- Creates the Discord bot's database via dblink so CREATE DATABASE runs on a
-- separate connection (it cannot execute inside a transaction block).
-- dblink is bundled with PostgreSQL contrib and available on the postgres:17 image.
CREATE EXTENSION IF NOT EXISTS dblink;

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'botdb') THEN
    PERFORM dblink_exec('dbname=' || current_database(), 'CREATE DATABASE botdb');
  END IF;
END $$;

-- migrate:down
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_database WHERE datname = 'botdb') THEN
    PERFORM dblink_exec('dbname=' || current_database(), 'DROP DATABASE botdb');
  END IF;
END $$;
