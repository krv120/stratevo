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

## Content Studio video (fal.ai)

Video generation adds an outbound dependency and real money, so it has its own preconditions:

1. Durable PostgreSQL with `STRICT_PERSISTENT_DB=true` is mandatory outside local development. Jobs submitted from an ephemeral `/tmp` database cannot be reconciled after a restart, and the API refuses to submit them.
2. `FAL_KEY` belongs in the hosting secret manager (`Settings → Environment Variables` on Vercel), scoped to Production. It is read only by `app/fal.py` and never reaches the browser. Do not add it to `.env.example`, `vercel.json` or any `PUBLIC_`/`NEXT_PUBLIC_` variable.
3. `PUBLIC_BASE_URL` and `PUBLIC_ORIGIN_VERIFIED=true` must be set for the signed completion webhook (`/api/video/fal-webhook`); without them the job is still tracked by polling.
4. Start with `VIDEO_SPEND_LIMIT_USD=1.00` and `VIDEO_MAX_JOB_USD=0.50` until the first real clip is reconciled against fal's billing dashboard.
5. `vercel.json` permits `media-src` from `*.fal.media` and `storage.googleapis.com` so the private dashboard can play the clip. Public pages get the same header; it does not allow scripts or styles from those hosts.
6. The first live generation, the fal billing cross-check and webhook delivery to the real host are **not** verified by the repository tests. Treat them as deployment acceptance steps.

## Migration and rollback boundaries

Migrations 001–007 run through `app/connections.py`. Tests cover isolated PostgreSQL bootstrap/concurrency and reinitialization, not a copy of production data. No destructive production migration has run. Existing legacy records remain; retired product workflows are not exposed by the new directory interface.

Before deployment, rehearse application rollback against a restored database. Prefer reverting the application deployment while retaining additive schema when compatibility has been verified. Do not drop directory tables or rewind the production database simply to roll back code: new registrations could be lost. If a data restore is required, pause writes, obtain separate authorization, preserve post-backup changes securely, restore to an isolated instance first, and reconcile before switching traffic. Record the exact previous deployment and restoration evidence.

## Important limitations

- Browser public backup is seven-day, per-browser and public-only; authenticated sync cannot reconstruct missing server accounts or override moderation.
- Strict persistence mode is fail-closed, not database provisioning. Do not enable real submissions without verifying it on the actual host.
- Optional TOTP means password/token strength and secret protection remain essential.
- No live mail, booking completion, production database, DNS or deployment smoke test was performed for this candidate.

## Static public site / Python API deployment (current)

`vercel.json` sets Framework to Other (`null`), runs `python3 scripts/build_static.py`, and publishes `public-site`. Keep the repository root as the Vercel Root Directory. Do not override this output with `web`, `dist` or a framework preset. The build creates public HTML/assets only; source, templates, tests and private data are not copied into it.

Public pages are no longer routed through Python. `/` is a real `index.html`; clean URLs resolve the other pages, with an explicit alias for `/supplier/account`. Public API aliases remain available, while generated pages call `/api/index.py` directly with an explicit API-path parameter. That function URL is excluded from rewrites, so browser requests do not rely on an edge rewrite preserving the original URI. Local dynamic previews remain compatible.

The API permits exact Vercel deployment origins from VERCEL_URL/VERCEL_BRANCH_URL/VERCEL_PROJECT_PRODUCTION_URL when VERCEL=1, plus explicitly configured origins. It does not trust arbitrary Host or forwarding headers. Production still needs durable PostgreSQL, approved public origin, private admin credentials and the preceding launch checks.

Generated SEO/robots/sitemap reflect the build environment. Keep indexing disabled until approved, and rebuild if launch/indexing settings change. Existing public-domain SEO defaults remain www.stratevo.online; do not claim that a Vercel preview URL is the canonical production domain.

A successful build is not live verification. Open the new protected preview while signed in; check the homepage, supplier form, Marketplace, version endpoint and registration. Do not promote a deployment still returning an error. No production promotion is performed by this handoff.
