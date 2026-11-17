# V2 context failure contract, before a positive owner exists

This narrow change distinguishes the public missing-scope case from corrupted
native state. It does not create a loader, owner, publisher, scope constructor
or successful operation. The existing PREPARED1 gate and no-cap paths are not
unlocked. Positive V2 testing remains blocked until the real complete capability
and source/audit/FIFO implementation exist.

For an actual valid V2 financial connection and current fenced token:

| Actual condition | Result |
| --- | --- |
| No native operation and no actual intent under the requested CID | `credit_v2_scope_missing`; only this code may be mapped to original public new-borrow501 |
| Actual intent exists but the transaction's operation context is absent | `credit_v2_context_invalid`, poison the real guard |
| Existing context has wrong service/guard/PID/thread/generation/identity/actual intent/source/prestate | Typed invalid context, poison the real guard |
| Actual token validation fails | Retain the actual fence error and poison the guard |
| Staged intent inventory cannot be read | Typed invalid context, poison the guard |

The true no-context public wrapper opens a new transaction and still cannot
borrow. Existing CID replay remains before the new-operation check. No caller
flag can confer a scope. A caught corrupted-context or expired-token error must
not be converted into a normal501 and later committed. Original `Database`
before-COMMIT denial handling retains the latched failure.

The new branches are for the yet-unavailable V2 owner and are **not** claimed as
executed positive/forged-owner tests here. Existing actual financial/read/raw
no-cap boundary evidence is retained in the earlier context commit. Full native
before-COMMIT must additionally scan actual staged effects even when the in-memory
context is absent; this error distinction alone is not that final validator.

No schema migration, activation or deployment is supplied. Revert this isolated
API contract before dependent capture/FIFO code uses its error taxonomy; do not
delete a future persisted capability or undo committed customer effects.
