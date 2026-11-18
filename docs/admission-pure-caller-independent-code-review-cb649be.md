# Independent PURE7 caller CODE review: cb649be

**NOT CLOSED / NOT_RUN**, with one concrete completion-deadline finding.
Reviewed caller CODE is `68b650e21f26140e6d8f70ec477f75868bfa7399`, tree
`5b3a2b7ebfc0526eeb322f0e2adc106d1154c1e5`; invocation OWN is
`cb649be08f7d0d67ad5d1558a9c6b16352e30c19`, tree
`33039663772276c3768fa1d3e15a59b0597320d3`. No target, caller, SQL, PID API,
worker, probe or benchmark was executed. No child agent was created.

## Required correction

At caller lines141-157, the normal pipe loop can end at its30s deadline with
`eof=False`. If the outer has already exited, the following `wait(timeout=0)`
can nevertheless return0/reaped. The finally drain at lines190-199 can then
observe only EOF and overwrite `eof=True`; it sets sticky only for late bytes.
The remaining completion guard at line266 permits deadline+2.2. Thus a normal
completion not observed within30s can be repaired by late EOF and qualify as
PASS. This contradicts the declared timeout-to-UNKNOWN contract. It is a
static path finding, not an executed timeout or a failed test.

Keep a separate sticky normal-completion qualification. It may become true
only when both original EOFs and actual outer wait/reap have been observed
before the original30s deadline. Finally may supplement true exit/reap/EOF
facts, but cannot restore that qualification. Preserve a genuinely observed
rc0 as rc0 while classifying late completion UNKNOWN. The2s reap/.2s drain
allowance is cleanup/validation capacity, not a successful capture-window
extension. Rebind the new caller source/plan before any GO; keep the retained
entry, pure plan and financial/test bytes unchanged.

## Other finite checks

Caller18,696B SHA-256
`e2ea7f486f650cbdcb95edc555bd78098f6be818fb83e04a4ecea08f2661192f`
and caller-plan SHA-256
`d81205f9f81033e6488e58bf0402ea77ab4f5aa2f4e6c05f6bb0f041cbf66fb4`
match physical regular files and final Git. All64 retained pins/1,337,823B
match; entryc84a, pure-planc7c1, all61 UTA and both tests remain unchanged.
The caller is a separate65th control pin, not target-retained code. The exact
bootstrap literal matches the retained entry. Both proposed private namespaces
are absent at review time. Only metadata and AST were processed.

The caller validates actual final HEAD, both plans,64 inputs, self pin and
runtime before releasing its new child. It records sys.orig_argv and literal
gated Popen/outer argv. The birth check rejects protected literals before
pidfd/gate release. Failure cleanup uses only a held descriptor for this new
Popen child, at most one KILL attempt, and waits on that original handle; no
proc read, foreign lookup, bare-PID signal or raw waitpid fallback is present.
Normal success requires no cleanup attempt. Outer timeout never certifies
descendant reap. This source inspection invoked none of those capabilities.

The1KiB launcher cap reserves512B, makes short/overflow capture sticky and
requires empty launcher payload. The target32KiB remains separate; successful
aggregate acceptance reserves caller trailer capacity within32KiB. The64KiB
caller controls plus target logical accounting remain within8MiB on success,
without a cross-process hard quota claim. Full BEGIN, inner intent/receipt/END,
capsule64, literal timeout/bootstrap argv and source-after checks address the
previous caller-binding prerequisites. Actual external caller exit/end still
must be observed: CALLER_END, pre-fsync records and proposed statuses cannot
prove their own future process completion.

No other specific blocker was found in this finite caller delta. Earlier
entry f4af and financial071e closures remain unchanged. Earlier caller
preparations remain NOT_RUN history; none is a target RED or retry. This old
cb649 source is not approved for a first run. Four SQL tests, migration,
performance and production remain unauthorized. This review writes only its
two safe files and preserves author/source and earlier evidence.
