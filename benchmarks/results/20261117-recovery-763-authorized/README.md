# Authorized 763 recovery component evidence

Actual runtime: `763202df9cb3ce089721e5281371aff3eab58089`. Actual immutable driver: `d886cdbfafbc491e1a7705313080f910712bd185`. Both used native CPython3.12.14 matching the original qualification report. This archival commit is separate from that driver; it does not change its source, registration, clock, TTL or resource limits.

| Actual cohort | UTC start/end | Measured workload + cleanup / metadata total | Result |
|---|---|---:|---|
| 1k contract | 09:08:05.527660 / 09:08:07.343993 | 1.811717s / 1.816346s | Strict contract passed; real original-CID `REJECTED/order_not_found`, complete before/after read-only replay and expected head |
| 250k | 09:12:42.421783 / 09:13:40.690001 | 58.265583s / 58.268230s | **NO-GO**, watchdog interrupted at56s and killed at58s before a durable command or worker ownership; final independent replay unavailable |

The large case retained journal head250000 with the expected hash, an empty inbox and only the generation-zero `enabled_guard_v1` event. No worker/acquire/renew/READY was observed. The absence of `credit_schema` is expected before the worker creates its credit module. This is an owner-before-start budget failure, not observed lease expiry or a completed owned-recovery experiment. Neither the missing summary nor the missing final replay is replaced with a pass. No retry, deadline extension, extra financial replay, service or6h run occurred.

The1k replay took63.462ms, below the ordinary five-second lease. It verifies the contract and provenance path; it is not evidence that the new runtime completes a250k recovery or that a full replay longer than TTL was exercised in this case. Financial readiness remains false because no market or trading activation was requested. Both cases use balanced synthetic system-account journal events and zero-funded customers, not matched trades or real funds. Production, HA and capacity gates remain false.

`public-manifest.json` distinguishes original private byte hashes from the public derivatives. Writer/coordinator/auth identifiers, host boot UUIDs and cohost session IDs are replaced by stable labels; the private originals were not changed. Native code-artifact manifests and their content-addressed identities are retained unchanged. Database, WAL, SHM and lock bytes are excluded. `private-authority-references.json` records their original paths and existing byte fingerprints only; the canonical private authorities remain under `/tmp` and were not moved or deleted.

Each cohort includes all allowed original JSON/JSONL/text outputs, actual source/configuration and loaded-code observations, independent analysis, original manifests, stdout/stderr and the external console captures. The250k case also includes its actual live pidfd metadata observation. Source originals, including original1k/250k manifests, remain available privately; the original manifests describe private bytes and must not be confused with public derivative checksums.
