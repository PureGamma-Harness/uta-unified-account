# Independent review: finite monitor failure diagnostic

**CODE CLOSED for the diagnostic-only scope; execution and native causality remain OPEN.**
Reviewed code `4f23633b418b817be594cc2ae014379058540b04`, tree
`20f6b0d04684c37ae38739f85b3406c85da010a2`, and preparation owner
`f30b431b1f3e39b47636f5abf4227f36f978c17b`, tree
`6ac86009be2d89324f9e04d69738bed80ca3ebb9`. Base is PR49
`7665253ced0888e8204b9806b63c4163f2cafe42`. No target was imported, compiled,
tested or executed; no SQL, native/process/PID probe, signal or child was used.
Git/text/stdlib AST and byte hashing only were used for this code conclusion.

## Preserved behavior and observation limits

Removing the one new helper import and unwrapping the selected test's final
Try produces an AST identical to the original entire test module. The five
wrapped statements preserve the original publication timeout4, elapsed assertion5,
publishing assertion, worker-change observation and halted assertion. Bootstrap,
STOP injection, lease0.6 and cleanup are unchanged. The helper is called only
after a failure in that tail, before the original cleanup. Nested BaseException
handling suppresses diagnostic failures, and the outer bare raise retains the
same primary exception and traceback. Success only adds the inert module import;
it invokes no observation or output. The four new pure test methods add test
coverage proposals, not an observed unit-count or pass claim.

The new helper reads live frame code filename/function/line metadata only.
Paths are mapped to a finite allowlist; unknown functions/modules become
`<unlisted>`, line numbers are bounded native ints, and no path, thread ID,
exception text, PID, nonce, router worker cache or registration payload is emitted.
It neither reads live-frame locals/globals nor acquires the router mutex or a
Python stream lock. It creates no thread, process, signal, SQL or PID operation.

`sys._current_frames()` necessarily creates references for all interpreter
threads; the helper selects only current-caller and cached supervisor IDs,
walks at most eight frames each, and clears the snapshot dictionary in finally.
It verifies exact native Thread type/name and two unlocked `_active` identity
samples. This does not prove that a snapshot frame belongs to the same thread
incarnation throughout the sampling interval. Its `matched_unlocked_samples`
label and documentation correctly describe a racy memory observation, not
process ownership, SH ownership, shard identity or causal timing proof.

The primary projection uses the already-loaded native `capture_failure` from
unchanged `uta.failure_diagnostics`. `durable_process` imports durable_commands,
which imports that helper. No new failure-time financial import is introduced.
The existing helper bounds eight causes/eight frames/16 metadata attributes,
does not format exceptions or read locals, and obtains only bounded traceback
module `__name__` metadata from globals. The new projection retains two causes,
eight frames each, allowlisted type/module/function/public-code fields, bounded
SQLite numeric code, and truncation/cycle flags. This is not a claim that the
existing primary helper never reads `f_globals`; that narrower claim applies
only to the new live-stack walk. Unavailable collector metadata produces a fixed
failure packet and preserves the original test exception.

The rendered ASCII packet, prefix and newline included, is at most32768 bytes.
Oversize produces a fixed quota packet. `write_packet` refuses a blocking
non-regular descriptor before writing, leaves FD flags unchanged, and makes at
most one `os.write`, with no retry for a short write. The unchanged validation
runner redirects child stdout/stderr to its regular `unittest.txt` descriptor.
Nonblocking sinks can reject or short-write; a partial/missing packet is not
complete evidence. Regular-file writes, interpreter snapshot/audit hooks and
external descriptor rebinding do not have a hard wall-time guarantee here.
No new watchdog/lock workaround is added and no sandbox claim is made.

## Source binding and remaining acceptance

All66 source-manifest entries match Git blobs, byte lengths and SHA256 at both
CODE and owner: 1,380,956 bytes. The61 financial runtime Python files and unchanged
worker are byte-identical to PR49. The actual worker source has seven native
unit-result fields plus the two lease-observation projection fields, nine total;
no old seven-field result or earlier native run substitutes for its execution.

The source worktree is sparse: only the four declared diagnostic/doc/test inputs
are physically present and Git-matched; 62 runtime/worker inputs are missing.
This is a Git closure, **not physical runtime materialization**. Manifest SHA256
is `d92eda08887c70ace7dfdbfdca7b62dd406cd2870e9db3871c6b3d59184bb094`;
plan SHA256 is `0f12682f32eb7d4fa4ad25dce8044b9a3ab39642ddc6eee9a317eff4a1cabf37`.
AST checks verify four fixed pure method names, the exact original-body
restoration, bare raise and absence of new helper process/SQL/signal/mutex calls.
These static checks do not substitute for executed pure assertions.

A minimal bounded pure entrypoint with exact source/selector/resources/host
capture must be prepared and independently reviewed before a separate root GO.
Only the helper and four inert pure tests are proposed; they patch frame/Thread/
FD operations and do not prove native recovery or the real failure-path metadata.
Full physical materialization and exact source review precede any wider native
or ordinary CI execution. The first actual result must be preserved.

Synthetic registry baseline/cap fixtures are not implemented or run. The
documented different shard-order schedule is an assumption, not a replay of the
original stopped-shard0 CI failure. A frame in `_record_process` cannot identify
the registration shard or establish that it preceded the selected holder's
kill. Real first-CI cause remains UNDETERMINED. This diagnostic does not add the
historical0.1s registry cap, change existing10s connection policy, renew TTLs,
retry the failed4s publication, repair holder proof, or certify availability.
Production, HA, capacity, real funds, insurance and ADL remain NO_GO.

Rollback reverts only the test import, exception wrapper, helper and its inert
tests while retaining first failures and any original packets privately. No
schema, financial source, ledger, risk parameters or authority migration changes.
Full CI/unit logs still require separate private retention and finite export
review; an allowlisted packet does not make the rest of the log public-safe.

## Review-workflow incident: main index prestate UNKNOWN

During creation of this independent worktree I mistakenly ran this exact shell
with workdir `/workspace/uta-unified-account`:

```text
git worktree add --no-checkout -b review/monitor-registry-failure-account /workspace/uta-monitor-registry-failure-account-review f30b431b1f3e39b47636f5abf4227f36f978c17b
git read-tree HEAD
```

The tool's overall shell exit was0. The final read-tree command therefore had
actual exit0; the worktree-add individual numeric exit was not separately
captured (UNKNOWN), although normal creation output and the new worktree were
observed. No preceding main-worktree status/index snapshot was collected.
The before state, possible loss of staged changes and exact changed-path list
are UNKNOWN. Read-tree is an index operation, but its command semantics are
not a before/after proof that no staging was lost or no relevant state changed.
My initial message saying no files changed was too broad as an evidence claim;
that assurance is withdrawn. Parent was notified immediately and owns read-only
investigation. I performed no main-worktree repair/reset/further read-tree.
Parent subsequently reported a read-only check around11:47: current
`git status --porcelain-v1 -z` had zero entries and `git diff --cached --quiet`
returned0, so the index then matched HEAD. The original prestate remains UNKNOWN;
this poststate does not establish that no staged changes were lost. No business
recovery is indicated by the accidental index command itself.
This incident is separate from target execution; it remains an OPEN workflow
record and is not erased by the static CODE closure above.
