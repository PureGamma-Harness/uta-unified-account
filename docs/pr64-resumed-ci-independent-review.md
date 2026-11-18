# PR64 resumed independent RAW review

New independent read-only review: **PASS with explicit NOT_VERIFIED limits**. The base collector commit is `ebed13aaca5b7e3bb30202ab247c7944f8612c4d`; source is `d128ee6e40802482162dbc1f7716441ba91e5e0f`. This local review adds two SAFE files and is not pushed.

The old interrupted review remains **UNKNOWN** as a terminal result. Its ledger reported no pending intent at the snapshot; those reported bytes are preserved separately and are not backdated, reclassified as PASS, or assigned a larger budget. This review has its own frozen budget and complete logical byte-range ledger, with zero pending intents. Administrative cache retries are charged to its separate reread budget. Kernel physical I/O and interpreter bookkeeping are not claimed.

## Verified recorded evidence

- First captured push `44358530777` and PR `44358660859`, attempt 1, each reached SUCCESS. Eight jobs and all 200 recorded steps succeeded. Eight actual summaries each report 2200 tests, zero failures, errors or skips, and worker exit 0.
- Push summaries identify source `d128ee6e`; PR summaries identify provider merge `7e23fe7e15a35c35d9a28d0f50ee7df62fc18084`. Provider merge parents are `16f64fec1d2fba638ea99a6414cf8778f9638537` and the source. Provider merge tree equals the source tree. The merge commit object is missing locally; that is distinct from provider parent/tree evidence.
- All 56 sealed originals (77,374,458 bytes) match SHA256 and 0400 modes; all nine directories are 0500. Three small ZIPs have 25 CRC-checked members and 1,709,363 decoded bytes; all 25 expanded originals match their corresponding decoded members. Each small member was decoded once.
- Each fixed Python 3.13 log has 2172 strict same-line plain OK records. All 12 readiness and 29 funding methods complete exactly once in each log: 24 and 58 observations respectively. All 82 component rows are strict same-line plain OK; their exact method identities and completion types are retained in the JSON. Four before/after maps of 410 source paths match fixed Git bytes, for 1640 hash comparisons.
- Fixed Git has 7848 tracked paths. Runtime is 67 files: 66 Python and one HTML, 1,479,474 bytes. V4 contains the exact 66 Python runtime names. The reported package runtime map and required path set match Git.
- The installed report records eight tests, eight zero-return commands and 25 module paths under its reported site. Module values are paths rather than content hashes. `uta.funding_local`, `uta.funding_obligations`, `uta.perpetual_funding`, and `uta.funding_hold_pure` are absent from that direct module list; direct installed funding functionality remains NOT_VERIFIED.
- The 14 frozen SAFE files (347,888 bytes) contain no private absolute path values or signed references under this scoped review. The collector source matches its frozen hash; its AST differs from the PR63 public helper only by the approved source/tree and component tuple changes. A public source copy does not prove the actual executed helper identity.

## Explicit limits

Binary artifact `14451589577` (54,827,834 bytes) received one whole outer SHA256 read in this new scope plus central-directory review of two entries. Binary member payloads, member CRC, wheel and tar received zero reads. Binary qualification remains `null`; producer package checks are recorded assertions and do not establish inspected binary contents.

The finite recovery failure JSON occurred zero times in the two fixed complete logs. The recovery method's completion is observed; failure rendering remains NOT_VERIFIED. PR64 success does not determine or resolve the earlier PR63 push failure cause.

No target, repository import, compile, tests, SQL, process inspection/control, actors, network, or CI was run for this review. Production approval remains false. Original RAW, source, old review administration and earlier failures were not changed.

[Structured review and exact budget totals](../evidence/reviews/pr64-resumed-ci-independent-review.json).
