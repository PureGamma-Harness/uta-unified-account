# Observer first-fault diagnostics: CODE only

An earlier authorized private run rejected an incomplete SQLite observation
during first-book setup. It never entered timed matching. The original generic
latch did not serialize its category or underlying exception, so that historical
root cause remains UNKNOWN. The private failure artifacts are retained separately;
this clean branch starts at the pre-run CODE ancestor and does not include their
private database, nonce payload, archive, absolute original paths or commits.

This revision changes diagnostics only. The original audit-handle callback still
calls set_trace_callback at the same point. The SQL category callback, event
limit, successful counters and successful snapshot shape remain unchanged.
Incomplete observation still raises and cannot qualify as a profile. There is
no sys.monitoring, changed connection plumbing, native method override, runtime
change, new quote, TTL relaxation, fee change or disabled audit.

The first failure latches category, phase, fixed event name, total event count,
current-phase connection/category counters and the first exception's bounded type,
message and up to six stack locations. Later failures cannot overwrite it. Type
is capped at128 UTF-8 bytes, message at512, each stack file at256 and function
at128; truncation is explicit. Details are latched before formatting, and a
formatting error preserves incomplete state. Snapshot raises with the structured
first fault. The callback does not copy its expanded SQL statement argument.
Exception messages or stack paths may still contain sensitive content: they are
private by default and require a separately reviewed targeted publication filter.

Four synthetic fake contracts cover attach error/bounds, callback error/first
fault retention, the event budget and unchanged success output. They extract
only the observer class AST, use fake hooks/connections/events and never import
UTA or SQLite or execute SQL. Their source is prepared but has not been run.
They validate diagnostics behavior; they cannot identify the original native
cause or validate CPython connection readiness.

The new native entry is fixed to --setup-only, profile-set observer-setup,
book-size32 and book-selection scan. It needs a new frozen source, independent
review and separate root GO. It calls only run_observer_setup, which installs
the unchanged observer, builds one fresh native authority with the original two
accounts/deposits and32 orders, then calls snapshot and terminates. It never calls
run_profile, verify, a second quote after setup, profiler enable or match_once.
A captured fault remains incomplete and exits1 with OBSERVER_FAULT_CAPTURED.
Without a fault it exits0 with FAULT_NOT_REPRODUCED; this means only that setup
finished without the fault, never that matching or finance acceptance passed.
Both outcomes retain the new own structured evidence and leave historical H254
cause UNKNOWN. The controller finishes source/runtime verification and byte
inventory for either result; it grants no profile acceptance.

Native proposal: one allowed CPU, boundary guard20s plus root's independently
observed hard timeout20s/drain at most2s. The target creates no child/thread,
network, proc or PID action and may connect only inside its new authority scope.
Its old host startgate path remains required for full profiles; setup-only uses
root's separate timeout/taskset orchestration and refuses the host gate flag.
Logical total24MiB splits authority16MiB, mini2MiB, reports1MiB and5MiB reserved
for outer capture/cleanup. Target raw127KiB includes its512-byte trailer reserve;
root outer raw1KiB shares the128KiB pool. Length checks are not a kernel quota;
native I/O cannot be guaranteed to stop by a Python line guard. Late/missing
completion is failed or unknown and never justifies another run. Neither the original four-case
profile entry nor a benchmark retry is authorized by this plan. Deployment is
limited to diagnostic controls. Rollback is removal of these additions; financial
runtime and default scan remain unchanged. Original failed evidence is never
rewritten, repaired or retroactively relabeled.


The pure plan remains separate: exactly four explicitly named fake methods in
one test command, with its own two-source manifest. It has no native setup entry,
UTA/SQLite import or SQL. Neither plan authorizes execution and their raw/results
must not be combined. All actual diagnostic artifacts are private until a
separately reviewed filter excludes nonce payloads, DB/WAL/SHM binaries and
private original absolute paths. Private failed commits are not public ancestors.
