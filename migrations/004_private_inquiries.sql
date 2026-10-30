-- Additive private inquiry/notification/review tables; no existing data replaced.
BEGIN;
SET LOCAL search_path TO stratevo_private;

CREATE TABLE IF NOT EXISTS customer_inquiries (
 id TEXT PRIMARY KEY, submission_digest TEXT NOT NULL UNIQUE, payload_digest TEXT NOT NULL,
 created_at BIGINT NOT NULL, status TEXT NOT NULL CHECK(status IN ('new','contacted','qualified','closed')),
 payload TEXT NOT NULL, consent_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS inquiry_status_date ON customer_inquiries(status,created_at);
CREATE TABLE IF NOT EXISTS supplier_reviews (
 account_id TEXT PRIMARY KEY REFERENCES market_accounts(id),
 status TEXT NOT NULL CHECK(status IN ('new','contacted','reviewed','declined')), updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_jobs (
 id TEXT PRIMARY KEY, entity_type TEXT NOT NULL CHECK(entity_type IN ('customer','supplier')),
 entity_id TEXT NOT NULL, summary TEXT NOT NULL, created_at BIGINT NOT NULL,
 outbox_id TEXT REFERENCES outbox(id), UNIQUE(entity_type,entity_id)
);
ALTER TABLE customer_inquiries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON customer_inquiries FROM PUBLIC;
ALTER TABLE supplier_reviews ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON supplier_reviews FROM PUBLIC;
ALTER TABLE notification_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON notification_jobs FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM anon; END IF; END $$;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM authenticated; END IF; END $$;
COMMIT;
