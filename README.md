# STRATEVO — supplier directory release candidate

A lightweight Python/vanilla-JavaScript sourcing website. Buyers book a sourcing call at **https://app.minup.io/book/stratevo**. Suppliers register in one step and publish their company, focus and description immediately; registration is not verification or an order guarantee.

## Run locally

Python 3.11+:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env, then export it into this shell:
set -a; . ./.env; set +a
.venv/bin/python scripts/build_content.py
.venv/bin/python scripts/create_pages.py
.venv/bin/python -m app.server
```

The local server binds to `0.0.0.0:8000`. Set your own strong admin password/token in the environment before using `/admin`; there is no default login. Do not publish `.env`, private files or database backups. Production uses secure cookies and needs HTTPS.

## Current contract

- `/supplier`: single-step required company, category/custom specialty, description, private contact/email and one accuracy/Terms/Privacy consent. Optional phone, country, city and website. Bare domains are normalized to HTTPS. After the server confirms publication, registration automatically opens Marketplace with the new listing highlighted. The sign-in-link request form has been removed; existing sessions can use My Supplier Account. If the session expires, contact STRATEVO for ownership-verified access help.
- `/marketplace`: search/category-filtered supplier cards, accessible details dialog, external booking CTA. Public APIs exclude contact/email/phone/website/location and scrub recognizable contact strings from public text.
- `/supplier/account`: session-authenticated profile changes, withdrawal, browser-backup clearing. Owner actions never authorize restoration of removed/missing records.
- `/admin`: direct access only. Password or token works without TOTP when no TOTP secret is configured; configured MFA remains enforced. Private directory, moderation, rights operations and mail queue are authenticated.
- `web/storage.js`: public-only seven-day localStorage backup; authenticated reconciliation uses the server's canonical record. **This cannot recreate private records or provide shared durability after backend loss.**
- Booking-only customer conversion. Assessment/inquiry pages prioritize the same booking link, not competing intake forms. No orders or payments.
- No advertising/analytics requests. Optional in-page conversion events contain an allowlisted stage only, with no network transmission or persistence. `booking_opened` does not mean booking completed.

## Persistence and release status

Use durable PostgreSQL for real submissions, with `STRICT_PERSISTENT_DB=true`. SQLite is useful locally; serverless `/tmp` SQLite is ephemeral and instance-local. The clean interface does not change that limitation. Migrations are additive and preserve historical business data; new document uploads remain disabled.

This is a **release candidate, not a deployment or compliance certification**. See [DEPLOYMENT.md](DEPLOYMENT.md), [KEY-SETUP.md](KEY-SETUP.md), [RELEASE-TESTING.md](RELEASE-TESTING.md), [SECURITY-REVIEW.md](SECURITY-REVIEW.md) and [LIVE-COMPARISON.md](LIVE-COMPARISON.md). No production database, DNS or website replacement is authorized by this source handoff.

## Layout

`app/` backend; `api/` Vercel entrypoint; `web/` runtime static assets; `scripts/` generators/package tools; `tests/` active and explicitly retired contracts; `validation/` reviewed release evidence. Run both content generators after template edits. Dependencies are deliberately small; no frontend framework/build is required.
