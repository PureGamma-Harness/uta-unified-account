"""Bounded, exact synthetic credit certificates; no permission or DB side effect.

Validation establishes internal consistency and supplied expected identities.
Actual ledger/funding ownership must be checked by the offline native installer.
The only supported stage is NATIVE_PREPARED: it cannot authorize a writer,
readiness, activation, borrowing, repayment or real funds.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType


UNIT_LIMIT = 10**38
MAX_SHARDS = 256
MAX_ASSETS = 32
MAX_FUNDING_CLAIMS = 64
MAX_DESCRIPTOR_BYTES = 1024 * 1024
MAX_VERSION = 2**63 - 1
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_ASSET = re.compile(r"[A-Z][A-Z0-9]{0,15}\Z", re.ASCII)
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_UNITS = re.compile(r"(?:0|[1-9][0-9]{0,37})\Z", re.ASCII)


class CreditPolicyError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, field):
    raise CreditPolicyError(code, "invalid synthetic credit certificate: " + field)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix, value):
    return prefix + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _object(value, fields, field):
    if type(value) is not dict or set(value) != set(fields):
        _fail("credit_certificate_fields", field)
    return value


def _integer(value, lower, upper, field):
    if type(value) is not int or not lower <= value <= upper:
        _fail("credit_certificate_integer", field)
    return value


def _name(value, field):
    if type(value) is not str or _NAME.fullmatch(value) is None:
        _fail("credit_certificate_identity", field)
    return value


def _asset(value, field):
    if type(value) is not str or _ASSET.fullmatch(value) is None:
        _fail("credit_certificate_asset", field)
    return value


def _hash(value, field):
    if type(value) is not str or _HEX.fullmatch(value) is None:
        _fail("credit_certificate_hash", field)
    return value


def _content_id(value, prefix, field):
    if type(value) is not str or not value.startswith(prefix):
        _fail("credit_certificate_context", field)
    _hash(value[len(prefix):], field)
    return value


def _units(value, field, *, positive=False):
    if type(value) is not str or _UNITS.fullmatch(value) is None:
        _fail("credit_certificate_units", field)
    amount = int(value)
    if amount >= UNIT_LIMIT or positive and amount == 0:
        _fail("credit_certificate_units", field)
    return amount


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("credit_certificate_duplicate_key", "JSON object")
        result[key] = value
    return result


def _json_integer(value):
    # All numeric JSON fields are bounded format/version/index/scale integers.
    # Monetary values are strings. Bound before Python int conversion as well.
    if len(value) > 20:
        _fail("credit_certificate_integer", "JSON number")
    return int(value)


def _no_float(value):
    _fail("credit_certificate_number", "non-integer JSON number")


def _tree(value):
    stack, nodes = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > 65536 or depth > 16:
            _fail("credit_certificate_size", "JSON tree")
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                _fail("credit_certificate_fields", "non-text key")
            stack.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            stack.extend((child, depth + 1) for child in item)
        elif item is not None and type(item) not in (str, int, bool):
            _fail("credit_certificate_type", "JSON primitive")


def _document(raw):
    if type(raw) is dict:
        _tree(raw)
        try:
            raw = _canonical(raw)
        except (TypeError, ValueError, RuntimeError, UnicodeError, RecursionError) as exc:
            raise CreditPolicyError("credit_certificate_json", "invalid credit JSON object") from exc
    if type(raw) is not str:
        _fail("credit_certificate_json", "JSON text or plain dict required")
    try:
        if len(raw.encode("utf-8")) > MAX_DESCRIPTOR_BYTES:
            _fail("credit_certificate_size", "JSON bytes")
        result = json.loads(raw, object_pairs_hook=_pairs, parse_int=_json_integer,
                            parse_float=_no_float, parse_constant=_no_float)
        _tree(result)
    except CreditPolicyError:
        raise
    except (json.JSONDecodeError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise CreditPolicyError("credit_certificate_json", "invalid credit JSON text") from exc
    return result


@dataclass(frozen=True)
class CreditFundingClaim:
    source_reference: str
    command_id: str
    funded_units: int


@dataclass(frozen=True)
class CreditAllocation:
    certificate_id: str
    asset: str
    scale: int
    shard: int
    authority_id: str
    limit_units: int
    opening_principal_units: int
    opening_interest_units: int
    opening_pool_units: int
    funding_claims: tuple[CreditFundingClaim, ...]

    @property
    def allocation_id(self):
        return _identity("credit-allocation:",
                         [self.certificate_id, self.asset, self.shard, self.authority_id])

    @property
    def opening_debt_units(self):
        return self.opening_principal_units + self.opening_interest_units


@dataclass(frozen=True)
class CreditAssetBudget:
    asset: str
    scale: int
    global_limit_units: int
    allocations: tuple[CreditAllocation, ...]


@dataclass(frozen=True)
class NativeCreditDescriptor:
    descriptor_id: str
    canonical_payload: str
    policy_payload: str
    certificate_payload: str
    credit_policy_id: str
    certificate_id: str
    authority_id: str
    shard: int
    layout_hash: str
    budget_id: str
    budget_version: int
    authorities: tuple[tuple[int, str], ...]
    assets: tuple[CreditAssetBudget, ...]

    @property
    def stage(self):
        return "NATIVE_PREPARED"

    @property
    def validation_scope(self):
        return "certificate structure and supplied expected identities; not ledger or custody proof"

    def allocation_for(self, asset, shard):
        _asset(asset, "allocation lookup asset")
        _integer(shard, 0, MAX_SHARDS - 1, "allocation lookup shard")
        for budget in self.assets:
            if budget.asset == asset:
                for allocation in budget.allocations:
                    if allocation.shard == shard:
                        return allocation
        _fail("credit_allocation_missing", "allocation lookup")


def _expected_mapping(value, field):
    if type(value) not in (dict, MappingProxyType):
        _fail("credit_certificate_context", field)
    return dict(value)


def validate_native_descriptor(raw, *, expected_authority_id,
        expected_layout_hash=None, expected_shard=None, expected_asset_scales=None,
        expected_policy_id=None, expected_certificate_id=None, expected_authorities=None):
    """Return immutable typed declared facts, never a verified/ready permission.

    Expected context must originate outside the untrusted payload. Rehashing a
    modified certificate cannot satisfy a supplied sealed certificate identity.
    The native installer must separately check every local ledger/funding fact.
    """
    doc = _object(_document(raw), ("format", "stage", "synthetic", "authority_id", "shard",
        "layout_hash", "credit_policy", "credit_policy_id", "certificate", "certificate_id"), "descriptor")
    _integer(doc["format"], 1, 1, "descriptor format")
    if doc["stage"] != "NATIVE_PREPARED" or type(doc["stage"]) is not str or doc["synthetic"] is not True:
        _fail("credit_certificate_stage", "prepared synthetic stage required")
    authority = _name(doc["authority_id"], "authority")
    if authority != _name(expected_authority_id, "expected authority"):
        _fail("credit_certificate_context", "authority mismatch")
    shard = _integer(doc["shard"], 0, MAX_SHARDS - 1, "shard")
    layout = _hash(doc["layout_hash"], "layout hash")
    if expected_layout_hash is not None and layout != _hash(expected_layout_hash, "expected layout"):
        _fail("credit_certificate_context", "layout mismatch")
    if expected_shard is not None and shard != _integer(expected_shard, 0, MAX_SHARDS - 1, "expected shard"):
        _fail("credit_certificate_context", "shard mismatch")

    policy = _object(doc["credit_policy"], ("format", "name", "version", "new_interest_rate",
        "new_borrow_fee_rate", "require_managed_inbox", "borrow_batch_size", "production_approved",
        "credit_assets"), "credit policy")
    _integer(policy["format"], 1, 1, "policy format")
    _integer(policy["version"], 1, 1, "policy version")
    _integer(policy["borrow_batch_size"], 0, 0, "credit batch size")
    if (policy["name"] != "SYNTHETIC-CREDIT-ZERO-v1"
            or type(policy["name"]) is not str
            or type(policy["new_interest_rate"]) is not str or policy["new_interest_rate"] != "0"
            or type(policy["new_borrow_fee_rate"]) is not str or policy["new_borrow_fee_rate"] != "0"
            or policy["require_managed_inbox"] is not True or policy["production_approved"] is not False):
        _fail("credit_certificate_policy", "zero synthetic policy")
    credit_assets = policy["credit_assets"]
    if type(credit_assets) is not list or not 1 <= len(credit_assets) <= MAX_ASSETS:
        _fail("credit_certificate_asset", "policy asset list")
    for asset in credit_assets:
        _asset(asset, "policy asset")
    if credit_assets != sorted(set(credit_assets)):
        _fail("credit_certificate_asset", "sorted unique policy assets")
    policy_id = _identity("credit-policy:", policy)
    if doc["credit_policy_id"] != policy_id:
        _fail("credit_certificate_hash", "credit policy content identity")
    if expected_policy_id is not None:
        if _content_id(expected_policy_id, "credit-policy:", "expected policy ID") != policy_id:
            _fail("credit_certificate_context", "sealed credit policy mismatch")

    cert = _object(doc["certificate"], ("format", "budget_id", "version", "layout_hash",
        "credit_policy_id", "authorities", "assets"), "certificate")
    _integer(cert["format"], 1, 1, "certificate format")
    budget_id = _name(cert["budget_id"], "budget identity")
    version = _integer(cert["version"], 1, MAX_VERSION, "budget version")
    if cert["layout_hash"] != layout or cert["credit_policy_id"] != policy_id:
        _fail("credit_certificate_context", "certificate layout/policy binding")
    authorities = cert["authorities"]
    if type(authorities) is not list or not 1 <= len(authorities) <= MAX_SHARDS:
        _fail("credit_certificate_authorities", "complete authority list")
    authority_rows, seen_authorities = [], set()
    for index, entry in enumerate(authorities):
        _object(entry, ("shard", "authority_id"), "authority entry")
        if _integer(entry["shard"], 0, MAX_SHARDS - 1, "authority shard") != index:
            _fail("credit_certificate_authorities", "contiguous sorted authority shards")
        name = _name(entry["authority_id"], "authority identity")
        if name in seen_authorities:
            _fail("credit_certificate_authorities", "duplicate authority")
        authority_rows.append((index, name))
        seen_authorities.add(name)
    if shard >= len(authority_rows) or authority_rows[shard][1] != authority:
        _fail("credit_certificate_context", "local authority allocation")
    if expected_authorities is not None:
        external = _expected_mapping(expected_authorities, "expected authorities")
        for key, value in external.items():
            _integer(key, 0, MAX_SHARDS - 1, "expected authority shard")
            _name(value, "expected authority identity")
        if external != dict(authority_rows):
            _fail("credit_certificate_context", "authority set mismatch")

    assets = cert["assets"]
    if type(assets) is not dict or sorted(assets) != credit_assets:
        _fail("credit_certificate_asset", "certificate asset set")
    scales = None
    if expected_asset_scales is not None:
        scales = _expected_mapping(expected_asset_scales, "expected asset scales")
        for key, value in scales.items():
            _asset(key, "expected asset")
            _integer(value, 0, 18, "expected asset scale")
    certificate_id = _identity("credit-budget:", cert)
    if doc["certificate_id"] != certificate_id:
        _fail("credit_certificate_hash", "budget content identity")
    if expected_certificate_id is not None:
        if _content_id(expected_certificate_id, "credit-budget:", "expected certificate ID") != certificate_id:
            _fail("credit_certificate_context", "sealed budget mismatch")
    result_assets, seen_sources, seen_commands = [], set(), set()
    for asset in credit_assets:
        budget = _object(assets[asset], ("scale", "global_limit_units", "allocations"), "asset budget")
        scale = _integer(budget["scale"], 2 if asset == "USD" else 0, 8 if asset == "USD" else 18, "asset scale")
        if scales is not None and (asset not in scales or scale != scales[asset]):
            _fail("credit_certificate_context", "asset scale mismatch")
        global_units = _units(budget["global_limit_units"], "global asset budget")
        allocations = budget["allocations"]
        if type(allocations) is not list or len(allocations) != len(authority_rows):
            _fail("credit_certificate_allocation", "all authority allocations required")
        rows, total = [], 0
        for index, entry in enumerate(allocations):
            _object(entry, ("shard", "authority_id", "limit_units", "opening_principal_units",
                "opening_interest_units", "opening_pool_units", "funding_claims"), "allocation")
            actual_shard = _integer(entry["shard"], 0, MAX_SHARDS - 1, "allocation shard")
            if (actual_shard, entry["authority_id"]) != authority_rows[index]:
                _fail("credit_certificate_allocation", "allocation authority/order")
            limit = _units(entry["limit_units"], "shard credit limit")
            principal = _units(entry["opening_principal_units"], "opening principal")
            interest = _units(entry["opening_interest_units"], "opening interest")
            pool = _units(entry["opening_pool_units"], "opening pool")
            if principal + interest > limit:
                _fail("credit_certificate_allocation", "opening gross debt exceeds allocation")
            total += limit
            if total > global_units:
                _fail("credit_certificate_allocation", "allocation sum exceeds global budget")
            claims = entry["funding_claims"]
            if type(claims) is not list or len(claims) > MAX_FUNDING_CLAIMS:
                _fail("credit_certificate_funding", "funding claim list")
            typed_claims, ordering, funded = [], [], 0
            for claim in claims:
                _object(claim, ("source_reference", "command_id", "funded_units"), "funding claim")
                source = _name(claim["source_reference"], "funding source")
                command = _name(claim["command_id"], "pool command")
                amount = _units(claim["funded_units"], "funding amount", positive=True)
                if source in seen_sources or (actual_shard, command) in seen_commands:
                    _fail("credit_certificate_funding", "funding source/command reused")
                seen_sources.add(source)
                seen_commands.add((actual_shard, command))
                funded += amount
                if funded >= UNIT_LIMIT:
                    _fail("credit_certificate_funding", "funding aggregate exceeds ledger range")
                ordering.append((source, command))
                typed_claims.append(CreditFundingClaim(source, command, amount))
            if ordering != sorted(ordering) or pool > funded:
                _fail("credit_certificate_funding", "funding order or uncovered opening pool")
            rows.append(CreditAllocation(certificate_id, asset, scale, actual_shard,
                authority_rows[index][1], limit, principal, interest, pool, tuple(typed_claims)))
        result_assets.append(CreditAssetBudget(asset, scale, global_units, tuple(rows)))
    canonical = _canonical(doc)
    return NativeCreditDescriptor(_identity("credit-native:", doc), canonical, _canonical(policy),
        _canonical(cert), policy_id, certificate_id, authority, shard, layout, budget_id, version,
        tuple(authority_rows), tuple(result_assets))
