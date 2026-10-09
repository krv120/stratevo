# Start here — STRATEVO reviewed package

This ZIP contains the updated source, audit findings, AI knowledge/language guide, test suite and deployment instructions. It does **not** contain your API key, supplier exports, databases or private documents.

## Latest change

The homepage now follows the supplied black/blue screenshot reference; supplier signup and AI error handling have been refined. Read `REFERENCE-RESTORATION.md` first. Current automated suite: 80 passing tests. The older audit report is retained as historical validation, with ongoing launch gates.

## Your next steps

1. Unzip into a working folder. Read `AUDIT-REPORT.md` for fixes and remaining limits.
2. Deploy this code to a staging/preview hosting project first. Do not overwrite the live site without a backup and rollback plan.
3. Follow `KEY-SETUP.md`: keep your Gemini key in server-side environment variables. Use the Gemini OpenAI-compatible base URL, your available model ID, and `ONLINE_DISCOVERY_ENABLED=false` because you have not configured Brave.
4. Follow `DEPLOYMENT.md` for PostgreSQL migrations, canonical origin, manager hash, secure cookies and SMTP/worker setup.
5. Sign into `/admin`, run **Test AI connection**, then use `/ai`. Your manager session unlocks research/chat; the owner-token field is not an API-key input.
6. Run the live-language and sourcing cases in `AI-EVALUATION.md`. Prompt guidance is improved, but actual Gemini quality has not been measured by this package's mocked tests.
7. Test real supplier email verification → approval → private profile access. Approval activates the profile immediately, but actual access-email delivery requires a working mail service/worker.

## Files worth reading

- `AUDIT-REPORT.md`: earlier engineering review and remaining launch gates; the latest 80-test validation is in `REFERENCE-RESTORATION.md`.
- `AI-KNOWLEDGE-GUIDE.md`: curated sourcing knowledge and slang/Greeklish interpretation rules.
- `AI-EVALUATION.md`: 26 manual cases for your real model after deployment.
- `KEY-SETUP.md`: exact Gemini setup without Brave, and optional search setup later.
- `DEPLOYMENT.md`: backend/database/email/hosting requirements.
- `README.md`: developer overview and test commands.
- `validation/`: selected test/static-analysis logs, when included by the release builder.
- `MANIFEST.json`: SHA-256 checksums of every other packaged file. It is an integrity aid, not a digital signature or security certification.

The live production domain has not been updated by generating this file. All changes here must be deployed before your hosted app can use them. Historical notes in `SOURCING-AI-NOTES.md` and `LIVE-SITE-AUDIT.md` describe earlier work; the current audit/report and setup guide take precedence for this release.
