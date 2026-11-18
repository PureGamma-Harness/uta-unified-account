"""Finite read-only checks for four declared synthetic admission authorities."""
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import re
import sqlite3


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def snapshot(connection):
    schema = [tuple(row) for row in connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
    tables = [row[1] for row in schema if row[0] == "table"]
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in tables):
        raise ValueError("unexpected identifier in fresh schema")
    rows = {name: [tuple(row) for row in connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
            for name in tables}
    return sha256(canonical({"schema": schema, "rows": rows}).encode()).hexdigest()


def money_equal(actual, expected):
    return all(Fraction(Decimal(actual[key])) == Fraction(Decimal(value)) for key, value in expected.items())


def verify_cases(owned, expected_db, oracle, read_regular, closed_handles, disk_snapshot):
    from uta.decision_audit import DecisionAudit, _json, code_artifact
    from uta.existing_services import _source_arguments
    from uta.market import MarketSnapshot
    from uta.service import ExchangeService
    from uta.storage import Database, StorageError
    from uta.writer_fence import WriterFenceError

    details, shared_artifact = {}, None
    totals = {"fresh_authorities": 0, "ledger_events": 0, "decision_rows": 0,
              "order_rows": 0, "fill_rows": 0, "policy_rows": 0,
              "source_arguments_expected_rejections": 0, "read_only_guard_negative_cases": 0,
              "decision_replays": 0, "accepted_order_replays": 0, "fill_admission_unsupported": 0}
    for label in oracle["fixture_order"]:
        expected, data = oracle["cases"][label], owned[label]
        database = Database(expected_db[label])
        before_bytes = sha256(read_regular(expected_db[label])).hexdigest()
        with database.read_transaction() as connection:
            if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
                raise ValueError("actual read-only reopen lacks query_only")
            before = snapshot(connection)
            if label == "coexist":
                try:
                    _source_arguments(connection)
                except StorageError as error:
                    if str(error.__cause__) != "existing base policy is missing or ambiguous":
                        raise
                else:
                    raise ValueError("coexisting policy reconstruction unexpectedly succeeded")
                totals["source_arguments_expected_rejections"] += 1
                # Known original constructor arguments, not automatic source
                # reconstruction or a policy deletion/selection fallback.
                scales = {"USD": 2}
                arguments = {"decision_audit": True, "fee_rate": Decimal(".0004")}
            else:
                scales, arguments = _source_arguments(connection)
            if scales != expected["scales"]:
                raise ValueError("manual asset precision differs")
            service = ExchangeService(database, scales, clock=lambda: data["times"][0],
                                      _existing_connection=connection, **arguments)
            ledger_events = service.ledger.verify(connection=connection)
            if ledger_events != expected["ledger_events"]:
                raise ValueError("manual journal count differs")
            balances = {(row["account"], row["asset"]): Fraction(int(row["units"]), 10**scales[row["asset"]])
                        for row in connection.execute("SELECT * FROM ledger_balances") if int(row["units"])}
            if balances != {(name, "USD"): Fraction(Decimal(value)) for name, value in expected["balances"].items()}:
                raise ValueError("full nonzero cash account inventory differs")
            event_ids = [row[0] for row in connection.execute("SELECT event_id FROM ledger_events ORDER BY sequence")]
            deposit_id = "deposit:" + sha256(canonical(["alice", "fund"]).encode()).hexdigest()
            fill_id = "fill:" + sha256(canonical(["alice", "fill"]).encode()).hexdigest()
            if event_ids != [deposit_id] + ([fill_id] if label == "configured" else []):
                raise ValueError("original deposit/fill business references differ")
            units = Fraction(Decimal(expected["deposit_USD"])) * 10**scales["USD"]
            if units.denominator != 1:
                raise ValueError("manual deposit is not a native currency amount")
            postings = [[tuple(row) for row in connection.execute(
                "SELECT account,asset,units FROM ledger_postings WHERE sequence=? ORDER BY ordinal", (sequence,))]
                        for sequence in range(1, ledger_events + 1)]
            wanted = [[("customer:alice", "USD", str(int(units))), ("system:custody", "USD", str(-int(units)))]]
            if label == "configured":
                wanted.append([("customer:alice", "USD", "-2"), ("system:fees", "USD", "2")])
            if postings != wanted:
                raise ValueError("manual per-currency event postings differ")
            account_rows = [tuple(row) for row in connection.execute("SELECT account_id,version FROM uta_accounts")]
            if account_rows != [("alice", expected["account_version"])]:
                raise ValueError("full account/version inventory differs")
            positions = {row["symbol"]: [Fraction(Decimal(row["quantity"])), Fraction(Decimal(row["cost_basis"]))]
                         for row in connection.execute("SELECT * FROM uta_positions") if row["account_id"] == "alice"}
            all_positions = connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0]
            if all_positions != len(positions) or positions != {s: [Fraction(Decimal(x)) for x in values]
                                                             for s, values in expected["positions"].items()}:
                raise ValueError("full position/cost inventory differs")
            if any(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                   for table in ("uta_liabilities", "uta_liquidation_accounts")):
                raise ValueError("unexpected debt or liquidation state")
            orders = {row["order_id"]: dict(row) for row in connection.execute("SELECT * FROM uta_orders")}
            if set(orders) != set(expected["orders"]):
                raise ValueError("full order inventory differs")
            for identity, exp in expected["orders"].items():
                actual = orders[identity]
                if actual["account_id"] != "alice" or actual["symbol"] != oracle["symbol"]:
                    raise ValueError("order ownership/product differs")
                for key, value in exp.items():
                    if key in ("reduce_only", "version", "status"):
                        if type(actual[key]) is not type(value) or actual[key] != value:
                            raise ValueError("manual order state differs: " + key)
                    elif Fraction(Decimal(actual[key])) != Fraction(Decimal(value)):
                        raise ValueError("manual order economics differs: " + key)
            fills = [dict(row) for row in connection.execute("SELECT * FROM uta_fills")]
            if len(fills) != expected["fills_count"]:
                raise ValueError("manual local fill count differs")
            if fills and (fills[0]["account_id"], fills[0]["fill_id"], fills[0]["order_id"],
                          Decimal(fills[0]["quantity"]), Decimal(fills[0]["price"]),
                          Decimal(fills[0]["realized_pnl"]), Decimal(fills[0]["fee"])) != (
                              "alice", "fill", "open", Decimal(".5"), Decimal(100), Decimal(0), Decimal(".02")):
                raise ValueError("manual single unpaired local execution differs")
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name='uta_matches'").fetchone() is not None:
                raise ValueError("Matcher schema unexpectedly initialized")
            if connection.execute("SELECT COUNT(*) FROM uta_events").fetchone()[0] != expected["uta_events"]:
                raise ValueError("manual business-event count differs")
            risk = service._risk(connection, "alice", service._market(connection, fresh=False))
            if not money_equal(risk, expected["risk"]) or service._halted(connection) is not expected["halted"]:
                raise ValueError("manual current risk/control differs")
            policies = list(connection.execute("SELECT policy_id,payload FROM uta_risk_policies"))
            if len(policies) != expected["policy_count"] or any(
                    row["policy_id"] != "policy:" + sha256(row["payload"].encode()).hexdigest() for row in policies):
                raise ValueError("archived policy inventory/digest differs")
            manifests = list(connection.execute("SELECT manifest FROM uta_code_artifacts"))
            if len(manifests) != 1 or manifests[0][0] != _json(code_artifact()):
                raise ValueError("strict stored current artifact differs")
            current_artifact = json.loads(manifests[0][0])
            if shared_artifact is not None and shared_artifact != current_artifact:
                raise ValueError("four authorities used different actual code/runtime artifacts")
            shared_artifact = current_artifact
            records = [dict(row) for row in connection.execute("SELECT * FROM uta_risk_decisions ORDER BY rowid")]
            if {row["kind"] + ":" + row["business_id"] for row in records} != set(expected["decisions"]):
                raise ValueError("manual decision inventory differs")
            replay_details, actual_decisions = [], []
            for row in records:
                key = row["kind"] + ":" + row["business_id"]
                exp = expected["decisions"][key]
                record = service.audit.decision(row["decision_id"])
                replay = service.audit.replay(row["decision_id"])
                actual_decisions.append({"decision": record, "replay": replay})
                if (row["pre_version"], row["post_version"]) != (exp["pre_version"], exp["post_version"]) or not replay["matches"] or not replay["valuation_matches"]:
                    raise ValueError("stored decision versions/numerical replay differ")
                if row["kind"] == "ORDER_ACCEPTED":
                    summary = record["summary"]
                    if (replay["admission"]["status"] != "VERIFIED" or not money_equal(summary["projected_execution"], exp["projected"])
                            or not money_equal(summary["admission"], {"projected_fee": exp["fee"], "projected_realized_pnl": exp["pnl"]})
                            or Decimal(summary["reserved_margin"]) != Decimal(exp["reserve"])
                            or orders[row["business_id"]]["admission_decision_id"] != row["decision_id"]):
                        raise ValueError("manual acceptance projection/fee/reserve/link differs")
                    market = MarketSnapshot.from_json(service.audit.market(row["market_snapshot_id"])["payload"])
                    policy = service.audit.policy_record(row["policy_id"])
                    # Tamper only a detached copy; no archived row or source is changed.
                    for bad in (1, "unknown"):
                        changed = deepcopy(record)
                        for side in ("before", "after"):
                            changed["inputs"][side]["halted"] = bad
                        negative = DecisionAudit._replay_admission(changed, market, policy, replay["values"], replay["operation"])
                        if negative["matches"] is not False or negative["checks"]["control_state_valid"] is not False:
                            raise ValueError("consistent corrupted control copy falsely verifies")
                    missing = deepcopy(record)
                    missing["summary"].pop("admission")
                    negative = DecisionAudit._replay_admission(missing, market, policy, replay["values"], replay["operation"])
                    if (negative["status"], negative["eligible"], negative["matches"]) != ("UNSUPPORTED", None, None):
                        raise ValueError("missing archived permission falsely reconstructed")
                    altered_fee = deepcopy(record)
                    altered_fee["summary"]["admission"]["projected_fee"] = "0"
                    negative = DecisionAudit._replay_admission(altered_fee, market, policy, replay["values"], replay["operation"])
                    if negative["matches"] is not False or "projected_fee" not in negative["differences"]:
                        raise ValueError("altered archived fee copy falsely verifies")
                    totals["accepted_order_replays"] += 1
                elif (replay["admission"]["status"], replay["admission"]["reason"]) != ("UNSUPPORTED", "decision_kind_not_supported"):
                    raise ValueError("local fill falsely claims admission replay")
                else:
                    if (fills[0]["execution_decision_id"] != row["decision_id"] or
                            not money_equal(record["summary"], {"fee": exp["fee"], "realized_pnl": exp["pnl"]}) or
                            record["inputs"]["operation"]["order_id"] != exp["order_id"]):
                        raise ValueError("actual fill/audit/fee/PnL business link differs")
                    totals["fill_admission_unsupported"] += 1
                totals["decision_replays"] += 1
                replay_details.append({"business_key": key, "numerical_matches": True,
                                       "admission_status": replay["admission"]["status"]})
            if snapshot(connection) != before:
                raise ValueError("read-only verification changed authoritative rows/schema")
            actual_postings = [dict(row) for row in connection.execute("SELECT * FROM ledger_postings ORDER BY sequence,ordinal")]
            actual_ledger_events = [dict(row) for row in connection.execute("SELECT * FROM ledger_events ORDER BY sequence")]
            actual_balance_rows = [dict(row) for row in connection.execute("SELECT * FROM ledger_balances ORDER BY account,asset")]
            actual_position_rows = [dict(row) for row in connection.execute("SELECT * FROM uta_positions ORDER BY account_id,symbol")]
        # A real guarded read connection must reject DML and poison its commit;
        # the failed statement cannot become a persisted control change.
        try:
            with database.read_transaction() as denied:
                try:
                    denied.execute("UPDATE uta_config SET value='false' WHERE key='halted'")
                except sqlite3.DatabaseError:
                    pass
                else:
                    raise ValueError("read role allowed a control write")
        except WriterFenceError as error:
            if error.code != "read_only_transaction":
                raise
        else:
            raise ValueError("caught denied read-role DML did not poison commit")
        with database.read_transaction() as connection:
            if snapshot(connection) != before:
                raise ValueError("denied write altered rows/schema")
        if sha256(read_regular(expected_db[label])).hexdigest() != before_bytes:
            raise ValueError("RO reopen changed main database bytes")
        totals["read_only_guard_negative_cases"] += 1
        totals["fresh_authorities"] += 1
        for key, value in (("ledger_events", ledger_events), ("decision_rows", len(records)),
                           ("order_rows", len(orders)), ("fill_rows", len(fills)), ("policy_rows", len(policies))):
            totals[key] += value
        details[label] = {"known_argument_RO_reopen": True, "source_arguments": expected["source_arguments"],
                          "ledger_events": ledger_events, "orders": len(orders), "local_fills": len(fills),
                          "policy_rows": len(policies), "decision_replays": replay_details,
                          "manual_cash_position_risk_equal": True, "rows_schema_and_main_DB_bytes_unchanged": True,
                          "read_only_DML_rejected_and_commit_poisoned": True,
                          "source_rows_schema_digest": before, "main_DB_sha256_before_after": before_bytes,
                          "actual_ledger_events": actual_ledger_events, "actual_postings": actual_postings,
                          "actual_balance_rows": actual_balance_rows, "actual_position_rows": actual_position_rows,
                          "actual_order_rows": list(orders.values()), "actual_fill_rows": fills,
                          "actual_decisions_and_replays": actual_decisions,
                          "not_full_open_existing_services_acceptance": True}
        if not closed_handles()["all_observed_handles_already_closed"]:
            raise ValueError("owned handle remained open after case reopen")
        disk_snapshot()
    if totals != {key: oracle["aggregate"][key] for key in totals}:
        raise ValueError("manual aggregate component count differs")
    return {"cases": details, "totals": totals, "oracle_passed": True, "shared_actual_code_artifact": shared_artifact,
            "independent_Cross_risk_model": False, "Matcher_calls": 0,
            "paired_fill_throughput_claim": False}
