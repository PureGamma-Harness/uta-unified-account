# Target adapter v2: CODE candidate, NOT_RUN

This test-side adapter maps the frozen independent wire contract a33da700 to
the reviewed pure target ed81c424. It does not import or read the independent
reference core, its generated cases, expected values or financial helpers.
It constructs target DTOs, calls the public target operations, and serializes
every declared DTO field and computed identity. The target computes all money,
margin, backing, stage and wait results; the adapter contains no financial
equation or independent expected answer.

The complete actual validate_wait_records result is emitted as action_ids in
its original order. The adapter does not sort, deduplicate or replace it with
only a count. The separate record_count is input metadata. The input false
activation/true holds flags must be exact bool before omitting init=False
constructor parameters. Input arrays become explicit tuples, with no numeric
conversion. Unknown output DTO fields/types and unexpected exceptions remain
technical failures.

Transport has a 2 MiB UTF-8 bound and rejects duplicate keys, nonfinite values,
BOM/UTF16 inference and malformed envelopes. No case ID or business response is
invented for those errors. Finite JSON floats survive transport only to be
rejected by the target's exact typed inputs. Supplemental finite decoder bounds
are depth32, 250000 visited nodes and 128 integer digits; they cover valid DTO
histories and supported numeric domains. They require independent review and
explicit agreement with the separate reference decoder before broad codec
equivalence is claimed. The adapter has no public REST/WebSocket endpoint.

Only the adapter's exact InputReject or target's exact HoldError/HoldUnsupported
become the frozen generic business classifications. Unexpected TypeError,
ValueError, subclasses, malformed target returns and encoder faults escape.
The fixed hash_wire label describes the source contract, not execution status
or runtime qualification. The future differential runner must compare the
complete response and keep actual run evidence separately.

Nine test methods define transport/correlation, technical fault propagation,
complete output, immutable input, actual validator result preservation, native
numeric rejection and legacy-operation rejection. None has run. No imports,
target/reference execution, financial SQL, actors or CI ran for this source.
The source received AST data checks only, and requires separate CODE review.

This is not yet a differential runner. The independent v2 core, generator,
reference self-checks, full-field comparison and first execution plans remain
separate gates. Deployment is test-artifact only, with no service hook or data
migration; rollback removes these new adapter artifacts and preserves all
original source and economic history. D2/production/real funds remain NO_GO.
