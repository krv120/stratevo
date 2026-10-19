# Hosted deployment diagnosis — 2026-10-19

The supplied project hostname still returned JSON `{"error":"Not found"}` when checked. A successful GitHub Vercel build status is not evidence of a working page or proof that a particular alias serves that revision. The preview URL posted by the Vercel bot returned DEPLOYMENT_NOT_FOUND during the preceding investigation. The production/main branch has not been merged or changed.

Current Vercel routing-utils compiles the existing catch-all to a Python destination with a captured path. Current python-analysis selects the `handler` export. Those checks do not establish the version/configuration deployed on the failing hostname. The imported base class is now private (`_BaseHandler`) to remove a second public handler name; this is defensive hardening, not a proven hosted root-cause fix.

`GET /api/version` now returns only a public release marker and, when available, a validated 40-character Vercel commit SHA. It does not access the database or reveal environment settings, credentials, sessions or customer records. All application responses carry X-Stratevo-Release. This distinguishes code identity from database health and allows an authentic application 404 to be attributed to a release.

Expected marker: `2026.10.19-routing-check-1`. If the endpoint is still absent after a deployment is Ready, inspect that deployment's source revision and runtime logs rather than shipping another unverified ZIP. If the marker is present, capture the failing path and HTTP status for diagnosis. A marker alone does not prove registration, mail delivery or durability.

Local validation: 96 tests and the rewrite-aware browser suite passed. No production deployment, domain change, main merge or production data change was performed. Approved-branch pushes may trigger hosting automation.
