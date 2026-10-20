# Reproducing candidate checks

Use isolated synthetic data only. No real emails or bookings are required or authorized by these scripts.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
mkdir -p private/browser
cp tests/browser-package.json private/browser/package.json
npm install --prefix private/browser
.venv/bin/python scripts/build_content.py
.venv/bin/python scripts/create_pages.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=.:tests .venv/bin/python tests/postgres_current.py
PYTHONPATH=. .venv/bin/python tests/run_browser.py
PYTHONPATH=. .venv/bin/python tests/run_browser.py --postgres
PYTHONPATH=. .venv/bin/python tests/run_browser.py --rewrite
PYTHONPATH=. .venv/bin/python tests/run_browser.py --rewrite --postgres
.venv/bin/python -m compileall -q app api scripts tests
for f in web/*.js; do node --check "$f"; done
.venv/bin/pip check
.venv/bin/pip-audit -r requirements.txt
.venv/bin/bandit -r app api scripts -f json
```

Browser tooling uses pinned development packages and a packaged Linux Chromium, or the supported launcher in `tests/browser_support.cjs`. PostgreSQL tests use an isolated local `pgserver` instance, not a managed production database. Browser tests use the actual Vercel request handler through local HTTPS, not Vercel infrastructure. Browser evidence is written into ignored `private/audit/` paths.

## Scope and interpretation

Active `test_directory.py` and `test_suppliers.py` cover validation, immediate publication, private/public projections, idempotency, account sessions, auth/MFA, moderation, synchronization and relevant compatible legacy behavior. Retired tests under `tests/previous_contracts/` preserve historical contracts and are **not current passing evidence**.

Browser runs cover eleven routes at five widths including 320/375/430px, card/details/booking navigation, single-step registration, private profile changes, optional-MFA admin, moderation, blocked storage, lost response retry, stalled-request timeout and duplicate-submit protection. Keyboard/dialog/drawer behavior, reduced motion, automated accessibility and overflow are checked. Automated accessibility does not replace assistive-technology/manual testing. Booking navigation is intercepted; completion and the external provider's availability are not tested. Mail is disabled/mocked; no delivery claim.

Review `validation/` and `RELEASE-NOTES.md` for the final recorded results. Historical screenshot labels distinguish **local previous-release renders** from live evidence. No live screenshots were obtained.

## Exact archive

`scripts/package_release.py --output /home/user/STRATEVO-2026.10.20-static-rc1.zip` creates the complete candidate source archive with an internal SHA-256 manifest, excluding private files, credentials, runtime databases, tooling caches and dependencies. Extract into an isolated directory, verify `MANIFEST.json`, and run the same generators, active suite and browser checks against that extracted root. The GitHub commit archive is independently immutable but does not contain the ZIP-only generated manifest. Never package ignored `private/` evidence wholesale.

## Routing regression

`--rewrite` simulates the configured Vercel rewrite before dispatch to the actual adapter. The former destination loses the original route and fails the regression (homepage, pages, assets and health). This is additional boundary coverage, not proof of a hosted deployment. The latest hosted URL returned JSON Not found; hosting validation remains required after redeployment.

## Static build regression checks (current deployment)

Run `python3 scripts/build_static.py`, then `PYTHONPATH=. .venv/bin/python tests/run_browser.py --static` and the same command with `--postgres`. These serve the built public output with the real API handler, exercising the direct function transport, not the former catch-all page rewrite. `test_static_output.py` verifies pages still work when the API page router is disabled and verifies the public artifact allowlist. `public-site` is a generated, ignored directory, recreated by Vercel from source.
