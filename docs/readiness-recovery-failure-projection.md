# Preserve the actual recovery-readiness failure observation

PR63 source16f64fec's first push44353030187 failed its Python3.12 unit job;
first PR44353143243 succeeded. Collector6cd4c01d retained both scopes and reports
seven successful jobs and one failure, 2200 tests in each summary, with the sole
failure at test_process_readiness.py:200 in
test_same_version_changed_persistent_content_is_not_reused. Independent RAW
review remains separate. No previous failed result is replaced or retried.

That line checked financial_ready with no failure message. The prior assertions
in that method check rejection of persistent same-version changed content,
worker reason and unchanged stored faulty bytes; the reported failure is the
final check following activation of a distinct generation. The original log
does not contain that final diagnostic report. Its reason, lease, observed
market/control state and timing therefore remain UNDETERMINED. A preceding
successful wait is a different observation; it cannot supply the missing facts.

This candidate saves the same single diagnostics return value before evaluating
the identical financial_ready assertion. It attaches the existing finite
_readiness_failure_message projection to that same result. There is no extra
observation, wait, retry, altered predicate, changed market payload or replacement
financial result. The formatter already restricts output to booleans, finite
reason codes and bounded counts; it excludes arbitrary strings and identities.

No runtime, financial formula, fixture quote/lease/timeout, cleanup, assertion
outcome, source inventory or CI configuration changes. No target, import,
compilation, SQL, actor, test or new CI has run for this candidate. Static review
must precede a separate first normal CI. A future passing run would not explain
the historical failure, and a future failure would remain its own source scope.

Deploy this diagnostic-only candidate to the same fresh synthetic engineering
environment. Rollback reverts the two test lines and this document, with no data
migration or authority change. Keep all confirmed obligations, trades, positions
and journals. This instrumentation does not close readiness correctness,
funding differential, replicated recovery, capacity, production or real-funds
gates.
