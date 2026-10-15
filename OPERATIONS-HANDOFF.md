# Operational handoff — 12 October 2026

This is reconstructed source, not a recovered or verified copy of the deployed site. Do not replace production based on local tests. No production deployment, migrations, email, deletion, DNS change, merge or push was performed in this audit.

## Configuration and service ownership

Use `.env.example` as a field reference, **not as production-ready settings**. Set secrets in hosting's private environment store; never in chat, Git, URLs or browser code.

- Set `APP_ENV` to `preview`, `staging` or `production` as appropriate. Production Vercel cannot be downgraded to local mode. Use separate database credentials/projects for every environment. `DATABASE_ENVIRONMENT` must match. This variable is an operator assertion, not independent proof of database identity: verify project/database IDs in the hosting consoles before connecting.
- `PUBLIC_BASE_URL` is the HTTPS origin used in email, never the request Host. Outside local/test, `PUBLIC_ORIGIN_VERIFIED=true` requires operator verification. `CANONICAL_BASE_URL` defaults to the previously supplied apex `https://stratevo.online`, not a verified redirect decision. Verify apex/www routing and canonical ownership before changing either. No `.store` or `.co` business identity is selected by this code.
- `BOOKING_URL` defaults to the owner-supplied Minup booking route. It is centrally rendered; backend constants resolve at process startup, so redeploy after changes. No booking uptime or booking receipt claim is made.
- No email contact is published unless `PUBLIC_CONTACT_EMAIL` is set and `PUBLIC_CONTACT_VERIFIED=true`; otherwise the sourcing inquiry is the contact route. This does not establish a legally sufficient rights-contact process.
- Indexing needs production mode **and** `SITE_INDEXABLE=true`, `SITE_LAUNCH_APPROVED=true`, `PUBLIC_ORIGIN_VERIFIED=true`. Keep disabled until operational and legal approvals. Private account, AI and inquiry routes stay noindex.
- Retain secure cookies and same-origin framing in production. Preview embedding is local-only by operational policy; production configuration rejects it.

## Named administrators and recovery

`ADMIN_ACCOUNTS_JSON` is a private array of account objects with `id`, `password_hash`, `totp_secret`, and optional boolean `disabled`. No example real credential or seed is supplied. Generate a password hash privately with `python -m app.suppliers hash-password` (16+ characters, PBKDF2-SHA256 600,000 rounds). Provision a random base32 authenticator seed of at least 20 decoded bytes using an approved password manager/enrollment process; never expose it through this website. Production requires named accounts and MFA. There is no public enrollment, password reset or seed-return endpoint.

Provision two separately controlled administrators if your operating policy allows it. Changing a password hash/seed, removing an account or setting `disabled=true` invalidates that named account's sessions on their next request. `/api/admin/revoke-sessions` revokes current sessions for a named actor; also disable/rotate the account to prevent re-login. TOTP counters cannot be replayed. Maintain an accurate server clock.

Recovery is an **operator/hosting-console procedure**, not a complete self-service account-management product: verify the administrator through your approved process, privately replace their credentials, redeploy, verify old-session denial, and record the recovery outside public logs. Loss of all hosting/admin access requires the hosting provider's recovery process. Legacy password-only login is non-production compatibility only. Rotate historically exposed credentials; never reuse them.

## Staging, migrations, least privilege and rollback

1. Identify the actual live repository/build/runtime/domain configuration. Compare with this reconstruction; do not assume equivalence.
2. Approve a maintenance plan; take an encrypted database/object backup using the operator's existing tooling. Record timestamp, checksum, schema version, access controls and recovery owner without placing data in Git.
3. Restore the backup into an isolated, access-restricted staging database. Disable SMTP, public AI, discovery and scheduled jobs; verify isolation before opening a preview. Prefer synthetic records unless real-data staging is explicitly authorized.
4. Apply additive migrations `001` through `005` in order using the migration role. `005_operational_hardening.sql` is rerunnable and contains no business-record deletion. Do not run the application initialization CLI against production as an automatic deployment hook.
5. Use a separate server-only runtime role with only required schema/table DML. Do not grant client `anon`/`authenticated` access. RLS/client-role denial is tested; a genuinely least-privileged hosting role must still be provisioned and verified by the owner. The repository does not establish your database credential privileges.
6. Verify schema presence, real `/api/health`, account verification/publication, private-document authorization, named admin MFA/revocation, inquiry retries, pagination, suspension, privacy dry runs, worker claims and quota behavior on staging.
7. Rehearse rollback: stop new writes/jobs, preserve post-deployment writes separately, restore the prior application build against the additive schema where compatible. Do not drop new tables to roll back code. Database restoration requires an approved reconciliation/deletion plan, not blind overwriting of newer records.
8. Obtain explicit promotion authorization only after the live service/legal smoke tests below. No authorization is implied by this handoff.

## Mail worker and safe delivery validation

`MAIL_DELIVERY_ENABLED=false` is the default. Configure authorized `MAIL_FROM`, verified `NOTIFICATION_EMAIL`, SMTP credentials/STARTTLS and a trusted public origin first. Owner notifications can remain unassigned when configuration or queue capacity is unavailable without deleting the underlying submission.

The existing CLI `python -m app.suppliers send-mail` processes up to ten jobs. A serverless-compatible `GET` or `POST /api/jobs/mail` handles one job when given `Authorization: Bearer <CRON_SECRET>`; the secret must be at least 32 characters. Set this through the host's secret facility, never a query parameter. HEAD does not send mail. **No scheduler has been installed.** An owner-approved scheduler must supply the secret header, monitor non-2xx results/backlog, and run frequently enough for the registration volume. Check the hosting plan's scheduling limits; a daily-only scheduler is inadequate for prompt verification. No paid service was selected or subscribed to.

Global SMTP-attempt allowance is 60/hour. Claims last 120 seconds; failed attempts retry after the lease and stop at five. Each SMTP socket operation has an eight-second timeout; this is not an absolute end-to-end delivery deadline. Serverless termination can interrupt a send; expired leases allow recovery. SMTP delivery is **at least once**, never exactly once. A crash after SMTP acceptance but before the DB update can duplicate mail. Message IDs are stable but do not guarantee recipient deduplication.

Expired/used/suspended authentication links are cancelled before transport and their queued bodies cleared. A token can still expire/be consumed after that check, or while an accepted email is delayed: consumption always rechecks it. Existing recipients retain already-delivered messages. Owner retry does not reactivate old authentication links. Status metadata distinguishes sending, SMTP accepted, retry, exhausted, cancelled/expired and rate-limited; SMTP acceptance is not inbox receipt. A process crash may leave `sending` until a later claim.

Only after explicit recipient authorization: enable mail on staging, send a controlled verification, inspect acceptance **and actual inbox receipt**, test resend/single use/expiry/restart, then separately validate sender DNS/authentication and delivery monitoring. No such live test was performed here.

## AI and resource limits

Public AI remains password-free. Keep provider keys/model/base URL server-only; configure the provider's own spending cap/alerts where supported. `PUBLIC_AI_ENABLED=false` is the emergency stop. Daily request and concurrency limits are durable; failed attempts count and abandoned leases expire. They are not a euro budget. Metrics expose daily outcomes, aggregate elapsed milliseconds and provider-reported token counts where supplied; missing usage is not proof of zero billing. Browser cancellation does not guarantee cancellation of provider computation or charges.

Public model tool calls cannot silently turn inferred details into a catalog query. Users must submit the explicit qualification form. Deterministic results remain at most three anonymized leads. Live multilingual quality, Greeklish/corrections and adversarial prompt behavior need approved model testing; mocked transport tests are not that evidence.

Storage controls cover accounts/pending accounts, products, base64 photo bytes, inquiries, outbox records, report count and rate-bucket count. Image decoding has two durable leases by default, expiring after 60 seconds, plus existing 500 KB/12 MP/single-image reencoding limits. Registration bodies no longer reserve PDF capacity. These are application ceilings, not a total hosting bandwidth/CPU/connection budget. Configure trusted edge limits through an approved host; no arbitrary forwarded IP headers are trusted. A global quota can be consumed by an attacker to deny other users service; monitor this tradeoff.

## Uploads, moderation and privacy operations

New PDF uploads are blocked; there is no flag that simply labels unscanned uploads safe. Implement and test actual quarantine/scanning before reconsidering acceptance. Existing authorized document download remains available as a restricted attachment; use an isolated viewer, not public malware-upload services. Product images are reencoded but OCR/logo/watermark identity detection is not implemented; review reported images manually.

Email confirmation automatically publishes. Internal review is not a publication approval gate. Suspending an account revokes sessions/tokens and hides its published listings. Restoration allows fresh sign-in but does not republish hidden/withdrawn products. Suppliers can withdraw listings. Active limit is 50; retained history limit is 500/account. Marketplace browsing uses SQL pagination across all eligible rows; manager registry has 25-row pages. The **research matcher**, separately, still considers at most 2,000 recent Marketplace candidates plus its bounded private-research set; this is not exhaustive catalog search.

Listing reports are private, rate-bounded and do not automatically remove products. The manager workspace includes report review, reasoned suspension and private export/correction/deletion controls. Customer rights requests require verified human handling: an inquiry ID/email alone is not authentication. Supplier session holders can export their own profile via `/api/marketplace/export`. Exports exclude raw documents/access tokens and include product metadata; image/document binaries need separately authorized retrieval. Supplier email changes and full public-product editing are not implemented by correction controls: use a new verified account flow or staff-assisted withdrawal/relisting, not an unverified email overwrite.

Business-data retention is **off by default**. Obtain controller/legal approval before setting any `RETENTION_DAYS_*` value. No legal period is chosen here. Dry run:

```sh
python -m app.maintenance --environment staging
```

After a verified backup, identity/policy approval and review of counts, set `RETENTION_APPLY_APPROVED=true` privately and explicitly run:

```sh
python -m app.maintenance --environment staging --apply
```

Environment confirmation must match. The business-record batch is limited to 100; rerun supervised batches as appropriate. Closed inquiries, abandoned unverified accounts, retained documents and sent-mail/operational records have separate policies. All configured day thresholds currently measure age since record creation, not time since closure or mail acceptance; approve that exact policy before enabling it. Applying also removes expired/consumed authentication tokens, expired sessions and old technical rate buckets. In-flight email leases block related record erasure. **No retention schedule has been activated.** Named-admin direct erasure additionally requires `RIGHTS_ERASURE_APPROVED=true` and exact-ID confirmation. Keep it false until procedures are approved.

Erasure covers live linked records, documents, products, tokens, sessions, relevant outbox/jobs and entity-linked events. It cannot recall delivered emails or delete provider logs/backups automatically. Keep a restricted erasure ledger outside the restored dataset; reapply authorized deletions before making any restored backup accessible. Approve encrypted backup retention/access/destruction, legal holds, email mailbox deletion and processor deletion workflows separately. Do not store that ledger or exports in Git.
