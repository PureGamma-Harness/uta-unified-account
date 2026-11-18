# Independent FIRSTFAIL review: Cross538 pipe fsync

**Overall FIRSTFAIL independently confirmed. No execution-chain PASS.** The
unique execution of actual source `283dec8e16321697124a19847f103476136de683`
completed five test methods and538 recorded comparisons, then failed before
successful target exit. Both prefix exit and external root-tool exit were1.
This review added zero target runs, imports, compilations, SQL, process/PID
probes, signals or source repairs. It read sealed bytes/JSON/ZIP and Git only.

Owner SAFE seal `4f4dd04155e7da84e21527759614c1c8f292fd65`, tree
`4fe3896664f03cc50517acd99e5a0a39fc7896fe`, adds exactly eight finite files,
17,711 bytes, to actual source283dec8e. All export lengths/SHA256 match physical
files and Git. Export manifest is1,614 bytes, SHA256
`f1e1858d698867056d077a66f48713175728707a714d71ee3a19c4183cdd2078`.
Its numerical/terminal/cause projections match the independently read originals;
its opaque inventory exports no private paths, inode/owner/time bindings or full
vector payload. Full originals/ZIP/vectors remain PRIVATE, with no copies here.

## Confirmed terminal defect and correction of prior review

**CROSS-ENUM-ENTRY-002: inherited PIPE is passed to target fsync.** Frozen parent
`tools/run_cross_enumeration_capture.py:180` starts the target with stdout/stderr
PIPE. The unchanged target uses those descriptors directly and, after writing
vectors, its receipt and END, executes `os.fsync(1)` at
`tools/run_cross_enumeration_once.py:252`. Original stderr H003 shows:

```text
Ran 5 tests in 0.327s

OK
Traceback ...
  File "tools/run_cross_enumeration_once.py", line 252, in main
    os.fsync(1)
OSError: [Errno 22] Invalid argument
```

This is a bounded source/trace projection; the complete1332-byte stderr stays
private. Its SHA256 is
`7ec999a2ab69530128f091ce08cb1fffb291c279e99da7f492bf475da6fdd1f1`.
The actual frame matches Git283dec8e and the captured parent source. No native
FD/PID probe was required. The second fsync at253 is not reached in this trace.
The old file-redirection durability assumption was incompatible with the new
inherited-pipe capture contract; this is an entry defect, not a failed financial
comparison or missing-liquidity event.

I missed this deterministic descriptor-contract mismatch in review
`a175570745f6a5432460f4a9d463d83701b08dbe`. Treat its terminal-compatibility CODE
closure as **withdrawn/superseded by this confirmed finding**. That original
commit/report remains unchanged. Merely saying late fsync could fail did not
identify that the approved wiring supplied a pipe. The prior review's source
hash and negative-exit checking observations do not establish readiness of the
combined entry. The parent correctly refused qualification after the failure.

Required future minimum is to remove target fsync of inherited stdout/stderr;
the parent already fsyncs its own regular raw files. Keep existing target control/
vector-file fsync and parent sticky fsync-error handling. Do not broadly suppress
OSError. A correction needs new frozen source/plans, a fresh private namespace,
independent delta review and a distinct unique root GO. No correction or rerun
is performed here, and this first failure must remain first failure.

## Limited numerical evidence retained from the failed execution

All five original actual test IDs occur as `ok` in H003 and match the inner
receipt/vector groups. Counts are512/6/8/8/4=538, failures/errors/skips native
integer0. The complete866704-byte vector archive T003 has SHA256
`724c13aa2a429fc83e751304926e34ae00c7ecc5e684353fb6a16030dee4a44e`.
Every expected/actual map and verified stage was checked directly, beyond the
inner passed flag. All534 first-four-group five-field metadata maps have the
fixed expected native values. All recorded feasible-unit lists are ordered,
bounded and give the actual archived quote maximum. Hostile-context inputs
repeat the first eight seed inputs;538 is completed checks, not distinct states.

The four strict zero/equal-rate examples independently enumerate to9/10/9/10.
Additional direct hand arithmetic checks all six tier/freeze and eight MM/reserve
records. This verifies bounded archive consistency plus those explicit cases,
not a third full Cross implementation, joint borrowing/admission authority,
concurrency proof or production acceptance. Single-asset quote maxima cannot
be combined as jointly funded loans.

Target intent/BEGIN/END match source283dec8e, planf51c0f682c24febadfac5f8bb6338d26752e0bd90877843fee34f75a4efea255,
five selectors, runtime Python3.12.14/executablefa674435/isolated/no-site/no-bytecode/
CPU1, and eight loaded UTA modules. No forbidden listed event was reported and
thread count is1. Original target before/after facts match; all70 host pin maps
match before/after and exact Git objects. This is trusted source/archive evidence,
not hostile-replacement attestation or a general OS sandbox proof.

## Actual outcome, resources and sealed originals

H009 records actual prefix1, successful wait/reap, both EOF and no internal
capture fault. It retains the numerically complete inner receipt but its own
status is FIRST_FAIL_OR_UNKNOWN_NO_RETRY. Internal actual_host_exit is null,
as required. H010 preserves root tool chunkb9fe1f's actual exit1 and its exact
literal tasksetCPU1 command; tool output equals the98-byte parent summary H001.
Thus inner passed=true and END cannot override actual terminal failure.

Raw stdout H004 is13011 bytes, stderr H003 is1332:14343 reserved/written bytes,
no short write/cap overflow. Both summary copies add196 bytes; total14539 stays
under32768. The capture inventory's exact eight pre-inventory files match their
digests. Inventory excludes itself and the root witness added afterward.
Original target controls total895773 bytes; original runtime parent controls/raw
total60711, combined956484 before the1011-byte root witness:957495 afterward.
This is final logical use only, not a transient/kernel quota proof.

Separate clocks remain separate: unittest log0.327s; target module-loading/tests
370308485ns; prefix launch-through-wait/drain/raw-fsync673916129ns; parent start
to before-receipt752083973ns. Tool reply wall0.667241169s is retained as reported,
not asserted to be full host lifetime or E2E latency. No throughput conclusion.

All13 originals/957495 bytes match seal hashes and device/inode/mtime/seal-after-
ctime; files0400 and roots0500. Private seal7309 bytes SHA256
`cc273abb112b833d276092ef7185efd8524b97c2980369942c10e98454bbead1`.
Private ZIP107660 bytes SHA256
`f1153c2e23277feb5ae918b44956444520a8f8318b8089268ae6f9e2a7d46d20`;
all13 member CRCs/content match originals. All13 content hashes still match
after review. No claim covers unchanged atime or external descendant discovery.

One reviewer-only parser initially keyed originals by relative name, merging
target/host intent.json and failing its total assertion. It was corrected to
role+relative; the original tool failure is retained. Owner separately disclosed
its administrative source-selector assertion/correction in SAFE metadata. These
metadata operations are distinct from the one target execution and do not
erase or retry its terminal failure.

No deployment/data migration occurred. Preserve all old plans, first raw bytes,
vectors and financial history. Production, service activation, SQL/matching,
custody, HA, capacity, real funds, insurance and ADL remain NO_GO. No main
worktree/index operation was performed by this independent RAW review.
