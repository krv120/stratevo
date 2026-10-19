# Live/source comparison and search handoff — 2026-10-19

## Evidence boundaries

Text fetches of the live www site were possible during the audit. Direct curl failed TLS connection establishment and automated browser navigation was inaccessible. Consequently there are **no live screenshots, verified live response headers or live interactive-flow results**. `before-local-*` screenshots are renders of the previous local release, not production screenshots.

| Routes | Live text fetch observation | Candidate source/local browser |
| --- | --- | --- |
| `/`, `/methodology` | Previous assessment-led content and retired helper panels | Booking-only primary conversion, current sourcing methodology |
| `/supplier`, `/marketplace` | Previous product-public/private-company flow, product filters and temporary-storage notices | Single-step immediate supplier publication; company/focus cards and private contact separation |
| `/assessment`, `/inquiry` | Previous competing forms and preview notices | Distinct booking-priority pages with the same authorized destination |
| `/supplier/account`, `/admin` | Previous workspace/panels and mandatory-MFA instructions | Session-owned directory profile and direct staff workspace; MFA optional unless configured |
| `/privacy`, `/cookies`, `/terms` | Previous inventory/unfinished operator notices | Current public backup and private-contact disclosures; supplied operator contact; legal gaps still unresolved |
| `/robots.txt`, `/sitemap.xml` | Robots disallowed all; sitemap fetch tool returned HTTP 500 | Indexing gated by environment, launch approval, origin verification and SITE_INDEXABLE; not enabled by this release |

Source/local tests cover eleven routes at five widths. Local screenshots cover selected routes, not every live page. No production deploy, DNS change, database modification or booking was performed.

## Technical search and geographic guidance

Public pages have route-specific title/description, canonical www URLs and sharing metadata. Account/admin remain non-indexable. Verify actual host redirects, robots and sitemap after an approved deployment. Distinct assessment/inquiry copy avoids presenting duplicate competing forms; inquiry remains intentionally non-indexable. Do not fabricate testimonials, credentials, factory claims, office addresses or location pages.

Official guidance reviewed:

- https://developers.google.com/search/docs/appearance/snippet — snippets primarily come from page content and sometimes descriptions; search engines can choose different text.
- https://developers.google.com/search/docs/appearance/ai-features — ordinary technical/search requirements apply; no special visibility guarantee or special schema is established by this release.
- https://support.google.com/business/answer/13763036 — eligibility depends on in-person customer contact; online-only/lead-generation activity does not justify an invented Business Profile or office location.

Geographic and generative-search visibility should follow accurate service descriptions and ordinary crawlable content, not invented regional presence or ranking promises. No webmaster account/index submission or invasive analytics was enabled. In-page conversion events expose only a stage and are neither analytics collection nor conversion-completion evidence.

## Legal and storage inventory

Operator contact: Vasilis Krevatsoulis / info@stratevo.store / +30 6989472740. Required establishment/address and applicable registration/VAT disclosures remain unresolved; no compliance certification is claimed. Review GDPR transparency/retention/rights, applicable e-Commerce disclosures and content-notice/redress obligations with counsel. The public browser backup is persistent seven-day functional storage requiring purpose/exemption review; authentication cookies serve sessions. There is no embedded booking tracker: the external Minup link opens a separate service whose processing is governed by its policies. No cookie banner is added merely for decoration, and this does not certify legal readiness.
