"""Construct actual services from one verified existing snapshot, without writes.

These constructors mint no actor, token, role or readiness result. A returned
service keeps the exact Database object supplied by the caller. A future writer
must use the separately validated real native token and a new construction.
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

from .storage import Database, StorageError


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _tokens(statement):
    # Fixed CREATE definitions only. Whitespace and SQLite's standard quoted
    # identifiers may differ after ADD COLUMN; strings and constraints may not.
    pattern = re.compile(r"\s+|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|\|\||!=|<>|<=|>=|[(),=<>+*/.;-]")
    result, offset = [], 0
    while offset < len(statement):
        match = pattern.match(statement, offset)
        if match is None:
            raise StorageError("existing schema has an unsupported SQL token")
        token = match.group()
        offset = match.end()
        if token.isspace():
            continue
        if token.startswith('"'):
            name = token[1:-1].replace('""', '"')
            if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name) is None:
                raise StorageError("existing schema has a nonstandard quoted identifier")
            token = name
        result.append(token if token.startswith("'") else token.upper())
    return tuple(result)


def _fixed_definition(statement):
    definition = statement.replace(" IF NOT EXISTS", "", 1)
    match = re.match(r"CREATE (TABLE|TRIGGER|(?:UNIQUE )?INDEX) ([a-z_0-9]+)\b", definition)
    if match is None:
        raise StorageError("compiled existing schema object is not a fixed CREATE")
    kind, name = match.groups()
    table = name if kind == "TABLE" else re.search(r"\bON ([a-z_0-9]+)\b", definition).group(1)
    return name, ("index" if "INDEX" in kind else kind.lower(), table, definition)


def _additional_columns(statement, columns):
    if not columns:
        return statement
    prefix, chunks = _table_components(statement)
    constraints = ("CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN")
    fields = [chunk for chunk in chunks if chunk[0] not in constraints]
    trailing = [chunk for chunk in chunks if chunk[0] in constraints]
    # SQLite's ADD COLUMN inserts before trailing table constraints, rather
    # than after the final PRIMARY KEY clause. Reproduce that fixed rewrite.
    rewritten = fields + [list(_tokens(column)) for column in columns] + trailing
    body = []
    for chunk in rewritten:
        if body:
            body.append(",")
        body.extend(chunk)
    return " ".join((*prefix, "(", *body, ")"))


def _table_components(statement):
    tokens = _tokens(statement)
    if not tokens or tokens[-1] != ")":
        raise StorageError("compiled existing table has no final column list")
    start, depth, chunks, current = tokens.index("(") + 1, 0, [], []
    for token in tokens[start:-1]:
        if token == "," and depth == 0:
            chunks.append(current)
            current = []
            continue
        current.append(token)
        depth += int(token == "(") - int(token == ")")
    chunks.append(current)
    if depth != 0 or any(not chunk for chunk in chunks):
        raise StorageError("compiled existing table has an invalid column list")
    return tokens[:start - 1], chunks


def _column_names(statement):
    _, chunks = _table_components(statement)
    return tuple(chunk[0].lower() for chunk in chunks if chunk and chunk[0] not in
                 ("CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN"))


def _auxiliary_objects(connection):
    """Only fixed compiled additions, after the original native load checks."""
    from .writer_fence import (_load, _verify_control_schema, _verify_data_guards,
                               _guard_sql, _guard_actions, _data_tables)
    state = _load(connection)
    result = {}
    if state is not None:
        _verify_control_schema(connection, state)
        if state["guard_format"] == 1:
            _verify_data_guards(connection)
            for table in _data_tables(connection):
                for action in _guard_actions(table):
                    name, sql = _guard_sql(table, action)
                    result[name] = ("trigger", table, sql)
        # _load itself validates the complete installed native capability.
        if state.get("credit_format") == 1:
            from .credit_native import OBJECT_SQL
            for statement in OBJECT_SQL.values():
                name, definition = _fixed_definition(statement)
                result[name] = definition
    from .decision_audit import _guard_definitions
    for name, (table, sql) in _guard_definitions().items():
        result[name] = ("trigger", table, sql)
    return result


def _verify_fixed_schema(connection, statements, *, added_columns=None):
    added_columns = {} if added_columns is None else added_columns
    expected = {}
    for statement in statements:
        name, definition = _fixed_definition(statement)
        kind, table, sql = definition
        if kind == "table":
            sql = _additional_columns(sql, added_columns.get(name, ()))
        expected[name] = (kind, table, sql)
    installed = {row[0]: tuple(row[1:]) for row in connection.execute(
        "SELECT name,type,tbl_name,sql FROM sqlite_master")}
    for name, (kind, table, sql) in expected.items():
        actual = installed.get(name)
        if actual is None or actual[:2] != (kind, table) or actual[2] is None:
            raise StorageError("existing schema object is missing or has a different type: " + name)
        if (actual[2] != sql if kind == "trigger" else _tokens(actual[2]) != _tokens(sql)):
            raise StorageError("existing schema definition differs from the fixed contract: " + name)
        if kind == "table":
            columns = list(connection.execute('PRAGMA table_xinfo("' + name + '")'))
            if tuple(row[1] for row in columns) != _column_names(sql) or any(row[6] for row in columns):
                raise StorageError("existing schema columns differ from the fixed contract: " + name)
    tables = {table for kind, table, _ in expected.values() if kind == "table"}
    allowed = _auxiliary_objects(connection)
    for name, (kind, table, sql) in installed.items():
        if table not in tables or name in expected or kind not in ("index", "trigger"):
            continue
        if kind == "index" and sql is None and name.startswith("sqlite_autoindex_"):
            continue  # Constraints themselves were checked in the table CREATE.
        if allowed.get(name) != (kind, table, sql):
            raise StorageError("existing schema has an unexpected constraint or guard: " + name)


def _authority_statement():
    return ("CREATE TABLE uta_authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
            "kind TEXT NOT NULL CHECK(kind IN ('exchange','research')))")


def _audit_table_statements():
    # Exact compiled base-format1 definitions; no temporary SQL model is built.
    return (
        "CREATE TABLE uta_audit_capability (singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL,enabled_at TEXT NOT NULL,legacy_event_watermark INTEGER NOT NULL,legacy_order_count INTEGER NOT NULL,legacy_fill_count INTEGER NOT NULL,gaps TEXT NOT NULL)",
        "CREATE TABLE uta_market_history (snapshot_id TEXT PRIMARY KEY,content_digest TEXT NOT NULL UNIQUE,payload TEXT NOT NULL,origin TEXT NOT NULL,recorded_at TEXT NOT NULL)",
        "CREATE TABLE uta_code_artifacts (artifact_id TEXT PRIMARY KEY,manifest TEXT NOT NULL)",
        "CREATE TABLE uta_risk_policies (policy_id TEXT PRIMARY KEY,payload TEXT NOT NULL)",
        """CREATE TABLE uta_risk_decisions (decision_id TEXT PRIMARY KEY,kind TEXT NOT NULL,
                    account_id TEXT NOT NULL REFERENCES uta_accounts(account_id),business_id TEXT NOT NULL,
                    market_snapshot_id TEXT NOT NULL REFERENCES uta_market_history(snapshot_id),
                    artifact_id TEXT NOT NULL REFERENCES uta_code_artifacts(artifact_id),
                    policy_id TEXT NOT NULL REFERENCES uta_risk_policies(policy_id),pre_version INTEGER NOT NULL,
                    post_version INTEGER NOT NULL,recorded_at TEXT NOT NULL,input_payload TEXT NOT NULL,
                    summary_payload TEXT NOT NULL,UNIQUE(kind,account_id,business_id))""",
    )


def _verify_exchange_schema(connection, statements, audit_required):
    from .decision_audit import DecisionAudit
    _verify_fixed_schema(connection, (_authority_statement(),))
    if [tuple(row) for row in connection.execute("SELECT singleton,kind FROM uta_authority")] != [(1, "exchange")]:
        raise StorageError("existing source is not an exchange authority")
    versions = [row[0] for row in connection.execute("SELECT version FROM uta_schema")]
    if versions != [3 if audit_required else 2]:
        raise StorageError("existing source requires an explicit offline trading schema migration")
    columns = {"uta_orders": ("fee_notional TEXT NOT NULL DEFAULT '0'", "charged_fee TEXT NOT NULL DEFAULT '0'")}
    if audit_required:
        columns["uta_orders"] += ("admission_decision_id TEXT REFERENCES uta_risk_decisions(decision_id) DEFERRABLE INITIALLY DEFERRED",)
        columns["uta_fills"] = ("execution_decision_id TEXT REFERENCES uta_risk_decisions(decision_id) DEFERRABLE INITIALLY DEFERRED",)
    _verify_fixed_schema(connection, statements, added_columns=columns)
    if audit_required:
        DecisionAudit.validate(connection)
        _verify_fixed_schema(connection, _audit_table_statements())
    elif connection.execute("SELECT 1 FROM sqlite_master WHERE name IN ('uta_audit_capability','uta_market_history','uta_code_artifacts','uta_risk_policies','uta_risk_decisions') LIMIT 1").fetchone():
        raise StorageError("existing source has an undeclared or partial base audit capability")


def _verify_exchange_configuration(exchange, connection, policy, risk_policy):
    for key, expected in (("policy", policy), ("risk_policy", risk_policy)):
        row = connection.execute("SELECT value FROM uta_config WHERE key=?", (key,)).fetchone()
        if row is None or row[0] != expected:
            raise StorageError("existing source configuration does not match its constructor inputs")
    exchange._halted(connection)
    if exchange.audit is not None:
        from .decision_audit import DecisionAudit
        payload = _canonical(DecisionAudit.policy(exchange))
        policy_id = "policy:" + sha256(payload.encode()).hexdigest()
        row = connection.execute("SELECT payload FROM uta_risk_policies WHERE policy_id=?", (policy_id,)).fetchone()
        if row is None or row[0] != payload:
            raise StorageError("existing source has no exact archived base audit policy")
        manifest = _canonical(exchange.audit.manifest)
        row = connection.execute("SELECT manifest FROM uta_code_artifacts WHERE artifact_id=?", (exchange.audit.artifact_id,)).fetchone()
        if row is None or row[0] != manifest:
            raise StorageError("existing source has no stored current-build base artifact")
        exchange.audit.policy_id = policy_id


def _source_arguments(connection):
    from .products import ProductCatalog
    from .portfolio import PortfolioRules
    scales = dict(connection.execute("SELECT asset,scale FROM ledger_assets"))
    values = {row[0]: row[1] for row in connection.execute("SELECT key,value FROM uta_config WHERE key IN ('policy','risk_policy','halted')")}
    if set(values) != {"policy", "risk_policy", "halted"} or values["halted"] not in ("true", "false"):
        raise StorageError("existing source configuration is incomplete")
    try:
        policy, risk = json.loads(values["policy"]), json.loads(values["risk_policy"])
        if (type(policy) is not dict or set(policy) != {"fee_rate", "usd_scale", "max_price_age_us", "order_precision"}
                or _canonical(policy) != values["policy"] or type(policy["fee_rate"]) is not str
                or type(policy["usd_scale"]) is not int or policy["usd_scale"] != scales.get("USD")
                or type(policy["max_price_age_us"]) is not int or policy["order_precision"] != 8
                or type(policy["order_precision"]) is not int):
            raise ValueError("trading policy fields")
        if type(risk) is not dict or _canonical(risk) != values["risk_policy"]:
            raise ValueError("risk policy encoding")
        if risk == {"mode": "legacy_reference"}:
            catalog = rules = None
        elif set(risk) == {"mode", "catalog", "rules"} and risk["mode"] == "phase1_cross":
            catalog = ProductCatalog.from_json(_canonical(risk["catalog"]))
            rules = PortfolioRules.from_json(_canonical(risk["rules"]))
        else:
            raise ValueError("risk policy fields")
        version = [row[0] for row in connection.execute("SELECT version FROM uta_schema")]
        if version not in ([2], [3]):
            raise ValueError("existing schema version")
        args = {"fee_rate": Decimal(policy["fee_rate"]), "max_price_age": timedelta(microseconds=policy["max_price_age_us"]),
                "product_catalog": catalog, "portfolio_rules": rules, "decision_audit": version == [3],
                "reserve_cache_size": 0, "market_cache_size": 0}
        if args["decision_audit"]:
            from .decision_audit import DecisionAudit
            DecisionAudit.validate(connection)
            candidates = []
            for row in connection.execute("SELECT policy_id,payload FROM uta_risk_policies"):
                archived = json.loads(row["payload"])
                if type(archived) is not dict or _canonical(archived) != row["payload"] or row["policy_id"] != "policy:" + sha256(row["payload"].encode()).hexdigest():
                    raise ValueError("archived base policy identity")
                options = archived.get("execution_options")
                archived_fee = archived.get("fee_rate")
                if (type(archived_fee) is str and Decimal(archived_fee) == Decimal(policy["fee_rate"])
                        and archived.get("scales") == scales
                        and archived.get("max_price_age_us") == policy["max_price_age_us"]
                        and archived.get("catalog") == (None if catalog is None else risk["catalog"])
                        and archived.get("rules") == (None if rules is None else risk["rules"])):
                    if type(options) is not dict or set(options) != {"reserve_cache_size", "market_cache_size"}:
                        raise ValueError("archived execution options")
                    candidates.append({**options, "fee_rate": Decimal(archived_fee)})
            if len(candidates) != 1:
                raise ValueError("existing base policy is missing or ambiguous")
            args.update(candidates[0])
        return scales, args
    except (ValueError, TypeError, KeyError, OverflowError, InvalidOperation) as error:
        raise StorageError("existing source configuration cannot be reconstructed") from error


@dataclass(frozen=True)
class ExistingServices:
    exchange: object
    credit: object
    ledger: object


def open_existing_services(database, *, clock=None, connection=None):
    """Construct and fully verify real services in one actual read snapshot."""
    if not isinstance(database, Database):
        raise StorageError("database must be a Database")
    if connection is None:
        with database.read_transaction() as current:
            return open_existing_services(database, clock=clock, connection=current)
    from .writer_fence import _assert_existing_read_joinable
    from .service import ExchangeService
    from .credit import CreditService
    _assert_existing_read_joinable(database, connection)
    scales, arguments = _source_arguments(connection)
    exchange = ExchangeService(database, scales, clock=clock, _existing_connection=connection, **arguments)
    credit = CreditService(exchange, _existing_connection=connection)
    exchange.credit = credit
    return ExistingServices(exchange, credit, exchange.ledger)
