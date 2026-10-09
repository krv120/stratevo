-- On-demand search evidence: backend only, never browser-readable.
BEGIN;
CREATE TABLE IF NOT EXISTS stratevo_private.discovery_evidence (
  id TEXT PRIMARY KEY,
  searched_at TEXT NOT NULL,
  evidence TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stratevo_private.discovery_budget (
  day TEXT PRIMARY KEY,
  calls INTEGER NOT NULL
);
ALTER TABLE stratevo_private.discovery_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE stratevo_private.discovery_budget ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON stratevo_private.discovery_evidence, stratevo_private.discovery_budget FROM PUBLIC;
DO $$
BEGIN
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
  REVOKE ALL ON stratevo_private.discovery_evidence, stratevo_private.discovery_budget FROM anon;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
  REVOKE ALL ON stratevo_private.discovery_evidence, stratevo_private.discovery_budget FROM authenticated;
 END IF;
END $$;
COMMIT;
