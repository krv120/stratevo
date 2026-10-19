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
