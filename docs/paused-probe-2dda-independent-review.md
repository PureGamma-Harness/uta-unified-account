# Independent paused-probe review: 2dda177

Reviewed source: `2dda177fc023c023f7a7d246f03c1530e4511f9d`.
Reviewer branch: `review/paused-probe-2dda`, separate worktree. This review does
not edit the author's test, driver, policy, original failure artifacts or runtime.
The reference base remains `8b7f544fcbdfd540d43de1d6560022c6ebbd3799`.

## Decision and limits

**GO for one CPU2 / Python3.13 native BUSY microcomponent, with the acceptance
conjunction below.** This is permission to obtain evidence, not a component PASS,
release acceptance, historical protocol-error reproduction or financial authority.
No native database, process injection or signal was executed by this review.

The complete test diff and 225-line driver were inspected. Production `uta/`
is unchanged. The selected capture uses the existing eight-attempt/five-second
horizon. The owned stop is undone without reading the blocked database. Only
actual kernel progress followed by one fresh native status read can reenter
capture; the same owner/generation must remain active. The .1-second status
budget is unchanged. Unknown observations do not become leases. Final cleanup
performs no status read and records an error without replacing an existing
primary exception. A cleanup error with no primary still raises.

The protocol exception rule is test-only. Ordinary callers still propagate
protocol errors. The explicit owned-stop flag permits only native base15, or
an exact builtin no-native-attribute `locking protocol` legacy exception, to
return unavailable/technical UNKNOWN. It does not treat that error as BUSY,
healthy authority or a financial result. Native IOERR, CORRUPT, NOTADB, LOCKED
and other errors remain fatal. The actual historical logs do not record a
numeric error code; the base15 rule is a system policy, not recovered evidence.

The undo helper checks pidfd exit readiness and PID/birth/boot/UID before a
signal. A known inactive/other-owner/other-generation value cannot take the
normal resume path. In cleanup it forces termination and marks that outcome.
The caller constrains this helper to its own injected stop. This is trusted
test code and does not create an external authority interface.

## Actual pure checks

At 2026-11-17 14:26 UTC, CPU3, `/usr/bin/python3.13`:

- The author's seven synthetic exception-policy tests passed once in .005s.
- Eleven separately written mocked undo vectors passed once. They cover same
  owner, unknown observation, known inactive, cleanup forced kill, other owner,
  other generation, changed birth/boot/UID, already-exited and exit-during-undo.
  Every vector forbids `WriterFence.status`; all signals, polling and identities
  are mocked. No SQLite connection, `/proc` read or native signal occurs.

Raw output and the separate vector source are in
`evidence/reviews/paused-probe-2dda/`. These checks validate control dispatch,
not a real SQLite lock or a process identity race. They are not substitutes for
the proposed native check or a new complete-release matrix.

## Native evidence acceptance conjunction

Use the unmodified author driver SHA256
`0768f4bc76e808dab4eb05f2844dface420de335ed146bb2c673d75db08236e1`
and test SHA256
`389ab057ab0e12fc0eb73d9f990a084c82565e2cb76dd0e8ac8c2fe8325309f6`.
Launch once from exact2dda with a new private output directory. Preserve any
failure; do not tune or repeat it into a green result. The native mechanism is
an intentional scratch EXCLUSIVE schema-observation lock with zero financial
DML, not a claim about the historical worker's unique WAL operation.

A successful exit code alone is insufficient. Independently require all of:

1. Exact source and both file hashes remain unchanged before/after.
2. Launch timed_out=false, exit0, actual whole wall <=30 seconds.
3. Worker component_passed=true and exactly eleven named checks, each true.
4. Original real BUSY5 exception object preserved through undo; zero status
   calls during undo; the three actual parent status reads have exact phases.
5. Actual same native owner/generation active after releasing the real SQLite
   and SH locks, with unchanged expiry and no renewal/reacquisition.
6. Native child exits normally, all owned identities are absent, and neither
   worker nor launcher used forced cleanup or reported residual/unknown state.
7. No logger/cleanup error; integer cash oracle and financial rows unchanged.
8. Retain launch, worker, trace and stdout bytes, including a failed attempt.

The internal watchdog covers the worker group for27 seconds, followed by
bounded waits/reaping. It is not a general OS resource reservation or proof that
arbitrary I/O cannot stall the outer launcher. The operator must enforce and
check the separately stated <=30-second whole-operation boundary. Any forced
outer termination, elapsed-budget overrun, incomplete artifact or unknown
cleanup result is NO-GO, even if another file contains exit0.

This microcomponent exercises BUSY5 and cleanup semantics only. It does not
manufacture native15, rerun the complete publication test, demonstrate HA,
prove financial replay, or qualify the source for production. Original8b
1472-test failures and the earlier scoped3af PASS remain unchanged.
