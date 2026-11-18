# Isolated m08 correction and its distinct first pure result

Atbf48ae2 this was a CODE-only, zero-execution preparation. Root subsequently
authorized its isolated first run: one method/four original selectors PASS,
zero failures/errors, actual host exit0, no retry. The [new first evidence](../evidence/reviews/owned-startup-read-admission/phase1-m08-first/README.md)
retains complete raw/host/input binding; it does not replace the earlier RED.

The first source88da96f run remains RED in sealed47dfa75, independently reviewed
at85a3d3c as EVIDENCE_BINDING_PASS / TEST_RED. Its12methods,11OK/1FAIL/0ERROR and
45 entered traces are unchanged. Three later m08 selectors and the known case's
post-counter receipt assertion were not covered. Preparations72dcebf/166ddf9
remain zero attempts; the separate conditional baseline has three RED.

Only fixture method08 changes. A local observer calls the existing stdlib
`copy` unchanged, retains the returned keeper Database object, and returns that
same object to the actual selected `_OwnedStartup._renew`. It neither replaces
the production copy implementation nor changes production renewal/COMMIT logic.
The successful-COMMIT counter expectation stays **one**, now checked on the
actual keeper copy. Additional assertions require exactly one copy, a distinct
Database object with the same connection, and the original Database's unchanged
zero integer counter. The one-COMMIT assertion now also covers the wrapper's
post-COMMIT unknown-return path. It is not weakened to expect zero COMMITs.

The four selectors and existing error identity, failed-attempt, last-known
receipt, wrong-receipt-token and optional-import assertions retain their
conditions. There were seven original assertion calls; six retain exact AST
arguments and the seventh changes its counter referent from the original to
the keeper object. Four additional observation assertions distinguish that
referent. The eleven other test method ASTs, all helpers and the original
whole-suite runner are identical to executed source88da96f. The static audit
record is `phase1-m08-CODE-isolation.json`; no method body ran during this audit.

The new `run_phase1_m08_once.py` loads the frozen fixture definitions under a
non-main namespace and constructs an explicit TestSuite containing only
`test_08_owned_same_token_last_known_and_postcommit_wrapper_unknown`. It does
not use discovery, the original twelve-method main runner or the other eleven
test bodies. Its result can pass only with exactly one method and four entered
selectors as well as successful assertions. Loading definitions is not itself
a native/product import; selected actual methods still use the reviewed memory
connection/COMMIT/clock/PID/lock/virtual-module boundaries. The original all12
driver/plan and original referenceJSON remain byte-identical to88da96f.

The new `phase1-m08-focused-plan.json` pins eight regular materialized files,
including the new driver and modified fixture. The3runtime/tool inputs remain
exact6303 bytes. Original tests are pinned only as unchanged-source provenance;
they are neither imported nor executed. The driver preserves the same reviewed
pre-exec immutable-byte binding, runtime/version/executable/flags and actualCPU1
checks, O_EXCL0700/0600 first evidence, shared256KiB reserve-before-write capture
with512-byte trailer, sticky125, internal10s and fixed outer timeout/taskset
argv. Only the event names, plan path, explicit one-method selector and reported
counts differ from the original driver. A definition-time stop cannot pass.

The source preparation itself had zero target executions. After independent
CODE review, root granted one specific CPU1/10s budget for the original four
selectors, below its8-trace maximum. No old11-method or all12 run was included.
Every first stdout/stderr/host exit and incomplete result is retained; no retry
follows a RED/ERROR/UNKNOWN. This successful isolated result supplements its
distinct source and preserves the original RED. No all12 rerun or
native/financial/CI/capacity approval is claimed.

Original PR38 causes remain UNDETERMINED. Phase2 remains NO_GO, and no expiry,
lease duration, keeper period, admission or financial policy changes. Rollback
of this CODE-only preparation reverts m08 and removes its new driver/plan/docs;
all original source, first RED/raw and independent review remain preserved.
Any real deployment or code-bound-authority upgrade needs separate qualification.
