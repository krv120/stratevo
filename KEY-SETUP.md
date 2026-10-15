# STRATEVO hosting setup — current AI/operations release

This guide supersedes the older compatible-chat-only, password-hash-only and email-before-publication instructions. See AI-OPERATIONS-RELEASE-2026-10-15.md for implementation details and limitations. Source publication is not deployment or proof of live service access.

## Keep credentials private

Configure server-side secrets in the hosting project running this Python application. For Vercel: Project → Settings → Environment Variables → select the intended environment. Apply changes through an authorized new deployment. Never put secrets in GitHub, chat, frontend code or browser storage; do not use NEXT_PUBLIC_ or VITE_ prefixes. Use separate preview credentials and databases.

## Owner administrator login

There is no default password, public fallback access or automatic administrator creation from an email address.

The simplest owner setup is:

- `ADMIN_PASSWORD`: a unique password-manager-generated value, minimum 16 characters; 24+ recommended.
- `ADMIN_TOTP_SECRET`: a Base32 TOTP seed containing at least 20 random bytes. MFA is mandatory in production.

Generate the seed on your own trusted computer (not in chat or CI logs):

```sh
python3 -c "import base64,secrets; print(base64.b32encode(secrets.token_bytes(20)).decode())"
```

Store the output privately in the hosting variable and add the SAME key manually to your authenticator app as a time-based account named STRATEVO owner. Keep a secure recovery copy. After an authorized deployment, sign in at `/admin` with username `owner`, your password and the current six-digit code.

Precedence: `ADMIN_ACCOUNTS_JSON` overrides aliases; otherwise `ADMIN_TOKEN`, then `STRATEVO_ADMIN_TOKEN`, then `ADMIN_PASSWORD`. Token aliases require at least 32 characters. Do not set multiple alternatives unintentionally. Do not remove intentional existing named-admin configuration without checking with its owner. `ADMIN_PASSWORD_HASH` alone is a legacy setting and does not provision a production MFA account.

Named accounts use `ADMIN_ACCOUNTS_JSON`: a JSON array of objects with `id`, `password_hash` and `totp_secret`. Generate the password hash privately with `python3 -m app.suppliers hash-password`. Each administrator should have their own credentials and authenticator seed. Never publish the resulting JSON.

`/api/admin/setup` reports only missing/invalid/ready configuration, not account names or secret values. A ready result means the local configuration validates, not that someone has successfully signed in. If locked out, an authorized hosting administrator must repair/rotate the settings and deploy. Rotation revokes old sessions; no public reset bypass exists.

## AI and actual external discovery

Set ONE intended provider key. Resolution order is:

`OPENAI_API_KEY`, `STRATEVO_AI_API_KEY`, `AI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`.

Remove stale higher-priority keys. `AI_PROVIDER` can explicitly select the provider; otherwise the key variable/prefix is detected. Leave `AI_BASE_URL` and `AI_MODEL` unset unless deliberately overriding. A key automatically enables live AI attempts; there is no secondary enable flag. Key presence does not establish validity, billing, model access or internet access.

For Gemini, set `GEMINI_API_KEY` and use the native default Gemini 2.5 Flash adapter; no OpenAI-compatible base override or Brave key is necessary for native grounded discovery. Native Anthropic, OpenAI search and Perplexity citations are also supported. OpenRouter/Groq/custom chat endpoints need a separate retrieval backend such as `BRAVE_SEARCH_API_KEY`; chat memory is not live search. Provider search/model features must be enabled and available to the account.

Use the AI Lead Finder on `/marketplace`, `/assessment`, `/supplier-account` or `/admin`. It separates self-reported Marketplace matches from source-backed external prospects. The engine requests 5–8 leads but returns fewer rather than fabricate companies, certifications or citations. Results are not verified suppliers, actual RFQs or confirmed buying intent.

In `/admin`, test the AI connection and online search, then run a narrow lead query and inspect its sources. These actions make real calls and may incur charges. Set provider spending limits and application quotas. Contract tests with synthetic responses are not successful live-provider verification.

## Persistent database and trusted URLs

- Configure `DATABASE_URL` or a supported PostgreSQL alias and set `STRICT_PERSISTENT_DB=true` for durable production operations.
- Back up and verify restoration before authorizing production schema changes. The application performs additive idempotent schema initialization; the database role must have appropriate migration permissions. Do not run a preview against the production database.
- Vercel `/tmp` SQLite is ephemeral and instance-local, NOT a shared durable fallback for submissions, admin sessions, leads or MFA replay protection.
- Set `PUBLIC_BASE_URL` to the intended HTTPS origin, `PUBLIC_ORIGIN_VERIFIED=true` only after verification, and `COOKIE_SECURE=true` for hosted HTTPS.

## Owner notifications and supplier access email

Set `MAIL_FROM` to a sender authorized by your mail service and set `ADMIN_NOTIFICATION_EMAIL` to the authorized owner destination. Alternatives are `ADMIN_EMAIL`, `NOTIFY_EMAIL`, legacy `NOTIFICATION_EMAIL`, or an email-valued `SMTP_USER`. A recipient saved through the authenticated admin notification panel takes precedence.

Transport selection is Resend → SendGrid → SMTP → webhook:

- Resend: `RESEND_API_KEY`.
- SendGrid: `SENDGRID_API_KEY`.
- SMTP: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_PORT` (587 STARTTLS or 465 implicit TLS).
- Webhook: `NOTIFICATION_WEBHOOK_URL`; webhook acceptance is NOT email delivery, and authentication links are not sent to webhooks.

If `MAIL_DELIVERY_ENABLED=false` is set, it deliberately prevents delivery. Change it only when the recipient, sender, transport and sending authorization are verified. An unset flag permits configured transport selection.

Publication, profile updates and buyer inquiries save notification intent alongside business data, then attempt immediate delivery. Missing configuration queues notices in the admin inbox; a delivery failure does not erase the submission. `sent` means transport acceptance, not inbox receipt. In admin, explicitly use Send Test Notification Email and verify arrival in the authorized recipient's inbox. Do not send real test mail without permission.

Schedule the authenticated mail worker / `python3 -m app.suppliers send-mail` on an appropriate backend to recover queued work. Serverless background execution is not assumed. Monitor exhausted attempts and transport errors.

## Publication and manager workflow

Supplier Preview Listing → Confirm and Publish persists the record, publishes its product immediately and establishes a scoped HttpOnly management session. Email confirmation and staff approval are NOT publication prerequisites and do not establish business verification. Internal company/contact/license details remain private.

At `/admin`, use Supplier Submissions & Marketplace Manager, Admin Notification Inbox & Email Configuration, the discovered-lead CRM and Customer sourcing inbox. Refresh panels to see new submissions. The original storage.js did not cache business submissions: there is no invented localStorage import; unknown imports are rejected for review.

## Verify before production use

Use isolated staging first. Verify administrator login/MFA, PostgreSQL persistence across instances, supplier publication and private account edits, real AI evidence, owner/supplier email receipt, inquiry visibility, retries and recovery. Check privacy/legal disclosures for full-detail notifications and stored prospect research. No source archive or automated fixture suite certifies these live services.

## Local development

Environment files are not loaded automatically. Use shell environment variables or an ignored, access-restricted `private/local-config.json`, then:

```sh
python3 scripts/run_preview.py private/local-config.json
```

Restart after changing settings. Never put private configuration under web/ or include it in an archive. Use production MFA and HTTPS settings in hosted environments.
