# Once-only instrumented native diagnostic

The root-authorized first batch completed four tests, zero failures and zero
errors. It was not rerun. Runtime control is `ff814d4bcaee079b0e0503ea8072c24e3563c443`;
driver SHA256 is `7c60c774c283e43dcd72c36cb357abee42d23bcab09c516de4d7d559b4afbaa8`.
This is a component diagnostic with trace/poll instrumentation. Original PR22
CI causality is unproven and production acceptance remains NO_GO.

| Case | Verified assertions in the first native batch |
| --- | --- |
| Before registry INSERT | Actual gated child exits; no SPAWNED row; lease generation zero |
| Actual registry COMMIT then injected reply loss | Original SPAWNED row retained; child exits; no lease owner/token; generation zero |
| Monitor COMMIT/reply-loss recovery | Failed gated child exits; distinct replacement reaches worker state=ready; three original SPAWNED rows retained; lease generation two |
| Exact kernel SH holder | Bound PID/birth/pidfd and active generation one; kernel SH captured before/after STOP; original 4s publication completes and replacement PID appears |

The OperationalError is injected before or after a real registry operation;
the batch does not reproduce SQLite's native locking-protocol fault. Worker
state=ready in the registry recovery case is not financial_ready=true:
that case has no market/unhalt activation. The kernel case uses the original
activation setup. Its final publication is publishing=false, halted=true.

Test elapsed time was 4.091s; inner ownership wall time 4.585325783s; detached
outer supervisor total 5.302555280s, below the 30s budget. Both ownership
harnesses report EXITED, return code zero, no watchdog reason, complete raw
streams and reaped direct leaders. Both CPU affinity ACKs are [1].

The kernel target PID was 423148, birth ticks 8571879, generation one, with one
kernel SH record both before and after its pidfd STOP. Publication returned in
1.126711011s. The trace has 440 events and is not truncated; an exception trace
event can describe an internally handled exception and is not itself a test
error.

Metadata-only post-check found no live members in the three new owned process
groups. The detached outer wrapper PID 423038, birth ticks 8571584, was already
exited in state Z under PID1. This observer cannot reap a process adopted by
PID1. That host-reaper boundary is retained explicitly; it is not counted as a
live child or hidden behind the two direct-leader reaping results. No signals
or SQLite operations were used in that post-check.

inner/ and outer/ are byte copies of their first raw artifacts. Their
sealed manifests also include hashes of the fresh synthetic private databases;
those databases were retained outside Git and are not copied here. The outer
supervisor source and launch/birth identity are included so detachment and
watchdog ownership can be reviewed. The protected pre-existing PIDs and frozen
authorities were not modified or signalled.
