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
