# Independent code review: exact-type reserve fallback

**PASS for this code-only change. Production and persistent-10k gates remain
false.** Reviewed fix `c6a7210412ce4e0888c5977743206b47c7933f75` against original
`057fa65d1d79ae1855e551e73b6f58eeb375197b`. No project function, test, SQL,
service, financial state, process fault or load was executed by this review.

The original candidate pre-read the margin-rate attribute of a custom
`ReserveInputs` subclass even for reduce-only input. The unchanged reference
does not need that attribute in that branch. The author's original single-case
negative result is retained at `811d583`: exit 1 in 55,919,351 ns, with the
expected `.1` reference value followed by the candidate's `RuntimeError`.
This review verified the three retained file hashes against its envelope;
it did not rerun the counterexample.

The fix changes the first gate from an `isinstance` check to
`type(inputs) is not ReserveInputs`, returning the unchanged reference
immediately. Consequently, custom subclasses and duck objects are delegated
before reading `usd_scale` or any numeric attribute. Exact plain
`ReserveInputs` continue through the same scale/Decimal checks and arithmetic.
The new regression's accessor raises if the unused margin rate is touched;
its reduce-only input must instead return `.1` with the reference Decimal tuple.

Independent AST comparison established that the type guard is the **only
production AST change**, every statement after it is identical, all other
functions/imports are identical, the Fraction reference is byte-identical, and
the only test AST change adds that one regression. The sole tracked `uta/`
text reference to the experimental entry point remains its definition.
[Machine-readable checks and source hashes](../evidence/reviews/reserve-exact-type-code/static-review.json)
are retained.

The author's single-regression run reports exit 0 in 81,747,535 ns and
`Ran 1 test in 0.000s`. Its original stdout/stderr and envelope were read from
the separate retained directory, hash-verified and copied as evidence. It is
an author execution reviewed independently, **not a new independent execution**
or a full-suite result.

The prior independent mathematical review `3b9da54` binds **original core
`02c2193` / source `057fa65`**: 3,352 value/tuple/string checks, 96 manual
components and 90 fallback checks, including the separately retained first
wire-oracle RED and its correction. Those results are not relabelled as a
full differential run of this fixed source. This code review supports the
narrow delegation repair; it does not grant production approval, capacity,
durability, matching, account admission or service-integration acceptance.

There is no schema/data migration or operational activation. Review and retain
the fix and its source-specific evidence through normal integration. Reverting
the fix reintroduces the recorded subclass compatibility defect; do not enable
a production caller as a rollback shortcut. Revert this review commit only to
withdraw its report, preserving the original negative result, one-regression
pass and prior mathematical evidence.
