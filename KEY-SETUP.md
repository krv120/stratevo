# Connect the AI and supplier accounts

## Your setup: Google Gemini, without Brave

Use these server-side values in the project that runs this code:

| Key | Value |
| --- | --- |
| `AI_API_KEY` | Your own secret Gemini API key from Google AI Studio |
| `AI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `AI_MODEL` | `gemini-2.5-flash`, if available to your key; otherwise an available compatible model ID |
| `AI_MAX_OUTPUT_TOKENS` | `4096` for this Gemini setup (bounded by the application to 256–8192) |
| `AI_REASONING_EFFORT` | `low` for Gemini 2.5; only use values supported by your model |
| `ONLINE_DISCOVERY_ENABLED` | `false` |
| `BRAVE_SEARCH_API_KEY` | Leave unset |

Deploy the updated source, save the environment variables, and redeploy after changing them. The Gemini key enables conversation, **not** live supplier search. Do not put the Gemini key in the Brave field or any customer form. These are configuration examples, not a claim that this session has tested your key or model access.

## Hosted deployment (Vercel)

Open your Vercel dashboard → the project running **this new Python build** → Settings → Environment Variables. Add the following to the deployment environment you intend to use (Production, and optionally Preview). Treat keys and database credentials as sensitive. Then **redeploy**; saving variables does not change an existing deployment.

Do not add these keys to GitHub files, frontend JavaScript, browser storage, or a chat. Do not prefix them with `NEXT_PUBLIC_` or `VITE_`.

| Variable | Value |
| --- | --- |
| `AI_API_KEY` | New secret key from your AI provider |
| `AI_MODEL` | Exact model ID available to that key; it must support Chat Completions and function tools |
| `AI_BASE_URL` | Provider's HTTPS API base URL, e.g. `https://api.openai.com/v1` for OpenAI; do not append `/chat/completions` |
| `BRAVE_SEARCH_API_KEY` | Secret from your Brave Search API subscription (separate from the AI key) |
| `ONLINE_DISCOVERY_ENABLED` | `true` only with a Brave key; otherwise `false` |
| `ONLINE_DISCOVERY_DAILY_LIMIT` | `50`, or a lower daily request budget |

Only OpenAI-compatible Chat Completions endpoints are supported by this adapter; an arbitrary provider key or consumer chatbot subscription is not sufficient. Model access, quota/billing and hosting outbound access must be valid. Never reuse a previously exposed key.

### Database and account prerequisites

API keys alone do not deploy the application or provision persistence. For hosted operation also set:

- `DATABASE_URL`: private server-side PostgreSQL/Supabase connection string. Apply `migrations/001_private_platform.sql` followed by `002_private_discovery.sql` and `003_public_ai_marketplace.sql` first.
- `PUBLIC_BASE_URL`: exact live HTTPS origin, without a path or trailing slash. Use the real deployment domain, not a preview URL from an old session.
- `ADMIN_PASSWORD_HASH`: generate using `python3 -m app.suppliers hash-password`. Paste the entire hash as one value. This is not a plaintext password.
- `COOKIE_SECURE=true` for HTTPS.
- SMTP: `SMTP_HOST`, `SMTP_PORT` (normally `587`), `SMTP_USER`, `SMTP_PASSWORD`, and `MAIL_FROM` using an address your mail service authorizes.

Schedule `python3 -m app.suppliers send-mail` on an appropriate backend worker. The manager's “Send next queued email” button supports manual delivery testing. Registration/access requests attempt their own email when SMTP is configured. A retry scheduler is still required; queued verification email is not the same as delivered email.

## Test after redeploying

1. Open `/admin` and sign in with your manager password.
2. In **Service connections**, inspect configuration status.
3. Click **Test AI connection**. This makes a real provider call and may incur a small charge. A success means the model responded; it is not a full sourcing-quality/tool-calling evaluation.
4. Only if Brave is configured, click **Test online search**. This performs a generic real search, records private evidence and consumes one daily request allowance. Raw supplier URLs never appear in its response.
5. Open `/ai` signed out or in incognito. No customer token/password is required. Ask a general question, then a sourcing question. Provider configuration alone is not a successful response.
6. Supply product, positive quantity/unit, preferred location and certifications for up to three anonymized matches. Public chat does not invoke live discovery; that is an owner-only capability.
7. Submit a product through the supplier popup using a real test inbox. Confirm the email and check automatic Marketplace publication and `/supplier/account` access, then add/withdraw a product. Do not approve it manually.
8. Set `PUBLIC_AI_DAILY_LIMIT`, `PUBLIC_AI_CONCURRENCY`, `PUBLIC_AI_PER_MINUTE` and provider-side spending controls. `PUBLIC_AI_ENABLED=false` is the conversation kill switch. Default shared daily allowance: 100 model requests, not a precise monetary cap.

These controls report actual failures rather than saying a key is working merely because it exists. They do not reveal keys or raw provider error bodies.

## Email confirmation → public product, private account

New suppliers provide private business/contact/license details and their first product. The product is hidden until its owner confirms the single-use, 24-hour email link. Confirmation redirects to `/supplier/account` and publishes automatically, without manager approval. Further products publish from that authenticated account; suppliers can withdraw their own listings. Public fields contain no account details. Email confirmation is not business/product certification.

`/admin` provides a private supplier registry and post-publication removal. Existing legacy application/profile routes remain for compatibility, but new registrations cannot enter the old approval queue. See `PUBLIC-MARKETPLACE-UPDATE.md` for image/privacy limits and all launch requirements.

## Local development

The application reads environment variables; `.env` is not loaded automatically. You may export the variables through your shell, or put a JSON object of string-valued environment settings in an ignored file such as `private/local-config.json`, restrict it to your account (`chmod 600 private/local-config.json`), and run:

```sh
python3 scripts/run_preview.py private/local-config.json
```

Restart after changing local settings. Never put a secrets file in `web/` or include it in the source archive. Use a local HTTP origin with `COOKIE_SECURE=false` only on localhost; use HTTPS and secure cookies for hosted previews.

## Current validation limit

Configuration, response handling and account behavior are tested with isolated fixtures and mocked external providers. No real credentials have been added by this agent. Production AI/search requests and email delivery must be verified in your actual hosting environment after setup. The existing production site has not been replaced by these repository edits.
