# Configuration without sharing secrets

Copy `.env.example` for local development. Put production secrets into the hosting secret manager, never source control/chat. Rotate previously exposed credentials rather than reusing them.

- `DATABASE_URL`: durable PostgreSQL connection string with the hosting provider's required TLS settings. `STRICT_PERSISTENT_DB=true` rejects ephemeral fallback for real production use.
- `ADMIN_PASSWORD` **or** `ADMIN_TOKEN`: strong unique value; no default. `ADMIN_TOTP_SECRET` is optional; when configured, correct MFA is required and replay is rejected. Account-scoped roles remain supported by the backend.
- `PUBLIC_BASE_URL=https://www.stratevo.online`; buyer booking is fixed in code to `https://app.minup.io/book/stratevo` and cannot be overridden by an environment variable.
- `SITE_INDEXABLE=false` until the readiness checklist is approved.
- `MAIL_DELIVERY_ENABLED=false` until actual outbound mail has been separately authorized. Configure a supported API mail transport, SMTP or approved webhook, a verified sender and `ADMIN_NOTIFICATION_EMAIL`. Stdlib SMTP uses TLS-on-connect on 465 or STARTTLS on 587. Missing delivery credentials do not constitute delivery proof; monitor the authenticated queue.
- `RIGHTS_ERASURE_APPROVED` and retention settings are operational safeguards, not blanket authorization to delete records. Use approved, verified requests with backup/retention review.

- `FAL_KEY`: server-side fal.ai API key for Content Studio video generation. Create an API-scoped key at https://fal.ai/dashboard/keys and add it in the hosting environment (Vercel: Project → Settings → Environment Variables → `FAL_KEY`, Production, then Redeploy). Never use a client-exposed prefix, never commit it, never paste it into a page or chat. Rotate it in the fal dashboard if exposed. `VIDEO_SPEND_LIMIT_USD`, `VIDEO_MAX_JOB_USD` and `VIDEO_JOBS_PER_HOUR` cap spend before any request is submitted. See `docs/FAL-VIDEO-STUDIO.md`.

See `app/settings.py`, `app/admin_auth.py`, `app/mail_policy.py` and `app/maintenance.py` for complete compatibility settings. Do not enable obsolete external integrations. This application does not need third-party model or search credentials.

## Neural narration for the kinetic series

The 19 kinetic episodes need a human-sounding voice. `app/kinetic_voice.py`
supports three providers and uses the first one with a key:

| provider | env var | model | default voice | cost |
| --- | --- | --- | --- | --- |
| fal.ai | `FAL_KEY` | `fal-ai/minimax/speech-2.8-hd` | `Deep_Voice_Man` | $0.10 / 1k chars ≈ **$0.031 per clip** |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini-tts` | `onyx` | ≈ $0.015 / 1k chars |
| ElevenLabs | `ELEVENLABS_API_KEY` | `eleven_multilingual_v2` | `onwK4e9ZLuTAKqWW03F9` | plan-dependent |

Set it as a hosting environment variable (Vercel → Settings → Environment
Variables) or export it in the shell that runs the render. Then:

```bash
python -m app.kinetic_voice --check       # seconds, proves the key is live
python scripts/render_kinetic_series.py --start 1 --end 1 --out exports/preview
python scripts/render_kinetic_series.py            # all 19, only after approval
```

**Never paste a key into a chat, a commit or an issue.** Without a key the driver
raises `VoiceError` listing the variables it wants — that is the intended
behaviour, not a bug.
