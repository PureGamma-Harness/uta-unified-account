# Ordered postings candidate: implementation NOT_RUN

This follows the immutable contract/evidence milestone `67091b2`. The candidate changes only `DurableLedger.verify` and adds its synthetic differential tests. At this milestone the source and test AST parse, but no SQL/test/profile has run. `ordered_postings` must be an exact boolean and defaults false; there is no startup, command, service, plan or configuration wiring.

The event rows still use the existing `fetchall(N)`. Only postings consumption uses at most one current event's group and one following row. This is not an O(1) complete-history memory claim. Each original event's sequence/sealed/prior chain is checked before its posting units are decoded. No mismatching cursor sequence can be skipped; any remaining inventory is rejected. All original transaction/guard checks and final balance comparison execute.

The existing inspection is bound to the retained `original-storage.py.txt` bytes from Git base `c30457227e2bfc0a1e665ff67c9c148855ac624a` (SHA256 `9eee296159d0b0347feac3fd2f2b99b3216e8247e579e159e5adda8cbcb08a08`). The original `existing-evidence.json` remains unchanged. The source belongs to this repository under its original Apache-2.0 license. The inspection requires no Git checkout to reproduce the pinned baseline after this candidate changes storage.py.

## Catalogue gap: source-supported, not yet reproduced

The old verifier checks SQLite integrity, declared FKs, schema-version/asset-scale values and original trigger definitions. Its `_verify_protection` does not validate the table SQL or complete FK inventory. A table reconstructed without its original FK can therefore make `foreign_key_check` incapable of finding orphan rows. Per-event queries would never fetch postings with a nonexistent sequence. This is a static counterexample construction, not an observed runtime test result.

The opt-in stream explicitly rejects unmatched inventory even in such an unsupported/tampered catalogue. Equal result/error text is promised for the original supported catalogue with malformed data. The intentional stricter opt-in rejection for unmatched inventory under removed-FK catalogue is recorded separately; the original default verifier is unchanged. A shared complete-table/FK verifier would be a different integrity-policy patch and requires its own approval. This candidate does not silently claim that complete catalogue validation already exists.

## Pending execution and independent review

The new 20 tests contain the manual two-event reference, exact old/default/new SQL statement counts, option validation before storage, reverse physical insertion and all declared corruption families. Their literal hash/integer builder does not call production fingerprint/hash/normalization functions. These tests deliberately reconstruct corruptions offline in private temporary authorities and restore the original trigger bytes before either verifier runs. No verifier runs with its guards disabled.

Root approval for the exact source/harness and CPU4 release remain prerequisites for the single total-15-second scratch component. Full test/case/profile outcome is NOT_RUN. SQL count savings and elapsed-time improvement have not been measured. This candidate remains default-off and requires another group's independent review; the author cannot sign its acceptance.
