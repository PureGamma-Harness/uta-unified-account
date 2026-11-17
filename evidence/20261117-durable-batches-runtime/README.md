# First batch runtime checkpoint evidence

All accounts, prices, keys and debts are synthetic. No throughput or long run
was started. Files are actual unittest OS stdout/stderr captured at each named
stage; failed intermediates remain failed.

- `initial-assert-scope-error.txt`: authorizer denial is translated when the
  managed context exits; an inner assert was the wrong fixture scope.
- `selection-expired-fixture-error.txt`: an intentionally unresolved manifest
  correctly blocked prepare before the fixture reached its expired-token case.
  The fixture now resolves first, then checks the expired token.
- `process-first-three-fixture-failures.txt`: three wrong fixture assumptions:
  non-atomic marker content publication, start() waiting for worker READY, and
  all three selected commands fitting in a 5ms soft budget. Runtime actual
  financial completion remained separately observable; these did not pass.
- `core-py312-first.txt`: first 47 focused checks after the assert-scope fix.
- `core-legacy-py312-15.txt`: actual archived-source process checks included.
- `process-core-py312-19.txt`, `process-core-py312-21.txt`: later focused stages,
  not qualification for subsequent untested source changes.

An intermediate refactor also had a NameError (`now` moved into the selection
helper). Its full failed output was emitted in the tool transcript, not saved
as a raw file. This evidence gap is explicit; no reconstructed log is presented
as original output. The local variable reference was corrected before the later
recorded tests.

Source is evolving. Only each named checkpoint's stated scope is claimed. All
production, HA, real-funds, 6h/24h and 10k flags remain false. Separate authority
review found an extra-trigger inventory blocker after the first core commit;
that finding has not been silently counted as resolved by these green tests.
