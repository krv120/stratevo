# Historical contract tests — excluded from active discovery

These files preserve tests for prior releases, including product-review and retired integration contracts. They are historical source, not current behavior or current passing evidence. They have not been counted in this release's active results.

The current root `tests/test_suppliers.py` retains compatible legacy checks with fixtures/expectations adapted for the new directory/authentication contract. Its original predecessor is preserved here. Current directory acceptance tests are in `tests/test_directory.py`; browser and PostgreSQL checks are documented in `RELEASE-TESTING.md`. Do not restore retired interfaces merely to satisfy these old expectations.
