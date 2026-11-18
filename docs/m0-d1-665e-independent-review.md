# Independent D1 prefix-commit closure at665e178

Fixed candidate **`665e178db90dd729954e5cffa7897f9db6958132`**, controller SHA256 `b5dd83d95ddae3708d2d48f2ab20d909747d64fcb8ac9ce7501be74cad810761`, passes this narrow diagnostic-commit review. Original independent first RED `f605b96c4714c744b65403bbfe3861f68f62d768` remains unchanged. It is not relabelled as passing at its original3e586 source.

The only controller function change is `write_resource_diagnostic`. The entire module AST outside that function matches3e586, including all56 other top-level FunctionDef nodes, classes, globals, resource/aux admissions, parent/child budget checks and collection/schema routines. Crypto, workflows and the still-false spent03 template are byte-identical. No M04 or next execution is approved.

The new writer creates its O_EXCL/nofollow0600 candidate under the private incomplete name. Write, flush, file fsync and close must all succeed before hard-link publication; no overwrite or protocol fallback occurs. Failure before publication keeps any complete bytes private. The old public-first complete-prefix branch is removed. Successful link followed by private-alias unlink failure retains both paths; both are charged to the existing cleanup compartment. Reservation covers2×serialized bytes before writing.

**RECORDED means file-synced/closed and currently visible after link. Directory fsync is not called; crash durability, replicated receipt/RPO and hard I/O wall bounds remain unproven.** This scope does not upgrade old3e586 output directories. An empty valid manifest and collector COMPLETE mean only that currently published records were validated; they do not prove a failed diagnostic was delivered. Writer UNAVAILABLE and the original primary remain observable.

One independent CPU3/10s batch ran at `2026-11-17T23:10:00.462055+00:00` to `23:10:00.624141+00:00`, elapsed162092027ns, exit0. Eight grouped controls passed, including14 schema/route/collection negatives:

- The original triple fsync EIO / rename PermissionError / unlink PermissionError is retained. The naturally complete prefix is validated **without rewriting it malformed**; it stays private, writer UNAVAILABLE, public records0.
- Normal publication yields RECORDED/one public record and does not overwrite that first record on a later same-phase failure.
- Close and link failures each retain a valid private-only prefix, preserve primary/cause/context and publish no diagnostic.
- Post-publication alias deletion failure yields RECORDED, two same-inode paths and cleanup580B for the290B record. Original four stream byte arrays remain unchanged in every scenario.
- Exactly2×record headroom succeeds; one byte less fails before creating either candidate or public path.
- Unknown raw paths/secrets are absent; only the expected role-separated SHA256 is retained. Extra path/key/nonce, boolean/float/NaN/negative errno, boolean version, invalid hash and duplicate JSON keys reject.
- Public private-staging name, `.part` and nested diagnostic routes reject. A collection PermissionError leaves the primary unchanged and the existing public record unlisted, so public verification rejects it.

The original first fixture is preserved byte for byte as `original-f605-first-prefix.py.txt`, SHA256 `e4643f1f973b89b1478caa47346b263a4ed815ee03ab5c72b2cce5ceb9bef71f`. The new checker preserves the original three fault types/call sites and adjusts observations to the new private/public protocol; its outputs do not replace the original raw. Source, complete stdout/stderr, timing, hashes and static invariants are retained under `evidence/reviews/m0-d1-665e/`. No154/158 author suite was rerun.

This is tiny-file/fake-I/O validation only. Zero SQL, UTA import, actual owner/native process, crypto, network, service, signal, M04, CI or workload execution occurred. Existing financial modes, four-stream semantics, source909, all64/96/32/192MiB compartments, fresh2348810240B floor,3scan/50ms and56+2+2/60s limits remain unchanged.

Verdict: **PASS_SCOPED_DIAGNOSTIC_PRIVATE_PREFIX_COMMIT**. The old M03 missing path/cause remains unknown; original6010 CI FAIL, controlled-SH marker finding and native probe hard-budget gap remain independent open gates. Real-fund/production/capacity/HA approval stays NO_GO. Rollback keeps all evidence and leaves any next candidate unactivated; a candidate containing the original known prefix flaw must not be represented as qualified.
