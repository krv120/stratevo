# STRATEVO — production-readiness audit and repair

**Date:** 12 October 2026
**Result:** Repository repairs implemented and locally validated. **Not approved for production launch.** Live provider, inbox, hosting/domain and legal readiness checks remain blocked or incomplete.
**Scope:** Existing Python/vanilla-JavaScript project, not a replacement site. Black/blue screenshot-derived identity retained.
**Baseline:** `4195a46fadffb4d818a045d1c9213c35bb273a2e` on `arena/40bf7fdf-stratevo`; 101 baseline unit/HTTP tests passed. A SHA-256 inventory of the 57 original source/assets/test files was saved privately before edits. No production data was accessed or overwritten.

## A. Initial findings and actual causes

| Priority | Finding | Evidence / cause | Disposition |
|---|---|---|---|
| P0 launch blocker | Live AI failure cannot be diagnosed completely here | No local `AI_API_KEY`, `AI_MODEL`, database hosting or SMTP configuration. Sandbox outbound hosts exclude `stratevo.online`, Gemini, SMTP and booking services. No hosted logs or environment access. | Precise external blocker retained; do not confuse local configuration absence with the production root cause. |
| P0 launch blocker | Incomplete privacy/operator operating arrangements | No confirmed full controller identity, retention/deletion policy, processor/transfer list or verified rights-contact process. | Honest privacy and scope pages added; legal/operational approval still required. |
| P1 | No durable customer lead journey | No customer table, form endpoint or private customer inbox; chat offered booking links only. | Added separate sourcing-inquiry workflow, explicit AI handoff and authenticated inbox. |
| P1 | No supplier/customer owner notification workflow | Supplier signup queued only an applicant verification email; no persistent owner-notification entity. | Added transactional notification intents, outbox integration, missing-configuration recovery and manager retry controls. |
| P1 | Supplier review and customer work were not separate operational views | Only legacy application review and a product registry existed. | Customer inquiry statuses and supplier review statuses added without mixing records or requiring publication approval. |
| P2 | Supplier form imposed unnecessary friction | License and messaging contact were compulsory; city was absent. | City required; messaging, license number/PDF and advertised MOQ optional under the latest brief. Optional uploads still validated when provided. |
| P2 | Chat retry/new-chat experience incomplete | Failed retry appended another identical user bubble; no explicit retry control; new-chat left restored text in the input. | Fixed and browser-tested. |
| P2 | Legacy/admin request helper could wait indefinitely | No client abort timeout in `site.js`. | Bounded requests and safe non-JSON/timeout errors added. |
| P2 | Client disconnect caused noisy second-response exceptions | Server logs during fast browser navigation showed BrokenPipe/connection reset when responding to an already closed socket. | Catch only transport disconnects at the write boundary; do not send a second error response. Regression test added. |
| P2 | Category CTA context lost | Modal URL construction dropped query parameters; chat did not consume category intent. | Query preserved; safe allowlisted category prompts added without overwriting unsent input. |
| P3 | Positioning unclear | Hero did not explain China sourcing or intended small-business audience. | Rewritten in place; working inquiry CTA and clear next steps added. No fabricated metrics/testimonials. |
| P3 | SEO/indexing gaps | Shared generic description, no canonical/OG metadata, robots/sitemap or explicit private-page noindex. | Route-specific metadata, environment-controlled canonical/indexability, robots/sitemap and private noindex implemented. |
| P3 | Unnecessary downloads | Every page loaded account/market scripts; static assets all used `no-store`. | Page-specific scripts and ETag revalidation added; fonts cache for one day. Private data stays no-store. |

### Reported “Are you a supplier?” failure

The preserved branch already contained a real `/supplier` route and native dialog trigger from the previous repair. In this audit's Chromium runs, mouse/mobile navigation, direct access, form submission and confirmation worked. **The reported dead production button was not reproduced in this branch.** It may involve deployment drift, missing scripts or a production runtime issue, but those explanations are not established facts. No live-domain repair is claimed.

### What was inspected

Entry points (`app/server.py`, `api/index.py`), Vercel rewrite/bundle configuration, all page templates/generated routes, shared navigation/footer/dialog scripts, forms and chat state, all backend modules and their security/data boundaries, schema/migrations, environment references, dependencies, test suites, deployment and packaging paths. Particular attention went to catalog/import projections, matching qualification, live-discovery separation, private file retrieval, sessions, outbox leases and RLS. The existing font license and self-hosted assets were retained. No analytics or advertising integration was found or added.

The review is not a penetration-test certification, exhaustive line/path coverage, production crawl, legal opinion or guarantee of no undiscovered defects.

## B. Changes implemented

### 1. Customer sourcing inquiry and conversion path

- New `/inquiry` page and `POST /api/inquiries`.
- Required: name, email, product, requirement details, estimated quantity/unit (or explicitly undecided), destination and privacy acknowledgment. Optional: business, additional contact, budget and timeline.
- Server-side limits, email validation, honeypot, global/per-connection throttles, control-character checks and recognizable API/private-key rejection.
- Random submission key, hashed storage and payload fingerprint: retries of the **same keyed payload** return the same record; changed payload with the same key returns conflict. This is not a global deduplication guarantee across independent forms/new keys.
- Atomic record + notification-intent save. A database error cannot produce a fake success. A saved record survives email problems.
- Browser preserves the failed attempt in page memory; an ambiguous network failure can be retried safely. If details are changed during uncertainty, a restore action recovers the submitted payload before retry. No full inquiry is placed in browser persistent storage.
- Honest success reference and follow-up expectations. No invented response deadline, guaranteed result, payment or marketing enrollment.

### 2. AI integration and handoff

Kept the existing provider-compatible integration, including the configured Gemini-compatible path when deployed. No provider replacement or secret hardcoding.

Request trace: `web/app.js` → same-origin `/api/chat` → bounded history validation → durable quotas/concurrency reservation → `app.agent.reply` → server-only bearer-authenticated HTTPS `.../chat/completions` → bounded JSON response → source/privacy boundary → browser `textContent` rendering. The transport is explicitly non-streaming. Provider requests have a 25-second timeout; the browser has a 60-second recovery timeout. One model request is made per response; tool matches are rendered deterministically rather than followed by another model invention opportunity.

The updated instructions ask relevant questions sequentially about specifications, quantity/MOQ, budget/quality, customization, packaging, destination/shipping and timeline. They require separating user facts, general advice, unverified evidence and verified information. Before handoff the assistant is instructed to summarize actual facts and unknowns. **Its live language/qualification quality has not been measured here.**

The visible inquiry action copies only the user's own chat messages, not AI-generated assertions, into an explicitly requested, capped temporary same-tab draft. The user reviews and edits the form. Contact details are collected in that private form, not required in chat. Chat itself cannot save a lead or claim it notified the team.

Added retry control, duplicate-bubble prevention, reliable new-chat reset, category context and clearer output-limit misconfiguration handling. Safe rendering, public quotas, qualification before matching, maximum three anonymized leads, private sources and no public live-discovery invocation remain intact.

### 3. Supplier journey

Working accessible modal plus direct `/supplier` fallback retained. Required city and clear field indicators added; optional contact/document/MOQ friction removed. There is no approval requirement for product publication: the previously confirmed **email verification → automatic publication** policy remains.

An internal supplier review status (`new`, `contacted`, `reviewed`, `declined`) now supports staff assessment and follow-up independently of publication. **Declining internal review does not automatically hide products**; use the separate removal action when appropriate. Submission never guarantees commercial approval or business. Company identity, contacts and license remain private; public product data and existing photo protections are preserved.

### 4. Persistence and notifications

Additive migration `004_private_inquiries.sql` creates:

- `customer_inquiries`: ID, timestamp, status, validated private payload, consent version, unique submission-key digest and payload digest.
- `supplier_reviews`: account-bound internal review status/time.
- `notification_jobs`: unique entity-specific notification intent and optional outbox reference.

Existing tables/data are not replaced. New tables reside in `stratevo_private`, have RLS enabled and deny Supabase client roles. The application—not a public database client—projects public products.

`NOTIFICATION_EMAIL` selects the verified owner destination, separately from SMTP `MAIL_FROM`. Owner emails include record reference, limited context and the protected admin link; they do not include entire conversations, licenses or customer contact fields. Missing notification configuration leaves a persistent recoverable job. The existing mail worker queues waiting jobs once configuration exists and uses STARTTLS to send outbox entries.

Owner notification statuses distinguish awaiting configuration, queued, retry pending, exhausted attempts and SMTP acceptance. Manager retry resets exhausted **owner alerts only**, not expired applicant access links. SMTP remains **at-least-once** delivery: a transport/database interruption can cause a duplicate email even though record and job creation are idempotent. SMTP acceptance is never presented as inbox receipt.

### 5. Private operations, trust and security

- `/admin` now includes a customer inbox with status filtering/pagination and updates, source/consent details, notification overview and retry action. Supplier review stays in the supplier registry.
- Private routes require server-side manager authentication; supplier accounts remain owner-bound.
- Email validation tightened against display-name/header-like input and malformed local parts.
- Default same-origin `frame-ancestors` protection; explicit `ALLOW_PREVIEW_EMBEDDING=true` only for Arena preview embedding. Permissions-Policy disables camera, microphone and geolocation.
- No public access to inquiries, private profiles, documents or notification jobs; no raw exception/key output added.
- `/privacy` and `/terms` state actual service/data flows and unfinished legal requirements, rather than falsely asserting GDPR compliance or complete commercial terms.

### 6. SEO, performance and design

China sourcing/small-business positioning, clearer inquiry CTAs and next-step copy were implemented without replacing the design. Responsive forms, focus styles, semantic labels and status announcements were added.

Canonical/OG metadata, distinct descriptions, one primary heading per tested page, `/robots.txt`, `/sitemap.xml`, default preview noindex and private-page noindex were implemented. `CANONICAL_BASE_URL` defaults to the owner-supplied `https://stratevo.online`, **not a verified redirect observation**. Indexing stays off until explicitly enabled. AI/inquiry form routes remain noindex even when informational pages become indexable. No fake Organization address, reviews, ratings or product offers were added as structured data; business/legal structured data is deferred until disclosures are confirmed.

Page-specific JavaScript and static ETag/font caching reduce unnecessary transfers. No production Lighthouse/Core Web Vitals or ranking claim is made. Local navigation timings are recorded as test-environment observations only.

## C. Executed tests and evidence

Final local results: **115 Python unit/HTTP tests passed**, real ephemeral PostgreSQL tests passed, both Chromium suites passed, and no violations were reported by axe for the selected WCAG 2 A/AA and 2.1 AA rules in the 11 tested page states.

| Critical test | Result | Evidence / limitation |
|---|---|---|
| A: public chat request reaches backend; absent configuration reported honestly | PASS locally | Real browser request returns the backend's explicit unavailable state; no fake answer. |
| A: genuine configured provider answer and sourcing follow-up | **BLOCKED** | No hosted secrets/provider-host access. Mocked answers are not counted as genuine provider responses. |
| A: history, empty input, Enter, retry and duplicate protection | PASS | Chromium capture of requests/history; failed attempt then retry; one user bubble; follow-up retains context. |
| A: provider/network error and timeout recovery | PASS with injected failures | Unit transport errors; browser transient response injection; actual abort timer tested with browser clock advanced. UI recovers. |
| A: source privacy, safe rendering, qualification, no invented tool matches | PASS deterministic boundaries | Unit tests and literal HTML-like response rendering; live free-text factual quality remains unverified. |
| A: contact-free AI-to-form handoff | PASS | Only actual user messages copied; model text absent; draft removed on form read; review required. |
| B: valid customer inquiry saved exactly once per key | PASS | Real isolated SQLite submission; record inspected; duplicate response-loss retry; PostgreSQL concurrent retry test. |
| B: notification job/outbox created once per record | PASS | Actual database assertions; no customer-contact data in owner message. Actual SMTP inbox delivery blocked. |
| B: invalid/missing input, spam, changed-payload conflict | PASS | Unit/HTTP assertions; no invalid record saved. |
| B: database failure and mail failure after save | PASS with injected failures | Transaction rollback on queue/database error; failed SMTP preserves record and supports later retry. |
| B: private inbox authorization and filtering/status changes | PASS | Anonymous 401; authenticated browser update; persisted status inspected. |
| C: supplier modal, direct route, validation and real registration | PASS locally | Desktop/mobile browser and HTTP tests; required city; optional contacts/document/MOQ accepted in unit tests. |
| C: supplier/customer separation, owner notification and duplicate protection | PASS | Distinct tables/entity types; one supplier account/owner job; no customer inquiry created. |
| C: email confirmation, publication, ownership, photo privacy and removal | PASS local outbox + HTTP | One-time test token read from isolated outbox, not a real email; ownership and private projection tests retained. |
| C: real verification email reaches inbox | **BLOCKED** | No SMTP credentials, verified sender/mailbox or externally running mail worker. |
| D: navigation, direct routes/refresh, back/forward, category context | PASS tested routes | 11 pages, 14 distinct internal link targets; original Marketplace/account/moderation paths preserved. External booking/mail links not exercised against remote services. |
| E: responsive layout and mobile core flows | PASS Chromium | 320, 390, 768, 1440 and 1920px audit; prior suite also covers 1568px; no horizontal overflow. |
| E: automated accessibility, focus/Escape and reduced motion | PASS tested states | axe results empty; native dialog behavior, explicit focus, mobile navigation and reduced motion checked. Physical devices/assistive technology not tested. |
| F: unit/HTTP and extracted package suite | PASS | 115 tests; see packaged validation log and release verification. |
| F: PostgreSQL migration/idempotency/concurrency/RLS | PASS real PostgreSQL | All four migrations plus atomic notification recovery and client-role/RLS checks; not the production database. |
| F: syntax and whitespace | PASS | Python compileall, `node --check` for web/test JS, `git diff --check`. No TypeScript/build framework exists to type-check. |
| F: browser JS exceptions | PASS | None in completed critical suites. Deliberately injected failed API/network calls are expected test events. |
| F: static security scan | REVIEWED | Bandit: two medium, one low; no high findings. See below. Not a penetration test. |
| F: dependency advisory check | LIMITED PASS | PyPI release metadata reported zero vulnerabilities for pinned Pillow 12.3.0 and psycopg 3.2.10. Not a comprehensive transitive-dependency audit. |
| Live DNS/redirects, hosting bundle/runtime and external links | **BLOCKED** | Domain/provider/booking hosts unavailable under this environment's network restrictions. |

### Scanner findings retained, not hidden

- B608, medium: inquiry SQL composes only fixed application-owned clauses; all user values use bound parameters. No user SQL concatenation was found.
- B104, medium: intentional `0.0.0.0` binding required for Arena preview. Use the hosting adapter/production service, not an exposed development server, in production.
- B110, low: synchronous applicant mail attempt catches transport failure because saved/queued state must survive and provider details must not leak. The durable outbox tracks retries; operational monitoring is still required.

Repeated browser runs eventually exercised the real per-address hourly inquiry limit and received HTTP 429. The final run used a fresh isolated test database after archiving the previous fixture; application limits were not disabled or increased. No test was removed to achieve a pass. Existing fixture assertions changed only for intentional requirements: new city, optional messaging/documents and revised business copy. A browser image assertion was repaired to await decoding of the exact newly published photo rather than race the first image on the page.

### Evidence and reproducibility

`tests/test_intake.py`, `tests/test_marketplace.py`, the existing regression suites, `tests/postgres_integration.py`, `tests/browser.cjs`, and `tests/audit_browser.cjs` are included. Reviewed logs appear in the source ZIP's `validation/` directory, including accessibility and local navigation timing JSON. Test records are synthetic and confined to isolated private databases; none were seeded into the public preview.

The work used inspection, baseline tests, implementation, failure investigation, correction and repeated regression runs. No three-hour-duration claim is made; no time was spent waiting to satisfy a timer.

## D. Remaining requirements and risks

1. **Production root cause remains unconfirmed.** Inspect the actual deployment's `/api/agent/status`, manager connection test, server errors and configured model/key permissions. Local code success cannot prove the deployed build is current or billing/model access valid.
2. **Genuine model quality remains untested.** Run the requested packaging prompt, follow-up, Greek/Greeklish cases and adversarial/privacy cases against the real provider. Prompt instructions cannot guarantee all free-text answers are factually correct or anonymous.
3. **Real notification/verification delivery remains untested.** Verify mailbox ownership, SMTP sender/SPF/DKIM/DMARC, retry worker execution, bounce handling and actual inbox receipt. A correctly queued job is not delivery.
4. **Legal/privacy launch blockers:** confirm full controller identity/contact, lawful bases, subprocessors/international transfers, retention/deletion/backups and data-subject request procedures. Do not treat the published preview notices as full compliance.
5. **Security/operations:** license PDFs are signature/size checked but not malware-scanned; optional image rewriting does not detect visible logos/contacts. Add scanning/quarantine or omit uploads for public launch; strengthen moderation/report handling, edge abuse controls, storage quotas and pending-record cleanup. No automatic deletion schedule or comprehensive supplier suspension system is claimed.
6. **Abuse/cost:** shared durable AI request/concurrency caps are not a monetary billing cap. Connection-address throttles can group users behind proxies. Set provider spend limits and trusted edge controls; no CAPTCHA or paid anti-bot service was introduced.
7. **Account administration:** existing PBKDF2/HttpOnly session authentication is retained; production MFA, named-manager audit identity, recovery and session-management improvements remain advisable. Runtime database permissions should be minimized with the chosen host's deployment roles.
8. **Scope limits retained:** small-catalog search examines the latest 2,000 published products; supplier registry shows the latest 25 accounts; a supplier account's existing 50-listing cap includes withdrawn listings. This is not an unlimited marketplace.
9. **No conversion uplift or SEO score verified.** No tracking was added without a consent/measurement plan. Lead counts/statuses provide operational visibility, not a measured conversion-rate improvement.

### Acceptance checklist

Criteria 1, 4, 6–8, 10–12 and 14–16 are supported **within the repository/local-test scope**. Criterion 2 has a precise external blocker, not a confirmed hosted cause. Criterion 3 (genuine provider answers) and criterion 9 (real email delivery) remain **BLOCKED**. Criterion 5 passes deterministic non-fabrication/privacy boundaries, but live-model behavior remains **BLOCKED**. Criterion 13 is addressed through implemented controls plus the explicit remaining security/privacy launch requirements above. **Overall production acceptance is incomplete.**

## E. Exact next steps, in priority order

1. **Staging database:** back up the existing database, install `requirements.txt`, and apply migrations 001–004 in order with the migration owner. New migration: `migrations/004_private_inquiries.sql`. Keep `stratevo_private` outside exposed API schemas. No destructive migration is required.
2. **Hosting secrets:** configure the existing provider, not a replacement. Set `AI_API_KEY`, `AI_MODEL` (an ID available to that key), and `AI_BASE_URL`. For the previously selected Gemini integration: `https://generativelanguage.googleapis.com/v1beta/openai`. Set an integer `AI_MAX_OUTPUT_TOKENS` and supported reasoning effort. Keep keys server-side; never paste them into chat. Redeploy staging, use `/admin` → **Test AI connection**, then test the exact packaging conversation and follow-up.
3. **Mail:** configure `SMTP_HOST`, `SMTP_PORT` (STARTTLS, commonly 587), `SMTP_USER`, `SMTP_PASSWORD`, authorized `MAIL_FROM`, and verified owner `NOTIFICATION_EMAIL`. Set `PUBLIC_BASE_URL` to staging's exact HTTPS origin. Schedule `python3 -m app.suppliers send-mail` with the same environment/database on a suitable worker. The manual private “Send next queued email” control is a diagnostic fallback, not a scheduler. Verify real inbox delivery for both journeys and retry recovery.
4. **Operational/security/legal approval:** finish the items in section D; set `ADMIN_PASSWORD_HASH` to a newly generated hash and retain `COOKIE_SECURE=true`. Keep `SITE_INDEXABLE=false` and retain the preview disclaimer until launch approval.
5. **Canonical/production promotion:** check the actual apex/www redirect, configure `CANONICAL_BASE_URL` consistently, retain `ALLOW_PREVIEW_EMBEDDING=false` in production, perform staging acceptance tests on physical devices, then use a separate authorized deployment/promotion workflow. Enable indexing only when appropriate.

## F. Deployment status

Updated code is saved on the existing Arena working branch, with a local preview and source ZIP. The audit does **not** push, merge, publish or deploy production. No production database migration or live-domain change was performed. Existing remote branch/PR content may therefore be older than this audit; the workspace/source ZIP is the audited version. The in-Arena preview has no real AI or SMTP secrets and honestly reports those unavailable connections.

## Research references

Official OWASP source documents were retrieved during the review:

- [Input validation](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/Input_Validation_Cheat_Sheet.md): server validation, bounds and allowlists.
- [REST security](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/REST_Security_Cheat_Sheet.md): authorization per endpoint, controlled methods/types and safe errors.
- [File uploads](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/File_Upload_Cheat_Sheet.md): restricted formats, private storage, re-encoding and remaining scanning/resource-limit requirements.

Earlier email-token, AI operations and native-dialog research is recorded in `PUBLIC-MARKETPLACE-UPDATE.md`. These are engineering references, not security or legal certifications.
