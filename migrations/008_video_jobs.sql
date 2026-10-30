BEGIN;
SET LOCAL search_path TO stratevo_private;

-- Content Studio video jobs. Money-relevant columns are server-written only:
-- prompts and model choices come from authenticated staff, costs come from the
-- reviewed/live price table in app/video.py, never from the browser.
CREATE TABLE IF NOT EXISTS video_jobs (
 id TEXT PRIMARY KEY,
 client_key TEXT NOT NULL UNIQUE,
 model TEXT NOT NULL,
 endpoint TEXT NOT NULL,
 prompt TEXT NOT NULL,
 negative_prompt TEXT NOT NULL DEFAULT '',
 duration_seconds INTEGER NOT NULL,
 aspect_ratio TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('reserved','queued','in_progress','retrieving','canceling','completed','failed','canceled','submit_failed','unknown')),
 fal_request_id TEXT,
 status_url TEXT NOT NULL DEFAULT '',
 response_url TEXT NOT NULL DEFAULT '',
 cancel_url TEXT NOT NULL DEFAULT '',
 video_url TEXT NOT NULL DEFAULT '',
 video_content_type TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 queue_position INTEGER NOT NULL DEFAULT -1,
 attempts INTEGER NOT NULL DEFAULT 1,
 retried_from TEXT NOT NULL DEFAULT '',
 unit_price_usd REAL NOT NULL DEFAULT 0,
 cost_usd REAL NOT NULL DEFAULT 0,
 cost_basis TEXT NOT NULL DEFAULT '',
 currency TEXT NOT NULL DEFAULT 'USD',
 created_by TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL,
 completed_at BIGINT
);
CREATE INDEX IF NOT EXISTS video_jobs_date ON video_jobs(created_at DESC, id);
CREATE INDEX IF NOT EXISTS video_jobs_request ON video_jobs(fal_request_id);
CREATE INDEX IF NOT EXISTS video_jobs_client ON video_jobs(client_key);

ALTER TABLE video_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON video_jobs FROM PUBLIC;
COMMIT;
