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

Next native work requires a new frozen source, independent review and separate
root GO for one fresh32-order scan setup only. Its entry must stop before any
matching even if the fault does not reproduce. Neither the original four-case
profile entry nor a benchmark retry is authorized by this plan. Deployment is
limited to diagnostic controls. Rollback is removal of these additions; financial
runtime and default scan remain unchanged. Original failed evidence is never
rewritten, repaired or retroactively relabeled.
