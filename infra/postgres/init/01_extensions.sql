-- pgcrypto provides gen_random_uuid() and cryptographic helpers.
-- pgjwt is no longer needed: JWT signing is handled by auth-shim (PyJWT).
-- PostgREST only verifies tokens using PGRST_JWT_SECRET; it does not sign them.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
