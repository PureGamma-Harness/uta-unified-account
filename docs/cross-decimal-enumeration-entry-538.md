# Enumerated Cross entry delta: 538 checks

CODE_ONLY / NOT_RUN. Original source7b449f30 and its frozen536-check CODE
plan remain historical. Independent review2ce623c8 identified two explicit
gaps: nonzero equal IM/MM borrow rates, and failure-time vector retention.

The new last method adds USD11/LTV1/IM=MM0.1/step1 -> maximum9 and
USD11.01 -> maximum10. It retains the prior two zero-rate cases. The five
methods now require completed counts512/6/8/8/4=538, with the hostile-context
eight repeating the first eight seed inputs. Counts are checks, not538
distinct economic states. USD and BTC quotes are individual counterfactuals;
simultaneous quoted withdrawals are not authorized by the calculator.

Each check now sets active_vector before model construction, saves independently
computed expected values before calling the candidate, and saves actual values
before comparison. The retained entry archives completed values and any active
failure vector including partial stage. No active-stage record certifies a
completed test. Its result adapter captures ordinary errors/failures and
subTest failures without suppressing unittest's original behavior.

tools/run_cross_enumeration_once.py derives its full-module loader, guard and
stream accounting from the reviewed nine-method entry at public667171d1.
It uses the new five selectors and archives vectors.json before the outcome
receipt. It inherits externally captured stdout/stderr; it does not redirect
FDs away from the future parent capture. Each JSON file is capped4MiB and
control reservations share8MiB minus32KiB. Raw Python stream reservations
include a512B failure trailer and leave1024B for parent observations.

The target has no SQL, network, child process, worker or thread start. Existing
stdlib imports are trusted runtime dependencies; unittest's signal-module
import is not a signal invocation. The target cannot certify its own future
exit. External capture, actual prefix wait/reap/EOF and final source/Git checks
remain required before GO. This entry alone is NOT_EXECUTION_READY. Its future
proposal is CPU1, target20s plus2s classification, shared raw32KiB and logical
control8MiB. It gives no hard bound on blocked native filesystem I/O.

Only new synthetic pure inputs are eligible. Preserve first FAIL/UNKNOWN, full
vectors and source bytes, with no retry or fallback. No financial source,
migration, feature selection, product mode or default is changed. Rollback
removes these test/control files while retaining original536/538 evidence.

CROSS-ENUM-ENTRY-001 from independent d1c7551a is corrected by archiving all five expected provenance scalars before the candidate and all five actual scalars before any comparison. Historical4ac29 plan is preserved byte-for-byte as NOT_RUN; vector count, financial models and budgets remain unchanged.
