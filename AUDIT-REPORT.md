# STRATEVO code and AI review

**Review date:** 8 October 2026
**Scope:** current Python/vanilla-JavaScript checkout, backend workflow, model/search adapters, private research projection, migrations, frontend flows, configuration and release packaging. This is a targeted engineering audit, not a certification, formal penetration test or proof that every possible bug has been found.

## Executive summary

The source now includes a curated sourcing/language context layer, regression fixes, tested immediate approved-supplier profiles, Gemini setup instructions and a manual live-model evaluation checklist. Your Gemini-only setup should keep `ONLINE_DISCOVERY_ENABLED=false`. No Brave key is necessary for conversation; it is necessary for this application's live web discovery integration.

The code was exercised with **74 unit/HTTP tests**, an actual temporary PostgreSQL server, and Chromium desktop/mobile workflows. External AI/search responses were mocked in automated tests. Your live keys, hosted application, inbox delivery and actual Gemini response quality were not accessed or tested here. Existing production content was not deployed or replaced.

## Findings fixed

| Finding | Impact | Change / evidence |
|---|---|---|
| Long model replies could exceed the next request's 4,000-character per-message limit | A valid answer could break the next chat turn | Separate user (4,000) and assistant (16,000) limits; 48,000 total bound; frontend drops complete oldest pairs. Regression tests cover both acceptance and rejection. |
| Only four recent exchanges were retained; reset left old research cards visible | Lost context and misleading stale results | Up to eight recent pairs within total budget; new-chat clears cards/status. Browser-tested reset. This is not durable server-side conversation memory. |
| AI endpoint/key/model whitespace and accidentally using the completion URL as the base | Avoidable provider failures | Trim configuration; reject a completion URL used as base. Tested the exact Gemini-compatible endpoint and request format with a mocked transport. |
| Fixed 900-token output budget, with no finish-reason check | Short/truncated responses could be treated as complete | Configurable `AI_MAX_OUTPUT_TOKENS`, default 2048, bounded 256–4096. Reject `finish_reason=length`; enforce response-character bound. No claim that this guarantees every model's ideal token budget. |
| Disabled search was not explicit in the model's request context | Greater chance of claiming browsing with only a Gemini key | Inject actual available/disabled search state into every conversational request. External discovery still has server-side enabled/key checks. |
| Malformed bracketed URLs could evade matching or cause parser errors | Output boundary could miss bad links or turn an answer into an error | Broaden URL token handling and fail closed on parser errors. Existing encoded-source privacy tests still pass. Not a universal de-obfuscation guarantee. |
| Origin validation compared authority but not web scheme | Non-web or downgraded same-host origins were not explicitly rejected | Validate HTTP(S), authority, userinfo/path/query/fragment and canonical HTTPS; reject browser-declared cross-site requests. Retain authentication for non-browser requests without Origin. |
| Invalid imported MOQ/matrix values accepted booleans or wrong types | Bad data could be treated as facts or break comparisons | Validate positive finite numbers and text types before the transaction; reject boolean MOQ/lead time. Invalid target-currency types now produce validation errors. |
| Equivalent units such as `pcs` and `pieces`, or surrounding whitespace, could fail matching | False negatives | Narrow spelling aliases including Greek piece labels; no conversion of sets/cartons/weights to pieces. Unknown units remain unknown. |
| PostgreSQL fresh workflow initialization did not independently apply all private-table protections | Safety depended on completing the migration correctly | Enable RLS and revoke client/public access during workflow initialization as defense in depth. Hosted deployment still requires migrations and a server-only backend role. |
| Discovery migration assumed `anon` and `authenticated` roles existed | Failure on ordinary PostgreSQL installations | Conditional role revocation. Integration applies both migrations before and after creating those roles. |
| Concurrent duplicate applications could collide on the email unique constraint | One submitter could receive an error instead of the same non-enumerating response | Atomic `ON CONFLICT(email) DO NOTHING RETURNING id`; only the winning insert queues verification. Real PostgreSQL concurrency test verifies one application and one email. |
| Research manager API used hard-coded pending/import-status claims | Status could become incorrect after an import | Show actual stored-row count and explicitly unknown import completeness; removed hard-coded batch claims from live API/UI. |
| PDF response could emit duplicate CSP headers; importer left a file handle unmanaged | Ambiguous headers and resource hygiene | One explicit CSP response header; context-managed UTF-8/BOM-safe TSV read. |
| Manager decision-label spacing was cramped | Readability | Separated connection panel, license links and decision labels; browser flow/mobile checks pass. |

## Knowledge and conversational improvements

`app/knowledge.py` adds maintained context, not fine-tuning or new verified supplier records. `AI-KNOWLEDGE-GUIDE.md` is the readable export of the same guide.

- Four product pillars plus RFQ/specification, MOQ/cost, freight/Incoterms, due diligence/quality, compliance, negotiation/payment boundaries and inventory planning.
- Distinctions commonly mishandled: cost vs margin, advertised price vs quote, certification claim vs evidence, carton vs piece, ISO system certification vs product compliance, statistical sampling vs zero-defect assurance, freight payment vs risk transfer.
- Informal English, typos, abbreviations, business shorthand, Greek and Greeklish examples.
- Ambiguity safeguards: `asap` requires a date; `idk certs` does not mean none; `plug`, `ct`, `m`, decimal separators and selling units may require clarification.
- Professional tone without mocking, excessive slang, forced sales pitches or fabricated labor/notifications.
- At most four relevant knowledge modules are included per request, in addition to core/language guidance. Selection uses simple bounded keyword matching, not semantic retrieval or an independently sourced legal database.
- `AI-EVALUATION.md` provides 26 live acceptance cases. **These are not reported as passed model evaluations.** Run them against your actual deployed Gemini configuration.

## Validation performed

### Automated unit/HTTP suite

`python3 -m unittest discover -s tests -v`: **74 passed**. Covers approval/token/session roles, email outbox behavior, private paths, qualification gates, tool boundaries, source-link filtering, privacy projection, discovery budgets, connection diagnostics and new audit regressions. Test catalog records are synthetic and temporary.

### PostgreSQL integration

Actual ephemeral PostgreSQL, not SQLite emulation: both migrations, idempotent full-text import, private discovery persistence, search request budget, concurrent duplicate submissions, verification, concurrent approval conflict, exactly one queued approval email, approved supplier profile/session access, logout, client-role denial and RLS zero-row behavior after an accidental SELECT grant. This does not prove hosted Supabase configuration or SMTP delivery.

### Browser validation

Headless Chromium: public homepage; supplier application; explicit email verification; manager sign-in; private license download; approval; manager profile view; missing-key connection diagnostics; qualification/no-match/disabled-search behaviors; stale-result reset; automatic supplier redirect to private portal; role denial and logout. Six routes checked at 390px with no horizontal overflow or JavaScript exceptions. Desktop manager screenshot visually inspected. Not physical-device or multi-browser coverage.

Emails were read from the isolated test outbox; no real email was sent. No secret or real supplier profile is used in the browser fixtures.

### Static and packaging checks

Python compilation, JavaScript syntax and Git whitespace checks. Bandit reported one medium B104 finding: the development server binds `0.0.0.0`. This is intentional for the preview proxy, not suppressed or portrayed as a clean security certification. Do not expose the Python development server directly as production infrastructure. No dependency-vulnerability database scan or broad hosted penetration test was performed.

The package uses an explicit source allowlist and contains a SHA-256 manifest. Private owner records, databases, credentials, licenses, installed tooling, third-party notebook downloads and screenshots are excluded. Selected validation logs contain only synthetic test results.

## Important remaining risks / launch gates

1. **Actual hosting/model validation:** deploy this source, not only new variables into an old site. Confirm model access, billing, network access, function-tool compatibility and actual Greek/English quality. A basic connection test is not a sourcing-quality benchmark.
2. **Research access is still restricted:** chat/research currently require manager session or owner token. Public customer chat requires a deliberate access, privacy and abuse-control design; removing the gate would expose paid-provider costs.
3. **No private owner supplier data bundled:** online discovery is unavailable without Brave. Search candidate pages would still not verify supplier identity or requirements. No synthetic test row should be used as a real lead.
4. **Prompt reliability:** the model can misinterpret facts or generate inaccurate general text despite guidance. The application validates tool types/constraints, not semantic provenance of every extracted field. Supplier names embedded in free text and unusual link obfuscation still need editorial/privacy review. User-submitted historical assistant messages are untrusted, not authoritative facts.
5. **Language/search limits:** general chat is instructed to match language; deterministic shortlist/card labels remain English. Catalog matching uses keywords, not full semantic or technical equivalence. Location synonyms/regions are not resolved automatically.
6. **Certification/price limits:** no document-verification workflow, no live quotation integration, no guaranteed market compliance. Required certificates and target-price constraints may legitimately end in human handoff rather than a match.
7. **Email lifecycle:** provision SMTP and a worker/scheduler. Approval email is queued, not instantly delivered. Tokens expire from issuance; slow queues can deliver stale links. Monitoring/reissue and expired-job handling are operational requirements. SMTP acceptance is not inbox delivery; retries are at-least-once.
8. **PDF/privacy:** signature/size checks are not malware scanning. Add quarantine, scanning, retention/deletion procedures, restricted backups, legal operator/privacy terms and storage quotas before collecting real sensitive documents.
9. **Access management:** one manager role/password, no MFA or recovery console, no suspension/reapplication workflow. Add these if required before public launch; approval is not a certification badge.
10. **Abuse/cost controls:** workflow rate limits are global; conversational throttling is process-local. Edge/client controls, durable AI spend limits, concurrency limits and monitoring remain required before opening public usage. Discovery's persisted request cap is not a monetary billing guarantee.
11. **Deployment compatibility:** Vercel scaffolding is provided but not promoted/tested live here. Check routing, runtime/dependency availability, TLS, secret scopes, public origin, cookie policies, DB permissions and backup/rollback.
12. **No absolute completeness claim:** tests and source review cannot prove the absence of all defects or malicious inputs. Continue regression and live acceptance testing after every deployment/model change.

## External reference review

Official Google Gemini cookbook examples were fetched from GitHub and read during this audit:

- https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_OpenAI_Compatibility.ipynb — confirms the Gemini OpenAI-compatible base URL and Chat Completions/tool-declaration integration pattern.
- https://github.com/google-gemini/cookbook/blob/main/quickstarts/Function_calling.ipynb — supports the separation between model-requested calls and application-controlled execution/validation. That notebook also covers a different API; this project has **not** been silently switched to the Interactions API.

These examples do not prove availability of your account's model or key. The commercial/compliance guidance is educational and must be checked against applicable current requirements; it is not a live regulatory research service.
