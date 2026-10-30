# Candidate security and privacy review — 2026-10-19

## Verified locally

Active tests exercise authenticated owner/staff boundaries, optional/unconfigured and configured/replayed MFA, credential rotation, field validation, public projection, concurrent idempotency, stale-version rejection, moderation and erasure. Real isolated PostgreSQL tests cover migrations, concurrent bootstrap and RLS denying rows to an accidentally granted reader. These are not a penetration test or a managed-host audit.

Public endpoints disclose company, focus and scrubbed description only, plus operational listing identifiers/status. Private contact, email, phone, website and location remain server-side. Recognizable emails/phones/URLs embedded in public prose are scrubbed; no heuristic guarantees detection of every obfuscated identifier. Owners remain responsible for appropriate public content. Public browser backup never contains private contacts or credentials, expires after seven days, and cannot restore missing/removed records. Session cookies are authentication storage, not marketing tracking. Review the functional localStorage purpose and applicable consent exemption before launch; this report does not certify an exemption.

## Scanner findings

Runtime requirement audit reports no known vulnerabilities at the audit time; dependency installation consistency passes. Bandit reports 17 findings, none HIGH. They are not silently suppressed:

- B108 (`connections.py`): explicit `/tmp` SQLite fallback. It is intentionally ephemeral and unsuitable for real production durability; require PostgreSQL and strict mode.
- B110 (`directory.py`, `mail_policy.py`, `server.py`): best-effort delivery exceptions after committed records. Mail remains queued for recovery. Monitoring/retry and real delivery tests remain operational requirements; successful registration is not proof of email delivery.
- B608 (`directory.py` twice, `intake.py`, `maintenance.py`, `marketplace.py` three times): SQL statement composition uses internal fixed fragments/placeholder counts; user values are bound parameters. Keep fragments allowlisted when modifying these queries.
- B104 (`server.py`): local server intentionally binds all interfaces for preview access. Use deployment TLS/network controls; do not expose an unconfigured development server as production.

- B404/B603/B607 (`package_release.py`, five findings): local packaging invokes fixed `git rev-parse` and `git status` argument lists without a shell or user-supplied commands. Run packaging only in a trusted development environment/PATH.

No scanner result means zero defects. Secret-pattern packaging checks are an additional guard, not a complete secret audit. Private paths, environment files, database files and dependency directories are excluded from the archive.

## Outstanding external checks

Production hosting/security headers/redirects, real database backup/restore, host secrets/permissions, actual mail acceptance/inbox arrival, external booking completion, legal disclosure sufficiency and assistive-technology/manual usability remain unverified. New unscanned PDFs stay disabled. Do not enable public indexing or deploy on the strength of local tests alone.
