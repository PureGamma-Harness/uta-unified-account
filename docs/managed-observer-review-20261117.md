# Observer boundary review, 2026-11-17

Scope: independent review of observer `4d6ef69`, followed by own-tool fixes.
Two independent read-only subreviews checked the mount/FD/host-PID boundary and
the private-clone/qualification/final-watermark boundary. No real service,
one-minute soak, long observer or capacity test was started. The frozen producer
sources and the earlier 887 job, its databases and PIDs 4471/8784 were untouched.

Confirmed defects and resulting behavior:

| Finding | Correction |
| --- | --- |
| An inherited writable stdout FD bypassed a read-only bind mount in an isolated ordinary-text microprobe. | Reject regular fd0/1/2 silently before any CLI output; subprocesses use DEVNULL input, PIPE output/error and close nonstandard FDs. Trusted launchers save only controlled external outputs. |
| Full SQLite backup includes historical writer/control nonce columns and internal paths. | Root explicitly chose a private complete clone, preserving actual schema/identity semantics; old no-nonce/public-snapshot claims are retained with a visible correction, not silently rewritten as historical truth. Only allowlisted receipts/observations may be public. |
| Qualified clone omitted `validation/` artifacts required by actual producer audit. | Copy the three exact allowlisted artifacts with pinned hashes, preserve 0700 directories/0600 files, and execute the actual producer audit on the clone. |
| Final reopening compared only the business watermark. | Require its own golden, integrity/FK and retry checks as well as the same watermark. Recheck source, complete validation, original metadata/progress and original file identities at the end. |
| EACCES/malformed proc data appeared to prove a stopped process. | Distinguish observed, absent and unknown; require known stopped driver/listener/last worker identities for final acceptance, including a released lease owner's last recorded birth. |
| Observer qualification checked artifact immutability without independently checking all report success semantics. | Recheck typed literal flags/counts, worker agreement, raw log, full command, producer runtime, complete source inventory and tracked source membership. |
| Audit interpreter could differ from the validated runtime. | Probe actual Python/SQLite before making a clone; require exact metadata/evidence match and bind the audit runtime into the receipt. |

The mount is a guard on this tool's controlled pathname/SQLite opens. Host PID
namespace/stat visibility is intentionally retained and relies on a trusted
launcher; this is not an adversarial code/host-proc sandbox. Existing regular
stdio is rejected even when its path looks safe, because hardlinks and inherited
descriptors are not constrained by pathname checks.

The full clone lives only in `private-audit/private-full-clone-*`. Normal errors
clean up; an uncatchable kill can leave a private residual. Its disk cap is a
conservative estimate, not a filesystem quota. The default 2 GiB `RLIMIT_AS`
limits virtual address space, not measured RSS. Samples stream to JSONL and the
preceding full CID sample is released before another read. Full six-hour RSS,
output size and sampling latency remain unmeasured.

The independent subreviews found the original blockers addressed and no further
determinate false-PASS path in the revised boundary. The private-clone review's
last interpreter-identity recommendation was then implemented and covered by
actual runtime-probe and wrong-runtime regression tests.

Verification uses only tiny private fixtures on one allowed CPU. The producer
audit regression now executes the real producer's read-only `audit` command on
a hand-built SQLite fixture; it no longer mocks that first subprocess. Its
qualification sidecars are deliberately unit-test fixtures, never service-start
inputs and never evidence of actual release QA. Other report fixtures likewise
test rejection semantics without claiming a genuine validator run.
The final bounded regression run executed **47 tests in 1.221 seconds, OK**,
with the runner and its read-only audit children pinned to one allowed CPU.

The one-minute real synthetic smoke remains **pending** the new 7ae94eb freeze's
complete overall QA and root GO, with the exact matching Python 3.12 report and
runtime. See [the smoke plan](managed-observer-smoke-plan.md). Every long-run,
24-hour, production and 10k flag remains false; this review is not formal signoff.
