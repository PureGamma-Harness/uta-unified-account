# Added continuous host controller: independent preliminary review

Reviewed code source: `cd7d7b26aba6acd03d1129c0a5505572d10d7457`. This source corrects the earlier COMPONENT status literal and separates exactly nine comparable legacy-risk fields from quote observed_at provenance. The same-transaction quote/history/hash/version and original5s/1s freshness directions are represented, full raw risk/quote records remain, and config/liquidation state capture is outside the profiled window. The two initial H537 blockers are closed at code level in this source; no target execution followed.

The newly added host scope is **NOT_CLOSED**. Its two direct Popen children are distinct from the two targets' no-child/no-proc scope. These finite failure/budget paths require explicit handling before the new source is approved:

- Popen starts the target before pidfd acquisition. If acquisition fails, the target can already act while the host lacks its permitted handle. If a later pidfd signal raises, the current path can skip bounded wait and the receipt. Preserve a durable owned-child/handle record and all failure outcomes before losing this ownership. A fixed start gate is an available way to prevent target business work before the required binding; no unverified raw-PID fallback should be introduced.
- The current host does not apply the session's protected-ten numeric refusal before pidfd acquisition/signalling. Root must either explicitly bind its guard policy to this owned-child scope or include the same pre-refusal. No old process may be inspected to discover whether it is safe.
- Continuous total/control timing is checked at the end, but the next target can be launched after already known control or total budget exhaustion during receipt I/O. Check remaining control/sequence budget at each next Popen/aggregate boundary; a final late result cannot undo work started after a known expiry.
- The original320+176+16KiB raw allocations already total512KiB. The new host's own END/FAIL stdout is outside the aggregate BoundedText. Allocate or share a bounded host/aggregate pool so the declared joint budget covers all streams.

These are new-host preliminary findings, not requests for more performance samples, cases or capability probes. Root controls the exact revised scope. A future source must be reviewed after its final freeze and input binding; neither this note nor the old initial review supplies an execution GO.

The controller's positive sequence already distinguishes child actual exit/reap from the aggregate's in-process return, keeps raw/receipts outside target write roots, and requires final host completion plus caller-observed outer exit. Its monotonic main-entry boundary excludes interpreter startup and must not be relabeled as a whole-process timestamp. C I/O remains uninterruptible by Python boundary checks; late or uncertain outcomes remain non-accepting.

This review imported/compiled no target, opened no SQLite connection and executed no process/PID/network probe. Runtime61, financial models, fees, TTL, matching batch size, six-authority limit and performance/production NO_GO remain unchanged.
