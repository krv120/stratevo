# Screenshot-led frontend and Gemini refinement

Date: 2026-10-09

## Scope and visual reference

The owner supplied two screenshots and explicitly requested that appearance instead of the replacement layout. The frontend is now reconstructed from those screenshots: black background, the preview banner, restrained navigation, large lowercase hero text, blue square buttons, faint S mark, particle lines, the process strip, a scroll-highlighted brief and the floating AI entry point. This is a screenshot-led reconstruction, **not a claim to have recovered the original source or exact logo asset**. Lower sections use the same visual treatment without inventing supplier metrics.

- Shared appearance is in `web/reference.css`; decorative interactions are in `web/visual.js`.
- Homepage, supplier and AI templates are in `web/templates/`; run `python3 scripts/create_pages.py` after changing them.
- Inter font subsets are self-hosted in `web/fonts/`, with their SIL Open Font License included. No external font/image request is needed.
- Header labels go to implemented destinations. “Marketplace” goes to sourcing coverage, not an invented public supplier directory. Mobile navigation exposes supplier application/access and booking.
- Reduced-motion mode disables decorative animation; the brief remains readable. Keyboard focus and a skip link are provided.

## Supplier application changes

The existing approval backend is preserved. The application now has three explicit sections: business, contact details, documentation. Business email remains mandatory; WhatsApp OR WeChat is enforced before submission and on the server. File selection shows the filename/size and rejects non-PDF filenames or documents above 2 MB before submission; server PDF-signature/size checks remain authoritative, not malware scanning.

After a successful submission, the form shows the email-verification next step rather than leaving the user guessing. Pending applications cannot open approved profiles. Manager approval activates the private profile immediately; after secure email-link confirmation, the supplier is redirected to their page. This flow was tested in Chromium using a synthetic application and a test-only outbox.

Actual email delivery still requires SMTP and a worker. The page does not claim that a queued message was delivered. No supplier identity or license is sent to the AI or published.

## AI changes informed by official documentation

Google's compatibility examples show Chat Completions and function tools, as well as the relationship between reasoning effort and Gemini thinking budgets. We kept the existing OpenAI-compatible adapter rather than making an untested switch to a different API. [5](https://colab.research.google.com/github/google-gemini/cookbook/blob/main/quickstarts/Get_started_OpenAI_Compatibility.ipynb)

Google recommends clear function/parameter descriptions and specific types. The tool schema now explains quantity units, volume scope, lead time and currency requirements more explicitly. [2](https://ai.google.dev/gemini-api/docs/generate-content/function-calling)

Implemented:

- Gemini 2.5 requests default to `reasoning_effort=low` unless the operator explicitly configures another supported effort. Other provider/model families are not silently assigned this default.
- When no output-limit override is set, the official Gemini endpoint gets a 4,096-token limit; other endpoints retain 2,048. Explicit limits are bounded to 256–8,192. This gives more headroom; it is not proof against truncation or a guarantee of model quality.
- Truncated output still fails honestly instead of being labelled complete. No reasoning summaries or hidden thought text are exposed.
- Safe, actionable errors distinguish rejected configuration, key rejection, access denial, missing model, quota, network and timeout errors. Raw provider response bodies/secrets are not shown.
- The chat UI shows real request-pending state, retains a failed question, restores controls on failure, and handles non-JSON/deployment-routing failures. Enter sends; Shift+Enter adds a line. Prompt shortcuts are suggestions, not simulated AI replies.
- The existing curated sourcing/Greeklish/slang guidance, private-source controls, qualification gates and maximum-three evidence rules remain.

The exact OpenAI-compatible base URL and request shape were also checked against Google's current compatibility page: https://ai.google.dev/gemini-api/docs/openai . The selected account model has **not** been automatically replaced with a newly advertised model.

## Configuration: do not re-enter secrets in chat

Keep the keys already entered in your hosting project. Deploy this updated source into that same project's preview environment, preserving the Gemini base URL and model ID that your account supports. Redeploy after environment changes, then use `/admin` → **Test AI connection**.

Optional tuning:

- `AI_REASONING_EFFORT=low` for the user's Gemini 2.5 configuration; model support varies.
- `AI_MAX_OUTPUT_TOKENS=4096` if the hosting project still explicitly sets the older 2,048-token value.
- Keep `ONLINE_DISCOVERY_ENABLED=false` without a Brave key. Gemini conversation is not this application's live search integration.

The local preview has no AI/search credentials. This does **not** mean the user's hosting keys are absent or wrong; hosting secrets are not automatically available in this workspace. No real provider test was performed here.

## Validation for this revision

- **80 unit/HTTP tests passed**, including provider error mapping, Gemini default settings, required template content and previous workflow/privacy regressions.
- Real ephemeral PostgreSQL tests passed: both migrations, private search evidence, budgets, duplicate-submission concurrency, approval concurrency, sessions and client-role/RLS checks.
- Chromium passed application contact/file validation, next-step confirmation, email verification, manager review, private profile, automatic supplier redirect, role denial and logout.
- Browser tests also cover missing-key diagnostics, disabled web search, a mocked provider quota error with question preservation, mobile supplier navigation, six routes at 390px, and home/supplier/AI at 320/768/1568px. No horizontal overflow or browser JavaScript exceptions were observed.
- Desktop homepage, supplier page and mobile homepage screenshots were visually inspected against the supplied direction. Decorative screenshots are not a claim of pixel-exact identity.
- One auxiliary screenshot launch crashed in the packaged Chromium GPU setup; using minimal headless flags with GPU disabled resolved it. The updated test command then passed.
- JavaScript syntax, Python compilation and Git whitespace checks passed.

## Still not proved / not deployed

No real Gemini quality benchmark, actual search-provider call, SMTP inbox delivery, hosted Vercel/Supabase configuration or physical mobile-device test occurred. No production domain change was made. Source reconstruction, account approval and generic marketing claims do not establish supplier verification or legal readiness. See `AUDIT-REPORT.md` for remaining access, retention, scanning, abuse-control and deployment gates. The AI cannot be guaranteed perfect.
