# Start here — STRATEVO reviewed package

This ZIP contains the updated source, audit findings, AI knowledge/language guide, test suite and deployment instructions. It does **not** contain your API key, supplier exports, databases or private documents.

## Latest change

Public AI opens full-screen without customer credentials. Supplier registration opens a popup, and products publish automatically to `/marketplace` after email confirmation, with no manager approval. Identity/contact/license information stays private. Read `PUBLIC-MARKETPLACE-UPDATE.md` first; the screenshot-derived design is preserved. Current suite: 101 passing unit/HTTP tests plus real PostgreSQL and Chromium checks.

## Your next steps

1. Unzip into a working folder. Read `AUDIT-REPORT.md` for fixes and remaining limits.
2. Deploy this code to a staging/preview hosting project first. Do not overwrite the live site without a backup and rollback plan.
3. Follow `KEY-SETUP.md`: keep your Gemini key in server-side environment variables. Use the Gemini OpenAI-compatible base URL, your available model ID, and `ONLINE_DISCOVERY_ENABLED=false` because you have not configured Brave.
4. Follow `DEPLOYMENT.md` for PostgreSQL migrations, canonical origin, manager hash, secure cookies and SMTP/worker setup.
5. Sign into `/admin`, run **Test AI connection**, then use `/ai`. Then test `/ai` in a signed-out/incognito browser: customers need no credentials.
6. Run the live-language and sourcing cases in `AI-EVALUATION.md`. Prompt guidance is improved, but actual Gemini quality has not been measured by this package's mocked tests.
7. Test real supplier registration → inbox confirmation → automatic product publication → `/supplier/account` → withdrawal. Configure SMTP and its retry worker; queued mail alone is not proof of delivery.

## Files worth reading

- `AUDIT-REPORT.md`: earlier engineering review and remaining launch gates; the latest 101-test validation is in `PUBLIC-MARKETPLACE-UPDATE.md`.
- `AI-KNOWLEDGE-GUIDE.md`: curated sourcing knowledge and slang/Greeklish interpretation rules.
- `AI-EVALUATION.md`: 26 manual cases for your real model after deployment.
- `KEY-SETUP.md`: exact Gemini setup without Brave, and optional search setup later.
- `DEPLOYMENT.md`: backend/database/email/hosting requirements.
- `README.md`: developer overview and test commands.
- `validation/`: selected test/static-analysis logs, when included by the release builder.
- `MANIFEST.json`: SHA-256 checksums of every other packaged file. It is an integrity aid, not a digital signature or security certification.

The live production domain has not been updated by generating this file. All changes here must be deployed before your hosted app can use them. Historical notes in `SOURCING-AI-NOTES.md` and `LIVE-SITE-AUDIT.md` describe earlier work; the current audit/report and setup guide take precedence for this release.
