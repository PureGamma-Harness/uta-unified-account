"""Independent PR61/2bb/69 D1 v3 reference; definitions only until authorized.

Only native serialized data is accepted.  No production module, DTO, builder,
validator or arithmetic helper is imported.  Fraction is used in USD major
units; conversion back to minor units must be exact.  This is not an authority.
"""
from datetime import datetime
from fractions import Fraction
from hashlib import sha256
import json
import math
import re


WIRE = "PFH-D1-INDEPENDENT-WIRE-v3"
LEG_LIMIT = 10 ** 38
TOTAL_LIMIT = 1000 * (LEG_LIMIT - 1)
DERIVED_LIMIT = 4000 * LEG_LIMIT
TIME_LIMIT = 2 ** 63 - 1
MAX_CASE_BYTES = 2 * 1024 * 1024
MAX_WIRE_DEPTH = 32
MAX_WIRE_NODES = 250000
WIRE_INTEGER_LIMIT = 10 ** 128
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_PERIOD = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})\+00:00\Z", re.ASCII)
KEY_FIELDS = ("schema", "authority_id", "authority_generation", "symbol",
              "period_end", "interval_seconds", "settlement_asset",
              "account_id", "rule_scope_id")
SLOT_FIELDS = ("authority_id", "authority_generation", "symbol", "period_end",
               "settlement_asset", "account_id")
SCOPE_FIELDS = ("authority_id", "authority_generation", "account_id",
                "usd_scale", "settlement_asset")
STAGES = ("REGISTERED_UNASSESSED", "EXPOSURE_RATE_PENDING", "FINAL_PAYABLE",
          "FINAL_RECEIVABLE", "FINAL_ZERO")
POLICY_FIELDS = ("format", "policy_id", "clock_policy", "max_wait_us",
                 "min_query_interval_us", "max_query_attempts", "expiry_action")
OPERATIONS = ("duty_identity", "policy_identity", "action_identity", "stage_advance",
              "aggregate", "decompose", "payment_precondition", "wait_preview",
              "wait_records", "unsupported")


class ReferenceReject(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class ReferenceUnsupported(ReferenceReject):
    pass


class ReferenceWireReject(ReferenceReject):
    """Malformed transport/envelope: no correlated business response exists."""


def _require(condition, code):
    if not condition:
        raise ReferenceReject(code)


def _closed(value, fields):
    _require(type(value) is dict, "NATIVE_OBJECT_REQUIRED")
    _require(set(value) == set(fields), "EXACT_FIELDS_REQUIRED")
    return value


def _integer(value, low, high, code):
    _require(type(value) is int and low <= value <= high, code)
    return value


def _flag(value):
    _require(type(value) is bool, "NATIVE_BOOLEAN_REQUIRED")
    return value


def _identifier(value):
    _require(type(value) is str and _ID.fullmatch(value) is not None,
             "CANONICAL_ASCII_IDENTIFIER_REQUIRED")
    return value


def _money(value, nonnegative=False):
    return _integer(value, 0 if nonnegative else -LEG_LIMIT + 1,
                    LEG_LIMIT - 1, "MINOR_UNIT_DOMAIN")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _copy(value):
    # Input trees have already been restricted to closed native JSON types.
    return json.loads(_canonical(value))


def _bounded_transport(value):
    """Independent finite native-JSON walk; occurrences include dictionary keys.

    A path-local ancestor set rejects cycles, while ordinary aliases are counted
    again. Explicit exit frames avoid recursion and preserve the depth-0 rule.
    This validates logical limits; it is not a native-parser allocation quota.
    """
    todo = [(value, 0, False)]
    active = set()
    waiting, visited = 1, 0
    while todo:
        item, depth, leaving = todo.pop()
        if leaving:
            active.remove(item)
            continue
        waiting -= 1
        visited += 1
        if depth > MAX_WIRE_DEPTH or visited > MAX_WIRE_NODES:
            raise ReferenceWireReject("TRANSPORT_TREE_BOUND")
        kind = type(item)
        if kind in (dict, list):
            identity = id(item)
            if identity in active:
                raise ReferenceWireReject("TRANSPORT_CYCLE")
            child_count = len(item) * (2 if kind is dict else 1)
            # Every queued child must be visited, even before its descendants.
            if visited + waiting + child_count > MAX_WIRE_NODES:
                raise ReferenceWireReject("TRANSPORT_NODE_BOUND")
            if kind is dict and any(type(key) is not str for key in item):
                raise ReferenceWireReject("NATIVE_JSON_KEY_REQUIRED")
            active.add(identity)
            todo.append((identity, depth, True))
            if kind is dict:
                for key in reversed(item):
                    todo.append((item[key], depth + 1, False))
                    todo.append((key, depth + 1, False))
            else:
                for child in reversed(item):
                    todo.append((child, depth + 1, False))
            waiting += child_count
        elif kind is int:
            if not -WIRE_INTEGER_LIMIT < item < WIRE_INTEGER_LIMIT:
                raise ReferenceWireReject("TRANSPORT_INTEGER_DIGITS")
        elif kind is float:
            if not math.isfinite(item):
                raise ReferenceWireReject("TRANSPORT_NONFINITE")
        elif kind not in (str, bool, type(None)):
            raise ReferenceWireReject("NATIVE_JSON_VALUE_REQUIRED")
    encoded = json.dumps(value, ensure_ascii=True, allow_nan=False,
                         separators=(",", ":")).encode("ascii")
    if len(encoded) > MAX_CASE_BYTES:
        raise ReferenceWireReject("TRANSPORT_COMPACT_ASCII_BOUND")


def _scope(value):
    _closed(value, SCOPE_FIELDS)
    for name in ("authority_id", "authority_generation", "account_id"):
        _identifier(value[name])
    _integer(value["usd_scale"], 2, 8, "USD_SCALE_DOMAIN")
    _require(type(value["settlement_asset"]) is str, "SETTLEMENT_TEXT_REQUIRED")
    if value["settlement_asset"] != "USD":
        raise ReferenceUnsupported("ONLY_USD_SETTLEMENT")
    return value


def _key(value):
    _closed(value, KEY_FIELDS)
    _integer(value["schema"], 1, 1, "KEY_SCHEMA")
    for name in ("authority_id", "authority_generation", "symbol", "account_id",
                 "rule_scope_id"):
        _identifier(value[name])
    _integer(value["interval_seconds"], 1, 86400, "PERIOD_INTERVAL_DOMAIN")
    _require(type(value["settlement_asset"]) is str, "SETTLEMENT_TEXT_REQUIRED")
    if value["settlement_asset"] != "USD":
        raise ReferenceUnsupported("ONLY_USD_SETTLEMENT")
    text = value["period_end"]
    match = _PERIOD.fullmatch(text) if type(text) is str else None
    _require(match is not None, "CANONICAL_UTC_WHOLE_SECOND_REQUIRED")
    try:
        calendar = datetime(*(int(part) for part in match.groups()))
    except ValueError as error:
        raise ReferenceReject("INVALID_CALENDAR_DATE") from error
    epoch = datetime(1970, 1, 1)
    _require(calendar >= epoch, "PRE_EPOCH_PERIOD_UNSUPPORTED")
    elapsed = calendar - epoch
    whole_seconds = elapsed.days * 86400 + elapsed.seconds
    _require(whole_seconds % value["interval_seconds"] == 0, "UNALIGNED_PERIOD")
    return value


def _duty_id(key):
    # Direct implementation of the published 8008 canonical-data rule.
    return "funding-duty:v1:" + sha256(_canonical(key).encode("ascii")).hexdigest()


def _slot(key):
    return tuple(key[name] for name in SLOT_FIELDS)


def _ref(value, kind, key):
    _closed(value, ("kind", "digest", "duty_id", "rule_scope_id"))
    _require(value["kind"] == kind, "TYPED_CONTENT_REFERENCE_REQUIRED")
    _require(type(value["digest"]) is str and _SHA.fullmatch(value["digest"])
             is not None, "CONTENT_DIGEST_DOMAIN")
    _require(value["duty_id"] == _duty_id(key)
             and value["rule_scope_id"] == key["rule_scope_id"],
             "CONTENT_REFERENCE_LINK")


def _stage(value, key):
    _closed(value, ("kind", "amount_units", "exposure_ref", "cap_ref", "final_ref"))
    kind = value["kind"]
    if kind == "APPLIED":
        raise ReferenceUnsupported("APPLIED_REQUIRES_D2")
    _require(type(kind) is str and kind in STAGES, "SUPPORTED_STAGE_REQUIRED")
    amount = _money(value["amount_units"], nonnegative=True)
    if kind == "REGISTERED_UNASSESSED":
        _require(amount == 0 and all(value[n] is None for n in
                 ("exposure_ref", "cap_ref", "final_ref")), "UNASSESSED_SHAPE")
    elif kind == "EXPOSURE_RATE_PENDING":
        _ref(value["exposure_ref"], "EXPOSURE", key)
        _ref(value["cap_ref"], "CAP", key)
        _require(value["final_ref"] is None, "CAP_IS_NOT_FINAL")
    else:
        _ref(value["final_ref"], "FINAL_CUT", key)
        exposure, cap = value["exposure_ref"], value["cap_ref"]
        _require((exposure is None) == (cap is None), "FINAL_LINEAGE_PAIR_REQUIRED")
        if exposure is not None:
            _ref(exposure, "EXPOSURE", key)
            _ref(cap, "CAP", key)
        # 69: reachability decides absent direct lineage versus retained U pair.
        _require((amount == 0) if kind == "FINAL_ZERO" else (amount > 0),
                 "FINAL_AMOUNT_KIND")
    return value


def _allowed_step(before, after):
    if before["kind"] == "REGISTERED_UNASSESSED":
        return (after["kind"] == "EXPOSURE_RATE_PENDING"
                or (after["kind"] in ("FINAL_PAYABLE", "FINAL_RECEIVABLE", "FINAL_ZERO")
                    and after["exposure_ref"] is None and after["cap_ref"] is None))
    if before["kind"] == "EXPOSURE_RATE_PENDING":
        linked = (after["kind"] in ("FINAL_PAYABLE", "FINAL_RECEIVABLE", "FINAL_ZERO")
                  and after["exposure_ref"] == before["exposure_ref"]
                  and after["cap_ref"] == before["cap_ref"])
        if linked and after["amount_units"] > before["amount_units"]:
            raise ReferenceUnsupported("CAP_BREACH_PRESERVES_PRIOR_STATE")
        return linked
    return False


def _state(value):
    _closed(value, ("key", "usd_scale", "revision", "active", "history",
                    "activation_permission"))
    key = _key(value["key"])
    _integer(value["usd_scale"], 2, 8, "USD_SCALE_DOMAIN")
    _require(value["activation_permission"] is False, "NO_ACTIVATION_PERMISSION")
    history = value["history"]
    _require(type(history) is list and len(history) <= 2, "PURE_STAGE_HISTORY_BOUND")
    _integer(value["revision"], 0, 2, "PURE_STAGE_REVISION_DOMAIN")
    _require(value["revision"] == len(history), "PURE_STAGE_REVISION_HISTORY")
    sequence = history + [value["active"]]
    for stage in sequence:
        _stage(stage, key)
    _require(sequence[0]["kind"] == "REGISTERED_UNASSESSED", "INITIAL_STAGE_REQUIRED")
    for before, after in zip(sequence, sequence[1:]):
        # This verifies the provided history, not the authenticity of that history.
        _require(_allowed_step(before, after), "IMMUTABLE_STAGE_CHAIN_AND_FINAL_LINEAGE")
    return value


def _same_scope(state, scope):
    key = state["key"]
    if (any(key[n] != scope[n] for n in ("authority_id", "authority_generation",
            "account_id", "settlement_asset")) or state["usd_scale"] != scope["usd_scale"]):
        raise ReferenceUnsupported("CROSS_SCOPE_OR_SCALE_UNSUPPORTED")


def _major(units, scope):
    return Fraction(units, 10 ** scope["usd_scale"])


def _units(amount, scope):
    result = amount * 10 ** scope["usd_scale"]
    _require(result.denominator == 1, "EXACT_MINOR_UNITS_REQUIRED")
    _require(abs(result.numerator) <= DERIVED_LIMIT, "DERIVED_VALUE_BOUND")
    return result.numerator


def _aggregate(states, scope, complete):
    _scope(scope)
    if not _flag(complete):
        raise ReferenceUnsupported("INCOMPLETE_PROVIDED_BASIS")
    _require(type(states) is list and len(states) <= 1000, "DUTY_COUNT_BOUND")
    duties, slots = set(), set()
    values = {"P": Fraction(0), "U": Fraction(0), "N": Fraction(0)}
    for state in states:
        _state(state)
        _same_scope(state, scope)
        identity, slot = _duty_id(state["key"]), _slot(state["key"])
        _require(identity not in duties and slot not in slots, "DUPLICATE_DUTY_OR_SLOT")
        duties.add(identity)
        slots.add(slot)
        stage = state["active"]
        if stage["kind"] == "REGISTERED_UNASSESSED":
            raise ReferenceUnsupported("UNASSESSED_REQUIRED_DUTY")
        component = {"EXPOSURE_RATE_PENDING": "U", "FINAL_PAYABLE": "P",
                     "FINAL_RECEIVABLE": "N"}.get(stage["kind"])
        if component is not None:
            values[component] += _major(stage["amount_units"], scope)
    result = {name: _units(value, scope) for name, value in values.items()}
    result["H"] = _units(values["P"] + values["U"], scope)
    _require(sum(result[n] for n in ("P", "U", "N")) <= TOTAL_LIMIT,
             "TOTAL_CONTRIBUTION_BOUND")
    return {"scope": _copy(scope), "duty_ids": sorted(duties), **result,
            "activation_permission": False}


def _base(value):
    _closed(value, ("scope", "accounting_equity_units", "risk_equity_units",
                    "initial_margin_units", "maintenance_margin_units",
                    "order_reserve_units", "cash_units", "spot_frozen_units",
                    "funding_components"))
    _scope(value["scope"])
    _require(type(value["funding_components"]) is str, "FUNDING_COMPONENTS_TEXT_REQUIRED")
    if value["funding_components"] != "EXCLUDED":
        raise ReferenceUnsupported("BASE_ALREADY_CONTAINS_FUNDING")
    for name in ("accounting_equity_units", "risk_equity_units", "cash_units"):
        _money(value[name])
    for name in ("initial_margin_units", "maintenance_margin_units",
                 "order_reserve_units", "spot_frozen_units"):
        _money(value[name], nonnegative=True)
    _require(value["spot_frozen_units"] <= max(value["cash_units"], 0),
             "INVALID_EXISTING_BACKING")
    return value


def _policy(value):
    _closed(value, POLICY_FIELDS)
    _integer(value["format"], 1, 1, "WAIT_POLICY_FORMAT")
    _identifier(value["policy_id"])
    _require(value["clock_policy"] == "TRUSTED_UTC_PERSISTENT_HIGH_WATERMARK",
             "CLOCK_POLICY_REQUIRED")
    _require(value["expiry_action"] == "DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX",
             "PRESERVE_DEBT_ON_EXPIRY")
    _integer(value["max_wait_us"], 1, TIME_LIMIT, "WAIT_TIME_DOMAIN")
    _integer(value["min_query_interval_us"], 1, value["max_wait_us"], "QUERY_INTERVAL_DOMAIN")
    _integer(value["max_query_attempts"], 1, 10000, "QUERY_BUDGET_DOMAIN")
    return value


def _policy_digest(value):
    # 2bb explicitly adopts these seven fields, no prefix or implicit namespace.
    return sha256(_canonical(_policy(value)).encode("ascii")).hexdigest()


def _action_payload(value):
    _closed(value, ("scope", "allocation_id"))
    scope = _scope(value["scope"])
    allocation = _identifier(value["allocation_id"])
    return {"authority_id": scope["authority_id"],
            "authority_generation": scope["authority_generation"],
            "account_id": scope["account_id"], "settlement_asset": "USD",
            "allocation_id": allocation, "action": "CANCEL_QUERY",
            "terminal_goal": "CONFIRMED_CLOSED"}


def _action_id(value):
    return "funding-action:v1:" + sha256(
        _canonical(_action_payload(value)).encode("ascii")).hexdigest()


def _action(value):
    # No scale, duty, claim, policy or deadline creates another action budget.
    return _action_id(value)


def _wait_record(value):
    _closed(value, ("action", "policy", "revision", "started_us", "deadline_us",
                    "observed_highwater_us", "attempts", "last_dispatch_us",
                    "default_review"))
    _action(value["action"])
    policy = _policy(value["policy"])
    _integer(value["revision"], 0, TIME_LIMIT, "WAIT_REVISION_DOMAIN")
    start = _integer(value["started_us"], 0, TIME_LIMIT, "WAIT_START_DOMAIN")
    _require(start + policy["max_wait_us"] <= TIME_LIMIT, "DEADLINE_OVERFLOW")
    _require(type(value["deadline_us"]) is int
             and value["deadline_us"] == start + policy["max_wait_us"], "FIXED_FIRST_DEADLINE")
    highwater = _integer(value["observed_highwater_us"], start, TIME_LIMIT,
                         "PERSISTENT_HIGHWATER_DOMAIN")
    attempts = _integer(value["attempts"], 0, policy["max_query_attempts"], "ATTEMPTS_DOMAIN")
    last = value["last_dispatch_us"]
    if attempts == 0:
        _require(last is None, "DISPATCH_LINEAGE_REQUIRED")
    else:
        _integer(last, start, min(highwater, value["deadline_us"] - 1),
                 "DISPATCH_LINEAGE_REQUIRED")
    _flag(value["default_review"])
    return value


def _wait_preview(data):
    _closed(data, ("record", "now_us", "expected_revision", "expected_policy_digest", "dispatch_query"))
    record = _wait_record(data["record"])
    expected_digest = data["expected_policy_digest"]
    _require(type(expected_digest) is str and _SHA.fullmatch(expected_digest) is not None,
             "EXPECTED_POLICY_DIGEST_SHAPE")
    _require(_policy_digest(record["policy"]) == expected_digest, "WAIT_POLICY_CAS")
    _integer(data["expected_revision"], 0, TIME_LIMIT, "WAIT_REVISION_DOMAIN")
    _require(data["expected_revision"] == record["revision"], "WAIT_REVISION_CAS")
    now = _integer(data["now_us"], 0, TIME_LIMIT, "OBSERVATION_TIME_DOMAIN")
    _require(now >= record["observed_highwater_us"], "CLOCK_REGRESSION")
    dispatch = _flag(data["dispatch_query"])
    new = _copy(record)
    counted = False
    new["observed_highwater_us"] = now
    if record["default_review"] or now >= record["deadline_us"] or record["attempts"] >= record["policy"]["max_query_attempts"]:
        new["default_review"] = True
    elif dispatch:
        # An explicit pre-dispatch request must satisfy the interval. A caller
        # that only observes WAIT uses dispatch_query=False instead.
        _require(record["last_dispatch_us"] is None
                 or now - record["last_dispatch_us"] >= record["policy"]["min_query_interval_us"],
                 "QUERY_INTERVAL_NOT_REACHED")
        new["attempts"] += 1
        new["last_dispatch_us"] = now
        counted = True
        if new["attempts"] == record["policy"]["max_query_attempts"]:
            new["default_review"] = True
    # 2bb: changes, not observations, consume one record revision.
    if new != record:
        _require(record["revision"] < TIME_LIMIT, "WAIT_REVISION_OVERFLOW")
        new["revision"] += 1
    else:
        counted = False
    return {"record": new, "outcome": "DEFAULT_REVIEW" if new["default_review"] else "WAIT",
            "query_counted": counted, "holds_unchanged": True, "activation_permission": False}


def _evaluate(op, data):
    if op == "duty_identity":
        _closed(data, ("key",))
        key = _key(data["key"])
        return {"duty_id": _duty_id(key),
                "natural_slot": list(_slot(key)), "payload": _copy(key),
                "activation_permission": False}
    if op == "policy_identity":
        _closed(data, ("policy",))
        policy = _policy(data["policy"])
        return {"digest": _policy_digest(policy), "payload": _copy(policy),
                "activation_permission": False}
    if op == "action_identity":
        _closed(data, ("action",))
        return {"action_id": _action_id(data["action"]),
                "payload": _action_payload(data["action"]),
                "activation_permission": False}
    if op == "stage_advance":
        if type(data) is dict and "expected_active_ref" in data:
            raise ReferenceUnsupported("LEGACY_SINGLE_REF_UNSUPPORTED")
        _closed(data, ("state", "proposed", "expected_revision", "expected_active_stage"))
        state = _state(data["state"])
        proposed = _stage(data["proposed"], state["key"])
        expected = _stage(data["expected_active_stage"], state["key"])
        _integer(data["expected_revision"], 0, 2, "PURE_STAGE_REVISION_DOMAIN")
        active = state["active"]
        _require(data["expected_revision"] == state["revision"]
                 and expected == active, "STAGE_REVISION_COMPLETE_STAGE_CAS")
        if active["kind"] in ("FINAL_PAYABLE", "FINAL_RECEIVABLE", "FINAL_ZERO"):
            raise ReferenceUnsupported("FINAL_STAGE_IMMUTABLE")
        _require(_allowed_step(active, proposed), "IMMUTABLE_STAGE_OR_CAP_BOUND")
        new = _copy(state)
        new["history"].append(new["active"])
        new["active"] = _copy(proposed)
        new["revision"] += 1
        _state(new)
        return new
    if op == "aggregate":
        _closed(data, ("states", "scope", "basis_complete"))
        return _aggregate(data["states"], data["scope"], data["basis_complete"])
    if op == "decompose":
        _closed(data, ("base", "states", "basis_complete"))
        base = _base(data["base"])
        scope = base["scope"]
        totals = _aggregate(data["states"], scope, data["basis_complete"])
        major = lambda name: _major(base[name], scope)
        hold = _major(totals["H"], scope)
        risk = major("risk_equity_units") - hold
        raw = major("cash_units") - major("spot_frozen_units") - hold
        return {"scope": _copy(scope), **{k: totals[k] for k in ("P", "U", "N", "H")},
                "accrual_equity_units": _units(major("accounting_equity_units") - _major(totals["P"], scope) + _major(totals["N"], scope), scope),
                "risk_equity_units": _units(risk, scope),
                "available_margin_units": _units(risk - major("initial_margin_units") - major("order_reserve_units"), scope),
                **{k: base[k] for k in ("initial_margin_units", "maintenance_margin_units", "order_reserve_units")},
                "ordinary_spend_raw_units": _units(raw, scope),
                "ordinary_spendable_units": _units(max(raw, Fraction(0)), scope),
                "activation_permission": False}
    if op == "payment_precondition":
        _closed(data, ("states", "scope", "own_duty_id", "cash_units", "spot_frozen_units",
                       "prior_confirmed_settlements_clear", "quote_available", "basis_complete"))
        totals = _aggregate(data["states"], data["scope"], data["basis_complete"])
        cash = _money(data["cash_units"])
        frozen = _money(data["spot_frozen_units"], nonnegative=True)
        _require(frozen <= max(cash, 0), "INVALID_EXISTING_BACKING")
        prior = _flag(data["prior_confirmed_settlements_clear"])
        quote = _flag(data["quote_available"])
        own = [state for state in data["states"] if _duty_id(state["key"]) == data["own_duty_id"]]
        _require(len(own) == 1, "OWN_DUTY_REQUIRED")
        if own[0]["active"]["kind"] != "FINAL_PAYABLE":
            raise ReferenceUnsupported("OWN_FIXED_PAYABLE_REQUIRED")
        debit = own[0]["active"]["amount_units"]
        after = _units(_major(cash, data["scope"]) - _major(debit, data["scope"]), data["scope"])
        eligible = prior and frozen <= max(after, 0)
        return {"scope": _copy(data["scope"]),
                "outcome": "PREVIEW_BACKING_ELIGIBLE" if eligible else "WAITING_ENCUMBRANCE_RELEASE",
                "own_duty_id": data["own_duty_id"],
                "projected_cash_units": after if eligible else cash,
                "projected_P": totals["P"] - debit if eligible else totals["P"],
                "projected_U": totals["U"], "projected_N": totals["N"],
                "projected_H": totals["H"] - debit if eligible else totals["H"],
                "other_H_units": totals["H"] - debit,
                "risk_recheck_required": not quote, "activation_permission": False}
    if op == "wait_preview":
        return _wait_preview(data)
    if op == "wait_records":
        _closed(data, ("records",))
        records = data["records"]
        _require(type(records) is list and len(records) <= 1000, "WAIT_RECORD_COUNT_BOUND")
        seen = set()
        for record in records:
            _wait_record(record)
            action = _action(record["action"])
            _require(action not in seen, "DUPLICATE_SHARED_ACTION_BUDGET")
            seen.add(action)
        return {"action_ids": sorted(seen), "record_count": len(records), "holds_unchanged": True,
                "activation_permission": False}
    if op == "unsupported":
        _closed(data, ("operation",))
        _identifier(data["operation"])
        raise ReferenceUnsupported("UNSUPPORTED_OPERATION")
    raise ReferenceReject("UNKNOWN_OPERATION")


def evaluate_request(request):
    """Pure serialized reference response; unexpected implementation errors escape."""
    _bounded_transport(request)
    try:
        _closed(request, ("schema", "case_id", "op", "input"))
        _integer(request["schema"], 3, 3, "WIRE_SCHEMA")
        _identifier(request["case_id"])
        _require(type(request["op"]) is str and request["op"] in OPERATIONS,
                 "KNOWN_ENVELOPE_OPERATION_REQUIRED")
        _require(type(request["input"]) is dict, "INPUT_OBJECT_REQUIRED")
    except ReferenceReject as error:
        raise ReferenceWireReject(error.code) from error
    case_id = request["case_id"]
    response = {"schema": 3, "case_id": case_id, "status": "OK", "value": None,
                "diagnostic_code": None, "activation_permission": False,
                "hash_wire": "CODE_CONTRACT_IMPLEMENTED_NOT_RUN"}
    try:
        response["value"] = _evaluate(request["op"], request["input"])
    except ReferenceUnsupported as error:
        response.update(status="UNSUPPORTED", diagnostic_code="UNSUPPORTED_OPERATION_OR_CAPABILITY")
    except ReferenceReject as error:
        response.update(status="REJECT", diagnostic_code="REJECTED_INPUT_OR_PRECONDITION")
    return response


def load_request(raw):
    """Bounded JSON input, with duplicate keys rejected independently."""
    if type(raw) not in (str, bytes):
        raise ReferenceWireReject("SERIALIZED_JSON_REQUIRED")
    try:
        data = raw.encode("utf-8") if type(raw) is str else raw
        _require(len(data) <= MAX_CASE_BYTES, "CASE_SERIALIZED_BOUND")
        text = data.decode("utf-8")
        _require(not text.startswith("\ufeff"), "UTF8_BOM_UNSUPPORTED")
        def pairs(items):
            result = {}
            for key, value in items:
                _require(key not in result, "DUPLICATE_JSON_KEY")
                result[key] = value
            return result
        def invalid_constant(text):
            raise ReferenceReject("NONFINITE_JSON_NUMBER")
        def exact_integer(token):
            digits = token[1:] if token.startswith("-") else token
            if len(digits) > 128:
                raise ReferenceWireReject("TRANSPORT_INTEGER_DIGITS")
            return int(token)
        parsed = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant,
                            parse_int=exact_integer)
        _bounded_transport(parsed)
        return parsed
    except ReferenceReject as error:
        raise ReferenceWireReject(error.code) from error
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ReferenceWireReject("INVALID_JSON") from error
