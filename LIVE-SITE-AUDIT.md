# STRATEVO live-site inspection

Inspection date: 2026-10-07

## Scope and limits

The user identified https://stratevo.online as the current reference and instructed us not to use the old release files. Inspected public pages through text extraction only. No browser interaction, application submission, authentication, provider call, or production change was performed. The repository contains only its initial README and this audit; the existing application source is unavailable. Attachment notices were received, but no PDF or CSV exists in the mounted workspace, so no catalog data has been inspected or imported.

## Observations

- https://stratevo.online redirects to https://www.stratevo.online/ and serves the STRATEVO homepage.
- https://www.stratevo.online/api/health renders the site's branded '404 / That route is not in the network' page rather than a JSON health response.
- https://www.stratevo.online/api/agent/status also renders that branded not-found page rather than JSON status.
- These observations are consistent with missing API functions or frontend routing intercepting the paths. They do not prove the deployment architecture, HTTP status code, or absence of APIs at other paths. Inspect the actual frontend network requests and hosting configuration before selecting a fix.
- https://www.stratevo.online/supplier describes manual approval, private license evidence, secure email invitation, and a 1–3 business day target. These are visible claims, not verified backend behavior.
- Supplier copy currently lists email, WhatsApp AND WeChat. This differs from the earlier preference for email plus WhatsApp OR WeChat. Confirm and align copy, frontend validation and backend validation together when source is available.
- https://www.stratevo.online/ai yielded only the consent panel in text extraction. This is insufficient evidence to classify the page as broken; client rendering or extraction limitations may explain it.
- The homepage links to the correct booking URL: https://app.minup.io/book/stratevo.
- Extracted homepage counters are all zero. They may be animated starting values; visual browser testing is needed before treating this as a defect.

## Prioritized implementation work once current source is available

1. Identify the chat's actual network endpoints. Verify hosting builds server functions and excludes API paths from SPA fallback. Require JSON content types for health/status and structured API errors.
2. Validate provider configuration without exposing keys. Add bounded timeouts, cancellation and honest unavailable-provider states. Never label scripted fallback as a live model response.
3. Import only the newly supplied research data once accessible. Preserve provenance and distinguish listed prices/MOQs from verified current quotes. Keep contact information and supplier identities server-only.
4. Test privacy filtering before any streamed content reaches the client, tool authorization, prompt-injection resistance and anonymous-session isolation.
5. Verify durable session storage, expiry and deletion across separate serverless instances. Do not rely solely on process memory or temporary files.
6. Exercise supplier submission, restricted evidence access, manager decisions, invitation delivery and authorization after approval. Do not submit synthetic applications to production without permission.
7. Run real mobile and desktop browser tests, including consent controls, chat failures, form errors and booking navigation.

## Release evidence required

Record actual build/typecheck/test output, browser results, deployment identifier, API response shape/content type and remaining limitations. No previous transcript's test results are accepted as evidence for this deployment.
