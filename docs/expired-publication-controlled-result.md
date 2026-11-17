# One exact3af native component: scoped PASS, original full d421 still NO-GO

The integration lead authorized exactly one candidate run after independent
static review. Source was fixed at `3af589415ccfdb65ed84a952184a77030319a3df`,
clean before and after. The candidate helper SHA was
`d3387b91640171fe81fea4bc2ecf0d49f995eb4ce992affc2db9bc5789f3f8b5`;
test SHA was `03d48b5d34348a617c0a8cfee69abd9f3449a0c8e95a83020d26b14d70ab3105`.
All252 validator inputs were unchanged during execution, and every UTA runtime
file still matched immutable d421. No candidate/runtime change or second native
attempt occurred after this run.

Actual interval: **2026-11-17 13:27:13.452796 to 13:27:20.440180 UTC**,
6.987 seconds including the watchdog launcher and normal cleanup. Python3.10.22
ran the one testcase on CPU2; unittest reports 6.767 seconds. The full original
d421 matrix failure remains NO-GO. This component is not a replacement full
suite, package test, smoke, soak, capacity run or production approval.

## Actual lock and lease facts

Two capture observations were needed. The first retained a genuine bound
kernel SH lock but its actual SQLite BEGIN IMMEDIATE probe returned BUSY, so it
was correctly rejected as the desired pre-write fault setup. The same still-live
and unexpired binding was resumed. The second retained the same PID's native
READ record and the zero-DML BEGIN/ROLLBACK probe succeeded. The separate EX
probe failed as required. These were bounded fixture observations, not retries
of a business command. They demonstrate why the writer probe was needed;
they do not establish the unique cause of either historical failure.

The original worker was PID198062/birth5916033, generation1. A genuine .1-second
unexpired control confirmed it remained alive, active, bound and holding SH.
Its real five-second lease was not edited or renewed while paused. Publication
started only after a native remaining-time observation <=.25 seconds; the actual
publisher thread also observed the original binding still active. The real
supervisor killed that expired original child, and the successor PID198068
acquired generation2. No worker implementation was patched.

| Actual observation | Seconds from original publication thread start |
| --- | ---: |
| Bound old pidfd exit | 0.272428 |
| Original parent publication actually enters EX | 0.278103 |
| SQL confirms active new generation | 0.610802 |
| Original publication succeeds and finishes | 0.850245 |

All three recovery milestones met their separate original five-second horizon.
The **capture-to-old-exit duration was 4.830953 seconds** and
**capture-to-publication-complete was 5.408770 seconds**. The lease-wait period
must not disappear from reporting. The subsecond publication observations
therefore are not a subsecond fault-trigger RTO claim.

The separate 15-second watchdog covers the entire publication thread's success
lifecycle, including the API's distinct wait phases. It is neither merely
cleanup time nor an increase or substitute for the five-second recovery
assertions, and it does not create a five-second end-to-end production SLO.

## Original identities and financial scope

Original snapshot content identity, derived from the preserved full payload, is
`market:13beff1e50518f0c97af774fc2683c7f952bef0e07f6cb7685d21450a289cc98`.
The actual original publication CIDs were:

| Shard | Actual CID | Sequence | Persisted result |
| --- | --- | ---: | --- |
| 0 | `market:3:0:13beff1e50518f0c` | 4 | SUCCEEDED |
| 1 | `market:3:1:13beff1e50518f0c` | 3 | SUCCEEDED |

The bound test compared each exact original receipt to stored status and each
local market payload to the original bytes, without restamping observed_at or
submitting another publication. These facts are combined with the raw actual
receipt observations by the strict verifier.

The business command `held-gate-command` was enqueued once and initially only
durably queued/PENDING. Observed orders and ORDER_ACCEPTED events were both
zero. This is not evidence of business admission, matching or settlement; its
final business terminal was not independently recorded by this component.
The original test's orders<=1 invariant is retained and strengthened with
accepted-events<=1 and original order/account identity. Ledger events,
postings, balances, debt, fills, positions and matches were unchanged. Trading
schema3, ledger schema1 and configured cache capacities0 were checked. These
are direct fixture row/receipt comparisons, not an independent full risk replay
or cross-shard accounting proof.

## Strict acceptance and cleanup

The launcher did not time out, logger_failures was empty, and neither test nor
launcher needed forced cleanup. All three native child pidfds recorded exit;
their original identities were absent afterwards. A post-run query of only
this session198059 returned no remaining process rows. No old authority, job,
process affinity or signal target was touched.

The [read-only verifier](../evidence/runs/expired-publication-d421/controlled-3af-once/verify_trace.py)
uses only stdlib JSON/hash checks and the immutable records. Its
[twelve-predicate AND](../evidence/runs/expired-publication-d421/controlled-3af-once/strict-acceptance.json)
requires the actual case, source/helper identity, kernel/probe, unexpired
control, three separate horizons, original publication IDs, financial checks,
logger/watchdog and complete child cleanup together. It does not accept exit0
alone. The integration lead independently recomputed the same facts; that
unaltered [review record](../evidence/runs/expired-publication-d421/controlled-3af-once/root-independent-review.json)
is also archived. Raw records are copied byte-for-byte with SHA inventory.

`component_passed=true` is limited to this single controlled native component.
`original_d421_qualified=false` and `production_approved=false` remain explicit.
