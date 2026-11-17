# Offline credit accounting transition

`uta.credit_transition` is an unwired, read-only arithmetic component for future
credit operation replay. It has no database/queue mutation, client route,
activation capability or supported trading format. Its result explicitly sets
`operation_authorized=false`; the current managed new-borrow 501 remains in force.

`calculate_borrow_transition` accepts an already parsed static allocation
descriptor, account/asset identity, canonical native-unit strings, a complete
accounting snapshot, explicit account/local limits, a conservative quote and
quantity step. The quote must be independently reproduced from actual archived
market/risk inputs by the future audit layer; this component does not establish
the quote's authenticity or financial validity.

All quantity fields are native asset minor units, exact signed Python integers
with magnitude below 10^38, carried on the wire as canonical ASCII strings.
`scale` comes from the parsed descriptor. `version` is an integer in
0..2^63-2 and advances exactly once. Floats, bools, signs on zero, leading zeroes,
exponents, Unicode digits and unknown/missing fields fail closed. Decimal
precision, rounding and traps cannot change the arithmetic.

The snapshot preserves separate cash, principal, interest, their negative
customer liability journal balances, local aggregate principal/interest, funded
pool cash and gross principal/interest receivables. Debt cannot be netted against
positive cash. A negative cash balance remains a distinct cash component and
does not remove principal or interest. The expected receivables must equal the
local gross components; this is a stronger accounting invariant, not a claim
that the preexisting generic ledger verifier proves credit event semantics.

The requested quantity must be positive, align exactly to its step, fit its
supplied quote, and leave principal+interest at or below the explicit account
limit, local asset limit and immutable local allocation. Equality is allowed.
Pool liquidity must cover the request. No allowance is inferred from another
shard, a missing response, global unused capacity, a timeout or an UNKNOWN
command. An immutable certificate constrains the sum of assigned limits; this
single operation does not claim a cross-shard atomic transaction or a dynamic
global usage observation.

The result advances cash, principal, negative principal liability, local gross
principal, pool and principal receivable by their exact signed quantities.
Interest remains unchanged. Four distinct, lexicographically ordered journal
legs sum to zero. `compare_borrow_transition` checks every post-state field and
all four ordered legs, including strict ordinal and string types. It does not
prove the journal ID, sealed state, hash chain, physical COMMIT, source identity,
fencing, fresh market, margin, code identity or terminal durable receipt. These
remain blocking inputs to the complete future operation audit and native gate.

Typed arithmetic-input errors use `credit_transition_invalid`/503. Recorded
mismatches use `credit_transition_mismatch`/503. Quantity exceeding a supplied
quote or gross limit uses `credit_limit`/409; insufficient funded cash uses
`credit_pool_empty`/409. These are internal contracts, with no new HTTP mapping.

## Evidence and deployment

Eleven tests include manual gross/interest cases, shared local allocation,
unreachable other-shard capacity, exact equality, overflow, negative cash,
all-field/posting mutations and hostile numeric inputs. One actual synthetic
preseal transaction uses the configured catalog/rules to quote and borrow
0.4 BTC from a 1 BTC pool with USD100 collateral. The complete actual post-state
and journal are compared, COMMIT succeeds, then a new storage read snapshot and
the original ledger/credit verifiers agree. No managed intent, source or audit
is invented for this reference loan. The temporary directory is removed.

The first 11-test output and source hashes are retained in
`evidence/runs/credit-transition-initial/`. Tests also passed with the 17 artifact
tests on Python 3.10/3.12/3.13, 28 tests per runtime, with ResourceWarning treated
as an error; final raw output is in
`evidence/runs/credit-artifact-peer-fix/final-template/`. Independent integer
validation of this new component is still required before it is used by audit.

```sh
python3 -W error::ResourceWarning -m unittest tests.test_credit_transition -v
```

This slice has no deploy command, schema migration or permission flag. Reverting
the isolated module/tests/docs restores the previous unwired state. Future audit
consumers must retain matching immutable source and must add its loaded-code
identity before relying on it. No production, real-funds, interest-scheduler,
USDT/USDC, auto-borrow or throughput acceptance is claimed.

## Independent contract counterexamples and correction

The independent author froze an integer/Fraction oracle and safety assertions
in `7ece8c483571a9ff859f4c71aa1d64402351d90d` before observing the correction.
Against actual `23efd5f`, its 51 ordinary arithmetic cases matched, but four
safety assertions failed: a legal final version could not roundtrip; a public
descriptor dataclass could enlarge its allocation fields while retaining old
canonical bytes/IDs; a public result dataclass could double its four expected
legs and be compared to itself; unknown assets leaked a different error class
without the module's promised status. These are offline arithmetic/caller
contracts. They did not grant native permission, and `operation_authorized`
remained false. The original red outcome is retained separately.

The correction reparses the canonical descriptor using the real strict
certificate validator before using any allocation. Constructing or replacing
Python fields cannot enlarge that canonical budget. Its declaration still must
be pinned to the actual native authority by a future caller; no newly fabricated
but structurally valid certificate becomes a live budget here.

The calculator retains canonical primitive arithmetic inputs. Comparison
recalculates the expected transition from those inputs, validates primitive
result fields and checks its complete result before comparing recorded state
and postings. A result dataclass is data, not a verification seal. The retained
input reader bounds text at 4 MiB (including an escaped descriptor), rejects
noncanonical JSON, huge metadata integers and non-integer numbers, and never
imports or executes any retained symbol. Neither internally consistent inputs
nor the reconstructed result establish the provenance of a supplied quote,
limits or snapshot.

The final signed-64-bit account version can be a valid recorded post-state; it
cannot be a new operation's starting version. Missing allocations now return
`credit_transition_invalid`/503 with the original cause retained. Financial
formulas, interest, native SQL, managed paths and A2 behavior are unchanged.

Fifteen targeted tests, including real temporary preseal COMMIT/reopen, passed
on Python3.12 (0.072s), 3.10 (0.105s), and 3.13 (0.078s). All runs promote
ResourceWarning to an error. Full source hashes, commands, process times and raw
output are retained in `evidence/runs/credit-transition-contract-fix/`. Independent
rerun of the original safety assertions is required to close the four specific
blocks; these own tests do not substitute for that review or full operation audit.
