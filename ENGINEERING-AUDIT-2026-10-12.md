# STRATEVO — full engineering follow-up audit

**12 October 2026 · branch `arena/40bf7fdf-stratevo` · baseline `5283cc1`**

**Decision: suitable for further isolated staging validation, NOT approved for production launch.** Substantial repairs are implemented and locally tested. This is reconstructed Python/vanilla-JavaScript source, not verified recovered production code. No production deployment, merge, push, migration, deletion, email, DNS change or paid service activation was performed.

This report supersedes the earlier `PRODUCTION-AUDIT-2026-10-12.md` for current behavior and test evidence. That report records a different completed audit and must not be treated as proof for these changes.

## A — Findings and implemented changes

Fresh baseline: **115 tests passed in 8.347 seconds**, with a private source SHA-256 inventory. Present-but-not-printed configuration checks found no `AI_API_KEY`, `AI_MODEL`, `DATABASE_URL` or `SMTP_HOST` in the audit environment. No live integrations were invented or attempted with another credential.

| Priority | Confirmed finding | Implemented repair / source |
|---|---|---|
| P0 | Sensitive PDFs were accepted without malware scanning | `app/marketplace.py`, supplier template/page and `web/market.js`: reject new document bodies, remove file selection, explain disabled acceptance. Existing authenticated attachment access remains. No pretend scanner or unsafe enable flag. |
| P0 | Queued verification messages could contain consumed/expired links | `app/mail_policy.py`, `app/suppliers.py`: check token validity and suspension before SMTP, clear obsolete bodies, retain explicit private mail states. Consumption still independently validates tokens. |
| P0 | SMTP enablement and serverless worker operation were insufficiently explicit | Default-off `MAIL_DELIVERY_ENABLED`; protected one-job `/api/jobs/mail` GET/POST, 32+ character bearer secret, durable claim/retry state, TLS, eight-second socket-operation timeouts, 60/hour allowance. Rate rejection no longer burns delivery attempts. No scheduler activated. |
| P0 | Resource/storage limits did not bound several persistent datasets or image concurrency | `app/controls.py`: serialized account/product/image/inquiry/outbox checks, report ceiling, 10,000 rate-bucket ceiling, image-processing leases; registration body reduced after document removal. Full owner-mail queue retains inquiry + notification intent instead of rolling back the submission. |
| P0 | Public model tool arguments could silently imply confirmed buyer requirements | `app/agent.py`: public model-generated tool calls cannot execute catalog matching; explicit qualification form required. Private research behavior remains. No extra model pass can invent tool results. |
| P1 | Shared admin password and no MFA/revocation boundary | `app/admin_auth.py`, supplier auth and admin UI: environment-provisioned named accounts, PBKDF2 verification, production-required TOTP, replay prevention, credential-version session checks, disable/remove/rotate revocation and protected session-revocation endpoint. Non-production legacy compatibility is explicit. |
| P1 | No account suspension or public reporting | `app/controls.py`, marketplace/server and UI: private reports/review, reasoned suspension, session/token revocation, listing hiding. Restoration never republishes removed listings. Email verification still automatically publishes normal accounts. |
| P1 | No usable retention/rights implementation | `app/maintenance.py`, `web/operations.js`: private export/correction/guarded erasure, own-supplier export, default-dry-run configurable retention, environment confirmation, separate approval switches and in-flight-mail deletion interlock. No real data processed. |
| P1 | Unverified contact/domain assumptions, weak environment isolation checks | `app/settings.py`, privacy/SEO/backend links and generated templates: configured origins/booking, no published contact email without explicit verification, no Host-derived email links, environment binding assertions, production cookie/frame checks and no platform-environment downgrade. Actual database-project identity still requires owner verification. |
| P1 | Marketplace silently truncated public browsing to the latest 2,000; admin registry only 25 | SQL-filtered public count/pagination over all eligible listings; escaped literal wildcards; 25-row manager pagination. SQLite Unicode lowercase restores Greek case-insensitive search. The separate research matcher remains bounded and is disclosed below. |
| P1 | Health endpoint reported configuration instead of actual database access; unsupported methods returned HTML | `app/server.py`: database probe with safe JSON 503 on failure, explicit provider/mail `not_probed`, JSON unsupported-method errors, HEAD handling. Unknown API routes retain JSON errors. No production-404 root-cause claim. |
| P2 | Withdrawn products consumed the entire 50-listing quota | Separate 50-active / 500-retained limits with explicit error text. Storage ceilings still apply. |
| P2 | No aggregate AI operational outcomes | `app/public_ai.py`: daily success/failure/elapsed totals and bounded provider-reported token usage; authenticated metrics endpoint. No transcripts or billing estimates stored. |
| P2 | Frontend/template source could drift from generated output | Updated source templates, generated pages and generator; regeneration verified byte-identical. Existing black/blue design, full-screen AI, supplier popup and dedicated Marketplace retained. |
| P2 | Indexing could be enabled before explicit launch acknowledgment | Production-only indexing plus three independent explicit flags; private routes remain noindex. |

Additive **migration 005** introduces resource locks, processing leases, suspension controls, security events, listing reports, mail metadata, named-admin session metadata/TOTP counters and AI aggregates. All new private tables receive RLS and client-role revokes. Existing migrations/data are not replaced.

Additional touched subsystems: `app/catalog.py` environment guard; `app/intake.py` capacity/recoverable notification state; `app/privacy.py` configured contact/URL policy; source-release allowlist; `.env.example`; README/start/deployment/key handoff links; unit/PostgreSQL/browser suites. `OPERATIONS-HANDOFF.md` specifies operator procedures.

## B — Fresh verification, failures investigated and limits

### Commands and results on the final application code

| Command | Actual result |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -v` | **137 PASS** on final code (timing in packaged log). Baseline 115 + 22 new hardening tests. A concurrent-check run also passed 137 in 12.417 s. |
| `PYTHONPATH=.:tests .venv/bin/python tests/postgres_integration.py` | **PASS, 10 printed integration groups**, real ephemeral PostgreSQL. Migrations 001–005 applied and reapplied; concurrent registration/verification/inquiry/mail recovery/budget checks; RLS/client-role tests including all new tables; processing leases, search escaping, suspension/restoration and privacy erasure on synthetic data. |
| `node tests/browser.cjs` | **PASS**: actual local registration/token confirmation/publication, images, privacy projection, account withdrawal/new product, report submission/admin triage, suspension/session revocation, modal/mobile navigation and no JS exceptions. AI answers mocked. |
| `node tests/audit_browser.cjs` | **PASS**: inquiry loss/retry persistence and manager status, mocked AI failure/history/literal rendering/handoff/timeout; 11 routes, 14 internal link targets, 320/390/768/1440/1920 widths, navigation and no JS exceptions. |
| Axe in the audit browser suite | **0 findings** for tested WCAG 2 A/AA and 2.1 AA rules/states. Suite now explicitly fails on findings. This is not universal/manual accessibility certification. |
| `.venv/bin/python -m compileall -q app api scripts tests`; `node --check` for all web JS/test CJS; `git diff --check` | **PASS**. |
| `python scripts/create_pages.py` with before/after hashes | Generated public pages **byte-identical** on regeneration. |
| `.venv/bin/python -m pip check` | **No broken requirements.** |
| `.venv/bin/python -m pip_audit -r requirements.txt --vulnerability-service pypi --format=json --output private/hardening-audit/pip-audit.json` | **No known vulnerabilities** in resolved runtime graph: psycopg 3.2.10, Pillow 12.3.0, psycopg-binary 3.2.10, typing-extensions 4.16.0. PyPI service snapshot, not a guarantee or host-runtime audit. |
| `.venv/bin/python -m bandit -r app api scripts -f json -o private/hardening-audit/bandit.json` | **6 retained findings: 5 medium, 1 low; none high.** Investigations below; no blind suppression or false “clean” claim. |

Local Chromium measurements, one navigation sample per route: **DOMContentLoaded 22–45 ms, median 38 ms**; HTML navigation transfer **4,145–11,532 bytes**. These are local observations, not network-mobile performance, load capacity, Core Web Vitals or a production SLA. No load/soak test or hosting bill test was conducted.

New regression boundaries include unscanned upload denial, expired/consumed mail suppression, suspension/revocation/restoration, atomic storage limits, report review, named MFA replay/disable, export/erasure/retention guards, health errors, JSON methods, trusted settings, worker authentication, >2,000-product browsing, admin pagination, Unicode search, no inferred AI match, in-flight-mail deletion denial, image leases, indexing gates, private metrics and inquiry survival when the mail queue is full.

Test changes to old fixtures are intentional contract updates, not weakened assertions: new registration fixtures no longer upload prohibited PDFs; rejection has its own test; SMTP mock tests explicitly opt into delivery; indexing tests provide the new approval flags; unverified contact email is now expected to be blocked. Duplicate inherited fixture test discovery was removed so the count is not artificially inflated.

### Findings from the static scan

- **B608 / medium, `app/intake.py`**: query chooses only a constant optional status clause; status/offset are bound parameters. Reviewed, no user SQL interpolation.
- **B608 / medium, `app/maintenance.py`**: document predicate selects one of two fixed database-dialect strings; threshold is bound. Reviewed, not a caller-provided predicate.
- **Two B608 / medium, `app/marketplace.py`**: count/page SQL assembles allowlisted JSON field expressions and fixed clauses; query/category/offset use bound parameters, LIKE wildcards escaped. SQLite tests include literal `%`, and PostgreSQL integration tests cover escaping.
- **B104 / medium, `app/server.py`**: explicit `0.0.0.0` local-preview listener, necessary for Arena proxy access. Do not expose this development server directly to the public internet without a controlled hosting layer.
- **B110 / low, `app/server.py`**: best-effort immediate mail attempt cannot invalidate an already saved registration; durable worker/status handling is the recovery route. Provider exceptions/contents are intentionally not leaked into public responses/logs.

The scan is therefore **reviewed with retained findings**, not zero findings. Its exit status is expected to be non-zero.

### Failures actually encountered

Initial edits introduced an SQL-string quoting syntax error; import/test failures exposed it and it was repaired. A HEAD-aware response change accessed an absent `command` on a synthetic handler; the existing disconnect regression caught it and the adapter was corrected. New tests initially inherited/discovered old tests twice; fixture reuse was corrected. Subsequent full suites passed. Browser quotas were not weakened to obtain a pass; only an old synthetic fixture was archived before this audit's browser runs. No real/preview data was deleted to reset tests.

Evidence is under `private/hardening-audit/`; only reviewed synthetic logs are allowlisted into the source ZIP. Provider/SMTP calls in automated tests are **mocks**. Actual local HTTP/SQLite/PostgreSQL/browser operations are **real isolated tests**. No live AI language score, actual email receipt, public-domain response or deployed Vercel artifact is represented by those results.

## C — Known unresolved defects, limitations and next actions

| Severity | Remaining issue | Next action |
|---|---|---|
| **P0 launch** | Actual deployed source/build/API 404/provider root cause unknown; sandbox cannot reach production/provider/mail/booking hosts, and no authorized service configuration exists | Owner reconciles live source/build/logs and environment with this reconstruction, then authorizes staging/live smoke tests. Do not call this a production-404 fix. |
| **P0 launch** | No confirmed controller/legal identity, lawful bases, processor/transfer arrangements, verified rights contact or approved retention/backup policy | Complete professional/operator review and accurate disclosures before indexing or accepting unnecessary real data. |
| **P0 launch** | Live provider behavior/quality, costs and inbox delivery not validated; scheduled worker not installed | Approve configured service tests, actual inbox checks and scheduler monitoring. Set provider-native budgets/alerts; do not rely on request count as euros. |
| **P1** | Environment binding is an assertion, not independent database identity verification; runtime least privilege/backup restore are not proven on the actual host | Separate projects/credentials, verify target IDs, provision a runtime role, run the documented restore/rollback rehearsal before migration. |
| **P1** | TOTP enrollment/recovery and fine-grained admin roles are not a full management product; named admins currently have full manager rights | Use controlled offline provisioning/recovery; restrict who receives manager access. Consider scoped roles before adding non-owner staff. |
| **P1** | No automatic image text/logo detection; previously stored PDFs remain unscanned | Keep new PDFs disabled; use isolated authorized viewing and human photo moderation. Implement actual scanning/quarantine before enabling sensitive documents. |
| **P1** | Whole-host connection/bandwidth/CPU spend, distributed abuse, model prompt behavior and semantic private-name leakage cannot be guaranteed by application quotas/regex | Host-approved edge protections, monitoring, real adversarial multilingual tests and provider budget controls. Do not treat safe rendering as semantic correctness. |
| **P1** | SMTP is at-least-once; uncertain acceptance can duplicate a message; eight-second timeout is per socket operation, not total invocation | Monitor/reconcile worker state, use a suitable host execution window and provider features if authorized. Never claim exactly-once delivery or inbox receipt. |
| **P1** | Backups, sent email and external provider records are outside automatic erasure; retention has not been scheduled or legally approved | Approve identity verification, legal holds, restricted erasure ledger, backup expiry/destruction and restored-data deletion replay. |
| **P2** | Separate research matcher still uses up to 2,000 recent Marketplace candidates and a bounded private set | Scope is disclosed in the handoff; implement indexed/query-aware matching if exhaustive retrieval is required. Public browsing is no longer truncated. |
| **P2** | Supplier own history remains a bounded 500-row view; legacy application/research admin views retain earlier bounds | Current limits are acceptable for a controlled preview, not unlimited-scale admin operations. Add dedicated paging when those historical datasets warrant it. |
| **P2** | Correction supports selected private fields, not email ownership reassignment or complete public-product editing; exports omit image/PDF binaries | Use verified human handling and existing authorized retrieval/withdrawal/relisting; implement explicit re-verification/versioned editing if needed. |
| **P2** | Metrics are aggregates, not billing-grade; token counts depend on provider usage fields; no host alerting or soak testing | Wire approved monitoring and compare with actual provider bills/host limits before promotion. |
| **P2** | Browser abort does not cancel an already-running provider request; free-text model output is not guaranteed factual | Present no charge-cancellation guarantee; retain bounded server calls, quotas and human verification. |
| **P3** | Local performance/accessibility evidence covers selected states, not every assistive technology or production network | Manual keyboard/screen-reader and real-network checks before launch; repeat with real content. |

No claim is made that every possible repository defect has been found. Remaining service/legal/configuration work is not hidden behind local PASS results.

## D — Owner-only configuration and approvals

Do **not** send secrets in chat. Configure privately: verified canonical/public origin and contact choice; isolated database/project and runtime role; named admins/TOTP/recovery custodians; provider key/model/base/options/native budget; authorized SMTP sender/recipient and worker secret/scheduler; approved retention values and backup/deletion process; legal/controller/processor notices. Keep indexing, mail delivery, retention apply and rights erasure off until their independent approvals. Keep paid discovery opt-in. No new subscription, analytics or legal fact was invented.

The absent local provider/mail configuration is a testing limitation, **not evidence that production lacks it**. The supplied apex and booking URL are defaults from prior instructions, not freshly verified live ownership/routing.

## E — Staging, migration, worker, backup, rollback and promotion

Use **`OPERATIONS-HANDOFF.md`** as the step-by-step runbook. It covers: source reconciliation; verified backup; isolated restoration; ordered rerunnable migrations 001–005; role verification; environment settings; noindex staging; named-admin recovery; worker authorization/leases/retry/throughput; dry-run-first retention; explicit erasure safeguards; preserved-write rollback and restored-backup deletion replay.

Promotion requires explicit authorization after: actual live-domain/route checks, staging health/schema and access control, approved multilingual/provider tests, authorized mail acceptance/inbox tests, scheduler/restart monitoring, quota/alert checks, backup/restore rehearsal, verified disclosures and a reviewed rollback plan. **Do not run production migrations or replace the live site merely because the ZIP is available.**

## F — Contradiction register

| Earlier statement/assumption | Current authoritative position |
|---|---|
| Source was the original production site | It is reconstructed source; deployment equivalence is unverified. |
| Earlier report/package PASS means current code is approved | Historical evidence is version-specific; this audit reran checks and still denies launch approval. |
| Manager approval / 1–3-day wait publishes new suppliers | Superseded: email verification automatically publishes. Legacy account approval is a separate old workflow. |
| No verification is needed to publish | Incorrect: unconfirmed accounts remain invisible. |
| Optional PDFs are accepted | Superseded by the latest security requirement: new PDF uploads are blocked. Legacy documents remain restricted. |
| Email-confirmed means business/certification verified | Incorrect. All such claims remain supplier-provided until independently evidenced. |
| Queue success / SMTP success means inbox receipt | Incorrect. Saved record, queued job, SMTP acceptance and receipt are distinct. |
| “Exactly once” inquiry retry implies exactly-once mail | Incorrect. Keyed inquiry/job creation is idempotent; SMTP is at least once. |
| Health means AI/mail/DB are all ready | Health probes DB only; AI/mail are explicitly not probed. |
| Apex, www, `.store`, `.co` and old email are interchangeable verified identities | Not established. Central trusted configuration selects public origins; no old email is published without explicit verification. No DNS change made. |
| Choosing a booking link sends an inquiry or contacts staff | Incorrect. Booking navigation does not create an inquiry; the actual inquiry form persists a record and notification intent. |
| Public AI needs an access token/password | Incorrect. Anonymous AI remains public, subject to configuration and quotas. |
| A model's inferred qualification is confirmed buyer intent | Incorrect. Public lookup now requires the explicit qualification form. |
| Public AI performs live discovery / supplier introductions / orders | Incorrect. Private discovery is separate and opt-in. No introduction/order/payment/contract is created. |
| Every Marketplace product is searched by the research matcher | Incorrect. Public browsing is fully paginated; research matching remains a disclosed bounded candidate search. |
| Fifty withdrawn products permanently prevent listing | Superseded: 50 active and 500 retained records are separate limits. |
| Shared manager password is sufficient production authentication | Superseded: named admin + TOTP required in production. Legacy login only non-production. |
| Retention tooling means a lawful deletion schedule exists | Incorrect. Policy periods, execution, backup handling and legal approval remain unconfigured/owner-controlled. |
| Supplier restoration republishes all prior products | Incorrect. Hidden/withdrawn listings stay hidden/withdrawn. |
| Daily AI call count is a euro spending ceiling | Incorrect. Provider budgets/billing remain separate. |
| Mocked multilingual/browser tests prove live model quality | Incorrect. They prove local contracts, not live-language/provider reliability. |
| No scanner findings / no vulnerabilities means secure or GDPR-compliant | Incorrect. Six reviewed Bandit findings remain; dependency advisories and local tests are limited evidence, not certification. |

Earlier reports and instructions remain in the package for provenance; current report/runbook and current code take precedence for the changed boundaries.

## G — Risk assessment and deliverables

- **Repository:** meaningful P0/P1 hardening implemented; current local regression evidence is positive; scoped limitations remain above.
- **Local preview:** same branding and core flows retained, no synthetic public catalog required. Provider/mail remain honestly disconnected. Preview behavior is not deployed-site evidence.
- **Live integrations/deployment:** unverified and not modified. Local success cannot establish domain configuration, production privileges, billing, inbox receipt or legal readiness.
- **Recommendation:** do not promote to production yet. Proceed with authorized isolated staging and owner approvals, using the runbook.

Deliverables: this A–G report, `OPERATIONS-HANDOFF.md`, updated source/tests/additive migration, and a normal source ZIP from the release allowlist. Private databases, credentials, documents, screenshots, development dependencies and private configuration are excluded. ZIP contents and extracted-source tests are checked separately; final archive hash/size are supplied with delivery rather than embedded recursively into the archive.
