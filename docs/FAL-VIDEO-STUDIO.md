# Content Studio — fal.ai video generation

This document describes the fal.ai integration that exists in this repository,
where the key goes, what was actually verified, and what could not be verified
from the Arena sandbox.

Scope for this phase: **one** operator-submitted text-to-video job, shown in the
private dashboard. There is no publishing step and no batch generation.

---

## 1. Where the API key goes

`FAL_KEY` must be a **server-side secret**. The browser never receives it: the
dashboard calls this application's authenticated API, and only the server calls
fal.ai.

### Vercel (the host this repository is already configured for)

1. Create an API-scoped key at <https://fal.ai/dashboard/keys>. Give it an alias
   such as `stratevo-content-studio`.
2. Open the Vercel dashboard → select the Stratevo project.
3. **Settings → Environment Variables → Add New**.
4. Key: `FAL_KEY`
   Value: the key from step 1
   Environments: **Production** (add **Preview** too if you want to test there).
5. Save, then **Deployments → … → Redeploy** so running functions receive it.

Equivalent non-interactive form (run from your own machine, never commit it):

```sh
npx vercel env add FAL_KEY production   # paste the key at the prompt
npx vercel --prod                       # redeploy
```

Rules that matter:

- Do **not** prefix the variable with `NEXT_PUBLIC_`, `PUBLIC_`, `VITE_` or any
  other client-exposed convention.
- Do **not** put it in `.env.example`, `web/*.js`, `vercel.json`, a commit, a URL
  or a chat message.
- Rotate the key in the fal dashboard if it is ever exposed, then update the
  variable and redeploy.
- If you use a different host (Fly, Railway, Render, a VPS), use that host's
  secret/environment store with the same variable name. Nothing else changes.

### Why not "Arena's deployment settings"

There is no such surface for this repository. Verified in this session:

| Check | Result |
| --- | --- |
| Tools available to the agent | web search, image generation, file editing, sandbox bash, GitHub branch/PR |
| Deployment or secret-manager action | none exposed; no `vercel`/`flyctl`/`railway`/`aws`/`gcloud` CLI, no deploy token |
| Sandbox environment variables | only E2B sandbox internals and the GitHub token; no secret store |
| Sandbox egress | allowlisted to `github.com`, `codeload.github.com`, `api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`; `curl https://queue.fal.run` and `https://api.fal.ai` are reset during the TLS handshake |
| Persistence of sandbox processes | preview only; the server dies with the session and is not a production runtime |

So the key belongs in the hosting provider's secret manager — Vercel for this
repo. The application reports the same instruction in the dashboard when
`FAL_KEY` is missing, without ever echoing a value.

---

## 2. What is implemented

| Concern | Implementation |
| --- | --- |
| Official API | fal Queue REST API (`https://queue.fal.run`) via `urllib`, no SDK dependency: submit, status, result, cancel |
| Model | `fal-ai/kling-video/v2.5-turbo/pro/text-to-video` (default, $0.07/s) and `fal-ai/kling-video/v3/pro/text-to-video` ($0.14/s), validated against each endpoint's published OpenAPI schema |
| Prompt validation | 10–2000 characters, control characters rejected, model/duration/aspect checked against the endpoint's enum |
| Async lifecycle | `reserved → queued → in_progress → completed`, plus `retrieving`, `canceling`, `failed`, `canceled`, `submit_failed`, `unknown` |
| Status checks | `POST /api/admin/video/sync` polls fal; the dashboard polls active jobs every 6 s for up to 30 minutes |
| Callbacks | `POST /api/video/fal-webhook`, Ed25519 signature verified against fal's JWKS, ±5 min timestamp window, replay-safe |
| Failures | fal errors are stored with the operator-facing message; terminal failures release their budget reservation |
| Retries | Automatic for transport/5xx hiccups on the next sync; explicit `POST /api/admin/video/retry` creates a new attempt with `attempts+1` and a fresh budget check |
| Video URL | Stored only when HTTPS on `*.fal.media`, `fal.run` or `storage.googleapis.com`; returned in every job payload |
| Cost | Live `GET https://api.fal.ai/v1/models/pricing` when reachable, otherwise the reviewed table in `app/video.py`; stored per job with its basis |
| Spending limit | `VIDEO_SPEND_LIMIT_USD` per calendar month (UTC), reserved under a database row lock before submission; per-job cap `VIDEO_MAX_JOB_USD` |
| Rate limit | `VIDEO_JOBS_PER_HOUR` submissions per operator |
| Idempotency | A browser-generated `client_key` is unique in the database, so a retried request cannot buy a second generation |
| Persistence | `video_jobs` table, migration `008_video_jobs.sql`; durable PostgreSQL required outside local development |
| Secret handling | `FAL_KEY` is read from the environment per call, never logged, never stored, never returned |

### Endpoints

All `/api/admin/video/*` routes require an authenticated staff session; the
webhook requires a valid fal signature.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/admin/video/status` | Key presence, budget, models, webhook state, storage mode |
| GET | `/api/admin/video/jobs?offset=0` | Recent jobs, newest first |
| POST | `/api/admin/video/jobs` | Validate, reserve budget, submit to fal |
| POST | `/api/admin/video/sync` | Poll fal for one job |
| POST | `/api/admin/video/retry` | Retry a failed/canceled job as a new attempt |
| POST | `/api/admin/video/cancel` | Request cancellation |
| POST | `/api/video/fal-webhook` | fal completion callback (signature verified) |

### Cost semantics

`cost_usd` is the amount **this application commits against the budget**:
duration × the price in force at submission time. It is deliberately not
presented as a provider invoice. fal's Billing dashboard remains authoritative;
the Platform Usage API is aggregate and delayed, so it is not used to attribute
a single job. Each row stores `unit_price_usd` and `cost_basis`
(`fal_pricing_api` or `pinned_price_table`) so the number can be audited later.

The reviewed fallback prices (checked 2026-10-27 against <https://fal.ai/pricing>)
are `$0.07/s` for Kling 2.5 Turbo Pro and `$0.14/s` for Kling 3.0 Pro.

---

## 3. Configuration reference

| Variable | Default | Meaning |
| --- | --- | --- |
| `FAL_KEY` | *(empty)* | Server-side fal API key. Required for generation. |
| `VIDEO_SPEND_LIMIT_USD` | `5.00` | Monthly ceiling across all jobs, in USD. |
| `VIDEO_MAX_JOB_USD` | `1.00` | Per-job ceiling; a job above it is rejected. |
| `VIDEO_JOBS_PER_HOUR` | `6` | Submission rate limit per operator. |
| `VIDEO_WEBHOOK_ENABLED` | `true` | Set `false` to rely on polling only. |

The webhook URL is derived from `PUBLIC_BASE_URL` and therefore requires
`PUBLIC_ORIGIN_VERIFIED=true` in hosted environments, exactly like the rest of
the site. If the origin cannot be resolved, jobs are still submitted and tracked
by polling; the dashboard shows "callbacks not configured".

`DATABASE_URL` + `STRICT_PERSISTENT_DB=true` are required outside local
development: an async job that lives only in serverless `/tmp` cannot be
reconciled after a restart.

---

## 4. How the spending limit is enforced

1. The server resolves the unit price (live pricing API, else the reviewed table).
2. It computes `duration × unit price` and rejects the job if that exceeds
   `VIDEO_MAX_JOB_USD`.
3. Inside one transaction it takes a row lock on `resource_locks('video-budget')`,
   sums every job created this UTC month that is not `failed`/`canceled`/
   `submit_failed`, and inserts the job as `reserved` only if
   `spent + estimate ≤ VIDEO_SPEND_LIMIT_USD`.
4. The network call happens **after** the reservation commits.
5. Terminal failures release the reservation. An ambiguous submit (timeout or
   connection reset) becomes `unknown` and **keeps** the reservation, because
   fal may have queued and billed it. `unknown` can only be cleared by the
   operator after checking the fal dashboard.

This is why a second click, a retried request or two concurrent workers cannot
overspend the configured limit.

---

## 5. What was verified, and what was not

**Verified in this repository (133 tests pass, 33 of them new):**

- Ed25519 verification against RFC 8032 test vectors, plus tamper rejection.
- Webhook accept/reject paths, including stale timestamp, missing headers,
  wrong signature and unknown request id.
- Submit → queue → complete lifecycle against a local fal stub, with the exact
  request bodies fal documents (`prompt`, `duration` as a string, `aspect_ratio`,
  `enable_safety_checker`, `fal_webhook` query parameter).
- Budget: second job blocked at the limit, per-job cap, pinned-price fallback,
  live-price path, failure releasing budget, ambiguous submit retaining it.
- Idempotent re-submit (no second charge), retry as a new attempt, cancel paths.
- Rejection of untrusted queue URLs and of non-`fal.media` result hosts.
- The key never appears in any API response or stored row.

**Not verified — no claim is made:**

- **No real fal.ai generation was executed.** The sandbox has no `FAL_KEY` and
  its egress policy blocks `queue.fal.run` and `api.fal.ai` (TLS reset), so a
  live call is impossible from here. The first real clip must be generated on
  the deployed host after the key is added.
- No deployment was performed; no Vercel project, domain or environment was
  modified from this session.
- No PostgreSQL instance was exercised; the SQLite path and migration text were
  tested. The migration is additive and follows the existing `007` pattern.
- fal's live pricing API response shape was taken from its published reference;
  the fallback table covers the case where it differs or is unreachable.

---

## 6. First real run (operator checklist)

1. Add `FAL_KEY` in Vercel and redeploy (section 1).
2. Confirm `DATABASE_URL`, `STRICT_PERSISTENT_DB=true`, `PUBLIC_BASE_URL` and
   `PUBLIC_ORIGIN_VERIFIED=true` are set in the same environment.
3. Set `VIDEO_SPEND_LIMIT_USD=1.00` and `VIDEO_MAX_JOB_USD=0.50` for the first
   run. One 5-second Kling 2.5 Turbo Pro clip costs about `$0.35`.
4. Sign in at `/admin`, open **Content Studio · AI video**.
5. The panel should read "FAL_KEY is configured on the server" and show
   `$1.00` remaining. If it does not, stop: the variable is missing from the
   environment the function actually runs in.
6. Submit one prompt. `POST /api/admin/video/jobs` returns `queued` with a
   `fal_request_id` and `cost_usd: 0.35`.
7. Watch the card move to `in_progress`, then `completed`. The clip plays in the
   dashboard and the job row keeps the request id, video URL and cost.
8. Cross-check the charge in the fal Billing dashboard. If it differs from
   `$0.35`, update the reviewed table in `app/video.py` (or rely on the live
   pricing API, which is preferred automatically).

## 7. Rollback

- Set `VIDEO_SPEND_LIMIT_USD=0` (or remove `FAL_KEY`) and redeploy: no new job
  can be submitted, existing jobs can still be read.
- Revert the deployment to the previous revision. Migration `008` is additive;
  leaving the table in place is harmless and preserves the spend ledger.
- Revoke the fal key in the fal dashboard if it may have leaked.

## 8. Deliberately not built yet

- Publishing to any channel.
- Batch generation (including the 40-video batch).
- Image-to-video, audio, or multi-shot prompts.
- Storing generated media in our own bucket. fal media URLs expire; download
  anything you need to keep before it does.
