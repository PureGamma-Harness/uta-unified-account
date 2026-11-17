# Experimental authentication-only credit intake

This Draft adds a default-disabled H0 issuer and a fresh authentication-format2
store. It verifies signed requests, records consumed nonces and grant decisions,
and retains the immutable first observation for a command ID. A same-ID query
requires current authorization and returns that original observation. Every
observation keeps financial, source-delivery and execution authorization false.
Construction without literal `enabled=True` rejects with501. No public route,
financial source, loan execution or account-readiness activation is added.

The runtime under review is `5750e12d60dbf7f8414b4e837e076a60c93a23bc`,
retained with its original component evidence at
`912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a`. Later delivery commits add review
and independent harness/evidence paths. They do not replace original failures.

## Evidence and its limits

- Independent grant and revocation corruption cases originally failed. The
  retained-data and historical-profile fixes have separate source-bound checks;
  their original red records remain in this branch's history.
- The three original full-suite inner summaries each contain1823 passing tests
  and identical359-file input maps. The original outer controller lost its last
  outcome and matrix summary. Its recording remains incomplete; these are not
  three fully completed outer qualification receipts. The independent read-only
  audit is under `docs/reviews/auth-h0-draft-readiness/full3-original-integrity/`.
- Four observed P1 ordering cases passed, with the exact schedules described in
  `docs/reviews/auth-h0-draft-readiness/p1-first/`. They do not enumerate both
  directions of every race.
- P2 completed its fixed262 signed requests and all seven steps. It retained224
  ordinary observations and32 query observations, checked five expected
  refusals, and admitted one new command after releasing below total224. An
  independent postcheck linked every private MAC, nonce and audit. Query reserve
  was measured with intake and storage available, not under intake exhaustion.
- P3 completed three steps with one new worker exiting73 after AuthDB capture
  returned. Its actual parent waited/reaped it, and a new issuer's current read
  and same-ID retry returned one unchanged first observation. The postcheck
  linked all three private MACs, nonces and audits. The marker is not a physical
  COMMIT timestamp. No H0 result covers a financial COMMIT, mid-COMMIT storage
  loss, HA or a public HTTP timeout.

The original PR22 foundation recovery error remains a separate reliability
blocker. Its source is inherited here; this Draft does not include the later
supervisor recovery candidate. Historical passing unit summaries do not clear
that error, production capacity, disaster recovery or product activation gates.

## Deployment, compatibility and rollback

Deploy only as a disabled internal experiment. For a separately reviewed
synthetic AuthDB exercise, use a new private format2 store and dedicated profile
and grants; keep the directory0700 and files0600. Never reuse a financial DB or
silently upgrade an existing authentication store. The integration has no
customer endpoint or operational enable switch in the trading service.

To roll back, stop new H0 captures, release observations with their issuing
thread and disable the experimental issuer. Retain the private AuthDB and audit
history for reconciliation. Roll back code only with the format boundary
respected: an old reader is not authorized to rewrite a new-format store.
There are no financial effects to compensate in this milestone. If any financial
or source row appears, stop and investigate rather than applying this runbook as
though the milestone's boundary held.

Remaining gates include additional race schedules, storage/unknown-result
injection, Python3.10 execution of the new P2/P3 probes, a reviewed actual
AuthBridge and source catalog, complete deployment/restore validation and
independent production approval. This is an auth-only Draft, not full H0/H1,
an exchange-ready UTA, or approval to use real funds.
