# Publication pending: bounded protocol model

This is a new independent standard-library specification. It imports no UTA,
other model, SQL, clock, filesystem, process, thread or network API. At this
commit it is **CODE_ONLY / NOT_RUN**. It changes no financial runtime.

The model enumerates one publication over two shards, one original command ID,
one operator halt, one restart, one lease expiration and one quote expiration.
Every variant has a hard 25,000-state bound; exceeding it is an incomplete
exploration, not success. Baseline event counters must all be nonzero.

It distinguishes publication, the activation gap, validation and completion.
An in-flight activation pins an operator-intent revision. A later operator halt
dominates that older activation and its receipt. Market generation and operator
intent revision are distinct concepts; this specification does not demonstrate
that the current runtime persists either protocol exactly as modeled.

Eight negative variants must produce and JSON-round-trip replay a trace to the
named violated invariant: an integrity exception retaining the pause, late
publication resurrecting it, late activation reopening an operator halt,
partial-fanout visibility, charging a paused command's attempt, duplicate CID
reservation, stale-quote activation and restart losing the temporary marker.
Only the first is linked to an observed static candidate finding: independent
CODE `6057da2d` rejected source `3a530de5` for uncaught validation exits leaving
the marker true. The other variants are explicit abstract fault controls, not
claims that those bugs exist in the production source.

Atomic assumptions are explicit: a final admission check and its one reservation
are one transition; a fatal stop's control record commits atomically; observed
shard receipts mean durable installed snapshot identity; operator revision is
durable and compared before an older completion acts; restart reads that same
record and original CID. The model cannot establish these assumptions for SQL,
an unavailable disk, message delivery or a Python implementation. It does not
model stop-record write failure; runtime must report an unknown result rather
than infer a committed stop in that case.

There is no fairness or eventual completion claim. A stale quote or dead writer
may keep a command pending. A later explicit operator resume after a halt is
outside this one-halt scope; old in-flight work must not stand in for it. Multiple
accounts, head-of-line cancellation/repayment, financial amounts, fees, fills,
matching, partial fills, unknown batch recovery and physical fsync age remain
outside this model. A boolean live-lease predicate does not prove real fencing.

After separate review, the proposed command is:

```sh
/usr/bin/taskset -c 1 python -I -S -B formal/explore_publication_pending.py
```

The exact interpreter, source digest, fresh output namespace, CPU affinity and
finite output/runtime evidence will be fixed before the first run. No execution
permission, historical scope, native test result, model/runtime refinement,
capacity, HA or production approval follows from this document. Rolling back
this delivery removes its new model and documentation, with no data migration;
original candidate findings and execution evidence remain unchanged.
