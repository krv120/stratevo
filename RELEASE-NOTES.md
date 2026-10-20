# 2026.10.20-static-rc1 — remove Python catch-all page routing

Public pages now build to a public-only static Vercel output. Python is reserved for API requests. Built pages call the explicit Python function URL directly, preserving API route/query information without relying on an edge rewrite. Public REST aliases remain supported. Registration still navigates automatically to the highlighted listing; the sign-in-link request form remains removed.

Vercel-generated deployment origins are allowlisted by exact server environment value, never by user-supplied Host/forwarding headers. Private API authentication and origin checks remain enforced. No production data migration, domain change or production promotion is included.

Current local suite: 100 tests. Static-output browser journeys cover both SQLite fallback and isolated PostgreSQL. One initial PostgreSQL browser attempt timed out waiting for the newly registered card; a subsequent run passed. This intermittent observation remains disclosed; it is not a zero-defect claim. Further final/extracted-source results accompany the handoff. Vercel's routing compiler confirms public page paths and the direct function path do not match the API rewrite.

The supplied deployment screenshot remains genuine evidence of a hosted failure. The new architecture is not confirmed hosted-working until the owner opens the new protected preview and verifies it. Existing preview authentication is not removed automatically.

--- Previous release history ---

# 2026.10.19-directory-rc4 — direct registration to Marketplace

Removed the sign-in-link request form and obsolete navigation anchors. Successful registration now navigates automatically to Marketplace with the published listing highlighted. Validation and failed saves retain the form; retry/idempotency protection remains. Active registration sessions can use My Supplier Account; expired-session access requires ownership-verified assistance.

The explicit Vercel destination `/api/index.py?__stratevo_path=/$1` and adapter path recovery remain in place. Tests cover the configured rewrite, public pages/assets/health, query preservation, POST registration and HEAD requests. Browser scenarios cover automatic navigation, privacy, blocked storage, duplicate submissions and response-loss/timeout retries on both storage modes.

This is source/local regression evidence, not an observed Vercel deployment. Use the new commit's deployment, not the earlier f357c81 deployment URL. Project settings, environment and durable database provisioning must still be correct; no zero-error guarantee is made. No production data, DNS or main-branch changes are included.

---

# 2026.10.19-directory-rc3 — explicit Python entrypoint

## Explicit Python entrypoint correction

The catch-all now targets `/api/index.py?__stratevo_path=/$1`, explicitly matching the Python function filename while retaining original-path recovery. Configuration, GET/HEAD/POST routing and query preservation are covered by 93 passing tests. Both rewrite-simulated browser suites passed on fallback and isolated PostgreSQL. Logs: `validation/explicit-entrypoint-*.log`.

These checks do not certify an actual Vercel build. The correction is prepared for the approved branch push and Arena sandbox preview. No production hosting, database or DNS change was performed.

# 2026.10.19-directory-rc2 — routing correction

The supplied Vercel deployment returned `{"error":"Not found"}` for home, supplier and health. The prior local checks bypassed the catch-all rewrite. This release explicitly carries the public path in the Vercel destination and restores it in the adapter before routing GET/HEAD/POST, preserving query filters and request bodies. It does not trust forwarding headers.

The old rewrite fails the new regression; the corrected configuration passes it. Additional browser runs execute all journeys through a simulation of the configured rewrite with both fallback and real isolated PostgreSQL. This is not an actual Vercel deployment test. Vercel access remains disconnected; the existing URL cannot be declared repaired from these checks.

Current source testing: 91 unit/HTTP/envelope checks; rewrite browser suites on both storage modes. Updated logs are under validation/routing-*.log. Prior candidate evidence below remains historical, not evidence that the reported deployed site worked.

Production persistence, backup/restore, legal disclosures, authorized real email and external booking completion remain launch requirements. No production database/DNS operation or deployment was performed. Branch pushes can trigger hosting automation.

---

# 2026.10.19-directory-rc1

## Delivered source

Immediate single-step supplier directory; private contact separation; accessible supplier details and fixed Minup booking conversion; responsive navigation; owner edits/withdrawal; public-only browser backup with authenticated canonical sync; optional unconfigured admin MFA; updated contact/legal/storage copy; retired product helper interfaces removed. Existing historical records/migrations are preserved, not destructively rewritten.

## Current source checks

- Active unit/HTTP tests: **54 passed**, final run 8.886 seconds.
- Browser fallback and real isolated PostgreSQL: **both passed**, eleven routes × five widths plus registration/privacy/owner/staff/retry/accessibility scenarios.
- Independent real isolated PostgreSQL: **8 passed groups**, including concurrent bootstrap/registration, private projection, atomic edits, moderation, schema reapplication, RLS and erasure.
- Python compile, JavaScript syntax, generators and dependency consistency: passed.
- Runtime dependency audit: no known vulnerabilities reported at audit time.
- Bandit: 17 findings, none HIGH; contextual review in SECURITY-REVIEW.md.

These are synthetic local checks, not live production verification. Exact source archive extraction/hash verification and reruns are recorded separately in the release handoff to avoid self-referential evidence. Browser logs and selected local before/after screenshots are included in validation; prior local renders are explicitly labeled, never presented as live.

## Deployment blockers / limitations

Durable production PostgreSQL and tested backup/restore; host configuration/secrets; missing applicable legal disclosures; functional storage legal review; actual authorized mail delivery and external booking completion; actual host/redirect/header/indexing checks. Vercel was disconnected. No production deployment, main merge, database/DNS change, real email or booking was performed. Source branch push may trigger hosting automation and is not a guarantee of deployment isolation.
