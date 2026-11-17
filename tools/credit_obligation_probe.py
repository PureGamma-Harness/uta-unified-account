"""Candidate SQL obligations only; no online credit runtime or credit UDF.

Real core financial parents, native writer fencing and COMMIT are reused.
Future BORROW inbox rows and candidate metadata are manually seeded, expressly
without claiming SDK, HMAC, FIFO or production credit-context integration.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
import io
import gzip
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uta.credit import CreditService
from uta.decision_audit import DecisionAudit
from uta.durable_batches import BatchStore
from uta.durable_commands import QueueStore
from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, _json, _key
from uta.storage import Database
from uta.writer_fence import WriterFence

CID, ACCOUNT, AUTHORITY = "probe:loan:1", "alice", "probe:credit:authority"
AMOUNT, UNITS = "0.4", "40000000"
JOURNAL = _key("credit", "account:alice", CID)
DECISION = "decision:component-credit:1"
PAYLOAD = _json({"account_id": ACCOUNT, "asset": "BTC", "amount": AMOUNT})
PAYLOAD_HASH = sha256(PAYLOAD.encode()).hexdigest()
LEGS = sorted([("system:credit-pool", "BTC", "-40000000"),
               ("customer:alice", "BTC", "40000000"),
               ("liability:principal:alice", "BTC", "-40000000"),
               ("system:credit-principal-receivable", "BTC", "40000000")])


SCHEMA = (
    "CREATE UNIQUE INDEX probe_inbox_parent ON uta_command_inbox(command_id,account_id,kind,state)",
    "CREATE UNIQUE INDEX probe_credit_parent ON credit_commands(scope,command_id,kind,asset,amount,journal_event_id)",
    "CREATE UNIQUE INDEX probe_decision_parent ON uta_risk_decisions(decision_id,kind,account_id,business_id)",
    "CREATE UNIQUE INDEX probe_journal_parent ON ledger_events(event_id,sealed)",
    "CREATE TABLE probe_policy(id TEXT PRIMARY KEY NOT NULL)",
    "CREATE TABLE probe_allocation(id TEXT NOT NULL,authority TEXT NOT NULL,asset TEXT NOT NULL,PRIMARY KEY(id,authority,asset))",
    "CREATE TABLE probe_source(id TEXT NOT NULL,cid TEXT NOT NULL,account TEXT NOT NULL,payload_hash TEXT NOT NULL,PRIMARY KEY(id,cid,account,payload_hash))",
    """CREATE TABLE probe_intents(
      cid TEXT PRIMARY KEY NOT NULL,account TEXT NOT NULL,scope TEXT NOT NULL,
      inbox_kind TEXT NOT NULL CHECK(inbox_kind='BORROW'),
      terminal_state TEXT NOT NULL CHECK(terminal_state='SUCCEEDED'),
      credit_kind TEXT NOT NULL CHECK(credit_kind='borrowed'),
      asset TEXT NOT NULL CHECK(typeof(asset)='text'),amount TEXT NOT NULL CHECK(typeof(amount)='text'),
      units TEXT NOT NULL CHECK(typeof(units)='text' AND length(units) BETWEEN 1 AND 38
        AND units NOT GLOB '*[^0-9]*' AND substr(units,1,1) BETWEEN '1' AND '9'),
      payload_hash TEXT NOT NULL CHECK(typeof(payload_hash)='text' AND length(payload_hash)=64
        AND payload_hash NOT GLOB '*[^0-9a-f]*'),
      journal TEXT NOT NULL,sealed INTEGER NOT NULL CHECK(typeof(sealed)='integer' AND sealed=1),
      decision TEXT NOT NULL,decision_kind TEXT NOT NULL CHECK(decision_kind='CREDIT_BORROWED'),
      allocation TEXT NOT NULL,authority TEXT NOT NULL,policy TEXT NOT NULL,source TEXT NOT NULL,
      CHECK(scope='account:'||account),
      FOREIGN KEY(cid,account,inbox_kind,terminal_state)
        REFERENCES uta_command_inbox(command_id,account_id,kind,state) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(scope,cid,credit_kind,asset,amount,journal)
        REFERENCES credit_commands(scope,command_id,kind,asset,amount,journal_event_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(decision,decision_kind,account,cid)
        REFERENCES uta_risk_decisions(decision_id,kind,account_id,business_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(journal,sealed) REFERENCES ledger_events(event_id,sealed) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(allocation,authority,asset) REFERENCES probe_allocation(id,authority,asset) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(policy) REFERENCES probe_policy(id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(source,cid,account,payload_hash) REFERENCES probe_source(id,cid,account,payload_hash) DEFERRABLE INITIALLY DEFERRED
    )""",
    """CREATE TABLE probe_expected_legs(cid TEXT NOT NULL,ordinal INTEGER NOT NULL,
      account TEXT NOT NULL,asset TEXT NOT NULL,units TEXT NOT NULL,PRIMARY KEY(cid,ordinal),
      FOREIGN KEY(cid) REFERENCES probe_intents(cid) DEFERRABLE INITIALLY DEFERRED)""",
    """CREATE TRIGGER probe_credit_closing BEFORE INSERT ON credit_commands WHEN NEW.kind='borrowed'
      BEGIN SELECT CASE WHEN NOT EXISTS(
        SELECT 1 FROM probe_intents i JOIN ledger_events e ON e.event_id=i.journal AND e.sealed=1
        WHERE i.cid=NEW.command_id AND i.scope=NEW.scope AND i.credit_kind=NEW.kind
          AND i.asset=NEW.asset AND i.amount=NEW.amount AND i.journal=NEW.journal_event_id
          AND (SELECT COUNT(*) FROM probe_expected_legs x WHERE x.cid=i.cid)=4
          AND (SELECT COUNT(*) FROM ledger_postings p WHERE p.sequence=e.sequence)=4
          AND NOT EXISTS(SELECT 1 FROM probe_expected_legs x WHERE x.cid=i.cid AND NOT EXISTS(
            SELECT 1 FROM ledger_postings p WHERE p.sequence=e.sequence AND p.ordinal=x.ordinal
              AND p.account=x.account AND p.asset=x.asset AND p.units=x.units)))
        THEN RAISE(ABORT,'candidate complete sealed four-leg journal required') END; END""",
)

EFFECT_GUARDS = (
    """CREATE TRIGGER probe_posting_intent BEFORE INSERT ON ledger_postings
      WHEN NEW.account LIKE 'system:credit-%' OR NEW.account LIKE 'liability:principal:%'
        OR NEW.account LIKE 'liability:interest:%'
        OR EXISTS(SELECT 1 FROM probe_intents i JOIN ledger_events e ON e.event_id=i.journal WHERE e.sequence=NEW.sequence)
      BEGIN SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM probe_intents i
        JOIN ledger_events e ON e.event_id=i.journal JOIN probe_expected_legs x ON x.cid=i.cid
        WHERE e.sequence=NEW.sequence AND x.ordinal=NEW.ordinal AND x.account=NEW.account
          AND x.asset=NEW.asset AND x.units=NEW.units)
        THEN RAISE(ABORT,'candidate matching staged intent required') END; END""",
    """CREATE TRIGGER probe_debt_intent BEFORE INSERT ON uta_liabilities
      BEGIN SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM probe_intents i WHERE i.account=NEW.account_id
        AND i.asset=NEW.asset AND i.amount=NEW.principal AND NEW.interest='0')
        THEN RAISE(ABORT,'candidate matching staged debt intent required') END; END""",
)


def error_record(error):
    return {"type": type(error).__name__, "code": getattr(error, "code", None),
            "sqlite_errorcode": getattr(error, "sqlite_errorcode", None),
            "sqlite_errorname": getattr(error, "sqlite_errorname", None)}


class Component:
    def __init__(self, *, candidate=True, missing=None, posting_gate=True):
        self.temp = TemporaryDirectory(prefix="uta-credit-component-")
        self.path = Path(self.temp.name) / "authority.sqlite3"
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        self.candidate, self.missing = candidate, missing
        self.catalog = ProductCatalog(1, {"BTC-PERP": ProductSpec("BTC-PERP",
            ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD", D(".01"), D(".01"), D(1),
            status=TradingStatus.ACTIVE)})
        self.rules = PortfolioRules(1,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".5")),
             "BTC": CollateralRule("BTC", (CollateralTier(None, D(".8")),), D(".5"))},
            {"BTC": BorrowLimits("BTC", D(10), D(".2"), D(".1"), D(".01"))},
            {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(10000))
        db = Database(self.path)
        base = self.open(db, audit=False)
        for account in (ACCOUNT, "bob"):
            base.create_account(account)
        base.deposit(ACCOUNT, "opening", "USD", D(100))
        base.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        base.set_kill_switch(False)
        credit = CreditService(base)
        credit.configure_asset_limit("BTC", D(100))
        credit.configure_limit(ACCOUNT, "BTC", D(10))
        credit.fund_pool("opening-pool", "BTC", D(1), source_reference="synthetic:component:pool")
        QueueStore(db, initialize=True, clock=lambda: self.now)
        with db.inbox_transaction() as con:
            # The current SDK expressly cannot enqueue BORROW. This row is a
            # manually constructed future parent for candidate FK experiments.
            con.execute("INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,enqueued_at) VALUES (?,?,? ,?,'PENDING',?)",
                        (CID, ACCOUNT, "BORROW", PAYLOAD, self.now.isoformat()))
        audit = DecisionAudit(db)
        with db.transaction() as con:
            audit.install(con, policy=DecisionAudit.policy(base), recorded_at=self.now.isoformat())
            if candidate:
                for sql in SCHEMA + (EFFECT_GUARDS if posting_gate else ()):
                    con.execute(sql)
                keys = {"probe_intents": ("cid",), "probe_expected_legs": ("cid", "ordinal"),
                        "probe_source": ("id", "cid", "account", "payload_hash"),
                        "probe_allocation": ("id", "authority", "asset"), "probe_policy": ("id",)}
                for table, columns in keys.items():
                    for action in ("UPDATE", "DELETE"):
                        con.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'candidate metadata immutable'); END")
                    predicate = " AND ".join(f"{column}=NEW.{column}" for column in columns)
                    con.execute(f"CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {predicate}) BEGIN SELECT RAISE(ABORT,'candidate metadata cannot replace'); END")
                if missing != "policy":
                    con.execute("INSERT INTO probe_policy VALUES ('policy:component')")
                if missing != "allocation":
                    con.execute("INSERT INTO probe_allocation VALUES ('allocation:component',?,'BTC')", (AUTHORITY,))
                if missing != "source":
                    con.execute("INSERT INTO probe_source VALUES ('source:component',?,?,?)", (CID, ACCOUNT, PAYLOAD_HASH))
        fence = WriterFence(db)
        fence.enable(AUTHORITY)
        self.token = fence.acquire("component:owner", ttl_seconds=30)
        self.exchange = self.open(db.for_writer(self.token), audit=True)
        self.credit = CreditService(self.exchange)
        self.transaction_trace = []
        self.before = self.snapshot()

    def open(self, db, *, audit):
        return ExchangeService(db, {"USD": 8, "BTC": 8}, product_catalog=self.catalog,
            portfolio_rules=self.rules, fee_rate=D(0), clock=lambda: self.now, decision_audit=audit)

    def close(self):
        self.temp.cleanup()

    def snapshot(self):
        # Actual cold connection, not a cached helper receipt. Native fence
        # state is read by core RO transactions; no writer or new service.
        with self.exchange.database.read_transaction() as con:
            result = {"ledger_events": con.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0],
                "borrow_rows": con.execute("SELECT COUNT(*) FROM credit_commands WHERE kind='borrowed'").fetchone()[0],
                "decisions": con.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0],
                "accounts": [tuple(row) for row in con.execute("SELECT account_id,version FROM uta_accounts ORDER BY account_id")],
                "liabilities": [tuple(row) for row in con.execute("SELECT account_id,asset,principal,interest FROM uta_liabilities ORDER BY account_id,asset")],
                "balances": [tuple(row) for row in con.execute("SELECT account,asset,units FROM ledger_balances ORDER BY account,asset")],
                "inbox": con.execute("SELECT state FROM uta_command_inbox WHERE command_id=?", (CID,)).fetchone()[0],
                "loan_legs": [tuple(row) for row in con.execute("SELECT p.account,p.asset,p.units FROM ledger_postings p JOIN ledger_events e USING(sequence) WHERE e.event_id=? ORDER BY p.ordinal", (JOURNAL,))],
                "intents": con.execute("SELECT COUNT(*) FROM probe_intents").fetchone()[0] if self.candidate else None}
            return result

    def intent(self, con, *, overrides=None):
        values = [CID, ACCOUNT, "account:alice", "BORROW", "SUCCEEDED", "borrowed", "BTC", AMOUNT,
                  UNITS, PAYLOAD_HASH, JOURNAL, 1, DECISION, "CREDIT_BORROWED", "allocation:component",
                  AUTHORITY, "policy:component", "source:component"]
        for index, value in (overrides or {}).items():
            values[index] = value
        con.execute("INSERT INTO probe_intents VALUES (" + ",".join("?" for _ in values) + ")", values)
        con.executemany("INSERT INTO probe_expected_legs VALUES (?,?,?,?,?)",
                        [(CID, ordinal, *leg) for ordinal, leg in enumerate(LEGS)])

    def stage(self, con, *, missing=None, overrides=None, wrong_decision=False, legs=None):
        errors = []
        before = self.exchange._audit_state(con, ACCOUNT)
        risk_before = self.exchange._risk(con, ACCOUNT, self.exchange._market(con))
        if self.candidate and missing != "intent":
            self.intent(con, overrides=overrides)
        if missing != "journal":
            postings = [Posting(account, asset, D(units) / D(100000000)) for account, asset, units in (LEGS if legs is None else legs)]
            self.exchange.ledger.post(JOURNAL, postings, connection=con)
        self.credit._write_debt(con, ACCOUNT, "BTC", 40000000, 0)
        version = self.exchange._bump(con, ACCOUNT)
        result = self.credit._result(ACCOUNT, CID, "BTC", AMOUNT, 40000000, 0, version, JOURNAL)
        if missing != "decision":
            after = self.exchange._audit_state(con, ACCOUNT)
            self.exchange.audit.record(con, decision_id=DECISION, kind="CREDIT_BORROWED",
                account_id="bob" if wrong_decision else ACCOUNT, business_id=CID,
                market_id=self.exchange.audit.market_ref(con, self.exchange._market(con)),
                before=before, after=after, operation={"component_only": True, "amount": AMOUNT},
                summary={"risk_before": risk_before,
                         "risk_after": self.exchange._risk(con, ACCOUNT, self.exchange._market(con))},
                recorded_at=self.now.isoformat())
        if missing != "credit":
            try:
                self.credit._record(con, "account:alice", CID, "borrowed", "BTC", AMOUNT, result)
            except sqlite3.IntegrityError as error:
                # Intentionally exercise caught closing failures followed by
                # the real outer COMMIT; deferred obligations must still fail.
                errors.append(error_record(error))
        if missing != "terminal":
            con.execute("UPDATE uta_command_inbox SET state='SUCCEEDED',result=?,completed_at=? WHERE command_id=?",
                        (_json(result), self.now.isoformat(), CID))
        return errors

    def final_check(self, con):
        if not self.candidate or con.execute("SELECT 1 FROM probe_intents LIMIT 1").fetchone():
            self.exchange._market(con)  # Actual core freshness; synthetic clock.
        if con.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("candidate financial connection has FK disabled")

    @contextmanager
    def transaction(self):
        # This standalone wrapper is not integrated into Database/runtime.
        # It demonstrates an actual final recheck and actual outer rollback.
        with self.exchange._transaction() as con:
            def trace(sql):
                value = sql.strip().upper()
                if value in ("COMMIT", "ROLLBACK"):
                    self.transaction_trace.append(value)
            con.set_trace_callback(trace)
            yield con
            self.final_check(con)


def observe_case(*, candidate=True, missing=None, overrides=None, wrong_decision=False,
                 legs=None, posting_gate=True, late_stale=False, rollback_to=False):
    component = Component(candidate=candidate, missing=missing, posting_gate=posting_gate)
    result = {"candidate": candidate, "missing": missing, "late_stale": late_stale,
              "caller_rollback_to": rollback_to, "before": component.before,
              "statement_errors": [], "outer_commit_requested": False, "committed": False}
    con = None
    try:
        try:
            with component.transaction() as con:
                if rollback_to:
                    con.execute("SAVEPOINT caller_credit")
                result["statement_errors"] = component.stage(con, missing=missing, overrides=overrides,
                    wrong_decision=wrong_decision, legs=legs)
                if late_stale:
                    component.now += timedelta(seconds=6)
                    try:
                        component.final_check(con)
                    except Exception as error:
                        result["caught_late_error"] = error_record(error)
                if rollback_to:
                    con.execute("ROLLBACK TO caller_credit")
                    con.execute("RELEASE caller_credit")
                    con.execute("UPDATE uta_command_inbox SET state='REJECTED',error=?,completed_at=? WHERE command_id=?",
                                (_json({"code": "component_rejected"}), component.now.isoformat(), CID))
                result["fk_violations_before_commit"] = [tuple(row) for row in con.execute("PRAGMA foreign_key_check")]
                result["in_transaction_before_exit"] = con.in_transaction
                result["outer_commit_requested"] = True
            result["committed"] = True
        except Exception as error:
            result["error"] = error_record(error)
            try:
                result["in_transaction_after_error"] = con.in_transaction if con else None
            except sqlite3.ProgrammingError:
                result["connection_closed_after_error"] = True
        result["after_reopen"] = component.snapshot()
        result["native_commit_attempted"] = "COMMIT" in component.transaction_trace
        result["native_rollback_observed"] = "ROLLBACK" in component.transaction_trace
        financial = lambda value: {key: item for key, item in value.items() if key not in ("inbox", "intents")}
        result["financial_unchanged"] = financial(result["before"]) == financial(result["after_reopen"])
        result["core_ledger_verified_events"] = component.exchange.ledger.verify()
        result["core_credit_nonzero_liabilities"] = component.credit.verify()["nonzero_liabilities"]
        result["production_approved"] = False
        result["credit_runtime_integrated"] = False
        result["credit_context_or_ddl_authorizer_implemented"] = False
        return result
    finally:
        component.close()
        result["temporary_authority_removed"] = not component.path.exists()


def old_binary_controls():
    observations = []
    fixture = ROOT / "tests" / "fixtures" / "legacy_credit_45818c0_uta.tar.gz"
    provenance = json.loads(fixture.with_name("legacy_credit_45818c0_provenance.json").read_text())
    if sha256(fixture.read_bytes()).hexdigest() != provenance["archive_sha256"]:
        raise RuntimeError("old credit-gate source fixture differs")
    archive = gzip.decompress(fixture.read_bytes())
    with TemporaryDirectory(prefix="uta-credit-old458-") as temp:
        source = Path(temp) / "source"
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(source, filter="data")
        code = r'''
import json,sys
from decimal import Decimal
from uta.storage import Database
from uta.writer_fence import WriterFence
from uta.service import ExchangeService
try:
 db=Database(sys.argv[1]);fence=WriterFence(db)
 token=fence.acquire('old458:component',ttl_seconds=5)
 service=ExchangeService(db.for_writer(token),{'USD':8})
 service.deposit('alice','old458:proof','USD',Decimal(1))
 fence.release(token)
 print(json.dumps({'acquired_and_wrote':True,'rejected':False}))
except Exception as error:
 print(json.dumps({'acquired_and_wrote':False,'rejected':True,'type':type(error).__name__,'code':getattr(error,'code',None)}))
'''
        for batch, credit in ((False, False), (True, False), (False, True), (True, True)):
            path = Path(temp) / f"authority-b{int(batch)}-c{int(credit)}.sqlite3"
            db = Database(path)
            base = ExchangeService(db, {"USD": 8})
            base.create_account("alice")
            base.deposit("alice", "opening", "USD", D(100))
            QueueStore(db, initialize=True)
            if batch:
                BatchStore.initialize(db)
            fence = WriterFence(db)
            fence.enable("old458:inventory:component")
            if batch:
                fence.enable_batches()
            if credit:
                # Prototype reserved marker is installed offline by this test,
                # not by any real/current credit installer. There is no owner.
                con = sqlite3.connect(path)
                try:
                    con.execute("CREATE TABLE writer_fence_credit_capability(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1),descriptor TEXT NOT NULL)")
                    con.execute("INSERT INTO writer_fence_credit_capability VALUES(1,1,'prototype-only-not-a-runtime-capability')")
                    con.commit()
                finally:
                    con.close()
            env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1")
            ran = subprocess.run([sys.executable, "-c", code, str(path)], cwd=source,
                                 env=env, capture_output=True, text=True, timeout=5)
            observation = json.loads(ran.stdout)
            observation.update(batch=batch, prototype_credit_marker=credit, exit_code=ran.returncode,
                stderr_sha256=sha256(ran.stderr.encode()).hexdigest(),
                archived_source_commit=provenance["source_commit"], source_archive_sha256=sha256(archive).hexdigest())
            # Independent raw RO reopen remains possible even when both old
            # and current runtime deliberately reject an unknown marker.
            con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
            try:
                observation["actual_ledger_events"] = con.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0]
            finally:
                con.close()
            observations.append(observation)
    return observations


if __name__ == "__main__":
    if sys.argv[1:] == ["--baseline-red"]:
        observation = observe_case(candidate=False, missing="decision")
        print(json.dumps(observation, indent=2), flush=True)
        assert observation["financial_unchanged"], "baseline trusted-owner manual future loan COMMIT lacks new obligation/audit gates"
    else:
        raise SystemExit("Use component microtests; this tool is not a service or admission API")
