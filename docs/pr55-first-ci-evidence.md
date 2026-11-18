# First independent decimal-oracle CI

Source03dfa275 first push44313484420 failed its Python3.13 readiness activation
assertion; first PR44313787694 passed all four matrices. Fixed push/PR3.13
logs each ran2140 tests, with1F/0E and0F/0E respectively, no skips. All5 new
oracle methods,9 existing decimal-kernel methods and6 lease-tag methods had
actual plain ok records in both selected logs. Forty method observations are
not another independently counted or archived538-vector CI execution.

The push failure is `tests/test_readiness_sampling.py:369`: halted remained
true at activation after SID2 publish reported publishing=False, before the later actual-stale
assertions. Cause remains unresolved; no timing threshold or test was changed.
The first failure is preserved separately from the green PR run.

Both385-pin maps match exact Git source before/after;62 UTA Python modules and
CI source are unchanged versus base8262bb. Cleared golden vectors are866704B,
SHA25617364d12847d5f118cc62f0e301a45180e8ccd353a38010e3cf3582a917afd97
in the Git blob. The fixed push3.13 package report is absent, so this collection
does not verify its required-path, packaged-byte or installed coverage. Other
green package artifacts were not substituted; no binary was downloaded/opened.

See `evidence/runs/pr55-first-ci/README.md`. Originals are private and sealed.
Collector target/SQL/CI reruns: zero. Evidence-only rollback removes these files
while retaining original results and all confirmed financial history. Independent
RAW review is pending; production and capacity approval remain NO_GO.
