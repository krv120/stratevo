# Public AI and self-service Marketplace — 2026-10-09

This report supersedes the manager-gated AI and approval-only **new supplier** flow in the older reference/audit reports. The black/blue screenshot-derived design remains in place. This is implemented source, not a production deployment or a guarantee of perfection.

## Delivered behavior

- **Ask STRATEVO AI:** full-screen modal, no customer password, signup or access token. General questions and sourcing questions use the configured server-side model. `/ai` remains a real standalone fallback. Chat remains in memory when its modal closes, not in browser storage.
- **Are you a supplier?:** working modal with private business/contact/license fields plus first-product fields; `/supplier` is the standalone fallback. Email plus WhatsApp **or** WeChat is required. No manager approval for this flow.
- **Publication:** first product is invisible until an explicit, single-use email confirmation. Confirmation activates `/supplier/account` and publishes automatically. Authenticated suppliers can publish more products and withdraw their own products; adding a corrected listing replaces an outdated one. Accounts have a 50-listing lifetime cap, including withdrawn listings.
- **Marketplace:** `/marketplace` is a separate page with real submitted products, search, four categories, pagination, photos, advertised price/currency and MOQ/unit. There are no invented seed products. The small-catalog search examines the latest 2,000 published listings; pagination is 24 items per page.
- **Privacy:** business identity/contact/license data is stored separately, never returned in public product projections or AI tools. Public text suppresses known account identity/contact values and recognized links/phone formats. Product inquiries and reporting use STRATEVO's Minup booking, with the product reference; opening a booking link is not a submitted inquiry. No direct supplier contacts/source links or commerce tools are added.
- **Management:** private supplier registry and downloadable private licenses, plus post-publication listing removal. This is moderation, **not approval before publication**. The registry shows the latest 25 accounts. Legacy applications and `/portal` remain for old-account compatibility; new applications cannot enter that legacy queue (`/api/supplier/apply` returns 410).
- **Matching:** public qualified matching includes only email-confirmed, published product evidence and existing anonymized private research; max three leads. Certification, lead time and exact-variant prices remain unknown unless evidence establishes them. Public chat cannot invoke paid live discovery. Private research/search/discovery APIs and connection diagnostics retain their owner/manager gates.

## Controls and limitations

### Anonymous AI

Server credentials stay private. Durable database reservations enforce a default **100 model requests per UTC day**, **3 concurrent requests**, **10 requests/minute per connection address**, and **60/minute globally**. Configurable settings are in `.env.example`; the explicit kill switch is `PUBLIC_AI_ENABLED=false`. Failed provider calls consume the daily allowance; invalid/missing-configuration requests do not. Reservations release on errors and expire after 90 seconds if a worker dies. Browser conversation and server prompt/output limits remain bounded. One model call is used per chat response.

These are request/concurrency bounds, **not an exact currency spending cap**. Configure provider-side billing alerts/limits and deployment-edge abuse controls before public launch. Forwarding headers are deliberately not trusted, so customers behind a proxy can share an address limit. Distributed bots can consume the shared allowance. Manager connection tests/private discovery have separate controls and are not charged to the public-chat counter.

### Email and persistent hosting

Apply migration **003** after 001 and 002, before serving this revision. New account, token, product and AI-budget tables live in `stratevo_private`, with RLS enabled and client roles denied. The Vercel adapter continues to require `DATABASE_URL`; it does not migrate during requests.

Email links use 32 random bytes, hashed storage, 24-hour expiry, single-use atomic consumption, explicit confirmation POST and account-bound HttpOnly/SameSite cookies. Links use a URL fragment and are removed from browser history when read. Resend invalidates earlier links. Public responses do not disclose whether an account exists; timing is not equalized and should not be treated as perfect anti-enumeration.

When SMTP is configured, registration/access requests synchronously attempt **their own queued message only**, before returning, so a serverless freeze cannot discard an unawaited background send. Failures remain queued. A real retry worker/scheduler is still necessary. Queue acceptance and SMTP acceptance do not prove inbox delivery. Existing queue retry leases/attempt limits apply. No delivery secrets were available for a real inbox test here.

### Files and identity

Photos: JPEG/PNG/WebP only, 500 KB input/output bounds, maximum 12 megapixels, single frame. Pillow 12.3.0 decodes and re-encodes a fresh JPEG raster, removing original metadata. UUID-based retrieval serves only confirmed/published listings; withdrawn/hidden images return 404. Images live in the private database, not externally linked supplier storage.

**Metadata removal does not remove visible logos, names, contacts or watermarks.** The form prohibits them, known text identifiers are suppressed, and a manager can remove a listing, but there is no OCR/content moderation service or guarantee of anonymity for malicious/obfuscated submissions. Email confirmation is not business, product or certification verification.

Licenses remain private base64 PDFs, limited to 2 MB with signature checks, **not malware scanning**. Manager downloads are attachments, not embedded documents. Implement scanning/quarantine, retention/deletion jobs, account suspension tooling, storage monitoring/quotas and backup restrictions before production. At the current global registration ceiling (20/hour), storage growth is still a practical abuse risk; global caps do not replace edge protection or cleanup. Pending records are not automatically purged.

### Interface

Native `dialog.showModal()` supplies focus isolation and Escape behavior; close controls are explicitly focused. Same-origin iframe Escape forwarding and return-to-trigger focus are implemented. Unsupported-dialog browsers retain real-page links. No JavaScript-only anchor replaces Marketplace navigation. Third-party-cookie restrictions in embedded previews can prevent supplier sign-in; open the preview directly in a tab for that account flow if necessary.

## Validation completed

- **101 Python unit/HTTP tests**: public/no-auth access, private endpoint denial, malformed requests, cross-origin rejection, verification expiry/replay/resend/concurrency, projection privacy, ownership/IDOR, image format/size/metadata behavior, visibility lifecycle, matching qualification, durable daily/concurrency limits and specifically targeted mocked SMTP delivery; existing regression suite retained.
- **Real ephemeral PostgreSQL**: all three migrations, duplicate-registration and token-consumption races, automatic publication, ownership/withdrawal, shared AI budget concurrency, client-role denial and RLS on all five new tables; earlier catalog/discovery/legacy compatibility checks also pass.
- **Real Chromium** against an isolated test server: full-screen/no-credential chat, honest disconnected recovery, explicitly mocked general answer, Enter/Escape/reopen behavior; supplier popup/forms/contact validation; test-outbox confirmation → automatic publication → account; photo and public privacy; search; withdrawal/addition; manager-only registry/removal; mobile popup/navigation; 320/390/768/1568px overflow checks; reduced motion; no JavaScript exceptions.
- Syntax/compile checks for Python and JavaScript. Bandit reported two reviewed findings: intentional `0.0.0.0` preview binding (medium), and intentionally caught SMTP-send exceptions with queued retry/no sensitive provider output (low); no high-severity findings. Browser/test accounts exist only in an isolated test database, not the public preview or source ZIP.

**Not validated live:** hosted Gemini response quality/quota, Brave, SMTP or inbox receipt, production database/deployment, public-domain routing, physical mobile browsers, accessibility assistive technology, legal readiness or comprehensive penetration testing. Provider transport and SMTP were mocked where indicated; reading a test outbox is not receiving an email.

## Research reviewed

Official source documents retrieved during this revision informed the implementation:

1. [OWASP email validation/verification](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.md): random, single-use/time-limited tokens; generic responses and rate limiting.
2. [OWASP file uploads](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/File_Upload_Cheat_Sheet.md): restricted formats, bounded resources, decode/re-encode, metadata removal and defense in depth; rewriting is not a guarantee against malicious content.
3. [OWASP secure AI model operations](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/Secure_AI_Model_Ops_Cheat_Sheet.md): abuse/cost controls and kill switches. Anonymous customer access is intentional; private operational actions remain authenticated.
4. [MDN dialog source](https://github.com/mdn/content/blob/main/files/en-us/web/html/reference/elements/dialog/index.md): native modal/inert behavior, deliberate focus placement and Escape dismissal.

Prior Gemini-compatible API research is recorded in `REFERENCE-RESTORATION.md`. Actual provider compatibility still requires the hosted connection and live-model acceptance tests in `KEY-SETUP.md` and `AI-EVALUATION.md`.
