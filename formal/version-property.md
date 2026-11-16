# Reservation commit-version action property

## Scope

This is a finite specification check, not a change to the UTA runtime or a proof of implementation/model equivalence. The model has three one-shot order IDs, capacity two, one atomic state writer and no external side effects.

The state invariants `TypeOK`, `NoOvercommit` and `HeldMatchesReservation` do not imply that a commit uses a current version. Removing only the version guard can preserve those invariants.

`CommitUsesCurrentVersion` checks each transition from pending to held against the **pre-state** `seen[o] = version`. It observes the transition rather than invoking `Commit(o)` as its antecedent, so deleting the guard does not make the property vacuously true. Stuttering is allowed. This does not prove that pending orders eventually commit or reject.

## Reproduction

Use the official [TLA+ v1.7.4 release](https://github.com/tlaplus/tlaplus/releases/tag/v1.7.4), `tla2tools.jar` SHA-256 `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`. Observed TLC version: 2.19, revision 5a47802, Java 21.0.13, Linux x86_64.

From repository root:

```sh
java -XX:+UseParallelGC -cp /path/to/tla2tools.jar tlc2.TLC \
  -deadlock -workers 1 -config formal/Reservation.cfg formal/Reservation.tla
```

`-deadlock` disables deadlock checking because this finite lifecycle has intentional terminal states. It does not disable the configured invariants or action property, nor prove production deadlock freedom.

Safe model result: exit 0; 4,198 generated states, 2,628 distinct states, zero remaining states, depth 10. All three invariants and the new action property pass.

### Negative control

In a temporary directory, copy both specification/configuration files. Replace only the first occurrence of `/\\ seen[o] = version` in the copied Commit definition with `/\\ TRUE`; leave `VersionChecked` and all other expressions unchanged. Run the same command on the copies.

Observed result: exit 13, `Action property CommitUsesCurrentVersion is violated`; 137 generated / 105 distinct states, 73 remaining, depth 5. This is an expected failing negative control, not a complete state-space exploration.

The counterexample starts both orders at version 0, commits the first (version becomes 1), then commits the second using its stale observed version 0. Reservations total two, so capacity remains satisfied while the new protocol property detects the stale commit.

Do not modify the actual runtime or remove its guards to reproduce this test. Hosted Python CI does not execute TLC; record TLC results separately. Future changes must rerun the positive and negative checks. No liveness, replication, financial calibration, arbitrary-scale or real-money readiness claim follows from this result.

## Implementation bridge and explicit boundary

`tests/test_reservation_model_bridge.py` replays a path to every reachable state of the independent Python model, then checks every outgoing transition against the actual `uta.reservations.ReservationBook`: 2,628 states, 3,873 transitions, no snapshot or rejection mismatch. Rejections must have the expected error type and leave the book unchanged. A test-only mock deleting the version guard must be detected as an erroneously accepted rejection. Both tests pass locally and are included in normal unittest discovery.

Separate TLC state/graph exports matched the Python model after projecting away `seen_free`: exactly 2,628 states and 3,873 non-stuttering edges, with empty differences both ways. This comparison concerns this finite configuration, not arbitrary trace refinement.

**The implementation target here is the in-memory reference book, not ExchangeService.** `ReservationBook.reserve` checks caller `expected_version` for a new ID under a process lock. Existing-ID equivalent retries may return their prior result despite a stale version; dynamic capacity updates and these retries are outside this one-shot fixed-capacity model. State is lost on restart.

The durable `ExchangeService.submit_order` does not expose a caller expected-version argument. It computes current risk/reserve within a SQLite `BEGIN IMMEDIATE` write transaction; grouped admission shares that transaction. Its evidence comes from the independent cash/reserve oracle and concurrent writer tests in `tests/test_admission_invariants.py`, not from treating this versioned-book model as a proof of durable admission. No bridge result here establishes persistence, crash recovery, multi-process fencing, product correctness or production approval.

## Reproducible durable-admission oracle matrix

From the source checkout run `python tools/check_admission_oracle.py`. This harness reuses the independent rational reference in `tests/test_admission_invariants.py` with six fixed seeds and batch sizes 1, 2, 8 and 32. Each of the 24 cases creates temporary synthetic accounts and storage, checks 160 order/cancel/retry commands, then reopens storage and compares balances, reserve, available margin, event counts and ledger verification. Local result: all 3,840 positive-case commands matched the oracle.

A separate test-only mock increases the implementation reserve calculation by 10 percent. The harness requires the specific unexpected margin rejection at an expected-success receipt, not merely any nonzero exit. The mock is removed automatically and never edits runtime source. The JSON report labels this expected failing negative control separately; overall exit 0 requires every positive case and detection of that negative control.

The matrix is a source-checkout verification command, not automatically run by current hosted CI. It is neither a new independent oracle nor a full portfolio proof: it expands the existing fixed-price, linear-product cash/reserve fixture. It does not cover fills, external execution, price/rule calibration, replication, hardware failures or throughput acceptance. A test pass must not authorize real orders.

## Durable fill concurrency: separate evidence

At commit `f2d56b2f9f4983168176c1a97360e8c6c8fcc9fc`, [test_fill_races.py](../tests/test_fill_races.py) adds two tests to normal unittest discovery:

- Eight independent service instances concurrently replay one equivalent fill ID. The database must contain one fill and exactly the expected filled quantity. After reopening, an equivalent replay and a conflicting retry must leave the complete logical SQLite dump unchanged.
- Two different fill IDs each request 0.6 against an order of quantity 1. Exactly one must succeed and one must return `invalid_fill`; either winner is valid. After reopening, a 0.4 remainder completes the order exactly. Ledger verification is also required.

Reproduce from repository root:

```sh
python -m unittest discover -s tests -p test_fill_races.py -v
```

The two tests were repeated 20 times (40 successful test executions). The full local suite with these additions passed 520 tests in 28.902 seconds; the exact commit above also passed the eight hosted Python 3.10–3.13 push/PR checks. These are recorded observations, not evidence for later revisions.

A separate in-process negative control removed only the remaining-quantity clause from a temporary copy of `ExchangeService._apply_fill`, patched the method for the overfill test, and restored it immediately afterward. The original and restored implementation passed. The altered method allowed both fills; the test failed at its expected-success/error multiset assertion (two `ok` results, no `invalid_fill`). This checks sensitivity to that specific missing guard, not arbitrary implementation faults. The negative control is not part of hosted CI. Never remove the guard in runtime source or run mutation experiments against real storage.

These tests use temporary synthetic accounts and independent connections to one local SQLite database. They do not demonstrate venue-side idempotency, cross-host locking, replication, crash-safe external effects, or production approval. They are not covered by the finite reservation-version model above.
