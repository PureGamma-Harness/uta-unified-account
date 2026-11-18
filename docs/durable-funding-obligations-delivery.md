# Durable local funding obligations delivery

A local synthetic funding scheduler can now persist obligations before cash
settlement, page outstanding work after restart and query original command
outcomes. States are SCHEDULED, DUE, WAITING_DATA, WAITING_CAPITAL, APPLIED and
REVIEW_REQUIRED. An APPLIED receipt cannot be reopened; pending work stays
visible. Product/period identity and command replay prevent duplicate posting.

A trusted boundary cut freezes original quantity, account versions, event
watermark and code/rule/market bindings. Late execution without a valid cut
requires review; it cannot substitute current positions for old holdings.
Later settlement uses the frozen cash legs and current account risk. Missing
rate/quotes wait explicitly. Rounding uses real previously deposited treasury
capital, with traceable transfer and double-entry legs; no principal or capital
is minted. Existing FundingLocal and this capability reject coexistence.

The claim is a single SQLite generation/owner lease with observed UTC highwater.
It is not a managed HA writer or proof that a lease remains live until fsync.
Cut timing uses the declared trusted synthetic clock. No real scheduler daemon,
REST/worker activation or custody service is introduced.

Account and independent risk CODE reviewed the quote-gap corrections. The
proposed USD-quote gap003 was retracted because the public market command
requires USD at1; the correction and original gap report remain traceable.

First SQL6 source9171e8e5 ran six methods with internally passing financial
checks but the actual caller exited126/UNKNOWN: its plan dropped the first LF
of BOOTSTRAP. Strict argv comparison correctly rejected it. Independent RAWb5fbbf46
preserves46 originals7599738B and the exact one-byte mismatch; this result is
not replaced or relabeled.

The new intent-v2 source286f94e3 retains all69 target inputs, the caller and all
budgets. Its separate AST-only preflight derives the full literal and checks all
17 arguments without importing/executing target code. Root observed preflight
exit0 before the new unique run. The corrected caller actually exited0 with all
16 checks true, real prefix/outer wait/reap/EOF and no repair cleanup.
The two runs use separate new synthetic authorities and remain separate evidence.

Independent RAW77d5980a checked46 new sealed originals7602477B, all archive CRCs
and actual9 SQLite main files with a pure B-tree decoder, without SQL or target
imports. It independently checked46 journal events/9 authority-qualified matched
trades/18 side fills, USD0.72 fees, custody aggregate-15001,8 tasks/7 cuts/
48 commands,5 APPLIED and3 outstanding. Two declared competition threads exited;
all303 native handles were closed before cleanup and profiling hooks restored.
The new public finite export contains no DB, archive or process binding.

Tests22037626396ns, inner23717401549ns, target outer23983679558ns and caller
through validation24655524869ns have separate definitions; none is throughput
or a reconciled total wall time. Matches across independent namespaces are not
globally unique exchange trades. The reused target financial source remains
byte-identical after delivery integration; historical evidence retains its
actual execution SHA rather than the new publication SHA.

Deploy only with install_synthetic_fresh into a new authority, explicitly choose
this capability, use a valid current snapshot and pre-funded capital reference,
then query pending/command results and run verify/reconciliation. Existing
classic, funded, managed or old FundingLocal authorities must reject installation.
This release has no online migration. A deployed old binary is excluded by
environment isolation; managed old-writer exclusion remains unverified.

Rollback removes the candidate from a new environment while preserving all cuts,
commands, postings, failed first evidence and confirmed economic history. Never
delete pending obligations or reverse a confirmed funding post by editing rows.
Reconcile and use separately authorized compensating entries where necessary.

Pending funding is not yet reserved in order/withdraw/transfer budgets. The
fixtures do not cross MM or demonstrate negative-cash liquidation recovery;
persistent partial-market faults, crash/HA recovery, timer operation, custody,
multi-settlement assets, human financial signoff and sustained capacity remain
OPEN. This local prototype is NO_GO for production or real funds. First normal CI completed with a remaining blocker, detailed below.


First source118f7a6f push44307367546 failed only its Python3.13 unit job; PR44307604140 succeeded across all four jobs (7 successful/1 failed overall). Fixed push/PR3.13 logs each ran2061 tests: push1 failure/0 errors/skips, PR0 failures/errors/skips. All6 funding-obligation method IDs are plain ok in both selected logs; these12 observations are not independent local SQL6 RAW re-executions. The push failure is the existing bounded SH-capture precondition at test_durable_faults.py:1461, before the intended recovery case; cause remains unresolved and the first CI gate remains BLOCKED.

Collectore0dd90e2 and independent RAW104baa69 bind33 originals1577194B/two ZIPs6CRC,377-pin source maps and provider merge-tree evidence. The fixed push3.13 package is NOT_PRESENT because downstream stages were skipped; no alternative green package was substituted. New installed funding-module execution is NOT_VERIFIED and full qualification is null. This evidence-only integration changes no runtime, tests, tools, benchmark or CI files from source118f7a6f.
