# STRATEVO — reviewed source package

A Python/vanilla-JavaScript sourcing website and email-confirmed product marketplace. This is a new implementation, **not recovered production source**. Repository edits do not change `stratevo.online` until you deploy them.

## Latest update: public AI and self-service Marketplace

Read [PUBLIC-MARKETPLACE-UPDATE.md](PUBLIC-MARKETPLACE-UPDATE.md) for this revision. Public AI needs no customer credentials; new products publish after email confirmation without manager approval. The October 9 screenshot-derived black/blue design is preserved. Older audit/reference reports remain historical.

## Start here

1. **[KEY-SETUP.md](KEY-SETUP.md)** — your Google Gemini configuration, without Brave; manager connection tests; supplier email/profile setup.
2. **[AUDIT-REPORT.md](AUDIT-REPORT.md)** — verified findings, fixes, test results and remaining launch blockers.
3. **[AI-KNOWLEDGE-GUIDE.md](AI-KNOWLEDGE-GUIDE.md)** — curated sourcing, slang, abbreviations, Greek/Greeklish and uncertainty guidance added to the assistant.
4. **[AI-EVALUATION.md](AI-EVALUATION.md)** — live-model acceptance cases to run after deployment.
5. **[DEPLOYMENT.md](DEPLOYMENT.md)** — private PostgreSQL, hosting, SMTP worker and production launch gates.

## Features

- Responsive black/blue homepage, sourcing pillars/stages, specified `hello@stratevo.co` contact and Minup booking.
- Private application with business details, PDF license, email + WhatsApp **or** WeChat.
- Supplier popup → email verification → automatic product publication and private `/supplier/account`. No manager approval. Suppliers can add and withdraw their products.
- Separate `/marketplace` with product photos/details, advertised prices/MOQs, search and categories. Company identity/contacts/documents stay private; inquiries go through STRATEVO.
- Manager-only private registry, license downloads, post-publication removal and connection tests. Legacy applications remain separately labeled.
- Provider-configurable Chat Completions integration, including Gemini's OpenAI-compatible endpoint. Bounded curated context for sourcing and natural-language understanding. This is prompt augmentation, not fine-tuning or an encyclopedic verified knowledge database.
- Private catalog matching with four qualification points, conservative evidence checks, at most three anonymized leads and honest unknowns.
- Optional owner-only Brave web discovery. **Disabled without a separate search key.** Web candidate pages are not verified supplier matches. Original evidence remains manager-only; raw snippets do not enter the model or customer cards.
- SQLite locally; private PostgreSQL/Supabase schema on hosted deployments. No orders, payments, contracts or automatic factory certification.

## Local development

Python 3.11+. Install `requirements.txt`; Pillow is required for product-photo processing. `private/` is created as needed and must remain ignored.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export PUBLIC_BASE_URL=http://127.0.0.1:8000
export COOKIE_SECURE=false
python3 -m app.suppliers hash-password
# Set ADMIN_PASSWORD_HASH to the output using a secure environment editor.
python3 -m app.server
```

The development server binds `0.0.0.0:8000` intentionally for proxied previews. Use secure cookies and the exact HTTPS canonical origin on hosted previews. Open the preview directly in a tab if third-party cookie restrictions interfere.

`.env.example` documents variable names; `.env` is **not automatically loaded**. An ignored `private/local-config.json` environment object can be loaded using `python3 scripts/run_preview.py private/local-config.json`. Never put keys in frontend code or chat.

Routes: `/`, `/supplier`, `/supplier/account`, `/marketplace`, `/admin`, `/access`, legacy `/portal`, `/ai`. Chat and qualified matching are public with durable rate/request limits. Raw research, live discovery and operational controls stay private.

## Data and privacy

No actual supplier export, live owner database, license, password, API key or private source file is bundled. Historical data and attachment-availability notes appear in `SOURCING-AI-NOTES.md`; they are not assertions of current imported suppliers. Tests use isolated synthetic records visibly marked TEST ONLY.

Raw research provenance is private. Buyer projections strip recognized source URLs/emails; human editorial review is still needed for names, telephone numbers and unusual obfuscation. Certification marketing claims never become verified certificates automatically. Imported research is separate from email-confirmed supplier accounts; neither email confirmation nor publication verifies a business.

## Validation

Current revision: **101 Python unit/HTTP tests passed**, real ephemeral PostgreSQL migrations/workflows/concurrency/RLS passed, and Chromium public-chat/supplier-popup/auto-publication/account/moderation/responsive checks passed. See `PUBLIC-MARKETPLACE-UPDATE.md` for exact scope and limitations. External AI/search responses were mocked in automated tests; real credentials and SMTP inbox delivery were not tested here.

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js
node --check web/site.js
```

Optional integration tooling (kept private):

```sh
python3 -m pip install --target private/audit-tools pgserver 'psycopg[binary]==3.2.10' bandit
PYTHONPATH="$PWD/private/audit-tools:$PWD:$PWD/tests" python3 tests/postgres_integration.py
npm install --prefix private/browser --no-save --package-lock=false playwright @sparticuz/chromium
```

`tests/browser.cjs` requires an isolated server on port 8002, `private/browser-test.sqlite3`, `PUBLIC_BASE_URL=http://127.0.0.1:8002`, `COOKIE_SECURE=false`, no configured AI/search/SMTP credentials, and a generated test manager password. Store that test-only plaintext value as `TEST_ADMIN_PASSWORD` and its server hash as `ADMIN_PASSWORD_HASH` in ignored `private/browser-config.json`. Launch with `.venv/bin/python scripts/run_preview.py private/browser-config.json`; run `node tests/browser.cjs`. The test reads only its own test outbox (not a real inbox), explicitly mocks one chat response, and extracts Chromium's bundled Linux libraries. Never run it against production or the public preview database.

## Release and packaging

Run `python3 scripts/package_release.py` to create a source-only ZIP in `private/`, with a SHA-256 manifest and tests/guides. The script uses explicit allowed directories and excludes private data, caches, symlinks and credentials. Inspect the generated package before distributing.

No production deployment, comprehensive penetration test, public legal compliance review, real Gemini quality benchmark or guarantee of zero defects is claimed.
