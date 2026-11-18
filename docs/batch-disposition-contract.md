# Committed batch disposition contract: new targeted review

Frozen baseline is 909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0. This review follows the existing independent batch-recovery specification and does not repeat its real SQLite/process tests. Only committed-disposition validation is under review. No H1 AuthDB authorization probe is involved.

The real BatchStore.process loop visits immutable members in order, can skip a backoff member, earlier-account-head member or existing terminal, and can stop at the soft budget/control barrier. Therefore executed IDs form a duplicate-free **subsequence** of member order; a prefix is not required. Example selected [A,B,C], with B skipped, permits executed [A,C] and does not permit [C,A].

QueueStore._execute only writes SUCCEEDED or REJECTED before appending a CID to executed. QUARANTINED is created by the separate technical-failure record_failure path. A previously quarantined member can legitimately be present in commands but can never be newly claimed in this attempt's executed list. Actual terminal rows are immutable, so a SUCCEEDED/REJECTED result cannot later turn into QUARANTINED.

Baseline _verify_outcome checks only that executed is a unique subset and its recorded states are in _TERMINAL. It thus appears to accept the reversed execution list and a claimed newly executed QUARANTINED member. These are impossible audit dispositions under the production loop. This does not itself establish duplicate settlement or financial mutation.

The frozen baseline-only fixture extracts the actual _verify_outcome, actual _json and literal _TERMINAL AST definitions into an isolated namespace. It passes only synthetic dictionaries/JSON and executes no module import or DB/transaction code. Four valid controls preserve skipped-member, zero-execution, preexisting-quarantine and recovered-PENDING-later-terminal behavior; two existing rejection controls preserve duplicate/nonmember checks. Two new expected rejections expose the proposed counterexamples. Only one CPU1/10s baseline execution is authorized; keep its first outcome even if RED. No actual SQL/native/process/signal/network test is authorized.

The first fixture/negative result must be sealed before any source repair. A repair needs fresh code SHA, explicit new-test budget and independent review. No source or data migration is proposed yet. Production remains false.

## First baseline counterexamples retained

Frozen fixture f6f4707 executed exactly once with CPU1/10s. Exit1, eight cases: six controls matched policy and two new counterexamples were RED because old code accepted illegal dispositions. Inner AST/read/fixture duration 49,780,942 ns; outer subprocess duration 110,391,036 ns. No product module/SQL/worker/CLI/signal/network code was executed. Exact stdout3033B SHA990c173db43356d3c2e944dbc79de55b6b629eebb83090055e6e0ba3d0262c89, empty stderr, intent and execution are retained under evidence/reviews/batch-disposition-contract/first-baseline. These observations establish only validation/audit gaps; no duplicate financial effect or native recovery failure was demonstrated. The original source remained unchanged at this seal.
