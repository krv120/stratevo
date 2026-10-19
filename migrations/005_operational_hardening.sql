-- Operational hardening; additive only. Run after 001–004.
BEGIN;
SET LOCAL search_path TO stratevo_private;

CREATE TABLE IF NOT EXISTS processing_slots (id TEXT PRIMARY KEY, expires_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS resource_locks (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS account_controls (account_id TEXT PRIMARY KEY REFERENCES market_accounts(id), suspended INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '', updated_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS security_events (id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, entity_id TEXT NOT NULL, created_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS listing_reports (id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES market_products(id), reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','reviewed')), created_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS mail_state (outbox_id TEXT PRIMARY KEY REFERENCES outbox(id) ON DELETE CASCADE, status TEXT NOT NULL, updated_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_session_meta (digest TEXT PRIMARY KEY REFERENCES sessions(digest) ON DELETE CASCADE, actor TEXT NOT NULL, credential_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_totp (actor TEXT PRIMARY KEY, counter BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS event_date ON security_events(created_at);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(sent_at,claimed_until,attempts);
CREATE INDEX IF NOT EXISTS account_date ON market_accounts(created_at,id);
CREATE INDEX IF NOT EXISTS product_visibility_date ON market_products(visibility,created_at,id);
CREATE INDEX IF NOT EXISTS inquiry_date ON customer_inquiries(created_at,id);
ALTER TABLE processing_slots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON processing_slots FROM PUBLIC;
ALTER TABLE resource_locks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON resource_locks FROM PUBLIC;
ALTER TABLE account_controls ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON account_controls FROM PUBLIC;
ALTER TABLE security_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON security_events FROM PUBLIC;
ALTER TABLE listing_reports ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON listing_reports FROM PUBLIC;
ALTER TABLE mail_state ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON mail_state FROM PUBLIC;
ALTER TABLE admin_session_meta ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON admin_session_meta FROM PUBLIC;
ALTER TABLE admin_totp ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON admin_totp FROM PUBLIC;

CREATE TABLE IF NOT EXISTS suppliers (
 id TEXT PRIMARY KEY REFERENCES market_accounts(id) ON DELETE CASCADE,
 contact_email TEXT NOT NULL, contact_name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
 full_metadata TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', source TEXT NOT NULL DEFAULT 'user_submission',
 featured INTEGER NOT NULL DEFAULT 0, verification_note TEXT NOT NULL DEFAULT '', created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS platform_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_notifications (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, event_type TEXT NOT NULL, recipient TEXT NOT NULL,
 subject TEXT NOT NULL, body_preview TEXT NOT NULL, payload_json TEXT NOT NULL,
 delivery_status TEXT NOT NULL DEFAULT 'queued_in_admin_inbox', error_message TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL, read_at BIGINT, outbox_id TEXT REFERENCES outbox(id) ON DELETE SET NULL,
 UNIQUE(entity_id,event_type)
);
CREATE INDEX IF NOT EXISTS notifications_date ON admin_notifications(created_at,id);
CREATE TABLE IF NOT EXISTS notification_attempts (
 id TEXT PRIMARY KEY, notification_id TEXT REFERENCES admin_notifications(id) ON DELETE CASCADE,
 transport TEXT NOT NULL, delivery_status TEXT NOT NULL, error_message TEXT NOT NULL, created_at BIGINT NOT NULL
);


ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON suppliers FROM PUBLIC;
ALTER TABLE platform_settings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON platform_settings FROM PUBLIC;
ALTER TABLE admin_notifications ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON admin_notifications FROM PUBLIC;
ALTER TABLE notification_attempts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON notification_attempts FROM PUBLIC;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM anon; END IF; END $$;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM authenticated; END IF; END $$;
COMMIT;
