"""CODE-only target marshalling for PFH-D1-INDEPENDENT-WIRE-v2.

No reference implementation, financial equation, expected answer or service
hook belongs here. Unexpected target/constructor failures remain technical.
"""
from dataclasses import fields
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from uta import funding_hold_pure as target


REQUEST_BYTES = 2 * 1024 * 1024
HASH_WIRE = "CODE_CONTRACT_IMPLEMENTED_NOT_RUN"
WIRE_SHA256 = "d7d782e8007a0b4f9602483fb5ea2a373ac4bc42324f0fef94ba311bc7c2e3be"
OPERATIONS = (
    "duty_identity", "policy_identity", "action_identity", "stage_advance",
    "aggregate", "decompose", "payment_precondition", "wait_preview",
    "wait_records", "unsupported",
)
DTO_FIELDS = {
    "Scope": ("authority_id", "authority_generation", "account_id", "usd_scale", "settlement_asset"),
    "DutyKey": ("authority_id", "authority_generation", "symbol", "period_end", "interval_seconds", "settlement_asset", "account_id", "rule_scope_id", "schema"),
    "ContentRef": ("kind", "digest", "duty_id", "rule_scope_id"),
    "Stage": ("kind", "amount_units", "exposure_ref", "cap_ref", "final_ref"),
    "DutyState": ("key", "usd_scale", "revision", "active", "history", "activation_permission"),
    "Totals": ("scope", "duty_ids", "P", "U", "N", "H", "activation_permission"),
    "BaseValues": ("scope", "accounting_equity_units", "risk_equity_units", "initial_margin_units", "maintenance_margin_units", "order_reserve_units", "cash_units", "spot_frozen_units", "funding_components"),
    "Decomposition": ("scope", "P", "U", "N", "H", "accrual_equity_units", "risk_equity_units", "available_margin_units", "initial_margin_units", "maintenance_margin_units", "order_reserve_units", "ordinary_spend_raw_units", "ordinary_spendable_units", "activation_permission"),
    "PaymentProjection": ("scope", "outcome", "own_duty_id", "projected_cash_units", "projected_P", "projected_U", "projected_N", "projected_H", "other_H_units", "risk_recheck_required", "activation_permission"),
    "WaitPolicy": ("format", "policy_id", "clock_policy", "max_wait_us", "min_query_interval_us", "max_query_attempts", "expiry_action"),
    "ActionKey": ("scope", "allocation_id"),
    "WaitRecord": ("action", "policy", "revision", "started_us", "deadline_us", "observed_highwater_us", "attempts", "last_dispatch_us", "default_review"),
    "WaitProjection": ("record", "outcome", "query_counted", "holds_unchanged", "activation_permission"),
}
CONSTRUCTORS = {
    "Scope": target.Scope, "DutyKey": target.DutyKey,
    "ContentRef": target.ContentRef, "Stage": target.Stage,
    "DutyState": target.DutyState, "Totals": target.Totals,
    "BaseValues": target.BaseValues, "Decomposition": target.Decomposition,
    "PaymentProjection": target.PaymentProjection, "WaitPolicy": target.WaitPolicy,
    "ActionKey": target.ActionKey, "WaitRecord": target.WaitRecord,
    "WaitProjection": target.WaitProjection,
}
INPUT_FIELDS = {
    "duty_identity": ("key",), "policy_identity": ("policy",),
    "action_identity": ("action",),
    "stage_advance": ("state", "proposed", "expected_revision", "expected_active_stage"),
    "aggregate": ("states", "scope", "basis_complete"),
    "decompose": ("base", "states", "basis_complete"),
    "payment_precondition": ("states", "scope", "own_duty_id", "cash_units", "spot_frozen_units", "prior_confirmed_settlements_clear", "quote_available", "basis_complete"),
    "wait_preview": ("record", "now_us", "expected_revision", "expected_policy_digest", "dispatch_query"),
    "wait_records": ("records",), "unsupported": ("operation",),
}
OUTPUT_TYPES = {
    "stage_advance": target.DutyState, "aggregate": target.Totals,
    "decompose": target.Decomposition, "payment_precondition": target.PaymentProjection,
    "wait_preview": target.WaitProjection,
}


class WireReject(ValueError):
    """Transport/envelope failure; no response or fabricated case ID."""


class InputReject(ValueError):
    """Explicit input-shape rejection inside an already valid envelope."""


class AdapterContractError(RuntimeError):
    """Unexpected target return/schema: technical failure, never business reject."""


class _OutputMismatch(AdapterContractError):
    """Value mismatch, distinct from unsupported schema or reader failures."""


def _closed(value, names, error=InputReject):
    if type(value) is not dict or any(type(k) is not str for k in value) or set(value) != set(names):
        raise error("exact_object_fields_required")
    return value


def _array(value, maximum):
    if type(value) is not list or len(value) > maximum:
        raise InputReject("bounded_array_required")
    return value


def _dto(name, value):
    data = dict(_closed(value, DTO_FIELDS[name]))
    if "activation_permission" in data:
        if type(data["activation_permission"]) is not bool or data["activation_permission"] is not False:
            raise InputReject("fixed_activation_flag_required")
        del data["activation_permission"]
    if "holds_unchanged" in data:
        if type(data["holds_unchanged"]) is not bool or data["holds_unchanged"] is not True:
            raise InputReject("fixed_hold_flag_required")
        del data["holds_unchanged"]
    for field, child in (("scope", "Scope"), ("key", "DutyKey"),
                         ("active", "Stage"), ("action", "ActionKey"),
                         ("policy", "WaitPolicy"), ("record", "WaitRecord")):
        if field in data:
            data[field] = _dto(child, data[field])
    for field in ("exposure_ref", "cap_ref", "final_ref"):
        if field in data and data[field] is not None:
            data[field] = _dto("ContentRef", data[field])
    if "history" in data:
        data["history"] = tuple(_dto("Stage", item) for item in _array(data["history"], 2))
    if "duty_ids" in data:
        data["duty_ids"] = tuple(_array(data["duty_ids"], 1000))
    # TypeError/ValueError from an unexpected constructor is not swallowed.
    return CONSTRUCTORS[name](**data)


def _encode(value):
    kind = type(value)
    if value is None or kind in (str, int, bool):
        return value
    if kind is tuple or kind is list:
        return [_encode(item) for item in value]
    if kind is dict:
        if any(type(k) is not str for k in value):
            raise AdapterContractError("unexpected_output_key")
        return {k: _encode(v) for k, v in value.items()}
    for name, constructor in CONSTRUCTORS.items():
        if kind is constructor:
            declared = tuple(field.name for field in fields(constructor))
            if declared != DTO_FIELDS[name]:
                raise AdapterContractError("target_DTO_fields_changed")
            result = {field: _encode(getattr(value, field)) for field in declared}
            if "activation_permission" in result and result["activation_permission"] is not False:
                raise AdapterContractError("unexpected_activation_permission")
            if "holds_unchanged" in result and result["holds_unchanged"] is not True:
                raise AdapterContractError("unexpected_hold_release")
            return result
    raise AdapterContractError("unexpected_target_output_type")


def _states(data):
    return tuple(_dto("DutyState", item) for item in _array(data, 1000))


@lru_cache(maxsize=1)
def _wire_contract():
    path = Path(__file__).resolve().parents[1] / "evidence/designs/funding-hold-target-adapter-v2/wire-contract.json"
    with path.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536 or sha256(raw).hexdigest() != WIRE_SHA256:
        raise AdapterContractError("wire_contract_bytes_changed")
    return json.loads(raw.decode("utf-8"))


def _check_output_schema(schema, definitions, depth=0, active_refs=None, work=None):
    """Validate every schema branch before inspecting the candidate value."""
    if active_refs is None:
        active_refs, work = set(), [0]
    work[0] += 1
    if type(schema) is not dict or any(type(k) is not str for k in schema) or depth > 32 or work[0] > 8192:
        raise AdapterContractError("unsupported_output_schema_shape")
    if "$ref" in schema:
        ref = schema["$ref"]
        if set(schema) != {"$ref"} or type(ref) is not str or not ref.startswith("#/$defs/"):
            raise AdapterContractError("unsupported_output_reference")
        name = ref.removeprefix("#/$defs/")
        if name not in definitions or name in active_refs:
            raise AdapterContractError("unknown_or_recursive_output_reference")
        active_refs.add(name)
        try:
            _check_output_schema(definitions[name], definitions, depth + 1, active_refs, work)
        finally:
            active_refs.remove(name)
        return
    if "oneOf" in schema:
        options = schema["oneOf"]
        if set(schema) != {"oneOf"} or type(options) is not list or not 1 <= len(options) <= 4:
            raise AdapterContractError("unsupported_output_alternatives")
        for option in options:
            _check_output_schema(option, definitions, depth + 1, active_refs, work)
        return
    declared = schema.get("type")
    families = {
        "object": {"properties", "required", "additionalProperties"},
        "array": {"items", "minItems", "maxItems"},
        "integer": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"},
        "string": {"minLength", "maxLength", "pattern"},
        "boolean": set(), "null": set(),
    }
    if "type" in schema and (type(declared) is not str or declared not in families):
        raise AdapterContractError("unsupported_output_type")
    allowed = {"type", "const", "enum"} | (families[declared] if declared is not None else set())
    if not schema or set(schema) - allowed or declared is None and not (set(schema) & {"const", "enum"}):
        raise AdapterContractError("unsupported_output_schema")
    if "const" in schema and type(schema["const"]) not in (type(None), bool, int, str):
        raise AdapterContractError("unsupported_output_constant")
    if "enum" in schema:
        options = schema["enum"]
        if type(options) is not list or not 1 <= len(options) <= 32 or any(type(x) not in (type(None), bool, int, str) for x in options):
            raise AdapterContractError("unsupported_output_enum")
    numeric = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
    lengths = ("minItems", "maxItems", "minLength", "maxLength")
    for bound in numeric + lengths:
        if bound in schema and (type(schema[bound]) is not int or bound in lengths and schema[bound] < 0):
            raise AdapterContractError("unsupported_output_bound")
    for low, high in (("minimum", "maximum"), ("minItems", "maxItems"), ("minLength", "maxLength")):
        if low in schema and high in schema and schema[low] > schema[high]:
            raise AdapterContractError("inconsistent_output_bounds")
    if "pattern" in schema:
        if type(schema["pattern"]) is not str or len(schema["pattern"]) > 1024:
            raise AdapterContractError("unsupported_output_pattern")
        try:
            re.compile(schema["pattern"])
        except re.error as error:
            raise AdapterContractError("invalid_output_pattern") from error
    if declared == "object":
        properties, required = schema.get("properties"), schema.get("required")
        if (type(properties) is not dict or any(type(k) is not str for k in properties)
                or type(required) is not list or any(type(k) is not str for k in required)
                or len(required) != len(set(required)) or set(properties) != set(required)
                or schema.get("additionalProperties") is not False):
            raise AdapterContractError("unsupported_closed_output_object")
        for child in properties.values():
            _check_output_schema(child, definitions, depth + 1, active_refs, work)
    if declared == "array":
        if "items" not in schema:
            raise AdapterContractError("unsupported_output_items")
        _check_output_schema(schema["items"], definitions, depth + 1, active_refs, work)


def _match_output(schema, value, depth=0):
    """Closed native JSON-schema subset for the pinned output contract only."""
    supported = {"$ref", "type", "const", "enum", "oneOf", "properties", "required",
                 "additionalProperties", "items", "minItems", "maxItems", "minLength",
                 "maxLength", "pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}
    if type(schema) is not dict or set(schema) - supported or depth > 32:
        raise AdapterContractError("unsupported_output_schema")
    if "$ref" in schema:
        ref = schema["$ref"]
        if set(schema) != {"$ref"} or type(ref) is not str or not ref.startswith("#/$defs/"):
            raise AdapterContractError("unsupported_output_reference")
        name = ref.removeprefix("#/$defs/")
        definitions = _wire_contract()["$defs"]
        if name not in definitions:
            raise AdapterContractError("unknown_output_reference")
        return _match_output(definitions[name], value, depth + 1)
    if "oneOf" in schema:
        if set(schema) != {"oneOf"} or type(schema["oneOf"]) is not list or len(schema["oneOf"]) > 4:
            raise AdapterContractError("unsupported_output_alternatives")
        matches = 0
        for option in schema["oneOf"]:
            try:
                _match_output(option, value, depth + 1)
            except _OutputMismatch:
                continue
            matches += 1
        if matches != 1:
            raise _OutputMismatch("output_alternative_mismatch")
        return
    types = {"object": dict, "array": list, "integer": int, "boolean": bool,
             "string": str, "null": type(None)}
    if "type" in schema and (schema["type"] not in types or type(value) is not types[schema["type"]]):
        raise _OutputMismatch("output_native_type_mismatch")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise _OutputMismatch("output_constant_mismatch")
    if "enum" in schema and not any(type(value) is type(item) and value == item for item in schema["enum"]):
        raise _OutputMismatch("output_enum_mismatch")
    if type(value) is dict:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if (schema.get("additionalProperties") is not False or any(type(k) is not str for k in value)
                or set(value) != set(required) or set(properties) != set(required)):
            raise _OutputMismatch("output_object_fields_mismatch")
        for name in required:
            _match_output(properties[name], value[name], depth + 1)
    if type(value) is list:
        if "items" not in schema or len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 1000):
            raise _OutputMismatch("output_array_mismatch")
        for item in value:
            _match_output(schema["items"], item, depth + 1)
    if type(value) is str:
        if (len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 2097152)
                or "pattern" in schema and re.fullmatch(schema["pattern"], value) is None):
            raise _OutputMismatch("output_string_mismatch")
    if type(value) is int:
        if ("minimum" in schema and value < schema["minimum"]
                or "maximum" in schema and value > schema["maximum"]
                or "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]
                or "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]):
            raise _OutputMismatch("output_integer_range_mismatch")


def _validate_output(schema, value):
    _check_output_schema(schema, _wire_contract()["$defs"])
    return _match_output(schema, value)


def _checked_intermediate(name, value):
    # All failures here are technical; this guard runs before a downstream call
    # can mistake a malformed target result for an invalid customer input.
    try:
        if type(value) is not CONSTRUCTORS[name]:
            raise AdapterContractError("intermediate_target_type_mismatch")
        _validate_output({"$ref": "#/$defs/" + name}, _encode(value))
    except AdapterContractError:
        raise
    except Exception as error:
        raise AdapterContractError("intermediate_target_encoding_failed") from error


def _call(operation, raw):
    if operation == "stage_advance" and type(raw) is dict and "expected_active_ref" in raw:
        # The old keyword is a known unsupported capability, never inferred.
        raise target.HoldUnsupported("legacy_single_reference_unsupported")
    data = _closed(raw, INPUT_FIELDS[operation])
    if operation == "duty_identity":
        key = _dto("DutyKey", data["key"])
        slot = key.natural_slot
        if type(slot) is not tuple or len(slot) != 6 or any(type(item) is not str for item in slot):
            raise AdapterContractError("unexpected_native_natural_slot")
        return {"duty_id": key.duty_id, "natural_slot": list(slot),
                "payload": key.payload(), "activation_permission": False}
    if operation == "policy_identity":
        policy = _dto("WaitPolicy", data["policy"])
        return {"digest": policy.digest, "payload": policy, "activation_permission": False}
    if operation == "action_identity":
        action = _dto("ActionKey", data["action"])
        scope = action.scope
        return {"action_id": action.action_id, "payload": {
            "authority_id": scope.authority_id, "authority_generation": scope.authority_generation,
            "account_id": scope.account_id, "settlement_asset": scope.settlement_asset,
            "allocation_id": action.allocation_id, "action": "CANCEL_QUERY",
            "terminal_goal": "CONFIRMED_CLOSED"}, "activation_permission": False}
    if operation == "stage_advance":
        return target.advance_stage(_dto("DutyState", data["state"]), _dto("Stage", data["proposed"]),
            expected_revision=data["expected_revision"], expected_active_stage=_dto("Stage", data["expected_active_stage"]))
    if operation == "aggregate":
        return target.aggregate(_states(data["states"]), _dto("Scope", data["scope"]),
                                basis_complete=data["basis_complete"])
    if operation == "decompose":
        base = _dto("BaseValues", data["base"])
        total = target.aggregate(_states(data["states"]), base.scope, basis_complete=data["basis_complete"])
        _checked_intermediate("Totals", total)
        try:
            return target.decompose(base, total)
        except target.HoldError as error:
            # Base and aggregate already accepted this request. A downstream
            # rejection of their output is a broken composed target contract.
            raise AdapterContractError("accepted_intermediate_rejected_downstream") from error
    if operation == "payment_precondition":
        return target.backing_precondition(_states(data["states"]), _dto("Scope", data["scope"]),
            data["own_duty_id"], cash_units=data["cash_units"], spot_frozen_units=data["spot_frozen_units"],
            prior_confirmed_settlements_clear=data["prior_confirmed_settlements_clear"],
            quote_available=data["quote_available"], basis_complete=data["basis_complete"])
    if operation == "wait_preview":
        return target.preview_wait(_dto("WaitRecord", data["record"]), now_us=data["now_us"],
            expected_revision=data["expected_revision"], expected_policy_digest=data["expected_policy_digest"],
            dispatch_query=data["dispatch_query"])
    if operation == "wait_records":
        records = tuple(_dto("WaitRecord", item) for item in _array(data["records"], 1000))
        identities = target.validate_wait_records(records)
        if type(identities) is not tuple:
            raise AdapterContractError("unexpected_validator_return")
        return {"action_ids": identities, "record_count": len(records),
                "holds_unchanged": True, "activation_permission": False}
    if operation == "unsupported":
        target.unsupported_request(data["operation"])
        raise AdapterContractError("unsupported_operation_returned_normally")
    raise AdapterContractError("unreachable_operation")


def _native_tree(value, depth=0, ancestors=None, work=None):
    if ancestors is None:
        ancestors, work = set(), [0, 0]
    work[0] += 1
    if depth > 32 or work[0] > 250000:
        raise WireReject("bounded_JSON_tree_required")
    kind = type(value)
    if value is None or kind in (str, int, bool):
        if kind is int and value.bit_length() > 512:
            raise WireReject("bounded_JSON_integer_required")
        if kind is int and len(str(value).lstrip("-")) > 128:
            raise WireReject("bounded_JSON_integer_required")
        work[1] += len(value) if kind is str else 1
        if work[1] > REQUEST_BYTES:
            raise WireReject("request_too_large")
        return
    # Finite floats survive transport solely to be rejected by typed inputs.
    if kind is float:
        if not math.isfinite(value):
            raise WireReject("nonfinite_JSON")
        return
    if kind not in (dict, list) or id(value) in ancestors:
        raise WireReject("native_acyclic_JSON_required")
    ancestors.add(id(value))
    if kind is dict:
        if any(type(k) is not str for k in value):
            raise WireReject("string_JSON_keys_required")
        for key, item in value.items():
            _native_tree(key, depth + 1, ancestors, work)
            _native_tree(item, depth + 1, ancestors, work)
    else:
        for item in value:
            _native_tree(item, depth + 1, ancestors, work)
    ancestors.remove(id(value))


def evaluate(request):
    """Evaluate one bounded decoded request; transport errors escape untouched."""
    _native_tree(request)
    _closed(request, ("schema", "case_id", "op", "input"), WireReject)
    if type(request["schema"]) is not int or request["schema"] != 2:
        raise WireReject("schema_2_required")
    case_id, operation = request["case_id"], request["op"]
    if type(case_id) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", case_id) is None:
        raise WireReject("valid_case_id_required")
    if type(operation) is not str or operation not in OPERATIONS or type(request["input"]) is not dict:
        raise WireReject("known_operation_and_object_input_required")
    # This bound includes the complete envelope, not only monetary fields.
    if len(json.dumps(request, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")) > REQUEST_BYTES:
        raise WireReject("request_too_large")
    try:
        value = _call(operation, request["input"])
    except InputReject as error:
        if type(error) is not InputReject:
            raise
        status, value, diagnostic = "REJECT", None, "REJECTED_INPUT_OR_PRECONDITION"
    except target.HoldError as error:
        if type(error) is target.HoldUnsupported:
            status, value, diagnostic = "UNSUPPORTED", None, "UNSUPPORTED_OPERATION_OR_CAPABILITY"
        elif type(error) is target.HoldError:
            status, value, diagnostic = "REJECT", None, "REJECTED_INPUT_OR_PRECONDITION"
        else:
            raise  # Unknown subclasses are technical failures.
    else:
        status, diagnostic = "OK", None
        if operation in OUTPUT_TYPES and type(value) is not OUTPUT_TYPES[operation]:
            raise AdapterContractError("unexpected_target_return_type")
        value = _encode(value)  # Outside business catch: malformed returns fail.
        _validate_output(_wire_contract()["operations"][operation]["value"], value)
    return {"schema": 2, "case_id": case_id, "status": status, "value": value,
            "diagnostic_code": diagnostic, "activation_permission": False, "hash_wire": HASH_WIRE}


def decode_request(raw):
    """Strict bounded UTF-8 JSON; no BOM, duplicate keys or NaN/Infinity."""
    if type(raw) is not bytes or len(raw) > REQUEST_BYTES or raw.startswith(b"\xef\xbb\xbf"):
        raise WireReject("bounded_UTF8_bytes_required")

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise WireReject("duplicate_JSON_key")
            result[key] = value
        return result

    def bad_constant(_):
        raise WireReject("nonfinite_JSON")

    def bounded_int(text):
        if len(text.lstrip("-")) > 128:
            raise WireReject("bounded_JSON_integer_required")
        return int(text)

    try:
        request = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs,
                             parse_constant=bad_constant, parse_int=bounded_int)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise WireReject("malformed_UTF8_JSON") from error
    _native_tree(request)
    return request
