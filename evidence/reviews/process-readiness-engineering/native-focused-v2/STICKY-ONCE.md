# Isolated process-protocol correction: not run

The first pure20 remains RED:19 methods OK, one method with three ERROR,
exit1. Its raw and independent review are immutable. Native source59efb56
and the original assertions remain unchanged.

Only the affected method's local process standin changed to a plain class
with object-identity equality/hash and weakref support. This models the
BaseProcess mapping-key protocol without weakening the actual bindings guard.

[sticky-source-plan.json](sticky-source-plan.json) pins the isolated driver
and its inputs. The pending proposal selects exactly one method and four
fake traces: initial sticky denial and the same three previously errored
mutations. The other19 methods and the whole20 batch are not selected.

```sh
python -I -B evidence/reviews/process-readiness-engineering/native-focused-v2/run_sticky_once.py 59efb56f86de49c51bbea7407c3be447332df216
```

The scope remains one allowed CPU, actual ID recorded, wall10s and combined
raw256KiB with512 bytes reserved. Only selected AST definitions, memory and
inert spies execute. Source and materialization binding plus independent
CODE closure precede root's new once authorization. All first outcomes are
preserved without retry. Preflight/native execution remains unauthorized.
