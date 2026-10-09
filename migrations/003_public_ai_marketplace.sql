-- Automatic email-verified marketplace and bounded public AI. Backend owner only.
BEGIN;
SET LOCAL search_path TO stratevo_private;

CREATE TABLE IF NOT EXISTS market_accounts (
 id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, private_profile TEXT NOT NULL,
 created_at BIGINT NOT NULL, verified_at BIGINT
);
CREATE TABLE IF NOT EXISTS market_products (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES market_accounts(id),
 public_payload TEXT NOT NULL, image TEXT NOT NULL DEFAULT '',
 visibility TEXT NOT NULL CHECK(visibility IN ('published','withdrawn','hidden')),
 created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_tokens (
 digest TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES market_accounts(id),
 expires_at BIGINT NOT NULL, used_at BIGINT
);
CREATE INDEX IF NOT EXISTS market_product_owner ON market_products(owner_id);
CREATE INDEX IF NOT EXISTS market_token_expiry ON market_tokens(expires_at);

CREATE TABLE IF NOT EXISTS public_ai_budget (day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS public_ai_slots (id TEXT PRIMARY KEY, expires_at BIGINT NOT NULL);
ALTER TABLE market_accounts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON market_accounts FROM PUBLIC;
ALTER TABLE market_products ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON market_products FROM PUBLIC;
ALTER TABLE market_tokens ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON market_tokens FROM PUBLIC;
ALTER TABLE public_ai_budget ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public_ai_budget FROM PUBLIC;
ALTER TABLE public_ai_slots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public_ai_slots FROM PUBLIC;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
 REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM anon;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
 REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM authenticated;
 END IF;
END $$;
COMMIT;
