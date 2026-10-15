> **Current Vercel fix:** see [VERCEL-FIX-2026-10-15.md](VERCEL-FIX-2026-10-15.md) for changed immediate-publication behavior, automatic migrations and the limitations of ephemeral fallback. Earlier release results below are historical.

# Start here — STRATEVO reviewed package

> **Current release: 2026.10.13-rc1.** Start with `FINAL-RELEASE-2026-10-13.md`, `LIVE-SOURCE-COMPARISON-2026-10-13.md`, `SEARCH-AND-MEASUREMENT-HANDOFF.md` and `RELEASE-TESTING.md`. Older reports below are historical, not current production evidence. No production deployment is authorized by this release.

> **Latest hardening:** read `ENGINEERING-AUDIT-2026-10-12.md` and `OPERATIONS-HANDOFF.md` first. They supersede older upload, login, worker, retention and deployment instructions below. Migration 005 and explicit environment/service approvals are required; this is not launch approval.

This ZIP contains the updated source, audit findings, AI knowledge/language guide, test suite and deployment instructions. It does **not** contain your API key, supplier exports, databases or private documents.

## Latest change

Public AI opens full-screen without customer credentials. Supplier registration opens a popup, and products publish automatically to `/marketplace` after email confirmation, with no manager approval. Identity/contact/license information stays private. Read `PRODUCTION-AUDIT-2026-10-12.md` first; the screenshot-derived design is preserved. Current suite: 115 passing unit/HTTP tests plus real PostgreSQL and Chromium checks.

## Your next steps

1. Unzip into a working folder. Read `AUDIT-REPORT.md` for fixes and remaining limits.
2. Deploy this code to a staging/preview hosting project first. Do not overwrite the live site without a backup and rollback plan.
3. Follow `KEY-SETUP.md`: keep your Gemini key in server-side environment variables. Use the Gemini OpenAI-compatible base URL, your available model ID, and `ONLINE_DISCOVERY_ENABLED=false` because you have not configured Brave.
4. Follow `DEPLOYMENT.md` for PostgreSQL migrations, canonical origin, manager hash, secure cookies and SMTP/worker setup.
5. Sign into `/admin`, run **Test AI connection**, then use `/ai`. Then test `/ai` in a signed-out/incognito browser: customers need no credentials.
6. Run the live-language and sourcing cases in `AI-EVALUATION.md`. Prompt guidance is improved, but actual Gemini quality has not been measured by this package's mocked tests.
7. Test real supplier registration → inbox confirmation → automatic product publication → `/supplier/account` → withdrawal. Configure SMTP and its retry worker; queued mail alone is not proof of delivery.

## Files worth reading

- `AUDIT-REPORT.md`: earlier engineering review and remaining launch gates; the latest 115-test validation is in `PRODUCTION-AUDIT-2026-10-12.md`.
- `AI-KNOWLEDGE-GUIDE.md`: curated sourcing knowledge and slang/Greeklish interpretation rules.
- `AI-EVALUATION.md`: 26 manual cases for your real model after deployment.
- `KEY-SETUP.md`: exact Gemini setup without Brave, and optional search setup later.
- `DEPLOYMENT.md`: backend/database/email/hosting requirements.
- `README.md`: developer overview and test commands.
- `validation/`: selected test/static-analysis logs, when included by the release builder.
- `MANIFEST.json`: SHA-256 checksums of every other packaged file. It is an integrity aid, not a digital signature or security certification.

The live production domain has not been updated by generating this file. All changes here must be deployed before your hosted app can use them. Historical notes in `SOURCING-AI-NOTES.md` and `LIVE-SITE-AUDIT.md` describe earlier work; the current audit/report and setup guide take precedence for this release.

## Customer inquiries and owner notifications

`/inquiry` is a real private lead form, separate from supplier registration. Apply migration 004 after 001–003, set `NOTIFICATION_EMAIL` to a verified inbox, and run the existing mail worker. Test record save, exact-payload retry, private admin visibility and actual inbox delivery in staging. Keep indexing disabled until legal/operational readiness is confirmed. No production deployment or live API test is claimed by this package.
