BEGIN;
SET LOCAL search_path TO stratevo_private;

CREATE TABLE IF NOT EXISTS supplier_directory (
 id TEXT PRIMARY KEY REFERENCES market_accounts(id) ON DELETE CASCADE,
 public_payload TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('published','withdrawn','hidden')),
 revision BIGINT NOT NULL DEFAULT 1, created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS directory_date ON supplier_directory(status,created_at,id);

ALTER TABLE supplier_directory ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON supplier_directory FROM PUBLIC;
COMMIT;
