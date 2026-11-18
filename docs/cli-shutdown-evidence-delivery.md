# CLI shutdown failure evidence delivery

The first local Python3.13 full run at source6b7 ended with one ERROR: the
automation CLI did not exit within its original five-second wait after SIGTERM.
Its child stdout/stderr were discarded by cleanup, and no child stack identifies
the blocking phase. This delivery improves failure evidence. It does not fix or
claim a cause for that shutdown timeout. Trading runtime is unchanged relative
to recovery delivery6010.

Only the synthetic CLI test changes its observation plumbing: binary unbuffered
pipes retain the consumed banner prefix plus the remaining complete streams.
Business argv, startup/health/exit deadlines and business assertions remain
unchanged. Failures retain process identity, monotonic phases and raw streams in
private0700/0600 storage. Public notices contain typed identity/status/size/hash
fields. No EOF or exit proof means UNKNOWN rather than complete/reaped. Success
does not create failure archives. Archive/cleanup errors preserve the original
test exception, and fallback cleanup is registered before observer construction.

The first seven pure checks passed. Independent fake checks then found three
identity/cleanup defects, and those original RED results remain retained. Code
a43ce07 fixes them using a complete typed identity allowlist, safe unknown
observations, dropped extra fields and earlier cleanup registration. The one
new8+4-check pure batch passed. Independent CODE reviewf48e1bd checks these
closures, exact source/raw bindings and the unchanged normalized business AST.
The injected-reader counterexamples are not evidence of a default/proc secret
leak or a cause for the original timeout.

No actual CLI rerun, SQL, worker, signal or financial transaction was performed
for these fixes. A separately reviewed single-case native diagnostic remains a
future step with distinct source, output and execution authorization. It cannot
replace the original full-suite failure even if it passes. This test is separate
from the previously rejected AuthDB authorization probe.

Deployment changes test diagnostics only, without a schema migration, public
API change or service restart. Rollback restores the original test observation
plumbing while retaining both first failures and private originals. Integrated
CI, recovery correctness, production, real funds, sustained capacity and HA
acceptance remain open gates.
