# Post-connect observer attachment and lifecycle: CODE only

This revision uses the independently verified setup diagnostic to move attachment
out of the synchronous sqlite3.connect/handle audit callback. Historical H254
still has UNKNOWN cause; its bytes and the H33 capture are never rewritten.
Private native records, databases, nonce payloads and complete capsules remain
local and are not ancestors or contents of this public code delivery.

The exact pinned financial runtime is unchanged:61 UTA files from runtime C.
The static connect inventory records10 direct callsites. Only
uta.storage.Database._connect is on this Fixture's connection path. The other
nine services are unsupported by this component. _publish_private_database uses
private inode publication and fsync/link; it does not connect or execute SQL.
Every audit handle is counted. Unknown code/type, missing attachment, overflow,
attempt/count mismatch or tool failure prevents a complete snapshot.

The audit hook now records the native connection, exact caller frame and phase;
it calls no SQLite method. A Python3.12 sys.monitoring LINE callback is registered
only on the original Database._connect code object. A native C connect call must
return before that frame executes its next Python LINE. The callback requires
the same frame and phase, then calls the original set_trace_callback once.
Database and SQLite methods/functions are never replaced or subclassed.

For the pinned runtime, connect spans storage.py136–137 and the first explicit
SQL is PRAGMA foreign_keys at144. The control derives this SQL boundary from the
existing code object's execute instruction positions and rejects any pending
attachment delivered on a later line. It never makes up an opportunistic late
attachment and calls it complete. This is a claim about explicit Python SQL in
the supported code, not SQLite engine internal work during native connect.

Tool ID3 is fixed. An occupied or unsupported slot fails before a business
fixture starts; no foreign tool is freed or changed. Instance labels distinguish
successive owners. Both full profiling and setup-only entry points close the
observer in finally, save a private lifecycle record and reject cleanup failures.
Close first makes the permanently registered audit/trace hooks inactive, clears
pending connection/frame strong references and releases only the owned local
monitor/callback/tool. It never closes a borrowed native connection. A second
close from an old observer cannot alter a newer observer's same-number slot.
Pending references are bounded16; overflow remains counted and fatal.

Snapshots require every observed handle and attach attempt to match a successful
attachment, zero pending/unretained handles, an active owned tool and no latched
fault. For the supported _connect path each connection also issues a setup
PRAGMA; fewer phase PRAGMA trace events than attachments is incomplete. This
sanity check does not turn trigger-inclusive counts into exact logical calls.
The first bounded structured fault remains immutable. SQL trace limits
stay1000000 events; local LINE events have a separate1000000 limit. Faults and
exception messages remain private until a separately reviewed publication filter.

The local monitor remains enabled when the existing driver pauses legacy
sys.settrace around matching. It uses the same observer for both book-selection
modes and records handles, attempts, attachments and LINE counts by phase.
Actual cProfile coexistence and first-PRAGMA coverage still need native evidence;
no fake model or source inspection is presented as that runtime result.

Measurements change: valid counters now include connection setup PRAGMAs, and
wall/CPU include audit capture, local LINE callbacks, native callback installation
and SQL trace overhead. Monitor registration is a run-level control cost outside
the per-case setup timer. cProfile can suppress events inside monitoring callbacks,
so its rows do not prove a separately isolated complete observer duration.
Trace counts include SQLite trigger repeats and are not logical SQL/transaction
counts. Per-fill percentiles, throughput, regression acceptance and production
flags remain false.

Six explicit fake methods and an independently written manual expected table
exercise two short connection lifecycles, SQL/event guards, unknown and pending
handles, late LINE rejection, unsupported/occupied/registration-failed slots,
bounded first fault and old-close/new-observer isolation. They compile only the
observer AST with fake sys/SQLite/Database/monitor/frame objects. They do not
register a real monitor or import UTA/SQLite. This source has not been executed.
The pure plan, native setup smoke and eventual six-DB component profile each
need independent source review and a separate exact root GO in that order.

Deployment changes only benchmark controls. Rollback drops this observer revision
and stops its plan; it preserves all private failed originals. It never enables
snapshot as a production default or changes fees, clock, TTL, accounting or risk.

Python finally covers ordinary returns and exceptions. A hard process kill or
the existing childless driver's fatal os._exit may bypass it; that process-local
tool cannot outlive the dead process, and missing closure/completion records are
failed or unknown, never a reusable successful observer lifecycle.
