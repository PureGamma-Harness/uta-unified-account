"""Real public bootstrap for internal synthetic V2 integration, no fake grants."""
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
import json
import os
import stat
from tempfile import TemporaryDirectory, mkdtemp

from tests.credit_policy_cases import descriptor, reseal
from uta.credit import CreditService
from uta.credit_artifact import credit_artifact_id, credit_code_artifact
from uta.credit_audit_v2 import canonical
from uta.durable_commands import QueueStore
from uta.existing_services import open_existing_services
from uta.market import MarketSnapshot
from uta.portfolio import PortfolioRules
from uta.products import ProductCatalog
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence


class SyntheticCreditAuthority:
    def __init__(self, *, opening_principal=False, opening_interest=False):
        retained = os.environ.get("UTA_CREDIT_V2_PRIVATE_DB_DIRECTORY")
        if retained:
            root = Path(retained)
            info = root.lstat()
            if (not root.is_absolute() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o700):
                raise AssertionError("retained actual test databases require an explicit private owned 0700 directory")
            self.directory = None
            self.path = Path(mkdtemp(prefix="actual-credit-v2-", dir=root))/"synthetic.sqlite3"
        else:
            self.directory = TemporaryDirectory(prefix="uta-credit-v2-runtime-")
            self.path = Path(self.directory.name)/"synthetic.sqlite3"
        self.db = Database(self.path)
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        documents = json.loads(Path("tests/fixtures/managed_credit_v1_canonical_example.json").read_text())["documents"]
        self.market = MarketSnapshot.from_json(documents["market_snapshot"]["canonical_payload"])
        self.bootstrap = ExchangeService(self.db, {"USD": 8, "BTC": 8},
            product_catalog=ProductCatalog.from_json(documents["catalog"]["canonical_payload"]),
            portfolio_rules=PortfolioRules.from_json(documents["risk_rules"]["canonical_payload"]),
            fee_rate=D(0), clock=lambda: self.now, decision_audit=True,
            reserve_cache_size=0, market_cache_size=0)
        self.bootstrap.create_account("alice")
        self.bootstrap.deposit("alice", "opening-cash", "USD", D(100))
        self.bootstrap.publish_market(self.market)
        self.bootstrap.set_kill_switch(False)
        self.bootstrap_credit = CreditService(self.bootstrap)
        self.bootstrap_credit.configure_asset_limit("BTC", D(".5"))
        self.bootstrap_credit.configure_limit("alice", "BTC", D(".5"))
        self.bootstrap_credit.fund_pool("pool:0", "BTC", D(1), source_reference="synthetic:credit-pool:0")
        if opening_principal or opening_interest:
            self.bootstrap_credit.borrow("alice", "opening-loan", "BTC", D(".4"))
        if opening_interest:
            self.bootstrap_credit.accrue_interest("alice", "opening-interest", "BTC", D(".05"))
        QueueStore(self.db, queue_capacity=8, cancel_reserve=2, market_capacity=1, initialize=True)
        self.fence = WriterFence(self.db)
        self.fence.enable("synthetic:v2:shard0")
        static = descriptor("synthetic:v2:shard0")
        if opening_principal or opening_interest:
            static["certificate"]["assets"]["BTC"]["allocations"][0].update(
                opening_principal_units="40000000", opening_pool_units="60000000",
                opening_interest_units="5000000" if opening_interest else "0")
            reseal(static)
        from uta.credit_policy import validate_native_descriptor
        retained = validate_native_descriptor(canonical(static), expected_authority_id="synthetic:v2:shard0")
        self.envelope = canonical({"format": 2, "stage": "SYNTHETIC_INTERNAL", "synthetic": True,
            "authority_id": "synthetic:v2:shard0", "shard": 0, "static_budget": static,
            "static_budget_id": retained.descriptor_id, "audit_format": 2, "source_format": 2,
            "fifo_format": 2, "native_format": 2,
            "artifact_id": credit_artifact_id(credit_code_artifact()), "settlement_asset": "USD",
            "borrow_asset": "BTC", "batch_size": 0, "reserve_cache_size": 0,
            "market_cache_size": 0, "production_approved": False})
        self.token = self.services = self.fifo = None

    def install_and_open(self):
        from uta.credit_native_v2 import install_internal_credit_v2, acquire_credit_v2
        from uta.credit_fifo_v2 import InternalCreditFIFO
        self.installed = install_internal_credit_v2(self.db, self.bootstrap, self.bootstrap_credit, self.envelope)
        self.token = acquire_credit_v2(self.db, "synthetic:v2:runtime-owner", 60)
        self.services = open_existing_services(self.db.for_writer(self.token), clock=lambda: self.now)
        self.fifo = InternalCreditFIFO(self.services.exchange, self.services.credit)
        return self

    def close(self):
        if self.directory is not None:
            self.directory.cleanup()


def actual_credit_observation(connection, command_id):
    """Exact selected synthetic financial SQL only; never fencing/auth rows."""
    from uta.credit_audit_v2 import CreditAuditV2, journal_record
    inbox = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
    if inbox is None:
        raise AssertionError("original actual inbox missing")
    intent = connection.execute("SELECT * FROM credit_v2_intents WHERE command_id=?", (command_id,)).fetchone()
    credit = connection.execute("SELECT * FROM credit_commands WHERE scope=? AND command_id=?",
        ("account:"+inbox["account_id"], command_id)).fetchone()
    decision = connection.execute("SELECT * FROM uta_credit_decisions WHERE command_id=?", (command_id,)).fetchone()
    return {"source": dict(connection.execute("SELECT * FROM credit_v2_sources WHERE command_id=?", (command_id,)).fetchone()),
        "inbox": dict(inbox), "intent": dict(intent) if intent else None,
        "expected_postings": [dict(row) for row in connection.execute("SELECT * FROM credit_v2_expected_postings WHERE command_id=? ORDER BY ordinal", (command_id,))],
        "credit": dict(credit) if credit else None,
        "journal": journal_record(connection, credit["journal_event_id"]) if credit else None,
        "decision_bundle": CreditAuditV2._bundle(connection, decision) if decision else None}
