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

## Content Studio (fal.ai video)

`/admin` now includes a private Content Studio panel that submits one validated text-to-video job to fal.ai's official Queue REST API, tracks it asynchronously (status polling plus a signed completion webhook), stores the request id, video URL and computed cost in `video_jobs`, and refuses to submit when the configured monthly spending limit would be exceeded. `FAL_KEY` is a server-side environment variable only; the browser never receives it. Nothing is published and no batch generation exists. Setup, the exact key location, cost semantics and verified/unverified boundaries are in [docs/FAL-VIDEO-STUDIO.md](docs/FAL-VIDEO-STUDIO.md).

## Content pipeline (40 videos, captions, scheduling)

`/admin` also contains a **Production line** panel that writes 40 distinct
faceless vertical concepts (hook, script, prompt, TikTok and Instagram copy),
queues approved ones through the budget-checked fal.ai integration, burns a hook
and word-timed subtitles into each clip at 1080x1920 with ffmpeg, stores the
result behind an unguessable `/media/<token>.mp4` URL, plans 30 days of
Europe/Athens slots and submits them to TikTok/Instagram through Buffer's GraphQL
API. `BUFFER_API_KEY` and `FAL_KEY` stay server-side; `PUBLISHING_ENABLED=false`
prevents any post from being sent; nothing is marked scheduled until Buffer
returns a post id. A lease-based worker endpoint
(`/api/jobs/content-tick`, `CRON_SECRET`) keeps the pipeline moving with no open
browser. Costs, the cheapest suitable model, deployment, the one-video live test
and the remaining production steps are in
[docs/CONTENT-PIPELINE.md](docs/CONTENT-PIPELINE.md).

## Persistence and release status

Use durable PostgreSQL for real submissions, with `STRICT_PERSISTENT_DB=true`. SQLite is useful locally; serverless `/tmp` SQLite is ephemeral and instance-local. The clean interface does not change that limitation. Migrations are additive and preserve historical business data; new document uploads remain disabled.

This is a **release candidate, not a deployment or compliance certification**. See [DEPLOYMENT.md](DEPLOYMENT.md), [KEY-SETUP.md](KEY-SETUP.md), [RELEASE-TESTING.md](RELEASE-TESTING.md), [SECURITY-REVIEW.md](SECURITY-REVIEW.md) and [LIVE-COMPARISON.md](LIVE-COMPARISON.md). No production database, DNS or website replacement is authorized by this source handoff.

## Layout

`app/` backend; `api/` Vercel entrypoint; `web/` runtime static assets; `scripts/` generators/package tools; `tests/` active and explicitly retired contracts; `validation/` reviewed release evidence. Run both content generators after template edits. Vercel runs `python3 scripts/build_static.py` to produce the public-only `public-site` output; public pages do not pass through the Python API router. Dependencies are deliberately small; no frontend framework/build is required.
