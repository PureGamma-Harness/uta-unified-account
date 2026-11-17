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
