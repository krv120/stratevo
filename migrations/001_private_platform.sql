-- Run as the database owner, not from a browser. Keep this schema out of Supabase exposed schemas.
BEGIN;
CREATE SCHEMA IF NOT EXISTS stratevo_private;
REVOKE ALL ON SCHEMA stratevo_private FROM PUBLIC;
SET LOCAL search_path TO stratevo_private;

CREATE TABLE IF NOT EXISTS applications (
 id TEXT PRIMARY KEY, company TEXT NOT NULL, contact TEXT NOT NULL,
 email TEXT UNIQUE NOT NULL, country TEXT NOT NULL, category TEXT NOT NULL,
 capabilities TEXT NOT NULL, whatsapp TEXT NOT NULL, wechat TEXT NOT NULL,
 license_number TEXT NOT NULL, license_pdf TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending_email','pending','approved','rejected')),
 created_at BIGINT NOT NULL, reviewed_at BIGINT, review_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tokens (
 digest TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id),
 purpose TEXT NOT NULL, expires_at BIGINT NOT NULL, used_at BIGINT
);
CREATE TABLE IF NOT EXISTS sessions (
 digest TEXT PRIMARY KEY, role TEXT NOT NULL, application_id TEXT,
 expires_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL, action TEXT NOT NULL,
 created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
 id TEXT PRIMARY KEY, recipient TEXT NOT NULL, subject TEXT NOT NULL,
 body TEXT NOT NULL, created_at BIGINT NOT NULL, sent_at BIGINT,
 attempts INTEGER NOT NULL DEFAULT 0, claimed_until BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rate_limits (
 bucket TEXT PRIMARY KEY, started_at BIGINT NOT NULL, hits INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
 id TEXT PRIMARY KEY, batch TEXT NOT NULL, fingerprint TEXT NOT NULL,
 original TEXT NOT NULL, public_summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS search (id TEXT PRIMARY KEY REFERENCES records(id), description TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS catalog_search_vector ON search USING GIN(to_tsvector('simple',description));
CREATE INDEX IF NOT EXISTS session_expiry ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS application_status ON applications(status,created_at);
-- Defense in depth: no policies grant access to API/client roles. Backend owner bypasses RLS.
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE records ENABLE ROW LEVEL SECURITY;
ALTER TABLE search ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM PUBLIC;
DO $$
BEGIN
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
  REVOKE ALL ON SCHEMA stratevo_private FROM anon;
  REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM anon;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
  REVOKE ALL ON SCHEMA stratevo_private FROM authenticated;
  REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM authenticated;
 END IF;
END $$;
COMMIT;
