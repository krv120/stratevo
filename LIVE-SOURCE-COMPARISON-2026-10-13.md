# Live website vs source, preview and proposed release

Audit date: **13 October 2026**. Repository: `krv120/stratevo`; working branch: `arena/40bf7fdf-stratevo`.

## Evidence boundary

The web-fetch service retrieved the live site's extracted content and page titles. The apex homepage fetch resolved to `https://www.stratevo.online/`. That establishes the fetch's final address, **not the full redirect chain, status codes, canonical tags or owner-approved canonical configuration**.

Direct Python HTTPS access failed with TLS connection closed; Chromium failed with `net::ERR_CONNECTION_CLOSED`. Consequently, live source HTML/head metadata, browser-rendered screenshots, responsive layout, request/cookie inventory, CSP, caching, actual status codes and authenticated/live-provider behavior were **not verified**. A web-fetch tool error is not automatically a production-origin HTTP error. No live form submission, email or model call was made.

Local before screenshots were taken at 390/768/1440 widths before edits. Local screenshots must not be relabelled as production screenshots. The source inventory and fresh 137-test baseline are evidence of the restored working files, not the earlier commit claims: at the start of this turn Git HEAD was `6d4e00b` with the application restored as largely untracked files. The packaged manifest identifies the actual release commit.

## Route comparison

“Live not found” below means **retrieved STRATEVO page-not-found content**, not a verified HTTP status.

| Route | Live fetched evidence | Working source / initial local preview | Proposed release |
|---|---|---|---|
| `/` | Title “Evidence-led sourcing preview”; AI-led hero; links to `/rfq`; manual gatekeeper messaging; cookie-choice banner; process counters extracted as zero | China-sourcing homepage, longer text-first sections; no banner; inquiry persistence; confirmed-email publication | Clear service/audience/value; primary assessment CTA; visual brief/evidence card; compact four-stage process; preserved AI and booking paths |
| `/ai` | Fetch failed, reported HTTP 500 by fetch service; direct browser unavailable | Public full-screen assistant, honest disconnected local state, no consent layer | Retained; public lookup requires explicit qualification; guided assessment is independent of provider availability. Live AI remains unverified |
| `/rfq` | Four-stage “non-binding brief”, preview/no live distribution | Missing; actual durable inquiry is `/inquiry` | GET/HEAD navigation alias to `/assessment`; no legacy POST accepted or invented distribution |
| `/inquiry` | Page-not-found content | Real customer inquiry/private inbox/notification intent | Retained with reviewed assessment handoff, source classification and in-page conversion hooks |
| `/assessment` | Not fetched; no conclusion about live existence | Not implemented | New browser-only guided brief, validation, review, explicit temporary handoff, blocked-storage copy recovery |
| `/methodology` | Not fetched; no conclusion about live existence | Not implemented | Original evaluation method, clearly fictional comparison/filter experience, useful FAQs, ICC/ISO/EU references |
| `/marketplace` | Title “Demonstration marketplace”; extracted text contained only consent banner | Real supplier-submitted products, initially empty; no seeded public suppliers; SQL paging | Retained. Missing extracted body does **not** prove a cookie overlay caused the live problem |
| `/supplier` | Required official license, WhatsApp/WeChat and human approval; 1–3-day target | Optional messaging; new PDFs disabled; email confirmation automatically publishes | Retained current owner rule; no invented turnaround target. Dialog/direct route and publication tested locally |
| `/supplier-portal` | Linked from live supplier page; content not fetched | Account route is `/supplier/account` | Safe navigation alias to current account route; no conversion of old Supabase sessions |
| `/supplier/account` | Not fetched | Authenticated product account; withdrawal, history/storage bounds | Retained and regression-tested |
| `/admin` | Live link observed; no sign-in attempted | Named-admin/TOTP production boundary, non-production legacy test login | Retained; no public auth recovery or exposure of private records |
| `/access`, `/portal` | Not fetched | Expiring-token access; older supplier account compatibility | Retained, private/noindex; not conflated with new publication rules |
| `/privacy` | Controller disclosure blocked; describes stored AI sessions, Supabase browser auth, manually reviewed supplier files and retention periods | No stored AI transcript, essential HttpOnly session, temporary explicit handoff, configurable unapproved retention | Updated for assessment and precise storage behavior; no imported unsupported live retention promises |
| `/cookies` | Banner and inventory claim no optional trackers; includes consent, age-assurance, AI and Supabase local/session-storage keys | No cookie page/banner or those legacy keys in this source | Clear application inventory, no pointless consent choices; existing live storage is not silently erased |
| `/terms` | Demo listings and RFQs, manual supplier approval, required messaging | Real submitted product records after confirmation; separate paid scope | Retained current behavior and limitations; does not claim old live/demo semantics |
| `/business-information` | Launch blocked for missing legal/controller identity and operational disclosures | `/#launch-status` and privacy/terms explain blockers | Safe navigation alias to launch-status section; no legal identity invented |
| `/privacy-center` | Linked by live privacy/terms; not fetched | No public self-authenticated rights-request center; manager rights tooling and human process | Not falsely recreated; verified rights contact/identity process remains an owner launch prerequisite |
| `/robots.txt` | Retrieved page-not-found content | Valid plain-text generator; default disallow | Retained; production + origin + launch approval gates |
| `/sitemap.xml` | Retrieved page-not-found content | Valid XML, empty while non-indexable | New public pages included only when approved; private/account/AI/inquiry routes excluded |
| Unknown public URL | Live custom 404 content seen on the paths above | Generic JSON not-found response | Useful HTML 404, correct local HTTP 404, noindex, recovery links |
| Unknown API URL | Not fetched | JSON not-found response | JSON retained, including unsupported methods/errors |
| Favicon/social image | Not inspected in live source head | No complete social image/Twitter set or favicon route | Self-hosted SVG icon and 1200×630 brand graphic, OG/Twitter tags; no fabricated business imagery |

## Causes established vs hypotheses

**Established:** the content, routes, business rules and described persistence/authentication architecture differ. The earlier source-level SEO work cannot be treated as proof of the deployed build. This release contains no consent script to remove; the consent UI visible live belongs to a different build.

**Not established:** which repository/commit/environment built production; whether production lacks meta descriptions; whether its cookie screen blocks the AI or marketplace; the reason `/ai` could not be fetched; whether live API/provider/SMTP configuration works; the complete redirect/status chain. Deployment drift is demonstrated at the behavior/content level, not traced to a specific hosting misconfiguration.

**Before promotion:** owner must export the hosting build commit/framework/root directory/route configuration, inventory actual production requests/storage, inspect raw response head/headers, and reconcile live database/auth/file architecture with this Python reconstruction. No blind replacement or application of these migrations to an unrelated live schema is authorized.
