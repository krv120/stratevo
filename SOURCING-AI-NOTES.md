# Sourcing AI update — 8 October 2026

## What changed in this checkout

- Added a readable, separated “The brief” section, five sourcing stages, four service pillars and four customer stages. No invented supplier totals or success metrics were added.
- Added the owner-specified contact `hello@stratevo.co`. This is not verification of that mailbox, its delivery, or its intended difference from `stratevo.online`.
- Replaced the assistant prompt with a concise supply-chain-director persona, company/process context, qualification questions and honest human handoff.
- Added `/api/catalog/match` and a matching form in the restricted intelligence workspace. It works without an AI provider.
- Before reading the database, the matcher requires product, target volume with unit, ideal supplier location and required certifications. `any` and an empty certification list mean explicitly unrestricted requirements, not missing answers.
- Matching uses all supplied product keywords, exact location/unit comparisons, advertised MOQ and optional lead-time/price constraints. It is conservative keyword filtering, not semantic search or technical validation. It does not perform unit conversions, geographic alias resolution or supplier verification.
- At most three anonymized research leads are returned. Explanations and MOQ status are generated from the selected evidence, not written freely by a model after the tool call. Multiple parallel model queries are rejected.
- A missing/unsupported MOQ unit cannot produce a “Yes”. Nonmatching or unknown candidates are excluded, with evidence gaps and the Minup handoff shown instead of pretending they fit.
- Matrix output covers category, location, MOQ, lead time, certification evidence and target price. Missing facts remain unknown. Imported certification claims never become verified certifications, even if an import file labels them verified. A verified-document review workflow is not implemented.
- Target-price constraints currently cause a human handoff because the catalog lacks confirmed variant-specific quotations. Advertised ranges are not silently treated as comparable quotes.
- The AI cannot create a human task or notification. The link offers a scoping call; no “I'm flagging this” claim is made.

## What remains limited

The provider is not configured. General conversational/multilingual performance has not been tested against a real model. When connected, the prompt requests the user's language; deterministic matching replies and form labels currently use English. Multilingual matching templates/translation remain a follow-up.

The model extracts qualification fields from conversation. Application validation checks completeness/types, not whether every extracted fact really appeared in the user's words. The structured form is the explicit-input route. Prompt instructions are not a guarantee against every possible hallucination in free-text general answers.

The keyword lookup remains an owner-only research browsing feature, distinct from qualified matching. Free-text descriptions require editorial review to remove identifying information; structured allowlisting alone is not text redaction.

## Latest Alibaba batch: NOT imported

The conversation identifies source IDs `1791468889-1` through `1791468889-1008`. The raw export is not present in the restored workspace. No rows from that batch have been reconstructed or loaded. No usable-row, placeholder-row, supplier or verification count is asserted.

Upload the original CSV, XLSX, JSON or text export for normalization. Preserve raw rows privately, separate image-only placeholders, flag ambiguous price/title/MOQ boundaries, and retain original IDs for audit. Shipping routes do not identify the supplier's location; titles do not verify certificates; repeated titles do not prove distinct or identical suppliers.

The earlier 60-row private catalog is also absent in this restored checkout. The preview is intentionally empty rather than filled with fabricated records. Synthetic test fixtures exist only in temporary test databases and are visibly marked TEST ONLY.

## Normalized input options

`app.catalog.import_json` accepts private JSON records with:

- `source_row_id` (numeric batch-row ID)
- `description_summary` (buyer-safe, human-reviewed)
- `advertised_price` and `advertised_moq` (unknown fields null)
- Optional `matrix`: `category`, `location`, `lead_time_days`, `target_price`, `certifications_claimed`
- Private provenance/source fields, retained in the original record but not in buyer/model projection

The helper `scripts/normalize_research_tsv.py` is for **already reviewed, manually normalized TSV**, not arbitrary raw Alibaba Markdown. Its columns are:

`row`, `price_eur`, `moq_number`, `description_summary`, `category`, `certification_claims`

Use tab delimiters, a single numeric row ID, an explicitly EUR price or hyphen-separated range, a numeric MOQ and semicolon-separated marketing certification claims. The helper intentionally leaves MOQ units, supplier location and lead time unknown. Do not infer currency from an ambiguous dollar symbol or guess merged numeric boundaries. Use the JSON importer for other currencies, null prices or known additional fields.

```sh
python3 scripts/normalize_research_tsv.py private/reviewed.tsv --batch 1791468889
python3 -m app.catalog private/reviewed.json
```

Keep both files inside ignored `private/`; never put raw source/contact data in public assets.

## Public-domain audit scope

A text fetch of the existing production homepage still showed zero-valued counters and concatenated process-strip text. These may reflect animation/client-rendering behavior; text extraction does not prove the rendered counters are broken. The production page differs from this source checkout and has not been edited or deployed. This preview avoids those counter claims and gives each process stage a separate list item.

## Validation

- 51 Python unit/HTTP tests passed after replacing dependence on missing private owner data with isolated synthetic fixtures.
- Chromium: full supplier application/verification/manager approval/access workflow; qualified matching form; no-match handoff; incomplete-brief gate; six routes at 390px with no horizontal overflow or JavaScript errors.
- Email links came from a test-only outbox, not SMTP delivery.
- JavaScript syntax and Git whitespace checks passed.
- PostgreSQL was tested in the previous revision, not rerun for this update. No production deployment, real provider call or mailbox verification occurred.

## Source-link protection follow-up

Buyer projections now sanitize URL and email text recursively at import and read time, including previously imported summaries. Raw research is retained only in the original private record. The model's free-text answer is checked server-side: recognized unapproved links replace the entire answer with a private-source explanation and the official booking action. Tests cover source URLs in Markdown, bare domains, common encoded/obfuscated spellings, nested fields and legacy database rows. This is defense in depth, not proof against every possible obfuscation or a substitute for human review of names and contact details.

Current verification: 51 unit/HTTP tests pass. Browser tests and PostgreSQL integration were not rerun for this backend-only follow-up. No production deployment was made.

The latest message lists a CSV and PDF, but `/home/user/uploads/` does not exist in this workspace, and a search of accessible upload/workspace locations found neither file. Import is blocked on attachment availability, not rejected because of the filename or format. No rows from the missing files were reconstructed. Reattach the CSV as `suppliers.csv` to resume inspection and import. AI-provider credentials, SMTP, production hosting and real multilingual model validation remain separate launch requirements.

## On-demand online discovery (new scope authorized by owner)

The owner's new request supersedes the spreadsheet-only restriction **for online discovery**. Catalog matching remains available separately. Added a `Search online now` choice to the qualified-requirement form and a `discover_online` model tool. Both use the same four-point qualification validator. The tool is advertised to the model only when discovery is enabled and a search key exists; direct API calls also fail closed when disabled.

Integration: Brave Web Search API, fixed HTTPS endpoint, no redirects, 20-second timeout, bounded response size, no fetching of returned supplier URLs. This is search-result discovery, not live factory verification or comprehensive webpage extraction. Raw titles, snippets and URLs are saved privately with timestamps, and never passed to the model or customer. Up to three distinct-host candidate references are shown; different hosts are not proof of different suppliers. Relevance, company identity, MOQ, location, lead time and certification evidence remain unverified. No fabricated capability summaries are produced from search snippets.

Manager-only provenance endpoint: `GET /api/admin/discovery`. It is not exposed through the buyer cards or model tools. Manager provenance contains original source links for internal review only. Search candidates are not automatically imported into the catalog, approved as supplier accounts, or presented as qualifying matches.

Activation in hosting secrets (do not paste keys into chat):

- `ONLINE_DISCOVERY_ENABLED=true`
- `BRAVE_SEARCH_API_KEY` with a valid search subscription key
- `ONLINE_DISCOVERY_DAILY_LIMIT=50` (default, shared UTC daily cap)
- Existing `AI_API_KEY` and `AI_MODEL` for conversational use. The structured form does not require a language model.

Apply `migrations/002_private_discovery.sql` after the base migration for PostgreSQL. Local SQLite initializes the private tables automatically. The reservation counter persists before outbound calls and failed calls count toward the limit. There are no automatic retries or unbounded agent loops. Existing authenticated-request throttles also apply. Budget limits are not a guarantee of provider billing amounts.

The external provider receives product, preferred supplier location and certification search terms, not the complete conversation, target price or volume fields. Users must avoid confidential or personal information inside the product/search fields themselves. The UI discloses that the query goes to an external provider; production privacy and retention terms need to cover this integration and private evidence storage.

Validation: 57 Python tests passed, including qualification, disabled mode, persistent daily limits, provider failure handling, private provenance, maximum-three candidates, host deduplication and agent wiring. Provider calls were mocked; no real search API request, browser rerun, PostgreSQL rerun or deployment was performed for this change. Live search cannot be claimed until the hosting environment has credentials and passes an actual end-to-end test.
