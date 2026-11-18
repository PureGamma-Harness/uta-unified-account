# Consolidated first-phase engineering candidate

This branch combines the previously separate phase1 writer fencing, admission replay contracts, durable local funding obligations, opt-in exact decimal calculator, independent synthetic oracle, and bounded test diagnostics. It does not enable a new financial capability or change the default reference calculator. The combined runtime has its own source inventory; historical branch test results are references, not acceptance of this tree.

The code origin is `f6f27524f395d0aa2ca3e96e70269be36086f189`. The merge inputs are PR49 `c3e937a9`, PR52 `e7fa6e41`, PR53 `92979e9b`, PR55 `e3761f17`, PR54 `7e1990cd`, and PR56 `be082a76`. The three ledger/startup/writer-fence files remain byte-identical to PR49. Service/decision/credit audit files remain byte-identical to PR52. The three funding modules remain byte-identical to PR53. The calculator remains opt-in and is not selected by the service.

## Product and operation boundary

This is a synthetic-data, single-host engineering candidate. Existing synchronous and managed entry points retain their documented authentication, lease, transaction and queue contracts. Existing local spot lending, Cross collateral valuation and USD-reporting linear-perpetual examples retain their original limits. These examples do not establish a USDT/USDC production settlement service. The local funding-obligation capability requires its explicit fresh synthetic installation; adding its module does not install it into an existing authority.

Production Isolated/PM, options, inverse/delivery contracts, multiple real settlement coins, automatic borrowing, conditional or multileg orders, custody/on-chain operations, multi-node consensus, and real-funds enablement are not accepted by this delivery. Callers must use the existing product/capability validators; the candidate creates no generic successful fallback for unsupported operations. A research PM calculation is not a trading permission.

Pending funding debits are still not unified admission/withdrawal/transfer holds. The order/audit policy separation is retained, but new loaded-engine binding and shadow operation are not implemented here. An independent native trial on a different frozen source failed during a market-publication barrier; it is not evidence for this tree, and publication pause/activation handling remains an explicit open engineering issue. Same-account cancellation/repayment priority behind a queued order needs a separately reviewed causal-order policy.

## Reproduction and acceptance

Use a fresh synthetic checkout and private, disposable database paths. Existing documented commands remain `python -m unittest discover -s tests -v`, `python -m uta demo`, and `python -m uta acceptance`; managed deployment and authentication are described in `docs/durable-cli.md` and `docs/durable-api.md`. The ordinary GitHub CI workflow also builds and checks the wheel and source distribution. No combined-tree test has run at this documentation commit. The first normal push and PR runs must be retained, including failures, and reviewed independently before claiming functional acceptance.

The new source inventory binds every tracked runtime Python/HTML file. It is an identity record, not a test result, loaded-callable proof, performance run or approval. Existing oracle golden data remains synthetic and under its original exact-byte acceptance. Packaging byte equality and installed functional coverage must be reported separately.

## Deployment, data compatibility and rollback

Deployment is for isolated synthetic namespaces only. Keep the current source and artifact digest with every new authority. Do not open an existing financial database with another branch solely because a schema number matches: recorded policy and code-artifact checks remain authoritative. This consolidation performs no automatic schema migration or capability installation.

To roll back a new test deployment, stop its ingress and authority using its documented ownership protocol, retain command receipts, logs and databases, reconcile confirmed effects, and deploy the prior reviewed artifact into a separate fresh namespace. Do not reset or restore a database over confirmed post-cutover transactions. Existing-authority migration and post-trade rollback require their own independently tested handover/compensation procedure. Unknown results remain queryable by original command ID.

## Release gates

Independent source/interaction review and this tree's own first CI are pending. Further gates include full matching-to-ledger reconciliation, restart and fault injection, pending-obligation encumbrance, market-publication liveness, loaded-engine identity, product-specific settlement, replicated recovery, open-loop sustained 10000/s order and unique-liquidation-fill workloads, 30-minute and longer stability runs, and explicit real-funds approval. No capacity, HA, production or funds approval is granted.

Independent pre-CI review identified a deterministic integration mismatch: the ordinary source-inventory test still declared the62-module PR51 deployment, while this tree has65 Python modules. Inventory V3 explicitly adds the three funding modules and preserves the historical V2 tuple. Exact-set and fixed-count assertions remain strict; frozen historical runs retain their original source/test bytes and pins. Static AST/Git verification confirms all65 names; this is not an executed test result.
