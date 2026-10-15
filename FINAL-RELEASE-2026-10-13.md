# STRATEVO — final website quality and release audit

**Release candidate: 2026.10.13-rc1 · 13 October 2026**
**Decision: reviewed local/staging candidate, NOT production approved.**

Read this report and `LIVE-SOURCE-COMPARISON-2026-10-13.md` before using older audit reports. Prior requirements remain in force. No production deployment, merge, DNS change, production migration, real-data deletion or email occurred. Archive identity and per-file checksums are in `MANIFEST.json`; the delivery message supplies the archive SHA-256/size.

## A. Evidence and actual live/source comparison

A fresh baseline passed **137 tests in 9.463 s**. A SHA-256 inventory of the initial working source was saved privately before edits. The actual branch is `arena/40bf7fdf-stratevo` in `krv120/stratevo`. At baseline, Git HEAD was the initial `6d4e00b` and the application existed as largely untracked restored files—not the earlier conversation's claimed commit history. The release manifest records the actual packaged source commit.

Live extracted content was retrieved through the web-fetch service. The homepage resolved to `https://www.stratevo.online/`; `/supplier` still describes manual approval, mandatory license/contact channels and a 1–3-day target. `/rfq` is a preview brief. `/inquiry`, `/robots.txt` and `/sitemap.xml` returned STRATEVO page-not-found **content** through that tool. `/marketplace` returned a demonstration title but only consent text was extracted. `/cookies` says no optional trackers are installed, yet public pages display Accept all/Reject/Manage controls. Live privacy describes materially different AI persistence, Supabase auth, uploads and retention from this source.

**Limit:** Python direct HTTPS and Chromium live navigation failed at the connection layer. No live raw head/source, responsive screenshot, cookie/network trace, true HTTP status/redirect chain or provider/mail operation is verified. The fetch service's `/ai` error does not establish a production API root cause. The engineer's missing-meta-description concern is **unconfirmed on production**; the local implementation has descriptions and now tests them on every public-content page. Source-level fixes cannot be called deployed fixes.

The route-by-route matrix, established discrepancies and unknown causes are in `LIVE-SOURCE-COMPARISON-2026-10-13.md`. Do not replace the live application or apply these SQL migrations to its unknown schema without reconciling both architectures and verifying backup/rollback.

## B. Changes implemented, not merely recommended

### Visual clarity and conversion

- Retained the black/blue identity, existing brand mark, full-screen AI, supplier dialog, Marketplace and booking destination. No fake factory photographs, suppliers, client logos, savings, testimonials or verification results.
- Homepage now explicitly communicates China sourcing/manufacturer evaluation, audience and value, with a primary assessment CTA, a structured brief/evidence visual, clearer value labels, compact process cards and less repetitive introductory copy. The useful AI/inquiry/booking routes remain.
- Added `web/quality.css`; responsive spacing/type/layout, visual hierarchy and quieter decoration. The homepage no longer relies on the old scroll-word animation to explain the service. New content introduces no animation.
- Added `/assessment`: product and quantity → specifications/customization/evidence → destination/budget/timing → review. Unknowns are labelled, not converted to invented facts. Contact details are requested only in the subsequent inquiry form.
- The explicit handoff stores the user's structured answers in same-tab storage with a ten-minute validity window, consumes them into editable inquiry fields, and never sends them to AI. Blocked storage exposes a copyable brief rather than losing the work. Expired/malformed drafts fail safely.
- Existing server-side inquiry validation/idempotency/private inbox/outbox behavior is preserved. `assessment` is an additional allowed source value; no database migration is required for this JSON payload value.
- Added a useful `/methodology` page: common specifications, quote inclusions, MOQ/unit caveats, evidence provenance, sample/quality checks, service boundaries and original FAQs. Its six-row fictional comparison has working commercial/evidence filters. Follow-up counts describe missing rows, **not supplier scores or recommendations**.

### SEO / SXO / GEO

- Ten public-content routes have unique page-specific titles/descriptions, one canonical, explicit robots metadata, OG/Twitter titles/descriptions/image, favicon and modest WebSite/WebPage JSON-LD. JSON-LD values are escaped; no address, review rating, Product offer, credentials or unsupported Organization/LocalBusiness facts were invented.
- Added an original text-only **1200×630** sharing image and brand SVG favicon; images are self-hosted. Essential methodology/comparison content is readable without JavaScript. New explanatory pages have breadcrumbs and meaningful internal links.
- Added useful public HTML 404 responses while retaining JSON API errors. `/rfq`, `/supplier-portal` and `/business-information` have safe navigation aliases; no legacy POST submission or auth migration is implied.
- Indexing remains deliberately gated by production/origin/launch approvals. Private/auth/admin/account/AI/inquiry routes remain noindex. Sitemap/robots include appropriate new pages only after approval.
- Added optional escaped homepage `GOOGLE_SITE_VERIFICATION` and `BING_SITE_VERIFICATION` tags. They are blank by default and do not establish ownership or indexing.
- Static CSS/JS support gzip negotiation and weak ETag revalidation with Vary. Private JSON, auth tokens, documents and HTML are not compressed by this application change and retain their existing no-store behavior.
- Researched current official Google AI-search/snippet and Business Profile guidance. No AI-specific files or SEO gimmicks were added. GBP eligibility is unproven; online-only operation would be ineligible. See `SEARCH-AND-MEASUREMENT-HANDOFF.md` for primary-source links and exact owner steps.

### Cookie/tracking decision and privacy-conscious measurement

- There was **no consent banner or optional tracker in this source to remove**. We did not claim to remove the different live build's banner. Added `/cookies` and updated privacy content to describe this application's actual sessions/drafts, limits and outstanding host/operator verification.
- Added local DOM conversion-stage hooks only: assessment started/reviewed, inquiry submitting/saved. They contain no identifiers or field values; no network collector, persistence, analytics vendor or advertising pixel is activated. There is no measured uplift or historical funnel dashboard to claim.
- Anonymous public browser checks found no initial cookies, localStorage, sessionStorage or unsolicited third-party requests. Requested draft storage is separately tested; essential authenticated sessions remain intact in existing journeys.
- No old live Supabase/consent/age-assurance keys were blindly deleted. Migration of those different live features requires source/hosting reconciliation and explicit operational approval.

### Existing security requirements retained

Named-admin production TOTP/revocation, CSRF/origin/session boundaries, private files/RLS, default-disabled sensitive uploads, suspension/reporting, automatic publication after email confirmation, atomic resource quotas, durable AI budgets, authentication-mail expiry, at-least-once notification handling, opt-in retention and guarded privacy operations remain. A final source review also found a P0 fallback defect: native forms without a method could place credentials or contact fields into a GET URL if scripts failed. Generated forms now explicitly use POST and explain the JavaScript requirement; the existing JSON-only routes reject unsupported native submissions rather than putting data in a URL. No provider/SMTP credentials were present for authorized live tests. There are no new runtime frameworks or analytics dependencies and no new migration beyond existing 001–005.

## C. Current tests and what they prove

| Check | Actual result / distinction |
|---|---|
| Fresh baseline | 137 PASS, 9.463 s |
| Final unit/HTTP suite | **149 PASS**, including all previous tests and 12 release-quality tests; timing is recorded in the final packaged log |
| Real isolated PostgreSQL | **10 PASS groups**: migrations 001–005 applied/reapplied; real concurrent operations, budgets, RLS/client-role denial, leases, suspension and privacy erasure on synthetic records |
| `tests/browser.cjs` | PASS: local supplier registration, test-outbox token confirmation/publication, private projection, images, withdrawal/addition, manager removal, reporting/suspension, responsive/modal/keyboard journeys; AI responses mocked |
| `tests/audit_browser.cjs` | PASS: real local inquiry persistence/ambiguous retry/private inbox, mocked AI history/error/timeout/handoff; 11 routes, 17 internal link targets, five viewport widths, no JS exceptions |
| `tests/release_browser.cjs` | PASS: seven public routes at 320/390/768/1440/1920 widths; assessment invalid/empty/unknown/back/keyboard states; reviewed handoff; expired/malformed/blocked-storage recovery; real lost-response inquiry retry; repeated-submit guard and 30-second abort recovery with deliberately stalled transport/advanced clock; local stage hooks; comparison/FAQ/offline/no-JS behavior |
| Axe | Zero findings in both tested rule/state matrices (WCAG 2 A/AA and 2.1 AA); assertions fail on findings. Not universal accessibility certification |
| Public request/storage inventory | No unsolicited external requests or initial anonymous cookies/localStorage/sessionStorage in measured journeys. Auth/draft storage deliberately retained |
| Metadata/assets | Unique descriptions, single canonicals, robots gates, parsed JSON-LD, no fabricated rating/address/offer fields, favicon, sharing image size, API/public 404 types, aliases, static compression and private JSON exclusion tested |
| Syntax/generation | Python compileall, JS syntax checks, diff whitespace checks; final generated pages must reproduce byte-identically |
| Dependencies | `pip check` passed; PyPI-backed `pip-audit -r requirements.txt` reported no known vulnerabilities in resolved runtime packages. Not host/OS certification |
| Static security scan | Six retained findings: five medium, one low; individually reviewed below |
| Packaged source | ZIP CRC/path/manifest/private-artifact inspection and extracted-source unit run performed separately; delivery evidence records exact archive hash and result |

No live AI, SMTP/inbox, Search Console, Bing verification, PageSpeed Insights or production browser run is claimed. The Search Console connector is unsupported here. Local browser timings are observations, not production speed scores or rankings. Current measured seven-route local DCL range/median are in `validation/quality-timings.json`; no conversion uplift, Lighthouse score or Core Web Vitals result is invented.

Before screenshots: 12 public local captures at 390/768/1440. After screenshots: 21 captures over the new/important public routes at those widths. The package includes selected before/after homepage/inquiry captures and new assessment/methodology views in `RELEASE-SCREENSHOTS.html`. These contain no private customer records and are **not live-site screenshots**.

### Findings investigated, not suppressed

Bandit B608 medium: `app/intake.py` fixed optional WHERE clauses with bound values; `app/maintenance.py` fixed SQLite/Postgres dialect expression with bound cutoff; two `app/marketplace.py` dynamic SQL expressions made only of fixed clauses/field expressions with bound and escaped search/category/offset inputs. B104 medium: deliberate 0.0.0.0 development preview listener; do not expose it as an unmanaged production server. B110 low: best-effort immediate email exceptions cannot erase a saved record; durable queue/worker is the recovery path and secrets are not leaked. No high finding; these retained findings mean the scan is **not zero-findings**.

New test harness failures were investigated: HTTP fixture tuple order was initially wrong and a banner assertion accidentally matched explanatory policy prose. The harness was corrected to inspect the intended response/control; real browser checks also assert no Accept-all button. No previously failing application test was deleted or relaxed. The old homepage test now targets the actual AI CTA rather than assuming the first primary button still opens AI; the new primary assessment journey has its own coverage.

## D. Remaining severity-ranked blockers and limitations

**P0 — production source/hosting reconciliation:** this reconstruction and the live application's routing/auth/persistence/business rules differ. Obtain actual build commit/root/framework/env/routing and reconcile database/file/session schemas before considering deployment. Live metadata/status/cookie/provider failures are not diagnosed completely here.

**P0 — live service proof:** configure/authorize staging AI, models/options/native spending limits and controlled mail recipients; exercise genuine conversations (English, Greek, Greeklish, typos, decimal units, corrections and hostile input), inspect private data boundaries, verify sender authentication, SMTP acceptance and actual inbox receipt, then monitor the scheduler. No credentials in chat. Local quota tests are not a euro budget.

**P0 — legal/operational readiness:** confirm controller/legal identity, permitted public contact, processors/transfers, applicable lawful bases, rights handling, approved retention/backup/deletion policies and incident ownership. Public noindex/preview flags remain. Code and absence of a banner do not certify compliance.

**P1 — actual host controls:** verify database project isolation and runtime least privilege, backups/restoration, worker schedule/leases, logs, edge/bandwidth protection and rollback. Environment binding variables alone do not prove target-database identity. Canonical apex/www intent and redirect chain need owner verification.

**P1 — inherited limitations:** existing PDFs remain unscanned/private; new PDFs stay blocked. Image identity/logo detection is not guaranteed. Regex/model instructions cannot guarantee every semantic leak or hallucination is prevented. SMTP can duplicate after uncertain acceptance. Browser abort does not guarantee provider computation/charging stops. Restore/backups/delivered email need separate erasure procedures. Named-admin offline recovery and full-manager roles are not a complete scoped-role product.

**P2 — source feature scope:** research matching still uses a bounded candidate set (including up to 2,000 recent Marketplace products), unlike fully paginated public browsing. Supplier history is bounded; full product editing/email ownership transfer/exported binaries remain limited. No actual analytics collector, automated quality score, exhaustive route-state coverage, load/soak test or screen-reader/assistive-technology certification is supplied.

**P2 — public artifact transport:** the earlier hand-written sandbox host links failed for this user. A locally successful blob download proves byte correctness in Chromium, not Arena's external routing. Do not invent a new sandbox URL or declare the user download problem solved without a supported attachment or independently reachable download. Any publishing of the source to a public repository needs explicit authorization.

## E. Staging, migrations, rollback and owner steps

1. Read `OPERATIONS-HANDOFF.md` with this report's overrides. Reconcile the actual live architecture; create and verify an encrypted backup and isolated restore first. Never initialize an unknown live schema from this checkout.
2. Test the released source on isolated staging. Existing migrations 001–005 remain ordered/additive/rerunnable; this visual/SEO release adds no destructive or new database migration. Do not enable mail/AI/retention/deletion just by copying example config.
3. Provision named admins/MFA and a restricted runtime role; verify old sessions, anonymous/private file access, suspension, inquiry retries, queue recovery and restoration behavior.
4. Validate real provider/mail/host behavior with approved accounts/recipients; no unauthorized provider spend or email test occurred here. Monitor actual quota/worker outcomes.
5. Obtain legal/controller/contact and retention/backup/rights approvals. Confirm actual cookies/scripts—including host-injected technology—before asserting consent exemptions. New provider tracking needs authorization and required consent before loading.
6. Confirm canonical origin and use `SEARCH-AND-MEASUREMENT-HANDOFF.md` for owner-controlled Search Console/Bing tags/verification/sitemap submission and Business Profile eligibility. No DNS/profile changes were made.
7. Only after explicit production approval and a rollback rehearsal: promote the correct build. Keep prior build and backups, stop writes/jobs during a rollback decision, preserve/reconcile new writes; do not drop additive tables to reverse a frontend deployment. Reapply the restricted erasure ledger before exposing restored data.

## F. Contradiction register

- Prior source audit ≠ live deployment. This audit fetched evidence of a different build and does not claim to have deployed fixes.
- Live human gatekeeper/1–3 days ≠ current owner rule. The release preserves **email confirmation → automatic publication**, not manager approval.
- Live demo marketplace ≠ genuine records in this release. No demo suppliers were seeded; only the labelled methodology examples are fictional.
- Live required licenses ≠ safe upload policy. New PDFs remain disabled; old private documents are not called malware-free.
- Live stored AI/age/Supabase/consent inventory ≠ this application's memory/draft/HttpOnly-session inventory. No silent migration or deletion was attempted.
- Cookie banner absent ≠ no cookies or legal compliance. Essential sessions/drafts and server-side processing remain.
- Live missing descriptions reported by an engineer ≠ verified fact. Raw live head could not be retrieved; source descriptions are tested.
- Live page-not-found content at robots/sitemap/inquiry ≠ known HTTP status or proven deployment cause. Owner inspection is still required.
- Default noindex ≠ accidental loss of approved indexing. It is an explicit outstanding launch gate; do not enable it to inflate an SEO audit result.
- Guided assessment ≠ supplier match/feasibility rating/notification. Only an explicit inquiry submission creates a saved record.
- Comparison row counts ≠ evidence-based supplier scores. Examples are fictional and not production data.
- Conversion hooks ≠ collected analytics or conversion uplift. They are local integration points, without transport/storage.
- AI-search foundations ≠ special schema/ranking guarantee. No GEO hacks or fabricated authority were added.
- Online business presence ≠ GBP eligibility. Real qualifying customer contact must be established; no virtual-office fiction.
- Queue/SMTP success ≠ inbox receipt; browser cancellation ≠ zero provider charges; local test success ≠ production readiness.
- Earlier ZIP/hash/commit labels ≠ this release artifact. Use the delivered manifest and hash for this source.

## G. Release decision and deliverables

**Positive evidence:** implemented visual/interaction/SEO changes; intact prior security controls; 149 unit/HTTP tests, real PostgreSQL integration and three browser suites passing; selected accessibility, privacy-request, storage, metadata, image, packaging and dependency checks.

**Not established:** live-browser behavior/metadata, deployed build configuration, actual AI/mail, host privileges, legal readiness, search indexing, production performance or the user's external Arena transport.

Deliverables: final source/assets/config/migrations/tests, this report, live route matrix, search/measurement handoff, updated environment reference, reproduction instructions, operational migration/rollback runbook, selected screenshots, fresh safe validation evidence and checksummed ZIP. No secrets, real records/documents, database files, unreviewed research, browser dependencies or runtime private configs belong in the package.

**Recommendation:** approved for further isolated staging review only. Do not deploy to production yet. Download delivery must be verified separately; an artifact existing on disk is not proof the user can obtain it.
