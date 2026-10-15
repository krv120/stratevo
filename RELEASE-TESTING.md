# Reproducing the reviewed release tests

Version **2026.10.13-rc1**. Use synthetic/isolated environments only. Run from the extracted project root. Do not point tests at a real database or enable live provider/mail services.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Test-only tools (not runtime dependencies):

```sh
.venv/bin/python -m pip install pgserver bandit pip-audit
PYTHONPATH=.:tests .venv/bin/python tests/postgres_integration.py
.venv/bin/python -m bandit -r app api scripts
.venv/bin/python -m pip_audit -r requirements.txt --vulnerability-service pypi
.venv/bin/python -m pip check
```

PostgreSQL integration uses a bundled temporary server beneath `private/` and cleans up only its synthetic fixture. It applies and reapplies migrations 001–005, exercises concurrency and private role/RLS boundaries. Bandit intentionally retains documented findings; a nonzero scan exit is not a successful zero-findings audit.

For Chromium/axe tests, install development tools privately:

```sh
mkdir -p private/browser private/audit-20261012 private/release-20261013
npm install --prefix private/browser --no-audit --no-fund playwright @sparticuz/chromium @axe-core/playwright
```

Create `private/browser-config.json` locally, mode 0600, with `PORT=8002`, `APP_ENV=test`, blank `DATABASE_URL`, `SUPPLIER_SQLITE_PATH` pointing to the absolute `private/browser-test.sqlite3`, `PUBLIC_BASE_URL=http://127.0.0.1:8002`, `COOKIE_SECURE=false`, no AI/SMTP credentials, `MAIL_DELIVERY_ENABLED=false`, `NOTIFICATION_EMAIL=owner@example.invalid`, a fresh local-only random `TEST_ADMIN_PASSWORD` and its PBKDF2 `ADMIN_PASSWORD_HASH`, blank `ADMIN_ACCOUNTS_JSON`, and disabled indexing/erasure/retention apply. Use `app.suppliers.hash_password` to derive the hash; do not use production credentials.

In a separate terminal start the synthetic server:

```sh
.venv/bin/python scripts/run_preview.py private/browser-config.json
```

Then run:

```sh
node tests/browser.cjs
node tests/audit_browser.cjs
node tests/release_browser.cjs
```

The browser suites read only that synthetic SQLite outbox to simulate email receipt; no real email is sent. AI success/error/timeout replies are mocked. New inquiry loss/retry tests use actual local persistence. Specific timeout tests deliberately stall transport and advance browser time. Default quotas remain enabled; repeated full runs can exhaust them. Wait for the real window or archive/recreate only the explicitly synthetic fixture with the server stopped. Never lower limits or delete real data to force a pass.

The packaged PNG screenshots show local public pages without private records. They are not production screenshots. Additional before/after captures were retained privately during review. Public source-page generation is reproducible with `python scripts/create_pages.py`. The already-shipped OG image can optionally be regenerated with `scripts/create_brand_assets.py` on a system with DejaVu Sans at the documented script path; that font is a generation dependency, not a new remotely loaded website font.

Run `STRATEVO_RELEASE_COMMIT="$(git rev-parse HEAD)" python scripts/package_release.py` only after the final source/tests/docs are reviewed. Its allowlist excludes private data/configuration/dependencies, includes reviewed evidence only if available, and writes `MANIFEST.json` with release version, source commit and file SHA-256 hashes. A clean build without local validation files contains source but cannot invent missing evidence.

Inspect/extract the ZIP, verify manifest/CRC and exclusions, and rerun unit tests inside the extracted tree. Final application/browser/database evidence must match the packaged source; old reports are historical context, not a replacement for fresh tests.
