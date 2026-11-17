# Strict raw integer domains and terminal identity

The independent673 review at OWN36a4f1b/bc24a57 retained four real pure-data
acceptance controls: float nanoseconds, a boolean sequence with alternate IDs,
a rejected receipt belonging to another CID/account, and boolean false used
as the zero late-success count. These are unused diagnostic-checker defects,
not observed exchange trades or service failures. The original accepted red
records remain unchanged.

This second isolated fix validates integer domains **before** arithmetic,
set equality, dictionary equality or ID formatting. Exact `type(value) is int`
is required; bool and same-valued float are refused rather than converted.
The checks cover arrival/receipt sequence fields, every consumed raw/window/
footer nanosecond field, offered values, outcome/summary/technical/batch/RO
counts, worker count settings and PIDs. Only the three explicitly nullable
enqueue timestamps may be None. Config boolean flags retain their distinct
boolean domain. The failed-case forensic path shares strict row and footer
types and never invents a missing denominator.

Canonical `bench:<integer sequence>`, `order:<integer sequence>` and account
IDs are derived only after the strict sequence check. Every nonnull receipt,
including REJECTED, QUARANTINED and pending observations, must identify that
original CID/account before classification. Receipt attempts and rejection
status also have integer domains. Correct business rejection remains business
rejection: the positive control still has180 financial successes/20 business
rejections, a ten-second actual footer denominator and a green diagnostic gate.
A malformed record is refused as data evidence; it is not rewritten into a
new technical outcome. Unqualified forensic counts retain the original labels
and explicitly report `financial_verified=false`.

All33 pure checks passed on each Python3.12/3.10/3.13 in0.832/0.987/0.790s,
with ResourceWarning as error and forced GC. The exact original additional
script was copied byte-for-byte and executed: all four former accepted controls
are now refused. The original unchanged four-vector script remains4 PASS.
The original script's literal673 source label is retained; the surrounding
manifest and command/source hashes identify this author candidate. Earlier
author reruns and target logs are retained separately, not overwritten.

Evidence is in
[`evidence/runs/managed-runner-raw-contract-closure`](../evidence/runs/managed-runner-raw-contract-closure).
This step starts no dummy, collector, verifier, SQL, service, build/install,
benchmark, profile or long job. No financial core, original plan, frozen source,
historical raw result or active producer/observer is modified. The separate
output-path fix is OWNfb24d68. Both await independent closure, then new exact-
source qualification and an explicit execution GO; no prior qualification is
transferred. Rollback changes only a future diagnostic checkout and preserves
all red/control evidence, authorities and original business IDs.
