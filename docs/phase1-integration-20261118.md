# Phase-one integration candidate, 2026-11-18

This local candidate combines reviewed changes; it has not passed integrated
tests or CI and is not a production release. The immutable component results
remain results for their original source/rule/runtime, not this combined tree.

The baseline is PR35 `9b61e5f`. Included components are startup lease diagnostics
with the fingerprint-compatible Enum tag (PR42/44), native-integer reference
journal sequence validation (PR43), instrumented shared-gate recovery tooling
and its original first CI evidence (PR45), and the strict projected maintenance
guard plus corrected test descriptors (PR46). Funding, expanded admission
replay, snapshot book selection and reserve-cache candidates are separate
unintegrated branches. Phase-two credit read admission remains disabled.

Only four UTA files differ from the baseline. Service, startup and writer-fence
files match their component source bytes. Ledger retains the baseline durable
implementation and existing unit_digits API; only its replay sequence guard
is changed, identically to PR43. The provenance manifest proves that replacing
this guard alone yields the integrated file AST. No whole-file or whole-method
identity with the smaller main-based PR43 ledger is claimed.

Source `8b8eb7c9` is recorded in
`evidence/reviews/phase1-integration-20261118/CODE-integration-manifest.json`.
No schema migration, new route or product activation is added. Independent
integration CODE review must check fingerprints, source closure, original
default-off controls, exact guard placement and preserved confirmed-ID/RO
behavior before an explicit first integrated test run. Existing complete CI,
transactional scenario, package and bounded formal checks will supply fresh
evidence for the final integrated SHA. Do not execute historical component
plans against this tree and relabel their old source pins.

Independent CODE580f1ae6 blocked the initial integration before execution:
the ordinary tag test compared the current runtime with a historical plan's
source hashes. The revised test retains that strict injected-pin branch for
frozen runs. Ordinary tests instead independently read the current canonical,
regular source files using a versioned61-path inventory, bounded no-follow
reads and matching hashes/metadata before and after artifact calculation.
They do not call production source-enumeration helpers to form expectations.
Historical plans, financial runtime, validators, exclusions and unknown-object
negative controls are unchanged. This test correction is NOT_RUN pending
independent delta review; the combined suite remains unaccepted. Future module
inventory changes require an explicit test-inventory version update.

Known first failures remain visible: PR45's ordinary publication router_busy
error is not explained by its SH fixture; PR46's original descriptor errors
and separate capture-undo failure are retained. The corrected descriptor's
pure first run passed, pending independent RAW closure. A STOP-ack fixture
revision is separately under review and is absent here. These facts block
claims of universally passing recovery or integrated acceptance.

## Deployment and rollback

Use only a new synthetic code-bound authority for validation. Do not hot-swap
an existing authority or downgrade its source/artifact binding. Public data is
synthetic, and full databases, private process bindings and source capsules
remain private. Real funds, G3/G4 sustained10000/s, mixed load, long stability,
replicated durability, AZ recovery and financial approval remain NO_GO.

If validation fails, retain the first commands, receipts, snapshots, matching
results and journals; stop the candidate. Roll back the binary only through
the separately verified writer handoff, after resolving unknown command IDs
and reconciling confirmed history. Never undo a confirmed trade by deleting
storage or replaying it under a new ID. Reverting the MM guard restores its
known equality defect and requires blocking affected new-risk operations.

Preparation-only index/provenance assertion failures are recorded in the
manifest. All occurred before target execution in this new isolated directory;
existing authorities and sealed originals were untouched.
