"""Installed-wheel actual synthetic internal V2 smoke; no production approval.

Run once with a fresh retained private directory, under the installed venv's
``python -I`` from an external directory. Only the tests package is loaded from
the unpacked sdist. All uta imports must remain inside this venv's site-packages.
The original private database is retained and is never copied into the report.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from decimal import Decimal as D
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import sys
import sysconfig
import time
from types import ModuleType


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


@contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def assert_no_git(path):
    for directory in (path, *path.parents):
        assert not (directory / ".git").exists(), "smoke directory is in a Git checkout"


def installed_paths():
    # Never modify sys.path to import uta, and never accept a source checkout.
    import uta
    prefix = Path(sys.prefix).resolve()
    sites = {Path(sysconfig.get_path(name)).resolve() for name in ("purelib", "platlib")}
    assert all(site.is_relative_to(prefix) for site in sites)
    assert Path(uta.__file__).resolve().is_relative_to(prefix)
    assert all(any(Path(path).resolve().is_relative_to(site) for site in sites)
               for path in (uta.__file__, *uta.__path__))
    result = {}
    for name, module in sorted(sys.modules.items()):
        if name == "uta" or name.startswith("uta."):
            filename = getattr(module, "__file__", None)
            assert filename is not None, "uta module has no physical installed source"
            path = Path(filename).resolve()
            assert any(path.is_relative_to(site) for site in sites), "uta import escaped installed site-packages"
            assert path.is_relative_to(prefix), "uta import escaped installed prefix"
            if hasattr(module, "__path__"):
                assert all(any(Path(p).resolve().is_relative_to(site) for site in sites)
                           for p in module.__path__)
            result[name] = str(path)
    return result


def financial_snapshot(connection):
    # Fixed public synthetic financial tables only. No lease, auth or registry
    # state is read or included in the report or its digest.
    tables = ("credit_v2_sources", "credit_v2_intents", "credit_v2_expected_postings",
              "uta_credit_decisions", "credit_commands", "uta_command_inbox",
              "uta_accounts", "uta_liabilities", "ledger_events", "ledger_postings",
              "ledger_balances", "uta_events")
    return {table: [tuple(row) for row in connection.execute("SELECT * FROM " + table + " ORDER BY rowid")]
            for table in tables}


def selected_state(connection):
    names = ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions", "ledger_events")
    return {
        "counts": {name: connection.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                   for name in names},
        "debt": list(connection.execute(
            "SELECT principal,interest FROM uta_liabilities WHERE account_id='alice' AND asset='BTC'").fetchone()),
        "ledger_btc_units": {account: connection.execute(
            "SELECT units FROM ledger_balances WHERE account=? AND asset='BTC'", (account,)).fetchone()[0]
            for account in ("customer:alice", "liability:principal:alice", "system:credit-pool",
                            "system:credit-principal-receivable")},
        "foreign_key_check": [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--unpacked", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    # A parent timeout is still required. This bounds the individual smoke even
    # when it is called directly and does not grant any runtime capability.
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("installed V2 smoke exceeded 60 seconds")))
    signal.alarm(60)
    assert sys.flags.isolated == 1, "invoke this script with python -I"
    external = Path.cwd().resolve()
    unpacked = args.unpacked.resolve(strict=True)
    assert_no_git(external)
    assert_no_git(unpacked)
    assert external != unpacked, "start the smoke from its external directory"
    initial_uta_paths = installed_paths()  # uta is imported before tests paths.
    private = args.private_root.absolute()
    assert not private.exists(), "private root must be fresh; do not reuse a failed attempt"
    private.mkdir(mode=0o700)
    info = private.lstat()
    assert stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
    assert stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid == os.getuid()
    assert "tests" not in sys.modules, "tests namespace must start fresh"
    tests_path = unpacked / "tests"
    # tests is a namespace in this source distribution (there is no __init__).
    # Pin exactly that namespace without placing the sdist root on sys.path.
    specification = importlib.util.spec_from_loader("tests", loader=None, is_package=True)
    assert specification is not None
    specification.submodule_search_locations = [str(tests_path)]
    tests = ModuleType("tests")
    tests.__package__ = "tests"
    tests.__path__ = [str(tests_path)]
    tests.__spec__ = specification
    sys.modules["tests"] = tests
    from tests.credit_v2_runtime_fixture import SyntheticCreditAuthority, actual_credit_observation
    from uta.credit_audit_v2 import CreditAuditV2
    from uta.credit_audit_v2_replay import replay_bundle
    from uta.existing_services import open_existing_services
    from uta.service import ServiceError
    from uta.storage import Database

    fixture_sources = {}
    for name in ("tests.credit_v2_runtime_fixture", "tests.credit_policy_cases"):
        path = Path(sys.modules[name].__file__).resolve()
        assert path.is_relative_to(tests_path)
        fixture_sources[name] = {"path": str(path), "sha256": sha256(path.read_bytes()).hexdigest()}
    data_path = tests_path / "fixtures/managed_credit_v1_canonical_example.json"
    fixture_sources["canonical_documents"] = {"path": str(data_path), "sha256": sha256(data_path.read_bytes()).hexdigest()}
    print(canonical({"phase": "BEGIN", "python": sys.executable, "installed_prefix": sys.prefix,
        "external_cwd": str(external), "sdist_root": str(unpacked), "no_git": True,
        "isolated": sys.flags.isolated, "initial_uta_paths": initial_uta_paths,
        "fixture_sources": fixture_sources, "driver_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}), flush=True)
    os.environ["UTA_CREDIT_V2_PRIVATE_DB_DIRECTORY"] = str(private)
    # This public fixture reads one supplied JSON path relative to tests/. Only
    # its construction needs this cwd; no source root is added to sys.path.
    with working_directory(unpacked):
        fixture = SyntheticCreditAuthority()
    try:
        fixture.install_and_open()
        assert Path.cwd() == external
        exchange, credit, fifo = fixture.services.exchange, fixture.services.credit, fixture.fifo
        assert fixture.installed["stage"] == "SYNTHETIC_INTERNAL"
        assert fixture.installed["writer_acquired"] is False
        assert fixture.bootstrap.database.writer_token is None
        declaration = json.loads(fixture.envelope)
        flag_names = ("format", "stage", "synthetic", "audit_format", "source_format", "fifo_format",
                      "native_format", "artifact_id", "settlement_asset", "borrow_asset", "batch_size",
                      "reserve_cache_size", "market_cache_size", "production_approved")
        flags = {key: declaration[key] for key in flag_names}
        assert flags["synthetic"] is True and flags["production_approved"] is False
        assert (flags["batch_size"], flags["reserve_cache_size"], flags["market_cache_size"]) == (0, 0, 0)
        assert not exchange.readiness()["ready"]
        borrow_id, repay_id = "package-installed-loan-1", "package-installed-partial-repay-1"
        actor = "synthetic:package-installed-borrower"
        borrow_source, repay_source = "synthetic:package-installed:loan-1", "synthetic:package-installed:partial-repay-1"
        accepted = fifo.enqueue_borrow("alice", borrow_id, "BTC", D(".4"),
            actor_id=actor, source_reference=borrow_source)
        assert (accepted["state"], accepted["ack"]) == ("PENDING", "durably_queued")
        borrowed = fifo.process_one()
        assert (borrowed["command_id"], borrowed["state"], borrowed["result"]["principal"],
                borrowed["result"]["interest"]) == (borrow_id, "SUCCEEDED", "0.4", "0")
        with exchange.database.read_transaction() as connection:
            borrow_observation = actual_credit_observation(connection, borrow_id)
            assert len(borrow_observation["expected_postings"]) == 4
            assert len(borrow_observation["journal"]["postings"]) == 4
            assert borrow_observation["journal"]["sealed"] == 1
            borrow_counts = selected_state(connection)["counts"]
        bundle = borrow_observation["decision_bundle"]
        assert replay_bundle(bundle)["matches"] is True
        assert CreditAuditV2(exchange, credit).replay(bundle["decision"]["decision_id"])["matches"] is True
        assert fifo.enqueue_repay("alice", repay_id, "BTC", D(".1"),
            actor_id=actor, source_reference=repay_source)["state"] == "PENDING"
        repaid = fifo.process_one()
        assert (repaid["command_id"], repaid["state"], repaid["result"]["principal"],
                repaid["result"]["interest"]) == (repay_id, "SUCCEEDED", "0.3", "0")
        with exchange.database.read_transaction() as connection:
            repayment_observation = actual_credit_observation(connection, repay_id)
            assert (repayment_observation["intent"]["market_dependency"],
                    repayment_observation["intent"]["market_snapshot_id"],
                    repayment_observation["decision_bundle"]) == ("NONE", None, None)
            assert len(repayment_observation["journal"]["postings"]) == 4
            assert actual_credit_observation(connection, borrow_id) == borrow_observation
            actual = selected_state(connection)
            before_replay = financial_snapshot(connection)
        assert actual == {"counts": {"credit_v2_sources": 2, "credit_v2_intents": 2,
            "uta_credit_decisions": 1, "ledger_events": 4}, "debt": ["0.3", "0"],
            "ledger_btc_units": {"customer:alice": "30000000", "liability:principal:alice": "-30000000",
                "system:credit-pool": "70000000", "system:credit-principal-receivable": "30000000"},
            "foreign_key_check": []}
        assert fifo.status(borrow_id) == borrowed
        assert fifo.enqueue_borrow("alice", borrow_id, "BTC", D(".4"),
            actor_id=actor, source_reference=borrow_source) == borrowed
        assert fifo.enqueue_repay("alice", repay_id, "BTC", D(".1"),
            actor_id=actor, source_reference=repay_source) == repaid
        assert credit.borrow("alice", borrow_id, "BTC", D(".4")) == borrowed["result"]
        assert fifo.process_one() is None
        assert CreditAuditV2(exchange, credit).replay(bundle["decision"]["decision_id"])["matches"] is True
        # A separate unbound Database construction actually opens mode=ro and
        # query_only, then runs real complete existing-state constructors and
        # the independent ledger replay in the same read snapshot.
        readonly_db = Database(fixture.path)
        assert readonly_db.writer_token is None
        with readonly_db.read_transaction() as connection:
            assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
            reopened = open_existing_services(readonly_db, clock=lambda: fixture.now, connection=connection)
            assert reopened.exchange is not exchange and reopened.credit is not credit
            assert reopened.ledger.verify(connection=connection) == actual["counts"]["ledger_events"]
            assert reopened.credit._verify(connection) == 1
            assert selected_state(connection) == actual
            assert financial_snapshot(connection) == before_replay
            assert actual_credit_observation(connection, borrow_id) == borrow_observation
        readiness = reopened.exchange.readiness()
        assert readiness["ready"] is False
        assert readiness["reason"] == "internal_credit_authority_not_trading"
        try:
            credit.borrow("alice", "package-installed-public-new-refused", "BTC", D(".01"))
        except ServiceError as refused:
            assert (refused.code, refused.status) == ("unsupported_credit_operation", 501)
            public_refusal = {"code": refused.code, "status": refused.status}
        else:
            raise AssertionError("new public borrowing unexpectedly succeeded")
        with readonly_db.read_transaction() as connection:
            assert selected_state(connection) == actual
            assert financial_snapshot(connection) == before_replay
            assert actual_credit_observation(connection, borrow_id) == borrow_observation
        loaded = installed_paths()
        assert all(not Path(path).is_relative_to(unpacked) for path in loaded.values())
        result = {"phase": "END", "status": "PASS", "passed": True, "production_approved": False, "seconds": time.monotonic() - started,
            "runtime": {"python": sys.version, "executable": sys.executable,
                "installed_prefix": sys.prefix, "uta_paths": loaded},
            "fixture_sources": fixture_sources, "flags": flags,
            "command_ids": [borrow_id, repay_id], "borrow_counts": borrow_counts, "actual": actual,
            "borrow_ledger_legs": borrow_observation["journal"]["postings"],
            "repay_ledger_legs": repayment_observation["journal"]["postings"],
            "receipt_sha256": {borrow_id: digest(borrowed), repay_id: digest(repaid)},
            "original_cid_replay": "identical original receipt; no financial row changes",
            "readonly_reopen": {"separate_unbound_database": True, "query_only": True,
                "existing_source_full_validation": True, "ledger_verify_events": 4, "nonzero_liabilities": 1},
            "public_new_borrow": public_refusal, "readiness": readiness,
            "financial_snapshot_sha256": digest(before_replay),
            "clock_scope": "static public synthetic financial fixture clock; no live TTL freshness claim",
            "scope": "fresh installed-wheel internal synthetic V2 actual state/native SQL; no production, HA or performance claim",
            "private_database_retained": True}
        assert not args.output.exists(), "retain existing output"
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(canonical(result), flush=True)
    finally:
        fixture.close()  # Retained-root fixtures deliberately preserve the DB.
    signal.alarm(0)


if __name__ == "__main__":
    main()
