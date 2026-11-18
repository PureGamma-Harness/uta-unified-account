# Real SQLite matching once: independent CODE review, not closed

Reviewed source: `d517ea250628517b22c3193afbbded6f00f48624`; proposal tip: `bb7dec1ee55a0368033902ee2e84e799fc97f146`. This review read source and metadata only. It compiled/imported no target, opened no database, executed no case, queried no PID and made no network or capability probe.

The manifest SHA256 is `b0e982f8af66d1f59f772e36e1297ff56795621265d11eef4fef11e92fdfc0e4`. All 63 declared regular, canonical files were independently matched against Git mode/blob/length and SHA256; total 1,326,051 bytes. The accompanying source-binding record preserves the exact inventory. The 61 UTA files remain unchanged from the prior component source26fa.

## Concrete execution blocker

`sqlite_once.py:314` unconditionally reads `_sqlite3.__file__` when constructing the mandatory result, after all financial cases. The separately recorded readiness metadata establishes a built-in _sqlite3 deployment in this environment; such a module has no extension-file attribute. This candidate would therefore raise AttributeError at result construction even if all SQLite cases completed. This review did not reproduce or probe that fact.

CODE status is **NOT_CLOSED**. The candidate remains NOT_RUN/zero attempts. Root must separately approve any repaired source and execution scope.

The minimal compatible metadata path must validate the real built-in ModuleSpec/origin/loader/name membership, retain null extension path/SHA, and bind the executable and actual Python/SQLite values. Dynamic extensions retain consistent origin/loader/module path hashing. The current zero-proc scope permits no new maps inspection; unobserved loaded libraries must be marked NOT_OBSERVED/null. Unknown module layouts fail closed. This fix must not relax financial checks or reinterpret old metadata failures.

## Reviewed functional scope

The four scenarios use native ExchangeService/Database/DurableLedger/DecisionAudit/Matcher without method or clock substitution, in eight new databases. Hand expectations agree with the fixed input arithmetic: matches per mode are 2+3+0+1=6 and paired fills are12. FIFO fees are0.04 each; the partial sell reservation is20.08. The reducing account ends at 10000-0.12-2-0.0392-1-0.0396=9996.8012, quantity1 and cost100. Quantity2 at price99 has reservation20.0792 and each side pays0.0792 on its actual fill.

The seller LIQUIDATING write is explicitly a synthetic status fault through the existing transition method. It tests a real second-leg account_frozen rejection and savepoint rollback, not a full liquidation workflow or approved operator action. Reopen checks, strict match/fill/journal correspondence, independent rational cash/cost replay and one historical numerical FILL replay per nonempty authority are present. The latter is a sample, not complete decision replay.

The comparison retains complete ledger hashes/postings and economic fields. Only the declared timestamp keys and time-derived market references are excluded from cross-authority equality, while full raw rows and each quote's content identity/reference remain retained and locally checked. It does not round away financial differences.

Unmanaged, unconfigured, native-only construction leaves the startup actor registry empty: the selected call graph does not start its lease keeper or invoke boot-ID/PID observation. The sole unconditional _sqlite3 extension-file access in the inspected runner/audit/reconcile path is the blocker above. No additional deterministic blocker was identified in that finite scope.

## Resource and evidence limits

The driver reserves raw bytes before FD writes under a shared512KiB cap with a512-byte abort trailer. Its 64MiB tree limit is application monitoring and known Python-write prechecks, not a kernel quota. Its one-CPU30s Python-line/step checks cannot prove an upper bound for blocked C/I/O calls. These limitations are explicit. All first outputs, partial state and unknown outcomes must be retained without retry.

This source has no actual module-import/SQLite/settlement/performance result. Prior pure12 PASS and its independent raw review remain separate. Production, real funds, managed fencing, concurrency, HA, sustained capacity and default snapshot activation remain NO_GO.
