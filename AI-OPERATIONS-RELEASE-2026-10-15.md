## Follow-up audit — 2026-10-16 / 2026.10.16-ai-ops-rc2

The six-area implementation was re-audited after the owner encountered the missing-admin-configuration message. No default credentials were installed and no private hosting secrets were accessed.

Changes in this follow-up:
- Public admin setup diagnostics now validate actual account configuration instead of treating a nonempty variable as ready. Missing, invalid and ready states contain no hashes, password values, account lists or MFA seeds.
- Added an expandable, mobile-safe owner setup guide at `/admin`, including credential precedence, local authenticator-seed generation and authorized redeployment instructions. No public account-creation/reset endpoint or fallback bypass was introduced.
- Replaced contradictory legacy KEY-SETUP.md instructions with current native-provider, immediate-publication, MFA, durable-storage and real-mail guidance.
- Corrected a stale chat message: named external research is available through the AI Lead Finder, not only through a booked review. Chat alone does not imply live search or silently spend on research from inferred requirements.
- Added setup-state/privacy HTTP regressions and browser checks for the expanded setup guide. The new browser assertion caught mobile overflow from the setup command; wrapping was fixed without weakening the assertion.

Fresh verification: **185 unit/HTTP tests passed**, **13 actual PostgreSQL PASS groups**, and **seven browser runs passed**. Both engine browser modes were rerun after the mobile wrapping fix. Syntax/compile and dependency-consistency checks passed. Runtime requirement audit found no known vulnerabilities. A broader tooling scan found outdated local pip/setuptools; both were upgraded in the isolated development environment and its repeat audit was clean. This does not update or certify the hosting build image. External provider and mail responses in automated tests are synthetic; no live provider result or inbox receipt was verified.

Checklist scope remains: provider adapters + grounded discovery; normalized supplier publication/profile editing; real transports + persistent notices; private manager/CRM; additive schemas; synchronized templates and automated verification. Intentional safeguards: Marketplace membership is not falsely labeled verified; unsupported leads/RFQs are never invented to reach five results; no unknown localStorage import; missing admin configuration never exposes private records. Generic chat and unsubmitted assessment drafts are not automatically stored as qualified buyer inquiries: explicit lead-finder requests run research, and submitted inquiries appear in the customer inbox.

The previous rc1 source was pushed to the approved session branch. This follow-up does not authorize a production deployment or migration. Live AI/mail credentials, authorized recipient/sender, MFA provisioning, persistent PostgreSQL and staging validation remain operator prerequisites. The source ZIP cannot supply those secrets.

---

# AI, supplier and operations upgrade — 15 October 2026

Release candidate: **2026.10.15-ai-ops-rc1**. This report supersedes earlier release reports for AI, supplier fields, notification content and admin management. Implemented and tested in the repository, **not deployed or certified against production services**.

## What changed

### AI configuration and grounded discovery

`settings.ai_configuration()` resolves nonempty keys in this order: OPENAI_API_KEY, STRATEVO_AI_API_KEY, AI_API_KEY, GEMINI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY, PERPLEXITY_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY. AI_PROVIDER overrides provider inference; otherwise known prefixes and variable names choose the adapter. AI_MODEL and AI_BASE_URL are optional overrides. The old OpenAI default base no longer misroutes a detected Gemini/Anthropic key. A key activates AI without requiring PUBLIC_AI_ENABLED=true; that old flag does not disable a configured key.

Native Gemini generateContent and Anthropic Messages are implemented alongside OpenAI-compatible Chat Completions. Defaults: gpt-4o-mini, gemini-2.5-flash, claude-sonnet-4-5, sonar-pro, openai/gpt-4o-mini (OpenRouter), llama-3.3-70b-versatile (Groq). Defaults are configuration choices, not promises of current model access. Anthropic uses a newer model default rather than relying on a 3.5 alias; operators can override AI_MODEL. Official OpenAI model-not-found responses get one bounded fallback to gpt-4.1-mini or gpt-4o; authentication/quota failures are not blindly retried. Responses use a 25-second per-provider ceiling, safe error messages, no credential-bearing redirects and User-Agent `Stratevo-AI-Engine/2.0`. Structured text/tool arguments strip JSON fences before parsing; malformed output is rejected, not fabricated into success.

The new Lead Finder has real server integrations:

- OpenAI Responses with web_search_preview, using AI_SEARCH_MODEL (default gpt-4.1-mini).
- Gemini Google Search grounding, with a bounded thinking budget for Gemini 2.5 Flash.
- Anthropic's web-search tool, subject to model/account support.
- Perplexity Sonar citations.
- For chat-only OpenRouter/Groq/custom compatible endpoints, a configured Brave search key supplies retrieved evidence before the model structures it. A chat key alone is not silently treated as browsing capability.

Queries request 5–8 companies but **return fewer, including zero, rather than inventing evidence**. Results must have usable provider-issued citations connected to the company domain (or matched provider grounding titles for Google redirect citations). Website syntax is validated, not represented as a successful independent website inspection. Names, location, capability/certification claims, contact pathways, commercial estimates, subjective fit scores and rationale are projected into bounded structured objects. Guessed emails and uncited contact paths are not shown. These are **source-backed unverified prospects**, not verified suppliers, RFQs or confirmed purchasing intent. Human verification is still required; a citation does not prove every field.

Marketplace products, anonymized internal catalog research and named external leads stay distinct. Existing self-registered suppliers are not relabeled “verified” merely to match a UI heading. External leads persist in `discovered_leads`, with query, actor, status, timestamp and provenance. Lead Finder panels exist on home/AI, Marketplace, assessment, supplier account and admin. Public queries are limited by the existing database-backed usage controls. Automatic registration research has a 25-second aggregate provider budget; explicit finder calls have a 40-second aggregate budget. Per-request limits are not monetary caps. Known provider timeouts do not undo saved supplier records.

### Supplier form and account

Added private website, phone, capabilities, employee/year, categories, claimed certifications, materials, served regions and lead-time fields. Server normalization uses Unicode normalization, whitespace trimming, safe scheme insertion/URL validation, bounded list splitting and flexible MOQ notation (`1000`, `1,000 pcs`, `1k`). Ambiguous MOQ ranges are not silently converted; the form asks for a minimum and permits conditions in the description. Phone/employee/lead-time ranges remain bounded self-reported text, not verified numbers.

Native field validation and backend field identifiers drive inline messages/focus. AI Enhance sends only the entered capability summary, presents a reviewable suggestion and evidence questions, and requires an explicit Apply action; certification suggestions do not become certification claims. Public product content is used for optional automatic buyer-prospect research on publication. No company/contact/license fields are automatically sent for that research.

Review → Confirm and Publish retains the exact-retry key, disables duplicate submission, displays “Publishing & notifying admin”, and saves before attempting external services. The response includes the public product summary, supplier ID, HttpOnly management-session information, owner notification status and buyer-research result/status. Credentials are delivered via a Secure production cookie rather than a script-readable bearer token. Exact registration retries do not run paid discovery twice. Existing-account email alone cannot grant access.

Authenticated suppliers can now edit their own private profile; a submitted ID cannot redirect the edit to another account. Email changes remain a separate ownership-verification operation. Profile edits generate owner notifications. Product publication, withdrawal, moderation and suspension remain separate from business verification.

### Real notification delivery and audit

The existing durable outbox remains the delivery authority. Transport preference is Resend → SendGrid → SMTP → webhook. SMTP supports STARTTLS and TLS-on-connect (465). Messages contain plain text plus escaped HTML; HTTP transports use bounded requests, and credentials are never logged. Resend receives a stable idempotency key; SMTP and other transports remain at-least-once, not exactly-once. Supplier authentication links are never sent to a webhook.

Owner recipient resolution supports the authenticated UI setting, then ADMIN_NOTIFICATION_EMAIL, ADMIN_EMAIL, NOTIFY_EMAIL, the existing NOTIFICATION_EMAIL, and SMTP_USER if it is an email address. A saved UI setting has precedence. The explicit MAIL_DELIVERY_ENABLED=false setting remains an operator kill switch; when unset, configured transports are selected automatically. A verified sender/domain may still be required by the provider.

Supplier publication, buyer inquiry, profile updates and lead alerts create private `admin_notifications` records. Supplier access emails are logged separately without copying raw login tokens into the inbox. Owner emails now contain full submitted details, as explicitly requested; privacy copy is updated. `notification_attempts` records transport acceptance/failure metadata. Missing configuration stays `queued_in_admin_inbox`; known transport failures are recorded as failed without rolling back the saved business record. Registration tries supplier access mail and owner notification before returning; inquiries immediately attempt their owner notification. Queued recovery still requires the authenticated mail worker/operator action—serverless background execution is not assumed.

**`sent` means transport acceptance, not proof of inbox arrival.** Webhook acceptance is not email delivery. Full details sent to the selected provider are a deliberate change from the earlier minimal owner-notification policy. Operator authorization, sender verification, destination correctness, provider contracts and retention still matter.

### Private admin manager

Added paginated supplier search/details, profile editing, evidence notes, featured status affecting Marketplace ordering, guarded deletion and complete paginated CSV/JSON exports (10,000-row safety ceiling). CSV cells neutralize spreadsheet formula prefixes. Existing catalog research remains separately labeled rather than being converted into fabricated registered suppliers. Supplier business-review notes do not automatically create verified certification claims.

Added notification inbox/unread count, recipient configuration, explicit test-send action, saved-lead CRM/status filtering/exports and per-supplier buyer research. Existing inquiry/assessment inboxes remain, with one-click supplier research and initial loading. Fixed a refresh race: stale inquiry loads cannot replace an in-progress status selection. Private registry/notification/lead routes require authenticated admin sessions, with no public exports.

ADMIN_TOKEN / STRATEVO_ADMIN_TOKEN / ADMIN_PASSWORD aliases provision the `owner` login; production additionally requires ADMIN_TOTP_SECRET. Named ADMIN_ACCOUNTS_JSON users remain supported. Rotation invalidates old sessions. Missing credentials display a setup prompt: there is **no default password, anonymous admin or fallback bypass**.

This repository's `storage.js` never cached supplier/inquiry business records in localStorage. There is nothing in that format to silently sync. Unknown browser storage is not scanned/uploaded; `/api/suppliers/sync` rejects an unrecognized import with a review/resubmission instruction. This avoids sending Supabase/auth/other-deployment data to an unrelated backend. No client-only persistence or mock production backend was added.

### Schema and privacy

Idempotent migration 005 adds `suppliers`, `platform_settings`, `admin_notifications`, `notification_attempts` and `discovered_leads`. SQLite receives equivalent schema. PostgreSQL RLS and client-role revocation cover the new tables; the migration checksum ledger reapplies the additive change on a new worker. Existing accounts remain visible without a full-table backfill before the first page. Erasure removes related notices/outbox data and supplier metadata while preserving the in-flight-mail guard. Real production migrations were not run by the agent.

The admin page now has a real `web/templates/admin.content.html`. All generated pages are synchronized. New JS assets are explicitly allowlisted; internal reports/tests/validation remain excluded from Vercel serving/deployment.

## Verification and limits

- **183 unit/HTTP tests**: original regressions retained, plus key inference, adapters, grounded schema/provenance rejection, form normalization, notifications, authentication aliases, ownership, retries, profile updates, CRM and transport contracts.
- **13 real PostgreSQL integration PASS groups**, including additive reapplication and the new tables' RLS behavior even after accidental client SELECT grants.
- Three existing browser suites plus the Vercel HTTPS scenario in both storage modes and the new AI/operations HTTPS scenario in both modes: **seven browser executions**. Tested paths include mobile review, actual persistence, Secure sessions, enrichment review, publication, owner notification ledger, instant research, Marketplace/assessment discovery, admin edit/featured/export/configuration, profile ownership and error recovery. Accessibility findings are zero in tested states, not a universal accessibility guarantee.
- New AI/operations browser tests mock only external provider/transport responses, with explicit synthetic company names. Actual HTTP/database/auth/UI paths execute. Unit tests validate real outbound request contracts through controlled fixtures. No synthetic leads are seeded into production or the clean preview.
- Runtime dependency audit reports no known vulnerabilities; no runtime dependencies were added. Nine Bandit findings remain reviewed, not suppressed: fixed `/tmp` path; five fixed-clause/parameterized-SQL findings; preview listener binding; two best-effort mail-attempt exception handlers whose records remain queued. No high-severity finding was reported.

**No AI key or notification transport is configured in this workspace.** The agent cannot read your Vercel secrets, and this sandbox's outbound host allowlist excludes provider/mail hosts. Consequently actual provider search results, managed model/tool eligibility, real SMTP/Resend/SendGrid delivery, webhook destinations and inbox receipt are **not live-certified**. The implementation is not a claim of perfect operation or guaranteed real-world lead quality.

Vercel `/tmp` remains **ephemeral and instance-local**. It cannot provide shared durable submissions, sessions, CRM, notifications, MFA replay state or global cost controls across cold starts/instances. Configure PostgreSQL and STRICT_PERSISTENT_DB=true for real production operations. No browser caching or fabricated success masks this limitation.

## Operator activation and rollback

1. Confirm the Vercel project/production branch and a tested database backup/restore plan. Deploy to an isolated staging environment first. The earlier candidate was published to the approved source branch; no production merge, deployment, DNS change or production-data operation was performed by this agent.
2. Supply one intended AI key in hosting secrets. Remove stale higher-priority keys. Leave AI_BASE_URL / AI_MODEL blank unless deliberately overriding. Use the actual provider/account-supported model and enable its search tool/billing as needed; OpenRouter/Groq require a live search backend, not just chat access.
3. Configure PostgreSQL using one supported URL variable; ensure the backend role can run private-schema migrations. Use strict mode. Confirm `/api/health` reports postgres. Never reuse the production DB in a preview.
4. Provision named MFA admins or a strong owner alias (32+ characters for tokens, 16+ for password) plus a private base32 TOTP seed with at least 20 decoded bytes. Do not paste secrets into chat or commit them. No missing-secret bypass exists.
5. Configure sender MAIL_FROM, the intended notification recipient and Resend/SendGrid/SMTP credentials (or an authorized webhook). If MAIL_DELIVERY_ENABLED=false was previously set, explicitly change it only after authorizing delivery. Set the trusted PUBLIC_BASE_URL and PUBLIC_ORIGIN_VERIFIED=true for supplier access links. Do not derive credential links from untrusted Host headers.
6. In admin, test AI connection, run a narrow live lead search and inspect citations, then explicitly send a notification test and verify it in the destination inbox/provider log. Test supplier confirmation, owner notices, profile update, inquiry, retry and multiple fresh instances. Set up and monitor the authenticated mail worker; queued status is not completed delivery.
7. Review privacy/legal disclosures and retention for the new full-detail email/webhook transfer and stored research. Do not bulk-contact discovered prospects merely because the model assigned a fit score.
8. Rollback by restoring the prior deployment and compatible environment settings, not by dropping new tables. The schema additions are non-destructive; older code will not expose the new manager/data. Retain a working named-admin configuration for rollback because older builds do not recognize the new aliases. Do not overwrite post-backup live submissions without an explicitly approved recovery procedure. Ephemeral data cannot be automatically restored or migrated by this release.
