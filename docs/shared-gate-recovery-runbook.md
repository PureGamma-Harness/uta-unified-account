# Draft validation and recovery runbook

This candidate is for new CI and fresh synthetic authorities bound to the exact
reviewed source. It is not an instruction to replace the binary for an original
authority. The original PR 35 L1525 failure remains open; its actual cause is
UNKNOWN. SQLite internal WAL protocol retries/backoff, LOCKED/PROTOCOL handling,
disk I/O and OS scheduling remain outside a hard busy-timeout or five-second
guarantee.

Before validation, retain the exact source commit/tree, runtime hash, authority
identity and first-run evidence. Keep the first base RED, first candidate pure
result and original PR 35 failure separately identifiable. The runtime change
is limited to `uta/durable_process.py`: SPAWNED registry operations use a shallow
copy with `timeout=min(original.timeout, .1)`. Original control DB configuration,
all other event kinds, registry SQL, lease values and financial paths are
unchanged.

The three new discoverable cases in
`tests/test_shared_gate_registration_progress.py` are conditional pure models.
They have not been manually executed; their first execution belongs to new CI.
The existing base sixteen-case and candidate twenty-four-case first results
must not be regenerated or replaced. Unit discovery uses current source AST
and fake DB/Process/Pipe/clock objects, and rejects actual connections, worker
start, process wait/signal, thread start and sleep. It does not establish native
kernel SH release, kill/reap, new-owner READY or a market publication receipt.

Package validation must preserve the three existing provenance originals:
`baseline-first/manifest.sha256`, `candidate-source.manifest.sha256` and
`candidate-first/manifest.sha256` beneath `evidence/shared-gate-recovery/`.
`MANIFEST.in` names each exact file in a literal include. The surrounding JSON,
TXT, Python and Markdown files retain their existing extension selectors.
This local preparation checked those rules statically; it did not build or
install a package. New CI must inspect the built sdist before relying on it.

A separately reviewed native validation must use a fresh synthetic directory,
new authority identities and that exact source closure. It must retain the
original real bound PID/birth/UID, pidfd and inode-specific SH capture, the
original five-second lease/capture/recovery bounds, the original publication,
and financial/schema/cache assertions. A failed native sample remains a failure;
there is no blind retry or sample skip. Phase evidence must distinguish registry
waits, unknown lease reads, same-child kill/exit observations, new generation and
READY, original EX entry, exact market ACK/digest and reconciliation. This
document authorizes no such execution.

If a reviewed synthetic evaluation fails, retain the first streams, exit state,
source identity and authority metadata before changing code. A code rollback
selects the prior reviewed source for a newly planned evaluation; it does not
erase or rewrite durable command IDs, inbox/terminal receipts, process ownership
registry, writer lease events, schema identity, financial ledger history or
confirmed trades. Do not lower a generation, revive an expired token, recycle a
nonce/CID or replay a confirmed financial effect to make rollback appear clean.

Any original-authority rollout or rollback requires its own reviewed transition
bound to the exact source and persisted authority. Preserve queued and terminal
command facts and confirmed trades throughout that transition. The current
draft supplies no approval to switch an original authority's binary, deploy,
push, merge or run the original native SH case.
