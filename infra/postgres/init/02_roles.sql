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

-- Read the authenticator password from the environment variable injected by Docker.
\getenv authenticator_password AUTHENTICATOR_PASSWORD
ALTER ROLE authenticator PASSWORD :'authenticator_password';

GRANT anon          TO authenticator;
GRANT authenticated TO authenticator;
