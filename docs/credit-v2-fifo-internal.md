# Explicit internal synthetic credit FIFO

`InternalCreditFIFO` is not wired into HTTP, WebSocket, CLI or generic
`QueueStore`. The generic queue still rejects `BORROW`. Construction requires
the complete actual format2 capability; no-cap and PREPARED authorities remain
closed. No caller-provided flag grants a producer or financial role.

The explicit local synthetic producer takes a server-chosen actor and unique
source reference. It canonicalizes exact BTC native quantities, records the
immutable source and original PENDING row in one producer COMMIT, and returns
only after COMMIT. This is a queue acknowledgement, not risk acceptance. An
original CID retry checks canonical business content and the original source
actor/reference. A pre-cap receipt may be returned as `LEGACY_RECEIPT` without
creating historical source, intent, decision or inbox rows. `status` queries
the original actual inbox CID, with optional account isolation.

Execution selects one eligible oldest account command. An earlier PENDING
command of any kind blocks younger credit commands for that account. A real
SAVEPOINT precedes native operation setup; intent, expected legs, original
credit effect/receipt, dedicated borrow decision and SUCCEEDED terminal all
share the same outer financial COMMIT. REPAY uses the existing interest-first
four/seven-leg logic and has market dependency NONE. Queue capacity preserves
the configured additional reserve for repayments.

Known business refusals first roll back the real SAVEPOINT and then write only
REJECTED under a native rejection scope. Initial unavailable/incomplete market
quotes are confirmed no-effect refusals with status503. A late validation that
poisons the actual guard, hidden SQLite/ledger/storage failure, unknown error or
unobserved COMMIT result cannot become a business rejection. The exception to
generic StorageError classification is limited to the exact pure integer
`CreditTransitionError` quota/pool refusal at status409, while all of its cause
and context chains remain checked for real failures. Failed execution leaves
PENDING unless querying the original CID proves a terminal COMMIT. No automatic
quarantine, source replacement, cross-shard budget recycling or FIFO bypass is
provided. A truly unknown account head therefore also blocks younger repayment;
recovery must establish the original outcome before proceeding.

The component tests establish exact actual base queue SQL, no repair on weak or
extra constraints, closed construction without a capability, unchanged generic
BORROW rejection and rejection-cause taxonomy. Their raw run is in
`evidence/runs/credit-v2-fifo-components`. They do not prove a successful V2 loan,
native publication, lost-response recovery or restart. Those remain mandatory
integration gates. This slice needs no schema deployment; default behavior is
closed. Roll back code only before publication. Never delete a published marker
to make an older binary accept an authority.
