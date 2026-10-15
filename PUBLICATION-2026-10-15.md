# Publication and rebuilt evidence — 15 October 2026

Version: **2026.10.13-rc1**, repackaged on **15 October 2026**.

The owner explicitly authorized publishing the reviewed source and safe validation evidence on the public `arena/40bf7fdf-stratevo` branch. This does not authorize a merge into main, production deployment, DNS changes or production data operations.

## Why this archive differs from the earlier local ZIP

After the approval pause the source files remained, but the temporary ZIP, virtual environment, screenshots, logs and prior local Git commit did not survive. The previous 4.22 MB ZIP and its hash must not be used to identify this rebuilt archive. The source was preserved, dependencies restored, and validation rerun. The existing remote branch history is retained; no force push is required.

Fresh results: **149 unit/HTTP tests passed**, **10 real PostgreSQL integration groups passed**, and **all three browser suites passed**. Provider replies in browser tests and SMTP unit tests are mocked; local HTTP/database persistence is real. Axe reported zero findings in tested states. Runtime dependency audit reported no known vulnerabilities. Six reviewed Bandit findings remain as explained in the audit. Fresh logs and current public-page screenshots are in `validation/`.

Earlier before screenshots and the raw live-browser failure log are unavailable after the reset. The gallery explicitly marks the missing before captures instead of fabricating replacements. Current screenshots were recaptured. Prior live fetch observations remain documented historical observations, not freshly repeated production checks. The current application's source has not been replaced with an old GitHub build.

## Archive identity and use

The downloadable GitHub archive contains this reviewed branch's source, public assets, migrations 001–005, tests, environment template, setup/release/audit documents, fresh safe evidence and `MANIFEST.json`. The manifest's `source_commit` identifies the reviewed source-and-evidence commit; the subsequent publication commit adds the manifest itself. Per-file SHA-256 hashes exclude the manifest, as stated in that file. The delivery link pins the publication commit, not a moving branch or sandbox address.

The delivery response gives the actual downloaded GitHub archive's byte size and SHA-256. The GitHub ZIP has a top-level directory; extract it before following `RELEASE-TESTING.md` and `OPERATIONS-HANDOFF.md`.

No private configuration, real supplier/customer records, database files, keys, documents, research datasets, development dependencies or running-service state are included. Production remains unmodified and unapproved. Live source/hosting reconciliation, authorized provider/mail tests, canonical confirmation, backup/role/worker checks and legal/operator approvals remain launch blockers.
