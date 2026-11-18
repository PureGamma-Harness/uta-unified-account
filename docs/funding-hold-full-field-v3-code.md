# Independent V3 complete-response comparison: CODE candidate

This driver uses only the published V3 interfaces and contract data. The
independent generator supplies1024 ordered request wrappers; each complete
request is encoded and passed separately through the reference and target's
own loaders and evaluators. The driver contains no financial equation,
rounding helper, DTO builder or expected money amount.

Comparison covers the entire typed response. Canonical JSON preserves array
order and distinguishes false from0; extra fields are not removed. Unknown
implementation/transport exceptions are technical failures, never comparable
business rejection. Independently declared valid/negative and specific expected
statuses must also match actual outcomes, preventing two implementations from
passing by rejecting everything. Both actual status counts remain separately
reported; they are never replaced with declared counts.

The gate requires1024 unique ordered seeds/case IDs, all10 operation names,
the declared512 valid and512 negative inputs, unchanged decoded requests and
complete response equality. First mismatch stops this gate and records its
seed, input/response hashes and a bounded difference location/type. Exact
counterexamples remain reproducible from the fixed deterministic generator;
the failure message is a finite projection, not a claim to contain all inputs.
On full completion only, a summary records actual classifications and framed
input/reference/target response stream hashes. This is correctness evidence,
not an open-loop capacity or sustained-throughput result.

Four unittest definitions cover the complete stream and the comparison,
technical-exception and reject-all negative controls. They are NOT_RUN at this
freeze; unresolved reference imports become runnable only after the exact V3
source export is integrated. No target, reference, generator, validator, test,
SQL, actor or CI ran while preparing this source. Independent CODE review and
a separately recorded first execution remain necessary.

Only synthetic supplied-data D1 is covered. Real acknowledgement/outbox,
global history, durable CAS, financial settlement, risk/admission integration,
capacity, HA and real-funds production remain blocked. Deployment is test-only
with no data migration. Rollback removes this driver and its artifacts while
preserving every prior failed source/result and confirmed economic record.
