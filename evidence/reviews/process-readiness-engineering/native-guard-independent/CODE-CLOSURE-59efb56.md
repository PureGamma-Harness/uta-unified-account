# Independent outer/common CODE closure

**CLOSED for the reviewed CODE scope. No remaining concrete blocker found.**
Reviewed immutable source `59efb56f86de49c51bbea7407c3be447332df216`, focused
plan commit `2bda67300a968b708fa7ae077330bd6c794c0f71`, and materialization
intent commit `2b5a37d20de1730758c90c545872419cb09c91d7`.

This independent signature covers only `native_once_common.py`, `native_once.py`,
the nine guard properties, selected-AST support, the focused driver, and their
source/materialization boundary. The reviewer implemented case/export and the
eleven terminal properties, so their semantic approval belongs to the author's
separate review; this document does not self-sign those files.

| Reviewed input | SHA256 |
| --- | --- |
| `native_once_common.py` | `054a0cd2524643515ead366c367a98793656f7f0046638623038f9973245bf75` |
| `native_once.py` | `bb2576f279e362332be85ff57f46c3a1fb080e818393e30d69cd0b4be3526820` |
| `native-focused-v2/fake_support.py` | `652aa14594cb8839018cb4e0779f922298a6f812458fdfa8a17f76fb8038640e` |
| `native-focused-v2/guard_fakes.py` | `6cbd4f5624150166db69c8d45f958f50e993246c1b7dc22f4aa692980fe6d10d` |
| `native-focused-v2/run_focused_once.py` | `cfe3894c27baaf3b0a1a3f01440a307b6cadc790126f0adad50a37273bf425f8` |
| Native manifest | `9c5778c4b8595b1cb81055e9766e490f283fd17c4866315d76ddd8d586c71721` |
| Focused source plan | `b827601756473c7df20530b8a6136cbc1f8583312b91adc565510b78e6324dc8` |
| Materialization intent | `1dafb9f5f6f5ab46dc8d46e26da74b2289f8cdbf50dea1ec7eae2f90ea7daca0` |

Static checks confirm the union of ten protected numbers is rejected before
process/pidfd access, including protected TIDs before their owned `children`
files are read. Signal attempts are reserved before uncertainty, use a held
pidfd after birth/session/UID verification, and recheck the shared absolute
40-second deadline after the durable before-record. Popen and gate release
recheck the shared 30-second deadline. There is no process-group/bare-PID
signal or global process enumeration.

Journal and stdio writers reserve capacity before writing and latch failures;
partial writes, fsync failure, selector/read/EOF-close errors cannot authorize
more bytes or complete EOF. Actual child PASS/FAIL must respectively match
exit0/exit1. Role reconciliation compares already-bound birth dictionaries;
caller declarations never authorize opening or inspecting a PID. Observed
descendants must match closed roles, tracker normal exit requires integer
status0, and surviving/forced leftovers become UNKNOWN. Late/missing completion
or exit/completion disagreement remains UNKNOWN. OS/fsync blocking remains
outside hard real-time guarantees;64MiB remains a monitored business threshold.

Source verification requires declared regular, nonsymlink inputs with exact
length and SHA256. All69 native manifest Git blobs and all69 byte lengths were
independently recomputed without mismatch. The runtime metadata code hashes ten
declared multiprocessing source files plus the Python/SQLite binary boundary;
it does not connect to SQLite. These are metadata/source boundaries, not proof
of actual native execution or every runtime/standard-library file.

The focused driver selects exactly9+11 methods, validates all eight target/
fixture inputs before and after, forbids native/runtime imports and effects,
and uses a ten-second line guard. Its stdout/stderr share a256KiB cap, reserve
before write, and retain at most one bounded emergency trailer from512 reserved
bytes before immediate UNKNOWN exit. The materialization intent explicitly
uses approved Git/file preparation, checks existing bytes for WIP before
restoring78 declared paths, and preserves21 earlier SAFE files by hash without
restoring or executing them. Read-only Git inspection is not a zero-child claim.

The author's separate review confirms the case CLI flush-failure path always
reaches its final self-exit rather than later multiprocessing exit hooks. This
review does not substitute for that separate case/export signature.

This closure used only Git, source text and byte/hash operations. No new20
method batch, Python import/compilation, preflight, native case, SQL, process
fault, signal or protected `/proc` inspection was run by this closure. The
original guard6 first result remains1 PASS/5 RED/0 ERROR, unchanged and not
rerun. Root's separately authorized future pure batch is synthetic evidence
only; original CI failures, native GO and production approval remain open.
