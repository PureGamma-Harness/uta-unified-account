# Internal V2 reserved inventory and incomplete-runtime refusal

This slice recognizes a separate reserved V2 authority inventory and refuses
partial native objects before writer acquisition. It does not implement a
publisher, successful V2 owner, source/financial operation scope or financial
SQL-effect gate. Those actual functions are required by the loader and are
currently absent, so no partial build can publish/acquire V2. PREPARED1 remains
unchanged and cannot be promoted. No HTTP/CLI capability is added.

`writer_fence_credit_v2_capability` is independent from the immutable format1
marker. V2 may combine only with the standard guarded base, never batch or
PREPARED1. Its fixed fresh prefix is enabled_guard_v1 followed by
credit_internal_enabled_v2, both at original generation0/no owner. A missing
marker with native objects/event is partial state, not an unmanaged fallback.
Source rows will use UD writer guards and the separately required source INSERT
gate; a marker cannot be loaded until real complete capability validation exists.

Generic acquire refuses V2. The private internal acquisition selector still
requires an actual complete V2 from `_load`; calling it against a base authority
does not grant a capability. Loader checks are fixed compiled dependencies,
exact native/audit/FIFO SQL, actual foreign_keys ON, the current complete credit
artifact and retained matching manifest, exact immutable envelope/config and
local static allocation. Presence of method names alone is explicitly not the
financial proof: actual scope/effect/closing validators and acceptance are still
required. There is no caller-provided verifier, ready flag or positive callback.

The required code identity covers native V2, dedicated audit/replay, FIFO, pure
transition and payload contract. The audit class must implement real
runtime_evidence, begin/complete, verify_staged_borrow and replay. Missing fixed
implementation pieces cause typed `credit_v2_runtime_incomplete`. The real
control transaction's failed publication rolls back marker DDL, triggers and
event together; reopening retains generation0 and the original single event.
This tests the original Database physical-COMMIT boundary, not an online V2
installer that does not yet exist.

## Actual raw results, including failed development controls

| Retained run | Actual result and limit |
| --- | --- |
| First Python3.12 window, 13:10:22.411390–13:10:28.830448 UTC | 81 reported, 79 passed, one new old-binary harness failure (`with_writer` should have been `for_writer`) and one nonexistent joined-module command. The first child acquired but did not complete the financial write. Exit1 is retained. |
| Targeted corrected command, 13:11:37.777163–13:11:39.119787 UTC | 16 tests, 15 passed. Actual old child acquired and wrote; the test incorrectly expected version0→1 although the reused fixture deposit already set version1. Actual result was1→2. Prototype negative control had not yet executed. This exit1 is retained and is not counted as a complete old-binary pair. Eleven actual joined-borrow methods passed. |
| Only the old899 pair, 13:13:19.163766–13:13:19.652605 UTC | One test,0.306s, exit0. Assertion now compares actual before-version plus delta. Real old source acquires and commits the actual account UPDATE in base format; the prototype V2 marker causes `fence_guard_corrupt`, with no owner/write/version/generation change. |
| Only missing-FIFO publication fault, 13:19:01.611431–13:19:01.965377 UTC | One test,0.088s, exit0. Fixed FIFO import is explicitly made unavailable; actual control COMMIT fails typed and rolls back all newly staged marker/event state. This remains meaningful once a real FIFO is added. It is absence fault injection, never a successful permission callback. |

All windows use CPU4 and ResourceWarning errors. The original79 green cases
were not rerun to wash the harness failures. This is not one final-build
91-test/multi-version acceptance claim: the current positive V2 branches remain
unavailable and unexercised. Context failure poisoning was isolated in its own
`2f29056` code contract, not attributed to either harness fix. A later required
audit/replay identity interface update was followed only by the specific
missing-FIFO test. Final source's introductory module docstring was clarified
after that run; the manifest verifies the known tested source hash and that
only that module docstring differs in AST. It does not relabel prior raw bytes.

The old source fixture is the public exact ancestor
`899c91d0a032d88cc4cb8c73ffb09cb2d1bd7236`, archived with LICENSE and no data.
Both actual child processes report the loaded writer source SHA256, verified
against provenance. The marker is deliberately a raw trusted-host inventory
prototype, not a fully installed V2 or a formal financial source. This proves
old unknown-inventory refusal; it does not prove positive V2 admission. No
customer artifact selects code to import or run. The two children exit and
their private temporary source/database directories are cleaned up. No nonce is
printed or retained, no listener/service is started and no live/frozen path is
used.

Exact commands, source/archive hashes, outcomes and all original stdout are in
`evidence/runs/credit-native-v2-fence-boundary/`. Reproduce the final independent
pair with:

```sh
python3 -W error::ResourceWarning -m unittest tests.test_credit_native_v2_fence_boundary.CreditNativeV2FenceBoundaryTests.test_actual_old_899_base_positive_vs_new_marker_negative -v
```

## Remaining acceptance and recovery

All NV2 positive gates remain pending. Actual scoped effects, SQL intent/effect
binding, source intake, before-COMMIT bidirectional reconstruction and immutable
prestate/isolation verification must be implemented before a publisher exists.
Fresh installation must reject non-BTC nonzero principal/interest; USD cash
deficits remain full risk inputs and are not reclassified as principal. Zero
legacy rows and original receipts remain queryable without backfilled audit.
Only explicit trusted metadata scopes may later halt/publish prices; they must
never alter cash, debt, accounts, positions or orders. REPAY remains independent
of new-borrow limits/quotes and uses market dependency NONE.

No deployment/migration/activation command ships here. Before a complete future
V2 marker is successfully published, revert code or clean a failed transaction
through its actual rollback. Do not delete a future committed marker, downgrade
format1/2, reassign static claims or roll back committed financial effects. A
full future authority requires original-CID forward recovery and independent
review. Neither internal positive approval nor production approval is supplied
by this slice.
