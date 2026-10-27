BEGIN;
SET LOCAL search_path TO stratevo_private;

-- One series = one batch of faceless videos for one niche/voice.
CREATE TABLE IF NOT EXISTS content_series (
 id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 niche TEXT NOT NULL DEFAULT 'sourcing',
 audience TEXT NOT NULL DEFAULT '',
 tone TEXT NOT NULL DEFAULT 'direct',
 target_count INTEGER NOT NULL DEFAULT 40,
 model TEXT NOT NULL DEFAULT 'minimax-h3-max-turbo',
 duration_seconds INTEGER NOT NULL DEFAULT 10,
 resolution TEXT NOT NULL DEFAULT '768P',
 aspect_ratio TEXT NOT NULL DEFAULT '9:16',
 created_by TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL
);

-- One idea = concept + hook + script + video prompt + platform copy + state.
CREATE TABLE IF NOT EXISTS content_ideas (
 id TEXT PRIMARY KEY,
 series_id TEXT NOT NULL REFERENCES content_series(id) ON DELETE CASCADE,
 position INTEGER NOT NULL,
 topic TEXT NOT NULL,
 angle TEXT NOT NULL,
 hook TEXT NOT NULL,
 script TEXT NOT NULL,
 video_prompt TEXT NOT NULL,
 negative_prompt TEXT NOT NULL DEFAULT '',
 tiktok_caption TEXT NOT NULL DEFAULT '',
 tiktok_hashtags TEXT NOT NULL DEFAULT '',
 instagram_caption TEXT NOT NULL DEFAULT '',
 instagram_hashtags TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL CHECK(status IN ('draft','approved','rejected','video_pending','video_ready','caption_pending','ready_to_publish','scheduled','published','failed')),
 video_job_id TEXT,
 source_video_url TEXT NOT NULL DEFAULT '',
 media_asset_id TEXT,
 caption_error TEXT NOT NULL DEFAULT '',
 approved_by TEXT NOT NULL DEFAULT '',
 approved_at BIGINT,
 reject_reason TEXT NOT NULL DEFAULT '',
 regenerate_count INTEGER NOT NULL DEFAULT 0,
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL,
 UNIQUE(series_id, position)
);
CREATE INDEX IF NOT EXISTS content_ideas_series ON content_ideas(series_id, position);
CREATE INDEX IF NOT EXISTS content_ideas_status ON content_ideas(status, updated_at);

-- Durable public media. Buffer fetches the file when the post publishes, which
-- can be weeks later, so generated URLs are copied here instead of relying on
-- fal CDN retention.
CREATE TABLE IF NOT EXISTS media_assets (
 id TEXT PRIMARY KEY,
 token TEXT NOT NULL UNIQUE,
 idea_id TEXT NOT NULL DEFAULT '',
 kind TEXT NOT NULL DEFAULT 'video',
 content_type TEXT NOT NULL DEFAULT 'video/mp4',
 bytes BIGINT NOT NULL DEFAULT 0,
 sha256 TEXT NOT NULL DEFAULT '',
 storage TEXT NOT NULL DEFAULT 'postgres',
 body BYTEA,
 external_url TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS media_assets_idea ON media_assets(idea_id);

-- Scheduled publications, one row per platform per idea.
CREATE TABLE IF NOT EXISTS content_publications (
 id TEXT PRIMARY KEY,
 idea_id TEXT NOT NULL REFERENCES content_ideas(id) ON DELETE CASCADE,
 platform TEXT NOT NULL CHECK(platform IN ('tiktok','instagram')),
 channel_id TEXT NOT NULL DEFAULT '',
 due_at BIGINT NOT NULL,
 local_slot TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL CHECK(status IN ('planned','submitting','submitted','confirmed','failed','skipped')),
 buffer_post_id TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 response_json TEXT NOT NULL DEFAULT '',
 attempts INTEGER NOT NULL DEFAULT 0,
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL,
 UNIQUE(idea_id, platform)
);
CREATE INDEX IF NOT EXISTS content_publications_due ON content_publications(status, due_at);
CREATE INDEX IF NOT EXISTS content_publications_idea ON content_publications(idea_id);

-- Worker queue. The HTTP worker leases rows; leases expire so a crashed run
-- cannot strand work. Nothing here stores secrets or prompt text twice.
CREATE TABLE IF NOT EXISTS content_jobs (
 id TEXT PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN ('generate','caption','publish','sync')),
 idea_id TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL CHECK(status IN ('pending','running','done','failed','dead')),
 attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 3,
 available_at BIGINT NOT NULL,
 leased_until BIGINT NOT NULL DEFAULT 0,
 leased_by TEXT NOT NULL DEFAULT '',
 last_error TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS content_jobs_ready ON content_jobs(status, available_at);
CREATE INDEX IF NOT EXISTS content_jobs_idea ON content_jobs(idea_id, kind);
CREATE TABLE IF NOT EXISTS content_state (
 name TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '', updated_at BIGINT NOT NULL
);

ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS idea_id TEXT NOT NULL DEFAULT '';
ALTER TABLE video_jobs ADD COLUMN IF NOT EXISTS resolution TEXT NOT NULL DEFAULT '';

ALTER TABLE content_series ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_ideas ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_state ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON content_series, content_ideas, media_assets, content_publications, content_jobs, content_state FROM PUBLIC;
COMMIT;
