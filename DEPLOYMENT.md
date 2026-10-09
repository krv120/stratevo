# Deployment handoff — Vercel + private PostgreSQL/Supabase

This is a new application candidate. First confirm which existing Vercel project serves `stratevo.online`; do not overwrite the current site without a rollback plan. No production deployment was performed during this work.

## 1. Persistent private database

Use PostgreSQL (e.g. Supabase's server-side pooler connection) with SSL. Install `requirements.txt` in your migration/import environment. Keep `DATABASE_URL` secret and server-side.

Run `migrations/001_private_platform.sql` as the database owner. It creates `stratevo_private`, application/token/session/outbox/audit/rate-limit tables and the research index. The schema must **not** be in Supabase's exposed API schemas. Client roles `anon` and `authenticated` have no schema/table grants and no RLS policies. Backend operations use the owner role; never distribute that connection string to a client.

Example using a securely configured environment (never put credentials in command history):

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_private_platform.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/002_private_discovery.sql
# Optional: import only your actual reviewed private file, when available.
# python3 -m app.catalog private/reviewed-research.json
```

The owner privately supplies research files; they are not in Git or the deployment bundle. Test the deployed catalog count/search after importing. No private owner catalog is bundled. Do not reconstruct missing rows or import test fixtures as real suppliers.

Local `python3 -m app.suppliers init` only initializes workflow tables; hosted installation requires the full SQL migration for catalog tables and access hardening.

## 2. Server-side configuration

Set environment variables in hosting settings; rotate all previously exposed secrets:

- `DATABASE_URL`: server-only Postgres connection with SSL.
- `PUBLIC_BASE_URL`: canonical HTTPS origin, e.g. the verified production domain. No path/trailing slash needed. Email links use only this value, never a request Host header.
- `ADMIN_PASSWORD_HASH`: output of `python3 -m app.suppliers hash-password` for a fresh 16+ character password.
- `COOKIE_SECURE=true`.
- `APP_ACCESS_TOKEN`: optional separate research-only token; manager sessions also grant research access.
- `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`: authorized STARTTLS email service with verified sender/SPF/DKIM/DMARC.
- `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`: optional compatible model configuration. Keep unset for explicitly catalog-only operation.

The admin password is hashed with salted PBKDF2-SHA256, 600,000 rounds. No historical admin code is embedded. Production should add MFA and named manager accounts.

## 3. Vercel

Import this repository/working branch into a **preview project first**. Python handler: `api/index.py`; rewrites in `vercel.json` route the website and API to that function. `web/**` must be included. `.vercelignore` and the function exclusions keep private data and secrets out of bundles.

The function refuses data APIs when `DATABASE_URL` is missing. Never use local SQLite or `/tmp` for serverless persistence. Apply migrations before traffic is enabled. Python dependencies are pinned in `requirements.txt`.

The entry point and config have not been deployed to Vercel here. Verify platform compatibility, route rewriting (including `/supplier`, `/admin`, and `/api/health`), bundled static files, origin headers, Secure cookies and request duration in a real preview before promotion.

## 4. Mail processing

Configure an external scheduler/worker to run `python3 -m app.suppliers send-mail` every minute with the same environment and database. This is a bounded batch sender, not a persistent server. On a serverless-only deployment, provision a proper authenticated scheduled queue consumer before go-live; no unauthenticated queue endpoint is provided.

The manager's “Send next queued email” control is a manual fallback. Queued emails are not sent automatically by an application request. The UI distinguishes SMTP configuration from delivery.

Verify actual inbox delivery, resend behavior, link expiry and one-time use. Failed jobs use a short lease and stop after five attempts. Monitor and handle exhausted or expired jobs; do not blindly resend stale links. SMTP acceptance is not proof of inbox receipt.

## 5. Launch gate — not optional

- Obtain the real operator's privacy/contact/retention terms without fabricating or prematurely publishing identity details.
- Add license malware scanning/quarantine, retention/deletion tooling and restricted backups. Current PDFs are stored as base64 in the private database (2 MB each), not public object storage.
- Add edge abuse protection (trusted per-client rate limits/bot defense), storage quotas and monitoring. Current durable workflow rate limits are global and conservative; AI's rate limiter is process-local.
- Review admin password recovery, session revocation, MFA, multi-manager audit identity and supplier suspension requirements. Current workflow deliberately has only final approval/rejection, not a full identity-management console.
- Verify hosted anonymous/authenticated role denial, private document access, CSRF origin checks, Secure cookie behavior and no source/bundle exposure.
- Confirm fresh AI credentials, provider data-retention terms, Greek/English conversation quality, prompt injection resistance, cost limits and graceful errors. Selected research text is untrusted evidence; no order/payment tools exist.
- Test email delivery and complete application/verification/approval/rejection/login/logout flows on the real deployment and physical mobile devices.
- Back up the current site and database; only then promote and attach the production domain.

No payment/order marketplace or guarantee of supplier certification is part of this release.
