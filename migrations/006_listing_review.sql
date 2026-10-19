-- Versioned product review and edit recovery. Existing data is preserved.
BEGIN;
SET LOCAL search_path TO stratevo_private;

CREATE TABLE IF NOT EXISTS listing_reviews (
 product_id TEXT PRIMARY KEY REFERENCES market_products(id) ON DELETE CASCADE,
 revision BIGINT NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','approved','rejected','withdrawn')),
 rights_confirmed_at BIGINT NOT NULL, updated_at BIGINT NOT NULL,
 review_note TEXT NOT NULL DEFAULT '', reviewed_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS listing_review_status ON listing_reviews(status,updated_at);
CREATE TABLE IF NOT EXISTS listing_requests (
 request_digest TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES market_accounts(id) ON DELETE CASCADE,
 payload_digest TEXT NOT NULL, product_id TEXT NOT NULL REFERENCES market_products(id) ON DELETE CASCADE
);
ALTER TABLE listing_reviews ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON listing_reviews FROM PUBLIC;
ALTER TABLE listing_requests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON listing_requests FROM PUBLIC;
COMMIT;
