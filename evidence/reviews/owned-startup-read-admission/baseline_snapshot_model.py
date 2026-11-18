"""Finite source-corresponding startup model; no database or native effects.

Only the original pure _observed/_assert_token ASTs are target functions.
Token/row/clock are synthetic. Lifecycle, financial watermark and READY policy
are an explicit abstract specification, not executed production startup code.
The first stale-snapshot cases intentionally expose conditional baseline RED.
"""
import ast
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


TTL_NS = 400_000_000
PID = 17  # Synthetic identity, never a real process observation.
CHECKS = 0


@dataclass(frozen=True)
class Token:
    authority_id: str = "synthetic-authority"
    owner_nonce: str = "synthetic-binding-tag"
    generation: int = 1
    process_id: int = PID


class FenceError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def targets():
    root = Path(__file__).resolve().parents[3]
    raw = (root / "uta/writer_fence.py").read_bytes()
    parsed = ast.parse(raw)
    selected = [node for node in parsed.body
                if isinstance(node, ast.FunctionDef)
                and node.name in ("_observed", "_assert_token")]
    assert {node.name for node in selected} == {"_observed", "_assert_token"}
    namespace = {"WriterToken": Token, "WriterFenceError": FenceError,
                 "os": SimpleNamespace(getpid=lambda: PID),
                 "_clock": lambda database: (database.now_ns, database.boot)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
                 "<source-observed-and-assert-token-only>", "exec"), namespace)
    return namespace["_assert_token"], sha256(raw).hexdigest()


def lease(token=Token(), *, expires=TTL_NS, observed=0):
    return {"authority_id": token.authority_id, "owner_nonce": token.owner_nonce,
            "generation": token.generation, "owner_pid": token.process_id,
            "boot_id": "synthetic-boot", "expires_ns": expires,
            "observed_ns": observed}


def live(assert_token, row, now, token=Token(), *, boot="synthetic-boot"):
    try:
        assert_token(SimpleNamespace(now_ns=now, boot=boot), row, token)
    except FenceError as error:
        return False, error.code
    return True, None


def ordinary_renew(assert_token, row, now, *, known_reply=True):
    """One abstract current-row renewal, no retry and unchanged TTL.

    The actual pure predicate controls permission. The returned row models a
    committed update; an unknown reply remains poisoned even when it committed.
    This is not a SQL transaction/COMMIT implementation.
    """
    permitted, error = live(assert_token, row, now)
    if not permitted:
        return dict(row), False, error
    updated = {**row, "expires_ns": now + TTL_NS, "observed_ns": now}
    return updated, known_reply, None if known_reply else "renewal_reply_unknown"


def binding(row):
    return tuple(row[key] for key in ("authority_id", "owner_nonce", "generation",
                                      "owner_pid", "boot_id"))


def certificate_policy(assert_token, snapshot, current, now, *, known=True,
                       snapshot_watermark=11, current_watermark=11):
    """Prospective specification, not an implemented runtime certificate.

    A financial watermark must cover every mutable financial projection, or
    equivalent actor exclusion must be separately proven. No such persisted
    aggregate watermark is assumed to exist in the current implementation.
    """
    current_live, _ = live(assert_token, current, now)
    return (known and current_live and binding(snapshot) == binding(current)
            and snapshot_watermark == current_watermark)


def ready_policy(assert_token, current, now, *, entry=True, scope=True,
                 parent=True, deadline=True, known=True, full_ledger=True,
                 full_credit=True, same_schema=True, same_watermark=True):
    """Abstract final fresh fenced COMMIT linearization point, not wire time."""
    current_live, _ = live(assert_token, current, now)
    return (entry and scope and parent and deadline and known and full_ledger
            and full_credit and same_schema and same_watermark and current_live)


class BaselineSnapshotModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        function, digest = targets()
        cls.assert_token = staticmethod(function)
        cls.source_sha256 = digest

    def mark(self):
        global CHECKS
        CHECKS += 1

    def test_committed_same_token_renewal_can_leave_old_snapshot_expired(self):
        # Each hand-calculated trace renews before the original400ms expiry.
        # Old snapshot expiry remains400ms while current expiry advances.
        for snapshot_at, renewed_at, asserted_at in (
                (0, 200_000_000, 400_000_000),
                (100_000_000, 300_000_000, 450_000_000),
                (300_000_000, 350_000_000, 700_000_000)):
            with self.subTest(snapshot=snapshot_at, renew=renewed_at, assertion=asserted_at):
                self.mark()
                snapshot = lease()
                self.assertLess(snapshot_at, snapshot["expires_ns"])
                current, known, error = ordinary_renew(self.assert_token, lease(), renewed_at)
                self.assertTrue(known)
                self.assertIsNone(error)
                self.assertTrue(certificate_policy(self.assert_token, snapshot, current,
                                                   asserted_at, known=known))
                baseline_admitted, code = live(self.assert_token, snapshot, asserted_at)
                # Expected baseline RED: a real current-row live owner can be
                # rejected by expiry from its older read snapshot. This does
                # not identify either real CI error's causal history.
                self.assertTrue(baseline_admitted,
                                "conditional baseline false rejection: " + str(code))

    def test_genuinely_expired_token_never_renews_or_revives(self):
        for now in (TTL_NS, TTL_NS + 1):
            self.mark()
            original = lease()
            after, known, code = ordinary_renew(self.assert_token, original, now)
            self.assertFalse(known)
            self.assertEqual(code, "lease_expired")
            self.assertEqual(after, original)
            self.assertFalse(ready_policy(self.assert_token, after, now))

    def test_current_identity_changes_cannot_be_mixed_into_old_certificate(self):
        variants = [lease(replace(Token(), authority_id="other-authority")),
                    lease(replace(Token(), owner_nonce="other-synthetic-tag")),
                    lease(replace(Token(), generation=2)),
                    lease(replace(Token(), process_id=PID + 1)),
                    {**lease(), "boot_id": "other-boot"}]
        for current in variants:
            self.mark()
            self.assertFalse(certificate_policy(self.assert_token, lease(), current, 100))
            self.assertFalse(ready_policy(self.assert_token, current, 100))

    def test_snapshot_identity_changes_are_not_authorized_by_live_current_owner(self):
        variants = [lease(replace(Token(), authority_id="other-authority")),
                    lease(replace(Token(), owner_nonce="other-synthetic-tag")),
                    lease(replace(Token(), generation=2)),
                    lease(replace(Token(), process_id=PID + 1)),
                    {**lease(), "boot_id": "other-boot"}]
        for snapshot in variants:
            self.mark()
            self.assertFalse(certificate_policy(self.assert_token, snapshot, lease(), 100))

    def test_keeper_unknown_failure_or_revocation_never_reaches_ready(self):
        self.mark()
        committed, known, code = ordinary_renew(self.assert_token, lease(), 100,
                                               known_reply=False)
        self.assertFalse(known)
        self.assertEqual(code, "renewal_reply_unknown")
        self.assertFalse(ready_policy(self.assert_token, committed, 101, known=known))
        for attribute in ("known", "scope", "parent", "deadline"):
            self.mark()
            self.assertFalse(ready_policy(self.assert_token, lease(), 100,
                                         **{attribute: False}))

    def test_financial_watermark_policy_has_an_explicit_stability_obligation(self):
        for current_head, expected in ((11, True), (12, False)):
            self.mark()
            self.assertIs(certificate_policy(self.assert_token, lease(), lease(), 100,
                                             current_watermark=current_head), expected)
            self.assertIs(ready_policy(self.assert_token, lease(), 100,
                                      same_watermark=current_head == 11), expected)

    def test_final_freshness_and_full_verification_are_not_cached(self):
        for now, expected in ((TTL_NS - 1, True), (TTL_NS, False), (TTL_NS + 1, False)):
            self.mark()
            self.assertIs(ready_policy(self.assert_token, lease(), now), expected)
        for attribute in ("full_ledger", "full_credit", "same_schema"):
            self.mark()
            self.assertFalse(ready_policy(self.assert_token, lease(), 100,
                                         **{attribute: False}))

    def test_clock_regression_and_expiry_equality_still_refuse(self):
        for row, now, expected_code in ((lease(observed=10), 9, "fence_clock_regressed"),
                                         (lease(), TTL_NS, "lease_expired")):
            self.mark()
            accepted, code = live(self.assert_token, row, now)
            self.assertFalse(accepted)
            self.assertEqual(code, expected_code)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(BaselineSnapshotModelTests))
    print(json.dumps({"scope": "CONDITIONAL_SOURCE_CORRESPONDING_MODEL_ONLY",
                      "target_source_sha256": BaselineSnapshotModelTests.source_sha256,
                      "methods": result.testsRun, "small_traces": CHECKS,
                      "failures": len(result.failures), "errors": len(result.errors),
                      "passed": result.wasSuccessful(),
                      "actual_CI_error_cause_proven": False,
                      "SQL_native_thread_process_signal_network_or_sleep": False,
                      "runtime_fix_implemented": False, "production_approved": False},
                     sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
