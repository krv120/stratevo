# Content pipeline: 40 faceless videos, captions and scheduled posts

Status: **implemented and locally verified; not deployed, nothing generated for
real, nothing sent to Buffer.** This document separates what the repository and
the local test suite prove from what still needs production credentials.

| Area | Locally verified | Needs production |
| --- | --- | --- |
| 40 distinct ideas (hooks, scripts, prompts, TikTok/Instagram copy) | Yes (`tests/test_content.py`) | — |
| fal.ai generation per idea, budget lock, per-job cap, idempotency | Yes, against `tests/fal_stub.py` | One real paid clip + fal billing cross-check |
| On-screen captions (hook + word-timed subtitles, 1080x1920) | Yes, real ffmpeg renders inspected frame by frame | Encoding time on Vercel's CPU |
| Durable public media URL for Buffer | Yes (`/media/<token>.mp4`, byte ranges, 404s) | Reachable at the real public origin |
| Europe/Athens 30-day slot planning | Yes (DST-aware tests) | — |
| Buffer `createPost` request shape | Yes (payload assertions) | A real TikTok/Instagram channel and a returned post id |
| Worker tick, leases, retries, crash recovery | Yes | A scheduler that calls it every few minutes |
| PostgreSQL migration `009_content_pipeline.sql` | Applied to an isolated PostgreSQL instance (`pgserver`) with BYTEA media round-trip and slot planning | Applied to the production database |

---

## 1. Audit of what existed before this change

The repository already had a working supplier/operations site with strict
patterns. The following were inspected before adding anything:

* `app/server.py` — one handler, explicit route allowlists, `origin_allowed()`,
  session cookies scoped to `/api`, CSP on `/admin`, `CRON_SECRET` bearer worker
  for `/api/jobs/mail`. **Reused, not duplicated.**
* `app/suppliers.py` — `database()` transaction helper, `WorkflowError`,
  rate limits, `now()`/`digest()`. **Reused.**
* `app/connections.py` — migration runner, SQLite mirror of module `SCHEMA`
  strings, `dirty` schema upgrade path. **Extended for 009.**
* `app/video.py` — fal.ai queue client, price table, budget reservation,
  idempotent `client_key`, webhook verification. **Extended, not rebuilt.**
* `app/settings.py` — `public_origin()` requires `PUBLIC_BASE_URL` and (outside
  local/test) `PUBLIC_ORIGIN_VERIFIED=true`.
* `vercel.json` — single Python function, `maxDuration: 60`, rewrite for `/api/*`,
  global security headers.

Bugs and gaps found, and what was done:

| Finding | Impact | Resolution |
| --- | --- | --- |
| `video_jobs` had no link to a content idea and no record of resolution | A 40-video batch could not be traced or priced per clip | `idea_id`, `resolution` columns in both the Postgres migration and the SQLite upgrade path in `connections.py` |
| `video_jobs` schema upgrade path only handled the legacy `outbox` table | Existing local databases crashed with `no such column: idea_id` | Explicit `PRAGMA table_info` upgrade, mirroring the `outbox` pattern |
| Price lookup used one unit price per endpoint | A 768P or 1080P MiniMax job would be under-reserved, silently breaking the $5 guard | Resolution-priced table used for budgeting (list price, never the promo rate) |
| Buffer has **no media upload API**; it fetches the file at publish time | A fal CDN URL can expire before a post publishes; the post then fails | Clips are copied to PostgreSQL and served from our own HTTPS origin at `/media/<token>.mp4` |
| Buffer queues a **maximum of 10 posts per channel** on the free plan | A 40-post plan would fail mid-batch | `BUFFER_QUEUE_CAP` tops the queue up over several worker passes instead of failing |
| `content_publications` could be stranded in `submitting` if the function died mid-call | A post would never be retried and never be confirmed | `recover_stuck()` returns abandoned rows to `planned` after 10 minutes |
| A write transaction wrapped an external HTTP call in the first draft | SQLite would deadlock ("database is locked") on a queue-cap skip | Cap check reads first, writes afterwards, Buffer call outside any transaction |
| Nothing drained long-running work without an open browser | Requirement 4 (unattended operation) would fail | Lease-based `content_jobs` + `/api/jobs/content-tick` secured by `CRON_SECRET` |

Nothing outside `/admin`, the new `/media/` route and the documented env vars
was changed. Public pages, supplier flows and the marketplace are untouched.

---

## 2. Architecture

```
/admin  ──►  web/content.js  ──►  /api/admin/content/*
                                     │
      ┌──────────────────────────────┼───────────────────────────────┐
      ▼                              ▼                               ▼
 content_library              video.py (existing)              buffer_api.py
 40 distinct ideas            fal.ai queue + budget            one channel per post
      │                              │                               │
      └────────► content.py ◄────────┘                               │
                     │                                              │
                     ▼                                              │
              content_jobs  ◄── /api/jobs/content-tick (cron)       │
                     │             leases, retries, dead letters     │
                     ▼                                              │
              captions.py (ffmpeg/libass) ──► media.py (Postgres BLOB) ──► /media/<token>.mp4
```

State machine per idea:

```
draft ──approve──► approved ──queue (paid)──► video_pending
  ▲                   │                            │ fal completes
  │                   │ reject/regenerate          ▼
  └───────────────────┘                      video_ready ──worker──► ready_to_publish
                                                                        │
                                             scheduled ◄── Buffer post id│
                                                                        ▼
                                                                   published
```

* **Draft → approved** is the only way to spend money, and queuing is a second,
  separate click with an explicit confirmation showing the amount.
* An idea with a paid generation or a live post cannot be regenerated (no double
  charging).
* `scheduled` is written **only** after Buffer returns a post id; a refused post
  is stored as `failed` with Buffer's message.

Tables (all in `migrations/009_content_pipeline.sql`, RLS enabled where the
existing migrations do it): `content_series`, `content_ideas`, `media_assets`,
`content_publications`, `content_jobs`, `content_state`, plus the two new
`video_jobs` columns.

---

## 3. The 40-video workflow

1. **Create the series** (§ Production line, first form): 40 ideas, 10 s, 768P.
   The cost panel shows the total *before* anything is queued.
2. **Review ideas** under *To review*: hook, script, prompt, per-network copy.
   Approve, reject, or regenerate. Regeneration replaces the concept in place
   and is free.
3. **Queue approved videos** in batches. Each batch is budget-checked
   server-side: the monthly limit, the per-job cap and a 6-per-hour rate limit
   all apply. `client_key = idea-<id>` makes the submit idempotent, so a retry
   after a timeout cannot create a second paid job.
4. **The worker** syncs fal jobs, moves completed ones to *Captioned*, downloads
   the clip, burns in the hook + subtitles at 1080x1920, stores the MP4 and marks
   the idea *Ready*.
5. **Plan 30 days**: even spread across Europe/Athens slots (`CONTENT_SLOT_LOCAL`,
   default 12:30 and 19:00), rotating the first slot by day so a single-post day
   alternates morning/evening. Short runs start tomorrow rather than waiting for
   a gap.
6. **Send to Buffer** (worker, or the admin button): one `createPost` per
   network, `schedulingType: automatic`, `mode: customScheduled`, `dueAt` in
   UTC. Instagram uses `type: reel`, `shouldShareToFeed: false`; TikTok sets
   `isAiGenerated: true`.
7. **Track**: every job keeps attempts, last error, cost, and the Buffer id or
   error message. `published` is set only when Buffer reports the post as sent.

### Captions

`app/captions.py` builds an ASS document and burns it with ffmpeg:

* script split into phrases of at most 26 characters, word-weighted timeline,
  minimum 1.1 s per line;
* `Hook` style — uppercase, yellow, top-centred, 2.4–4 s, font auto-shrinks for
  hooks longer than 32/48 characters;
* `Caption` style — white on black outline, bottom-centred above the safe area;
* `scale → pad → setsar → subtitles`, output 1080x1920 H.264 + AAC, faststart.

The bundled `imageio-ffmpeg` static build has libass but **no `drawtext`**, so
captions are ASS `Dialogue` events. If ffmpeg is missing the worker records the
error on the idea and leaves it in *Captioned* for a retry instead of losing the
paid clip.

Encoding is capped at `-maxrate 2200k -bufsize 4000k`: a 10 s 1080x1920 clip
lands around 3 MB, comfortably under **Vercel's 4.5 MB serverless response
limit**, which is what Buffer receives when it downloads `/media/<token>.mp4`.
Media responses are cached immutably (`s-maxage`) per token, so the edge serves
repeat downloads instead of the function.

---

## 4. Publishing through Buffer — verified requirements

Verified against `developers.buffer.com` on 2026-10-27:

* Endpoint `POST https://api.buffer.com`, GraphQL, header
  `Authorization: Bearer <personal API key>` from
  `publish.buffer.com/settings/api`. No OAuth app is needed for one account.
* **One channel per `createPost` call** — the worker issues one call per network.
* Video is attached as `assets: [{ video: { url } }]`. **There is no upload API**;
  Buffer fetches the URL at publish time. Hence `/media/<token>.mp4` must stay
  online for the whole 30-day window.
* Errors arrive inside HTTP 200 (`errors[]` or a `MutationError` union member).
  Both are treated as failures and never recorded as scheduled.
* TikTok metadata exposes only `isAiGenerated` (and `title` for photo posts);
  there are no privacy/duet/comment controls in the API.
* Instagram requires `type` (`reel` here) and `shouldShareToFeed`.
* Post status is `scheduled → sent → error`; the worker polls confirmed posts and
  marks the idea `published` on `sent`.
* Rate limits: ~100 requests per 15 minutes per client. Our worker uses four
  posts per pass.
* **Account eligibility is not verifiable from code.** The channel must already
  be connected in Buffer and be a TikTok Business/Creator or Instagram Business/
  Creator account, and the Buffer plan must allow the queue depth. The admin
  panel lists the connected channels it can see and refuses otherwise.

### Known Buffer limitations that shape this design

* No media upload → self-hosting is mandatory.
* No post webhooks → the worker polls (`refresh_publications`).
* Free plan: 3 channels, **10 queued posts per channel**, 3,000 API calls/30 days.
  Essentials ($6 per channel/month) removes the queue cap.
* Retries after a 429 respect `Retry-After` by simply not looping: the worker
  retries on its next pass.

---

## 5. Unattended operation (no open tab, no laptop)

Everything lives in Vercel + PostgreSQL; there is no separate worker service.
The only missing piece on a stock Vercel **Hobby** project is a frequent
scheduler: Hobby cron jobs run **once per day** and allow only two of them.

The tick endpoint is `GET|POST /api/jobs/content-tick` with
`Authorization: Bearer $CRON_SECRET` (at least 32 characters, `CRON_SECRET`
already exists for the mail worker). One tick:

1. polls active fal jobs (no paid work is created),
2. moves completed jobs to the caption queue,
3. renders at most one caption (fits the 60 s function limit),
4. submits up to 4 planned posts if `PUBLISHING_ENABLED=true`.

Options, cheapest first:

| Option | Cost | Frequency | Notes |
| --- | --- | --- | --- |
| **cron-job.org** (recommended) | €0 | every 1–5 min | Free account, one job with a custom `Authorization` header. No code changes. |
| **Cloudflare Worker cron trigger** | $0 on the free plan | 1 min | 10 lines of `fetch()` if you prefer owning it; still free. |
| GitHub Actions schedule | $0 on a public repo | 5 min (delayed in practice) | Needs a repository secret; not needed if the two above work. |
| **Vercel Cron** | included | **once/day on Hobby**, per-minute on Pro ($20/mo) | `vercel.json` already contains a daily 04:00 UTC safety net. |

Recommended setup: cron-job.org (or a Cloudflare cron) every 5 minutes as the
primary driver, plus the built-in Vercel daily cron as a fallback. Total
orchestration cost: **€0**. The $20/mo Vercel Pro upgrade is only worth it if you
want the scheduler and the function in one vendor.

If nothing calls the endpoint, nothing is lost: paid jobs are already recorded,
captions are retried when a worker eventually runs, and no post is ever sent
without `PUBLISHING_ENABLED=true`.

---

## 6. Budget and model choice

fal.ai prices checked 2026-10-27 (`minimax/h3-max-turbo/text-to-video` has a
promotional discount until 2026-10-31; budgeting uses the **list** price):

| Model | 5 s clip | 10 s clip | 40 × 10 s (400 s) |
| --- | --- | --- | --- |
| **MiniMax H3 Max Turbo 480P** | $0.125 | $0.25 | **$10.00** |
| **MiniMax H3 Max Turbo 768P** | $0.20 | $0.40 | **$16.00** |
| MiniMax H3 Max Turbo 1080P | $0.40 | $0.80 | $32.00 |
| Kling 2.5 Turbo Pro | $0.35 | $0.70 | $28.00 |
| Kling 3.0 Pro | $0.70 | $1.40 | $56.00 |

Promotional MiniMax rates until 2026-10-31: 480P $0.01625/s, 768P $0.026/s
(40 × 10 s at 768P ≈ **$10.40**).

**Chosen: MiniMax H3 Max Turbo, 768P, 9:16, 10 s.** Vertical-native, cheapest
per second at a resolution that reads well on a phone after the 1080x1920
upscale, and it returns audio-ready MP4s. 1080P is not worth double the cost for
a talking-caption clip; 480P is acceptable to halve the bill if the first clips
look soft.

Monthly total for one full 40-video run:

| Item | Cost |
| --- | --- |
| 40 clips × 10 s at 768P (list) | $16.00 |
| Buffer Essentials, 2 channels | $12.00 |
| Vercel Hobby + Neon/Supabase free tier | $0 |
| Scheduler (cron-job.org / Cloudflare) | $0 |
| **Total** | **~$28 (≈ €26)** |

Inside the €20–30 target. If you accept 480P, the same run is ~$22. Promo rates
bring it to ~$22 even at 768P until 2026-10-31.

Guard rails that stay in place:

* `VIDEO_SPEND_LIMIT_USD=5.00` — **do not raise it** until the first real clip
  has been reconciled against fal's billing dashboard.
* `VIDEO_MAX_JOB_USD=1.00` — a single clip can never cost more than $1.
* `VIDEO_JOBS_PER_HOUR=6` — a runaway loop cannot burn the budget in a minute.
* Every queue attempt reserves the money **before** calling fal and re-reads the
  committed total inside the same transaction (`resource_locks` row lock).

With the limit at $5, a full 40-clip run cannot start. That is intentional: the
first real generation must be verified first. Raising the limit is an explicit,
documented action (§8).

---

## 7. Deployment

1. **Apply migration 009** (additive, no drops):

   ```bash
   psql "$DATABASE_URL" -f migrations/009_content_pipeline.sql
   ```

   It creates `content_series`, `content_ideas`, `media_assets` (video bytes in
   `BYTEA`), `content_publications`, `content_jobs`, `content_state`, their
   indexes, and adds `video_jobs.idea_id` / `video_jobs.resolution` with
   `ADD COLUMN IF NOT EXISTS`. `app/connections.py` already expects migrations
   `001`–`009`, so a fresh PostgreSQL instance applies all nine automatically.

   Verified locally: the full migration chain (001–009) ran against an isolated
   PostgreSQL server, and a series, an approved idea, a stored media asset, a
   30-day plan and a worker tick all worked on it.

2. **Deploy** the branch. `vercel.json` now includes
   `crons: [{ "path": "/api/jobs/content-tick", "schedule": "0 4 * * *" }]`
   and `requirements.txt` installs `imageio-ffmpeg==0.6.0` (a ~80 MB static
   ffmpeg inside the function; Vercel's 250 MB limit is the constraint to watch).
   Set `CONTENT_CAPTION_PRESET=ultrafast` if caption rendering is slow.

3. **Environment variables** (Vercel → Project → Settings → Environment
   Variables, Production; never in the browser or in git):

   | Variable | Value | Why |
   | --- | --- | --- |
   | `FAL_KEY` | your fal key | generation (already required) |
   | `BUFFER_API_KEY` | Buffer personal key | posting |
   | `PUBLISHING_ENABLED` | `false` first, `true` only when you want posts sent | hard off-switch |
   | `CRON_SECRET` | ≥32 random chars | authenticates `/api/jobs/content-tick` (same variable as the mail worker) |
   | `PUBLIC_BASE_URL` | `https://www.stratevo.online` | absolute media URLs |
   | `PUBLIC_ORIGIN_VERIFIED` | `true` | required outside local/test |
   | `BUFFER_QUEUE_CAP` | `10` (free) / `50` (Essentials) | stops the worker at the real queue depth |
   | `CONTENT_SLOT_LOCAL` | `12:30,19:00` | posting times in Europe/Athens |
   | `CONTENT_CAPTION_PRESET` | `veryfast` | slow CPU: `ultrafast` |
   | `DATABASE_URL`, `STRICT_PERSISTENT_DB` | existing values | durable storage is mandatory |

   Keep `PUBLISHING_ENABLED=false` until §9.

4. **Verify after deploy**: `/admin` → Production line shows the series, the
   worker line reports `ffmpeg available`, and
   `curl -s https://<host>/api/admin/content/plugins` (with a session cookie)
   lists the Buffer channels.

---

## 8. First real test — one short video

Goal: prove status polling, media URL, playback, budget accounting and a real
fal charge, with the smallest honest spend (**$0.20**, 5 s at 768P).

**Option A — dashboard (recommended)**

1. Confirm `FAL_KEY` is set in Vercel and `VIDEO_SPEND_LIMIT_USD=5.00`.
2. Sign in to `/admin` → *Production line*.
3. Click **One-video real test** and accept the confirmation. It creates a
   one-idea series, approves it and queues exactly one 5-second 768P clip.
4. Within a minute or two the worker (or **Run worker now**) moves it to
   *Captioned*; then *Ready* with a playable 1080x1920 clip.
5. Check: the caption is legible, the hook sits inside the frame, the clip plays
   at `/media/<token>.mp4`, and the budget line shows exactly $0.20 committed.
6. Open fal.ai's dashboard → *Requests* and confirm the same request and charge.
   If the API cost differs, note the difference; do not raise the limit.

**Option B — API**

```bash
# 1. sign in and keep the session cookie
curl -s -c cookie.txt -X POST https://<host>/api/admin/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"owner","password":"<your admin password>"}'

# 2. queue the single test clip (same call the button makes)
curl -s -b cookie.txt -X POST https://<host>/api/admin/content/smoke \
  -H 'Content-Type: application/json' -d '{}'

# 3. drive the worker once instead of waiting for cron
curl -s -b cookie.txt -X POST https://<host>/api/admin/content/tick \
  -H 'Content-Type: application/json' -d '{}'

# 4. inspect the result (video_url must be https://<host>/media/...mp4)
curl -s -b cookie.txt https://<host>/api/admin/content/overview
```

Never paste `FAL_KEY` or the admin password into chat, a ticket or a commit.
If the smoke test fails, the state is recorded on the idea and the job row; no
money is spent when validation, budget or the per-job cap stop the request.

**Stop condition:** if the real cost differs from $0.20 or the video is unusable
at 768P, stop and adjust the plan (480P or a different model) before queueing
anything else.

---

## 9. Enabling publishing (after §8 passes)

1. Connect a **TikTok Business/Creator** and an **Instagram Business/Creator**
   account in Buffer. Confirm they appear in the pipeline panel.
2. Decide the plan: free (10 queued posts per channel, so the worker tops up)
   or Essentials ($6/channel/month for a full 40-post month).
3. Set `BUFFER_API_KEY` and `PUBLISHING_ENABLED=true` in Vercel; redeploy.
4. Plan the calendar, then click **Send planned posts to Buffer** for the first
   four posts and verify them in Buffer's own calendar.
5. Leave `PUBLISHING_ENABLED=false` if you want to keep generating and planning
   without any risk of publishing.

---

## 10. Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| "FAL_KEY is not configured" | missing/whitespace env var | add it in Vercel Production, redeploy |
| Ideas stay in *Generating* | no worker calling the tick | check cron-job.org, or press **Run worker now** |
| *Caption error: ffmpeg is not available* | function bundle missed `imageio-ffmpeg` | confirm `requirements.txt` deployed; check the build log |
| "PUBLIC_BASE_URL is not configured" | origin missing when sending | set `PUBLIC_BASE_URL` + `PUBLIC_ORIGIN_VERIFIED=true` |
| Buffer refuses a post | channel disconnected, wrong account type, queue full | the message is stored on the post row; reconnect in Buffer |
| Post stuck in `submitting` | function died mid-call | `recover_stuck()` returns it to `planned` on the next publishing pass |
| Database growing | captioned clips are stored in Postgres | `media.prune()` removes unscheduled media older than 45 days |

---

## 11. What is still missing

* **No real generation, deployment or Buffer schedule has happened.** Every
  claim above is either a local test or a documented API contract.
* **Vercel function limits.** An 80 MB ffmpeg plus the app must fit the 250 MB
  unzipped limit; a 10 s 1080x1920 encode must fit `maxDuration: 60`. Both are
  measured on the first deploy, not here.
* **Timezone data.** `zoneinfo` needs `tzdata`; Vercel's Python runtime provides
  it, a bare container may not.
* **TikTok/Instagram account eligibility** and Buffer plan limits can only be
  confirmed inside Buffer.
* **Music**: clips have model audio only. Adding a licensed track is out of
  scope.
* **Cost per minute on fal** is list-price based; only the first real job will
  confirm it.
