# Vercel storage and immediate-publication fix

Release: **2026.10.15-vercel-rc1**. Source changes and isolated validation only; not deployed by this agent. This document supersedes earlier release reports on storage and publication policy.

## Root cause

`api/index.py` rejected all POSTs, plus API GETs, unless exactly `DATABASE_URL` existed. It returned the reported “Persistent database is not configured.” message before the shared handler ran. Workflow guards duplicated this assumption. Catalog/discovery used a separate database resolver, and deployment startup did not guarantee migration execution. No live production credentials, database, mail provider or hosting settings were accessed to establish this source-level diagnosis.

## Changed contract

- The six requested database variables are checked in priority order: `DATABASE_URL`, `STRATEVO_DATABASE_URL`, `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, `NEON_DATABASE_URL`, `SUPABASE_DB_URL`. Blank values are skipped.
- `postgres://` becomes `postgresql://`. Known client-only pooler/Prisma hints are removed. Duplicate TLS modes retain the strongest mode; remote hosts default to `sslmode=require` when no explicit mode exists. Valid libpq options, encoded credentials and certificate settings are preserved. Connection errors never include the DSN in HTTP responses.
- All workflow/catalog/discovery PostgreSQL connections use `prepare_threshold=None`, `autocommit=False`, a connection timeout, transaction rollback on error and transaction-local private search path. A configured-but-broken PostgreSQL connection **does not silently fall back**, which would split real data.
- Without PostgreSQL, deployed modes use `/tmp/stratevo_runtime.sqlite3`, with private permissions, foreign keys, serialized writes and automatic schema initialization. `STRICT_PERSISTENT_DB=true` opts into rejection instead. Local development keeps its private SQLite paths.
- PostgreSQL migrations 001–005 run automatically on the first database use in each worker, before any application query, inside a transaction protected by a PostgreSQL advisory lock. A private checksum ledger skips unchanged migrations. SQL remains independently runnable and idempotent. SQLite uses equivalent dialect-specific schemas, including FTS and legacy outbox-column upgrades; PostgreSQL-only SQL is not sent to SQLite.
- Research/catalog tables initialize empty. **No fabricated supplier/catalog rows are seeded.** No authorized real catalog dataset was provided for automatic import. Existing records are retained; authenticated owner imports remain supported by `app.catalog.import_json`. New published products enter marketplace matching immediately.

### Immediate publication and account access

The public form now has Review → Back to edit / Confirm and Publish. Confirmation validates privacy/content consent, saves private account data and a public product, and sets a Secure (in production), HttpOnly, SameSite=Lax, `/api`-scoped management cookie. It does **not** falsely mark the email verified. Email confirmation remains available separately; legacy pending accounts retain their old confirmation gate.

A separate private `market_publications` table records the new publication entitlement and hashed registration retry key. Exact lost-response retries recover an authenticated session without inserting duplicate products. Email alone never grants access to an existing account; changed retry payloads, expired recovery and suspended accounts are rejected. Ownership, withdrawal, moderation, erasure and retention gates remain intact. Newly published but email-unconfirmed accounts are not treated as abandoned legacy registrations by retention.

The portal routes publisher sessions through its authenticated API to the current account page, without widening the cookie path. Legacy approved-supplier and manager profile views remain supported. `/supplier.html`, `/supplier-account`, `/supplier-account.html` and other listed page aliases redirect to the canonical application routes.

### Proxy, diagnostics and exposure

Only the Vercel runtime trusts Vercel's single-address forwarding headers; malformed/multi-address values fall back to the connection address. Other hosts do not trust forwarding headers. Production Origin checks allow HTTPS apex/www and an explicitly configured public origin, not arbitrary request Host headers. Cross-site browser mutations remain blocked. Global quotas remain intentional and can still return legitimate 429s.

`/api/health` and admin connection diagnostics identify `postgres`, `ephemeral_fallback` or `sqlite_local` without disclosing a DSN. Non-blocking form notices and submission results disclose ephemeral storage. Health failure does not disable frontend forms.

Internal Markdown reports, the screenshot gallery and validation artifacts are excluded from the Vercel bundle. Static delivery remains an explicit allowlist; internal reports, migrations, private paths and evidence return 404. Templates are regenerated with `scripts/create_pages.py`. Vercel's function bundle explicitly includes both `web/**` and `migrations/**`.

## Important limits — not “flawless without a database”

Vercel `/tmp` is **ephemeral, per-instance storage**. It is not persistent/shared infrastructure. A new instance can have an empty Marketplace and reject another instance's account session; restart/redeploy can lose all submissions, email jobs, usage counters and MFA replay state. The fallback enables flows within a worker but cannot guarantee cross-instance end-to-end continuity. Its rate limits and AI budgets are also instance-local. Use PostgreSQL and strict mode for real production data and financial/resource controls. This release does not copy ephemeral records into PostgreSQL or rescue already-lost records.

Missing AI/search credentials still produce honest unavailable states. Missing or disabled SMTP cannot deliver email or recover an expired/signed-out account session. Immediate publication does not need SMTP; future email sign-in does. Production admin still requires named accounts with MFA; there is no default/bypass administrator.

Live Vercel packaging, managed transaction-pooler behavior, external providers, SMTP inbox receipt, multi-instance behavior, legal disclosures and backups have **not** been certified. No production deployment, migrations, DNS changes or real data operations were performed. No automatic push is performed because a branch push may now trigger your Vercel production integration.

## Validation

- **159 distinct unit/HTTP tests** pass, including the actual Vercel adapter with production flags, strict rejection, URL aliases, TLS normalization, client-IP/origin handling, secret-free diagnostics, publication/session/retry, inquiries and named-admin MFA.
- **12 real PostgreSQL integration PASS groups**: existing 10 plus two fresh-database cold-start/pooler-configuration groups. Tests cover migrations/reapplication, concurrency, full-text search, discovery, RLS, rollback, quotas, publication and account controls.
- All **three existing browser suites** pass, plus the new Vercel-adapter browser scenario against **both ephemeral SQLite and PostgreSQL**. The latter uses local HTTPS and real Secure cookies, checks mobile review/axe, lost-response recovery, immediate publication, account/portal/withdrawal, inquiry and production MFA/admin. No browser exceptions in tested paths; axe reports zero findings in tested states.
- Providers and SMTP remain mocked/disconnected; no paid/provider or outbound mail tests were run. Browser transport failure is deliberately injected.
- Runtime dependency audit: no known vulnerabilities. Bandit retains seven findings: four fixed-clause/parameterized-SQL B608 findings; the requested fixed `/tmp` path (B108, mitigated by private creation and no symlink following, but inherently ephemeral); preview listener binding B104; best-effort immediate-mail exception handling B110 with saved outbox recovery. No findings were suppressed.

Current logs are in `validation/`. Earlier audit documents are historical, not proof of current production behavior.

## Deployment checklist and rollback

1. Back up the real PostgreSQL database (if any), verify restoration, and confirm which Vercel project/branch serves production. Test this candidate on an isolated preview first; do not reuse production data in preview.
2. Set one database variable to the intended PostgreSQL URL. Prefer the provider's recommended pooled URL; use certificate verification where available. The backend role must be able to create/migrate the private schema and access its RLS-protected tables; never expose that role/DSN to browsers. If `DATABASE_ENVIRONMENT` is set, it must match the deployment. An unset binding is now optional, not proof of isolation.
3. Remove an accidental `APP_ENV=local` override from a Vercel production environment. Keep secure cookies and same-origin framing. Set `STRICT_PERSISTENT_DB=true` for durable production operation. Check health for `storage.mode=postgres` after deployment; 503 on configured storage failure requires operator attention, not fallback.
4. Verify public URL/HTTPS redirects. Configure the trusted `PUBLIC_BASE_URL` and `PUBLIC_ORIGIN_VERIFIED=true` for email links. Configure and authorize SMTP/worker delivery, named MFA admins and any AI/search providers separately. Never put secrets in repository files or chat.
5. Test registration, immediate Marketplace visibility, account access, withdrawal, a buyer inquiry, admin inbox, email confirmation/recovery and multiple fresh browser sessions/instances. Test startup/migrations and real provider pooler connections in staging.
6. Rollback: restore the prior Vercel deployment with the same appropriate storage configuration. Changes are additive; retain `market_publications` and the migration ledger unless a separately approved recovery plan calls for otherwise. Older code ignores the new publication entitlement, so email-unconfirmed newly published products will no longer be publicly visible under old code. Do not delete tables or restore a backup over new live submissions without explicit authorization. Ephemeral data has no automatic rollback/recovery guarantee.
