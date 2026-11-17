# Fixed-74e batch/cache combination evidence

Runtime base: `74e03a8fc7e3265cb03a3ffa0ffcaeac88fc35fd`. These are small
actual-process and CLI combination tests. No runtime file changed. They are not
full correctness, remote CI, installed-package, capacity, HA or production gates.

Final committed tests: `af6cf5cf3acc04d3a3d0d7404287433debcdf6ed`, following
`f846a41` which introduced the tests. Both runs' original manifests, logs and
actual post-COMMIT diagnostic facts are retained separately, without rewriting
commit fields or paths. All recorded runtime-source hashes match immutable 74e;
test hashes match their respective immutable test commits. [copies.json](copies.json)
records byte-identical copies, original paths, sizes and SHA-256 values. The
actual driver is [uta-batch-cache-combination-check.py](uta-batch-cache-combination-check.py).

| Final runtime | SQLite | Cases | unittest elapsed |
| --- | --- | ---: | ---: |
| CPython 3.10.22 | 3.53.1 | 3 | 6.775 s |
| CPython 3.12.14 | 3.53.1 | 3 | 6.767 s |
| CPython 3.13.5 | 3.46.1 | 3 | 7.807 s |

Runs were sequential on CPU 0. Final raw files are in `final-af6cf5c/`; the
preceding `f846a41` run is in `intermediate-f846a41/`. All logs report OK without
skips. `elapsed_ns` in manifests includes driver/environment overhead; the
table uses unittest elapsed time. The final test adds the explicit assertion
that actual dispatch size equals the independently supplied batch flag.

Two cases create real separate owners with fresh durable batching and cache 8.
They record original ledger/credit RO verification, native prepared-object
identity and cold cache 8, real cache warming, actual 3-member durable manifests,
three original command receipts, unique orders/events/audit references, USD
10.04 reserves, unchanged balanced settled cash and journal count. The restart
case records the original PREPARED commit, kills only its owner, observes a new
PID/generation and cold cache, and queries real immutable recovery outcomes and
zero unresolved attempts before forwarding the original READY send. No authority
database was copied or moved. The third case validates simultaneous CLI flags,
zero defaults and configuration rejection before authority creation.

[validation-summary.json](validation-summary.json) is a read-only reduction of
the raw facts. At the unchanged **5ms** soft budget, both final Python 3.10/3.12
runs actually executed two original CIDs in their COMMITTED batch prefix, while
Python 3.13 executed one. Remaining originals completed through the normal
single-command lane; all three final receipts are persisted and unique. These
results do not claim three commands shared one COMMIT, count membership as
completed work or measure throughput. Same-direction orders produce no match or
liquidation fill; those paths require independent acceptance.

`initial-instrumentation-failure.txt` is a development observation error, not a
runtime defect. Its initial wrapper covered only the first spawn; the replacement
was actually READY but no longer wrote native observation files. The corrected
tests retain the call-through spawn observer through router close. The exact
initial instrumented source bytes were not retained, so this log is not treated
as reproducible qualification. The final two committed test sources and facts
are reproducible and separately identified.

Each final suite took under eight seconds. The bounded driver permits one CPU
and caps its overall small-run window; no sustained load or 45-second-plus
experiment was authorized. A new root runtime freeze must independently pass
full correctness, CI and package checks. Earlier 38/105-test results are not
reused as qualification of this combination or a later release.
