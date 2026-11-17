# Independent strict spot-confirmation JSON review

Original runtime subject: `3729b562f0935509322e8cffd684520069145420`.
This independent worktree changes tests, documentation and raw observations only.
It does not implement the runtime parser correction, alter the root/integration
checkout, modify the frozen release or touch any old soak authority.

The original eleven reverse-reconciliation and typed-side cases passed on Python
3.13.5: empty and remaining-valid receipt bundles are correctly rejected before
sealing, missing single fills are rejected, and unfilled/cancelled order
lifecycle events remain valid. The new maps use `(account_id, order_id)` for
order attribution, preserve both distinct account sides even with identical
order IDs, require a NULL global account and exactly the original eight private
payload fields, and compare integer versions distinctly from booleans. Added
runtime verification code issues no financial writes. Full ledger/history
scanning remains an unbounded lifecycle cost; these tiny tests make no capacity
or large-history availability claim.

Two raw-JSON boundaries remain incorrect at the original subject:

| Temporary offline fault | Public `SpotExchange.verify()` | `take_over()` |
| --- | --- | --- |
| Numeric `NaN`, `Infinity`, `-Infinity` or `1e999` in a private/global `market_version` | Raw `ValueError`, with no stable code/status | Existing helper converts it to `503 spot_corrupt`; remains unsealed |
| Duplicate `market_version` keys, first `999` and last the correct `1` | Accepted after `json.loads` discards the first key | Accepted and sealed at the original subject |

Python's default JSON parser accepts these nonstandard/overflowed numbers and
silently collapses duplicate object members. Canonical serialization later
rejects nonfinite floats outside the verifier's typed-error boundary; duplicate
keys have already disappeared before comparison. The latter is acceptance of
ambiguous historical evidence, not proof that a customer can submit such a
payload through the normal spot API. The source producer always records its own
confirmation objects; negative writes here are deliberately **offline synthetic
corruption**, with exact original event guards restored.

Each independent fixture replaces the raw stored substring directly. It never
passes the malformed payload through `json.dumps`, so raw `1e999` tokens and both
duplicate members reach the actual parser intact. Readback asserts the exact raw
payload, settled financial rows, spot rows and locks remain unchanged. Tests
require `ServiceError(spot_corrupt, 503)` from both verifier and migration and no
managed manifest/queue/fence; original failures remain ordinary red assertions,
without skips or expected-failure labels.

The required correction is strict confirmation parsing: reject duplicate object
keys and non-integer numeric forms/nonfinite constants, then preserve the exact
global receipt and typed eight-field private contract. Confirmation money is
stored as strings and versions/sequences as integers. This does not authorize
altering lifecycle-event interpretation, repairing payloads, dropping evidence,
unlocking assets, or admitting managed spot trading.

Reproduction:

```sh
/usr/bin/python3.13 -m unittest tests.test_spot_confirmation_json_reference -v
/usr/bin/python3.13 -m unittest tests.test_migration_reverse_evidence tests.test_spot_confirmation_integrity -v
```

The first command records the original strict-JSON failures; the second retains
the existing eleven green controls. On Python 3.13.5, the first command produced
**10 ordinary assertion failures in 2.793 seconds**; the second produced
**11 passing controls in 2.827 seconds**. Eight nonfinite/overflow faults exposed
raw `ValueError` while migration rejected; the two duplicate-key faults were
accepted by both verifier and takeover, with the raw evidence and financial rows
unchanged. Raw results and source/test digests are in
`evidence/runs/spot-confirmation-json-review/`. A later runtime repair must run
these same assertions unchanged and retain the original red evidence. No
production or long-run approval follows. Production remains **NO-GO**.
