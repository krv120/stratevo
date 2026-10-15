# Search, consent and measurement handoff

Reviewed 13 October 2026. This is operational guidance, not proof of indexing, legal compliance or rankings.

## SEO / GEO decisions and official sources

- [Google: AI features and your website](https://developers.google.com/search/docs/appearance/ai-features) states that established SEO practices remain relevant and there are no additional technical requirements for AI Overviews/AI Mode. Retrieved 13 October 2026; page states last updated 10 December 2025. We added useful crawlable content, navigation, metadata and modest WebSite/WebPage JSON-LD—not AI instructions, special AI schemas, `llms.txt`, mass articles or fabricated authority.
- [Google: snippets and meta descriptions](https://developers.google.com/search/docs/appearance/snippet) recommends accurate page-specific descriptions and explains that snippets are generated from content and may differ from the supplied description. No promised snippet, traffic or ranking is made.
- [Google Business Profile eligibility](https://support.google.com/business/answer/13763036) requires in-person customer contact during stated hours and lists online-only businesses among ineligible categories. [Representation guidelines](https://support.google.com/business/answer/3038177) require accurate real-world business information. STRATEVO's qualifying in-person activity is **not established**. If exclusively online, do not create a profile. No profile, virtual-office address or invented service area was created. Owner must document real eligibility and approve any account action first.
- The methodology page links the [ICC Incoterms rules](https://iccwbo.org/business-solutions/incoterms-rules/), [ISO certification explanation](https://www.iso.org/certification.html), and [EU Access2Markets](https://trade.ec.europa.eu/access-to-markets/en/home). These primary pages were retrieved; they are context for questions, not evidence of any supplier's compliance.

## Actual implementation

Ten public-content routes have unique titles/descriptions, one configured canonical, robots directives, OG and Twitter metadata, favicon and JSON-LD. The social image is a brand graphic, not factory or customer evidence. The method/assessment/cookie pages have visible breadcrumbs. Core explanatory content and comparison rows are in HTML without JavaScript; interactive steps have a conventional inquiry fallback. Private routes remain noindex.

Canonical defaults retain the earlier owner-supplied apex. The live fetch ended at www, but its raw canonical/redirect chain could not be inspected. **Resolve the intended origin with the owner before enabling indexing.** Set `CANONICAL_BASE_URL` and verified `PUBLIC_BASE_URL` deliberately; do not derive them from request Host. No DNS or live redirects were changed.

Indexing is intentionally OFF until `APP_ENV=production`, `PUBLIC_ORIGIN_VERIFIED=true`, `SITE_LAUNCH_APPROVED=true` and `SITE_INDEXABLE=true`, after legal and operational approval. An empty preview sitemap and disallow robots file are deliberate safeguards, not completed launch SEO. Even after approval `/ai`, `/inquiry`, authentication, account and admin routes stay non-indexable. A noindex/disallow combination is not a promise of removal of already indexed URLs: existing indexed pages require owner-managed recrawl/removal handling.

## Owner-controlled Search Console steps

The Search Console connector lookup returned unsupported. No account-level URL Inspection, ownership verification, indexing report, Search Console performance report or PageSpeed Insights run occurred.

1. Confirm the intended canonical origin and obtain approval for any hosting change. Compare HTTP/apex/www redirects and final HTML canonical on the actual deployed build.
2. In your own Google Search Console account, add an exact HTTPS URL-prefix property for that confirmed origin. Choose HTML-tag verification. Put only its public verification value into `GOOGLE_SITE_VERIFICATION` in the hosting environment. This release emits the escaped tag on the homepage; it does not verify ownership itself. Do not put an API key in this setting or share private account credentials.
3. Deploy to production only after the separately approved backup/rollback/promotion procedure. Check the tag in the fetched homepage source, then click Verify in Search Console. Alternatively use a Domain property and its exact console-generated DNS TXT record **only with explicit DNS authorization**; no record value is invented here.
4. After legal launch approval and intentional indexing activation, confirm `/robots.txt` and `/sitemap.xml` return correct content/types/statuses, then submit the sitemap in the verified property. Use URL Inspection for the homepage, methodology and assessment; inspect Google-selected canonical, crawl access, rendered HTML and snippet eligibility.
5. Monitor Page indexing, performance and Core Web Vitals. Run PageSpeed Insights on the final public URLs and record actual mobile/desktop findings. Those external/field measurements cannot be inferred from local Chromium timing.
6. For Bing Webmaster Tools, use the owner account's supported verification/import flow. `BING_SITE_VERIFICATION` emits `msvalidate.01` only if explicitly configured. Submit the same confirmed sitemap; no Bing verification/indexing claim is made here.

## Conversion measurement, without a new tracker

`web/stages.js` emits a `stratevo:stage` DOM CustomEvent containing **only** `{name, version: 1}`:

| Name | Actual trigger | Meaning / limit |
|---|---|---|
| `assessment_started` | First edit in the current assessment page | A local interaction, not a unique visitor or qualified lead |
| `assessment_reviewed` | User advances to review | Can repeat after going back; no feasibility score |
| `inquiry_submitting` | Valid form enters its send attempt | Attempts include retries; not proof of persistence |
| `inquiry_saved` | API returns confirmed saved ID | Local confirmation, not SMTP/inbox receipt or business qualification |

No event endpoint, collector, cookie, fingerprint, user ID, text payload, persistent history or analytics vendor is installed. Thus there is **no live funnel dashboard or historical event count** to report. The existing private inquiry source field now accepts `assessment`; it is operational metadata, not independently verified attribution. Do not claim measured conversion uplift.

A future collector requires explicit authorization, a documented purpose/minimization/retention design and applicable consent before activation. Consent refusal must not block assessment or inquiry. These hooks alone create no network/storage collection and do not justify adding a banner with empty optional categories.

## Cookie/storage decision

The release uses essential `stratevo_session` auth cookies (HttpOnly, Secure in production, SameSite=Lax, Path=/api, eight hours), requested same-tab AI/assessment drafts (ten-minute validity), in-page form/chat memory, self-hosted fonts and a same-origin dialog iframe. See `/cookies` for precise lifetimes, including unused expired drafts remaining until read/tab closure.

In tested anonymous journeys: no initial cookies, localStorage, sessionStorage or unsolicited external requests. Explicit draft handoff creates then consumes the relevant sessionStorage entry. Auth tests separately prove essential sessions still work. Backend AI/SMTP/database processing is not visible in a browser cookie inventory and remains subject to privacy/operator review.

The live site claims a different inventory, including `stratevo-consent-v1`, age assurance, AI session data and Supabase tokens. We could not verify that inventory in a live browser. Those keys are absent from this source; no unapproved deletion of old live authentication/storage was attempted. During an authorized migration, reconcile old sessions/storage and remove retired code/keys only after proving they are no longer required. Also inspect actual host/CDN scripts, cookies and security challenges. “No consent banner in this build” does not mean “no cookies” or legal certification.
