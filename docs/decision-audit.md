# Linear decision evidence, capability 1 / trading schema 3

Required guards are checked by their exact SQLite SQL definitions and target
tables, with a complete `audit_*` trigger inventory. A same-named weakened guard
or unexpected audit trigger is rejected as `audit_schema_corrupt`; startup does
not repair it. Archiving, recording a decision and reading historical evidence
also validate this inventory, so a previously opened audit object fails closed
after a guard definition changes. This is a local integrity check, not protection
against a trusted OS owner replacing the entire authority or executable.

This capability covers new linear perpetual order acceptance and confirmed
linear fills through `ExchangeService`, including matcher/liquidation paths that
call the same helpers. It retains the complete market payload and all valuation
inputs, and links each decision to unsigned code/runtime and risk-policy
artifacts. It does not enable additional products or change financial formulas.

Business rejections, spot decisions, new credit decisions, cancels and repayments
are outside this first decision archive. Durable command errors remain available
but are not claimed to contain complete historical risk inputs. Risk-reducing
cancel/repay operations retain their existing market-outage behavior.

## Explicit upgrade and rollback boundary

Legacy mode remains trading schema 2. Enabling required audit is an explicit
upgrade to trading schema 3; it must not be inferred from an empty table or
silently repaired after missing evidence. The activation record preserves the
last legacy event sequence and the counts of legacy orders and fills. Existing
rows retain NULL decision links. Those are evidence gaps, not zero-risk decisions
and not successfully replayed cases.

The service entry point is `ExchangeService(..., decision_audit=True)`; its
default is `False`. An already upgraded database rejects a default/legacy
constructor. New managed deployments must explicitly require the capability,
and existing managed authorities need an offline, token-authorized migration.
This constructor does not bypass or automatically enable writer fencing.

The current full market can be archived at the upgrade boundary as
`UPGRADE_OBSERVED`. This proves which bytes were observed at upgrade and permits
future decisions to refer to them. It does not prove earlier publication or
reconstruct replaced historical markets. No old decision is fabricated from a
current price. New publications are archived as `PUBLISHED` in their financial
transaction before changing the current market row.

New order and fill rows require decision links. The foreign keys are deferred
until commit so the business mutation and audit row can be written in the same
transaction. New market row insertion/update requires its exact full payload
already in the history table. Business triggers prevent a pre-upgrade protocol
from silently creating unaudited rows. Managed deployments additionally require
the persistent writer guard; application version checks alone do not fence an
already-running old binary.

A schema-2 binary cannot reopen schema 3 for financial service. Rolling back to
an old financial writer, deleting evidence, dropping triggers or lowering the
schema marker is unsupported. Incident rollback means halted ingress, preserved
pending commands and a compatible audited release, with read-only export and
reconciliation before activation. A verified restore is a new recovery exercise,
not permission to erase acknowledged decisions.

## Stored evidence

| Archive | Contents |
| --- | --- |
| `uta_market_history` | Exact full payload bytes, SHA-256 snapshot ID, origin and archive time |
| `uta_code_artifacts` | Application version; package Python-source hashes; deterministic loaded financial/replay code fingerprints; Python implementation/version, optimization flag and SQLite version |
| `uta_risk_policies` | Full catalog and rules JSON, asset scales, fee rate, age policy and formula/precision identifiers |
| `uta_risk_decisions` | Business/account IDs; market, artifact and policy IDs; account pre/post versions; operation and complete account valuation inputs; risk/reserve summaries |
| `uta_audit_capability` | Activation point and explicit supported/unsupported historical coverage |

All archives are append-only, including protection against `INSERT OR REPLACE`.
Artifact and policy bodies are stored once per content version; decisions refer
to them rather than duplicating source/configuration. The hashes are unsigned
identities on a trusted local host. They are not release signatures or external
tamper-proof audit seals. Retain the corresponding source release separately.
Deploy source files immutably for the process lifetime; a changed file under a
running interpreter cannot be claimed to replace already-loaded code. The archive
also fingerprints loaded functions in fixed financial/replay modules, including
wrapped function bodies. Paths and unordered constants are normalized so host
paths and process hash seeds do not produce different engine identities. These
checks remain unsigned evidence on a trusted interpreter, not an attestation
against arbitrary hostile in-process mutation.
The policy record also identifies the enabled mathematical/decoder cache sizes;
those options must not change the financial result.

New order receipts and `ORDER_ACCEPTED` events carry `decision_id`; legacy order
rows expose NULL with `decision_evidence="legacy_missing"`. Confirmed fill
receipts additionally carry `execution_decision_id`, and the fill event carries
that decision ID. Market publication receipts/events carry `market_snapshot_id`.
Legacy schema-2 API responses do not gain these fields.

The evidence includes settled balances without netting away liabilities,
separate principal and interest, positions with signed cost basis, current live
order economics and accumulated fees, frozen spot assets and halt/liquidation
state. This permits numerical valuation of the recorded state even after the
current account, prices or orders have changed.

`DecisionAudit(database)` provides `decision(id)`, `market(id)`, `artifact(id)`,
`policy_record(id)` and `replay(id)`. Replay verifies archived content IDs and
recomputes the currently installed source, loaded financial code and Python/SQLite
fingerprints before valuation. A valid archived digest or an equal cached startup
manifest alone is insufficient. A mismatch returns `replay_engine_mismatch`;
missing release files return `replay_artifact_unavailable`. Neither result reports
`matches` or calculates values. Use the matching Git/wheel release and runtime;
the tool never loads or executes code from database records. There is no default
compatible-math bypass. With a matching artifact it computes reserve and pre/post
risk from archived input states and the referenced historical market; it never
reads current account balances or current quotes for those values. It reports
each differing field. Use the recorded release/runtime to replay older artifacts.
An engine fingerprint is only a replay prerequisite. It does not authorize a
financial command, replace complete economic inputs, or permit sharing cached
risk decisions between accounts or different states.

Replay covers numerical valuation. It does not resubmit a historical order,
repeat matching, certify lease ownership or validate age against today's clock.
Historical freshness/ownership remains a separate timestamp/protocol evidence
question. Independent validation must use its own arithmetic, not only compare
this replay helper with production functions.

## Verification and deployment

Run `python -m unittest discover -s tests -p 'test_decision_audit.py' -v` and
the independent financial, concurrency and fault suites. Required acceptance
includes actual historical replay after later market/account changes, formula
differential checks, audit-write failure rolling back financial mutations,
same-ID receipt links, legacy-gap preservation, immutable history, missing-guard
refusal and rejection of an old active financial writer after upgrade.

Stage the explicit capability upgrade while ingress is halted. Back up and
verify the financial authority, enable required mode on the valid fenced writer,
and verify every shard's schema/capability before activation. Existing managed
authorities require a deliberate migration; do not let a restart fabricate
missing history. Default legacy calculations remain available for comparison in
separate schema-2 databases. No throughput, production approval or PM coverage
claim follows from enabling this archive.

This first implementation stores full account valuation inputs before and after
each supported decision. Evidence size and capture cost grow with live orders,
positions and liabilities. Archives are not pruned automatically. Measure disk
growth, write amplification and latency in required mode, including hot accounts;
legacy/no-audit throughput cannot be presented as required-audit capacity.
