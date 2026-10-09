# STRATEVO — reviewed source package

A Python/vanilla-JavaScript sourcing website and private supplier-approval platform. This is a new implementation, **not recovered production source**. Repository edits do not change `stratevo.online` until you deploy them.

## Start here

1. **[KEY-SETUP.md](KEY-SETUP.md)** — your Google Gemini configuration, without Brave; manager connection tests; supplier email/profile setup.
2. **[AUDIT-REPORT.md](AUDIT-REPORT.md)** — verified findings, fixes, test results and remaining launch blockers.
3. **[AI-KNOWLEDGE-GUIDE.md](AI-KNOWLEDGE-GUIDE.md)** — curated sourcing, slang, abbreviations, Greek/Greeklish and uncertainty guidance added to the assistant.
4. **[AI-EVALUATION.md](AI-EVALUATION.md)** — live-model acceptance cases to run after deployment.
5. **[DEPLOYMENT.md](DEPLOYMENT.md)** — private PostgreSQL, hosting, SMTP worker and production launch gates.

## Features

- Responsive black/blue homepage, sourcing pillars/stages, specified `hello@stratevo.co` contact and Minup booking.
- Private application with business details, PDF license, email + WhatsApp **or** WeChat.
- Email verification → manager review → approval/rejection. Approval immediately activates the private profile; a single-use email sign-in redirects the supplier to their own `/portal`.
- Manager queue, private license downloads, profile links, account-role enforcement and server-side connection tests.
- Provider-configurable Chat Completions integration, including Gemini's OpenAI-compatible endpoint. Bounded curated context for sourcing and natural-language understanding. This is prompt augmentation, not fine-tuning or an encyclopedic verified knowledge database.
- Private catalog matching with four qualification points, conservative evidence checks, at most three anonymized leads and honest unknowns.
- Optional Brave web discovery. **Disabled without a separate search key.** Web candidate pages are not verified supplier matches. Original evidence remains manager-only; raw snippets do not enter the model or customer cards.
- SQLite locally; private PostgreSQL/Supabase schema on hosted deployments. No orders, payments, contracts or automatic factory certification.

## Local development

Python 3.11+. SQLite mode needs no third-party runtime dependencies. `private/` is created as needed and must remain ignored.

```sh
export PUBLIC_BASE_URL=http://127.0.0.1:8000
export COOKIE_SECURE=false
python3 -m app.suppliers hash-password
# Set ADMIN_PASSWORD_HASH to the output using a secure environment editor.
python3 -m app.server
```

The development server binds `0.0.0.0:8000` intentionally for proxied previews. Use secure cookies and the exact HTTPS canonical origin on hosted previews. Open the preview directly in a tab if third-party cookie restrictions interfere.

`.env.example` documents variable names; `.env` is **not automatically loaded**. An ignored `private/local-config.json` environment object can be loaded using `python3 scripts/run_preview.py private/local-config.json`. Never put keys in frontend code or the owner access-token field.

Routes: `/`, `/supplier`, `/admin`, `/access`, `/portal`, `/ai`. Research/chat currently require manager session or owner token; this is not a publicly open, unrestricted chat service.

## Data and privacy

No actual supplier export, live owner database, license, password, API key or private source file is bundled. Historical data and attachment-availability notes appear in `SOURCING-AI-NOTES.md`; they are not assertions of current imported suppliers. Tests use isolated synthetic records visibly marked TEST ONLY.

Raw research provenance is private. Buyer projections strip recognized source URLs/emails; human editorial review is still needed for names, telephone numbers and unusual obfuscation. Certification marketing claims never become verified certificates automatically. Imported research is separate from approved supplier membership.

## Validation

Current audit: **74 Python unit/HTTP tests passed**; real ephemeral PostgreSQL tests passed; Chromium supplier workflow, manager profile/connection diagnostics and six 390px mobile routes passed. See `AUDIT-REPORT.md` for exact scope and limitations. External AI/search responses were mocked in automated tests; real credentials and SMTP inbox delivery were not tested here.

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js
node --check web/site.js
```

Optional integration tooling (kept private):

```sh
python3 -m pip install --target private/audit-tools pgserver 'psycopg[binary]==3.2.10' bandit
PYTHONPATH="$PWD/private/audit-tools:$PWD" python3 tests/postgres_integration.py
npm install --prefix private/browser --no-save --package-lock=false playwright @sparticuz/chromium
```

`tests/browser.cjs` requires an isolated server on port 8002, private test database, `PUBLIC_BASE_URL=http://127.0.0.1:8002`, `COOKIE_SECURE=false`, no configured AI/search credentials, and test password `browser-test-manager-password`. This intentionally published **test-only** password must never be used for production. On minimal Linux environments extract the Chromium package's `al2023.tar.br` libraries and use `LD_LIBRARY_PATH` as necessary.

## Release and packaging

Run `python3 scripts/package_release.py` to create a source-only ZIP in `private/`, with a SHA-256 manifest and tests/guides. The script uses explicit allowed directories and excludes private data, caches, symlinks and credentials. Inspect the generated package before distributing.

No production deployment, comprehensive penetration test, public legal compliance review, real Gemini quality benchmark or guarantee of zero defects is claimed.
