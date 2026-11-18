# Output schema meta-contract before value matching

This new correction addresses FTA-V3-B4 from independent review afdd9210.
Source4173d8d5 and its 16 unrun tests remain immutable historical inputs; their
original output, encoding and intermediate-return fixes remain in place.
Current metadata is code-candidate-v4.json. The older candidate and v3 files
continue to describe their own source versions, not the current source pins.

Before inspecting a returned value, the adapter now traverses the complete
schema graph, including every alternative, object property, array item and
referenced definition. The meta-contract rejects unknown types/features,
unsupported type-family keywords, malformed required/properties/enum/bound
values, invalid patterns, empty alternatives, unresolved/recursive references
and excessive depth/work. It supports the exact finite output grammar of pinned
wire061580ce; it is not a general JSON Schema implementation or transport API.

Value matching runs only after that complete pass. It can discard a known
value mismatch inside oneOf, but cannot skip an unknown schema merely because
another branch accepts the value. In particular a null value no longer hides
an unsupported number type, a nested unknown property/item, a string required
list, an empty nested alternative, bool array bound or malformed enum.

The pinned current wire already has valid output schemas. The previous review
did not demonstrate a financial result escaping its actual output constraints;
the blocker concerned the validator's promised rejection of unsupported schema
branches. This change closes that source path without loosening the pin or
altering financial calculations, output fields, exception boundaries or DTOs.

Two additional test definitions cover all-branch rejection and supported
native integer alternatives. The original 16 methods retain their exact ASTs;
all 18 definitions are NOT_RUN. Only AST/schema data inspection has occurred.
No target/reference import, compilation, generation, validator call, test,
SQL, actor, install or CI ran for this candidate. A separate independent CODE
review and first execution decision remain required.

No service activation, financial state or migration changes. Rollback reverts
only this new meta-validation delta and its metadata, preserving all prior
blocked sources/reviews and every confirmed economic record. Decoder equivalence,
full-field differential tests, D2, capacity and real-funds production remain open.
