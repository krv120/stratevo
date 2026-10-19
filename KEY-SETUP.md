# Configuration without sharing secrets

Copy `.env.example` for local development. Put production secrets into the hosting secret manager, never source control/chat. Rotate previously exposed credentials rather than reusing them.

- `DATABASE_URL`: durable PostgreSQL connection string with the hosting provider's required TLS settings. `STRICT_PERSISTENT_DB=true` rejects ephemeral fallback for real production use.
- `ADMIN_PASSWORD` **or** `ADMIN_TOKEN`: strong unique value; no default. `ADMIN_TOTP_SECRET` is optional; when configured, correct MFA is required and replay is rejected. Account-scoped roles remain supported by the backend.
- `PUBLIC_BASE_URL=https://www.stratevo.online`; buyer booking is fixed in code to `https://app.minup.io/book/stratevo` and cannot be overridden by an environment variable.
- `SITE_INDEXABLE=false` until the readiness checklist is approved.
- `MAIL_DELIVERY_ENABLED=false` until actual outbound mail has been separately authorized. Configure a supported API mail transport, SMTP or approved webhook, a verified sender and `ADMIN_NOTIFICATION_EMAIL`. Stdlib SMTP uses TLS-on-connect on 465 or STARTTLS on 587. Missing delivery credentials do not constitute delivery proof; monitor the authenticated queue.
- `RIGHTS_ERASURE_APPROVED` and retention settings are operational safeguards, not blanket authorization to delete records. Use approved, verified requests with backup/retention review.

See `app/settings.py`, `app/admin_auth.py`, `app/mail_policy.py` and `app/maintenance.py` for complete compatibility settings. Do not enable obsolete external integrations. This application does not need third-party model or search credentials.
