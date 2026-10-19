# Deployment and rollback — approval required

## Preconditions

1. Obtain explicit approval for the exact source revision, target and deployment window. A branch push may trigger a hosting build; it is not permission to replace production.
2. Verify an encrypted, access-controlled backup of the real database and a restore in an isolated target. Record existing deployment/environment versions without copying secrets into source or chat.
3. Provision durable PostgreSQL and set `DATABASE_URL` and `STRICT_PERSISTENT_DB=true`. Use least-privilege database credentials and provider-required TLS. Do not treat `/tmp` SQLite or browser backup as persistence.
4. Configure a strong unique `ADMIN_PASSWORD` or `ADMIN_TOKEN`; optional `ADMIN_TOTP_SECRET` enables required MFA for that login. Rotate any previously exposed secrets. Verify authentication, rate limits, secure cookies and access restrictions in the target.
5. Confirm sender/domain configuration before enabling mail. Authorize a real delivery test separately; local transport mocks do not prove delivery.
6. Resolve required establishment/address/registration/VAT disclosures where applicable with legal advice. Supplied legal contact is Vasilis Krevatsoulis, info@stratevo.store, +30 6989472740. Do not invent missing details. Review the browser-storage purpose/exemption and external booking privacy disclosure before launch.
7. Verify `PUBLIC_BASE_URL` and explicitly set `PUBLIC_ORIGIN_VERIFIED=true` on the target. Keep `SITE_LAUNCH_APPROVED=false` and `SITE_INDEXABLE=false` until deployment, legal, canonical/redirect and persistence checks are approved. No ranking or indexing promise is made.

## Deploy candidate only after approval

Vercel configuration is in `vercel.json`; `api/index.py` uses the same request handler exercised by integration tests. Static/HTTP tests do not substitute for a real Vercel deployment. The connector was disconnected during this audit; no deployment was performed.

Run generators and the documented tests, deploy the approved revision, then verify every public route, `/admin`, `/supplier/account`, assets, HTTPS/security headers, canonical host redirects, robots/sitemap, and actual PostgreSQL persistence across distinct instances/restarts. With synthetic authorized data, verify registration → immediate public listing → details → booking navigation, owner changes/withdrawal, moderation, erasure and retry behavior. Delete test data only under the approved procedure. Never send test messages to real suppliers.

## Migration and rollback boundaries

Migrations 001–007 run through `app/connections.py`. Tests cover isolated PostgreSQL bootstrap/concurrency and reinitialization, not a copy of production data. No destructive production migration has run. Existing legacy records remain; retired product workflows are not exposed by the new directory interface.

Before deployment, rehearse application rollback against a restored database. Prefer reverting the application deployment while retaining additive schema when compatibility has been verified. Do not drop directory tables or rewind the production database simply to roll back code: new registrations could be lost. If a data restore is required, pause writes, obtain separate authorization, preserve post-backup changes securely, restore to an isolated instance first, and reconcile before switching traffic. Record the exact previous deployment and restoration evidence.

## Important limitations

- Browser public backup is seven-day, per-browser and public-only; authenticated sync cannot reconstruct missing server accounts or override moderation.
- Strict persistence mode is fail-closed, not database provisioning. Do not enable real submissions without verifying it on the actual host.
- Optional TOTP means password/token strength and secret protection remain essential.
- No live mail, booking completion, production database, DNS or deployment smoke test was performed for this candidate.
