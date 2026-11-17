"""Strict dedicated credit operation replay from retained data only.

No current account/price is substituted, no archived symbol is imported and no
financial effect is resubmitted. Matching real code/runtime remains mandatory.
"""
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256

from .credit_audit_v2 import (CreditAuditError, _after_borrow_account, _fields, _scalar,
    borrow_operation_id, canonical, gross_components, replay_risk,
    runtime_manifest, strict_json, utc_checkpoint, validate_checkpoints, verify_journal)
from .credit_v2_payload_contract import (BUNDLE_FIELDS, DECISION_FIELDS,
    POLICY_FIELDS, POST_STATE_FIELDS, PRE_STATE_FIELDS, RECEIPT_FIELDS, RECEIPT_RISK_FIELDS,
    RISK_FIELDS, SOURCE_FIELDS)
from .storage import StorageError


DECISION_ROW_FIELDS = frozenset({"decision_id", "operation_id", "format", "kind", "account_id", "command_id",
    "inbox_kind", "terminal_state", "asset", "amount", "payload_hash", "source_id", "market_snapshot_id",
    "artifact_id", "policy_id", "descriptor_id", "allocation_id", "journal_id", "journal_sealed",
    "pre_version", "post_version", "selected_at", "last_checked_at", "recorded_at", "payload"})


def content_id(payload):
    _fields(payload, DECISION_FIELDS, "dedicated decision payload fields differ")
    return "credit-decision:" + sha256(canonical(payload).encode()).hexdigest()


def _state_consistency(account, credit):
    from .credit_transition import _snapshot
    from .ledger import Ledger
    _snapshot(credit, require_increment=False)
    codec = Ledger({"USD": 8, "BTC": 8})
    if (account["version"] != credit["version"]
            or codec._units("BTC", _scalar(account["balances"]["BTC"])) != int(credit["cash_units"])):
        raise CreditAuditError("credit_audit_state_mismatch", "actual account and credit cash/version components differ")
    liabilities = {row["asset"]: row for row in account["liabilities"]}
    row = liabilities.get("BTC", {"principal": "0", "interest": "0"})
    for field in ("principal", "interest"):
        if codec._units("BTC", _scalar(row[field])) != int(credit[field+"_units"]):
            raise CreditAuditError("credit_audit_state_mismatch", "actual account and gross credit debt components differ")
    if any(_scalar(row[field]) for asset, row in liabilities.items() if asset != "BTC" for field in ("principal", "interest")):
        raise CreditAuditError("credit_audit_policy_unsupported", "non-BTC opening credit debt is unsupported by internal v2")


def _risk_metadata(risk):
    _fields(risk, RISK_FIELDS, "complete actual credit risk decomposition is required")
    for field in ("account_version", "market_version", "rule_version", "catalog_version"):
        if type(risk[field]) is not int:
            raise CreditAuditError("credit_audit_invalid", "credit risk metadata requires exact integer types")


def _source(payload, capability, selected):
    from .credit_native_v2 import parse_source
    source = payload["source"]
    _fields(source, SOURCE_FIELDS, "original credit source row is incomplete")
    parsed = parse_source(source["payload"])
    expected = {"command_id": parsed.command_id, "source_id": parsed.source_id, "account_id": parsed.account_id,
        "kind": parsed.kind, "payload_hash": parsed.payload_hash, "source_kind": "synthetic_local",
        "actor_id": parsed.actor_id, "source_reference": parsed.source_reference,
        "authority_id": parsed.authority_id, "command_payload": parsed.command_payload,
        "payload": parsed.canonical_payload}
    command = strict_json(parsed.command_payload)
    if (source != expected or parsed.kind != "BORROW"
            or (parsed.command_id, parsed.account_id, parsed.source_id, parsed.payload_hash)
               != (payload["command_id"], payload["account_id"], payload["source_id"], payload["payload_hash"])
            or parsed.authority_id != capability.static_descriptor.authority_id
            or command != {"account_id": payload["account_id"], "asset": payload["asset"], "amount": payload["amount"]}
            or utc_checkpoint(strict_json(parsed.canonical_payload)["accepted_at"]) > selected):
        raise CreditAuditError("credit_audit_source_mismatch", "dedicated credit decision differs from original producer source")


def _funding(payload, static):
    from .credit_transition import _units
    from .service import _key
    if type(payload["pool_funding"]) is not list or not payload["pool_funding"]:
        raise CreditAuditError("credit_audit_funding_missing", "complete original synthetic pool funding is required")
    total, seen_commands, seen_sources, ordered, actual_claims = 0, set(), set(), [], {}
    for pair in payload["pool_funding"]:
        _fields(pair, {"command", "journal"}, "original pool funding pair is incomplete")
        command, journal = pair["command"], pair["journal"]
        _fields(command, {"scope", "command_id", "kind", "asset", "amount", "source_reference", "result", "journal_event_id", "created_at"},
                "original pool funding receipt is incomplete")
        if (command["scope"] != "pool" or command["kind"] != "pool_funded" or command["asset"] != "BTC"
                or type(command["command_id"]) is not str or command["command_id"] in seen_commands
                or type(command["source_reference"]) is not str or not command["source_reference"]
                or command["source_reference"] in seen_sources):
            raise CreditAuditError("credit_audit_funding_mismatch", "original pool funding identities differ or are duplicated")
        seen_commands.add(command["command_id"])
        seen_sources.add(command["source_reference"])
        ordered.append(command["command_id"])
        quantity = Fraction(_scalar(command["amount"]))*10**8
        if quantity.denominator != 1:
            raise CreditAuditError("credit_audit_funding_mismatch", "funding amount is not an exact native BTC quantity")
        units = _units(str(quantity.numerator))
        if not units:
            raise CreditAuditError("credit_audit_funding_mismatch", "funding quantity must be positive")
        actual_claims[(command["command_id"], command["source_reference"])] = units
        event_id = _key("credit", "pool", command["command_id"])
        result = strict_json(command["result"])
        _fields(result, {"command_id", "asset", "amount", "source_reference", "journal_event_id", "pool_balance"},
                "original funding result fields differ")
        if (any(result[field] != command[field] for field in
                ("command_id", "asset", "amount", "source_reference", "journal_event_id"))
                or command["journal_event_id"] != event_id or _scalar(result["pool_balance"]) < 0):
            raise CreditAuditError("credit_audit_funding_mismatch", "original funding result does not match its immutable receipt")
        legs = [{"ordinal": 0, "account": "system:credit-capital", "asset": "BTC", "units": str(-units)},
                {"ordinal": 1, "account": "system:credit-pool", "asset": "BTC", "units": str(units)}]
        verify_journal(journal, expected_event_id=event_id, expected_postings=legs)
        if journal["sequence"] > payload["pre_state"]["journal_head"]["sequence"]:
            raise CreditAuditError("credit_audit_funding_mismatch", "funding event is not part of the original opening history")
        total += units
    if ordered != sorted(ordered) or total >= 10**38:
        raise CreditAuditError("credit_audit_funding_mismatch", "original funding order or total exceeds bounds")
    before = payload["pre_state"]["credit"]
    if total != int(before["pool_units"])+int(before["shard_principal_units"]):
        raise CreditAuditError("credit_audit_funding_mismatch", "gross principal plus available pool does not reconcile to funded capital")
    allocation = static.allocation_for("BTC", static.shard)
    if (allocation.opening_principal_units+allocation.opening_pool_units != total
            or any(actual_claims.get((claim.command_id, claim.source_reference)) != claim.funded_units for claim in allocation.funding_claims)):
        raise CreditAuditError("credit_audit_funding_mismatch", "sealed opening capital or funding claims differ from actual original receipts")


def replay_bundle(bundle):
    """Reproduce the complete supported borrowing operation or fail typed closed."""
    from .credit_artifact import assert_current_credit_artifact, parse_credit_artifact
    from .credit_native_v2 import validate_envelope
    from .credit_transition import calculate_borrow_transition, compare_borrow_transition
    from .ledger import Ledger
    from .market import MarketSnapshot
    from .service import _key
    try:
        _fields(bundle, BUNDLE_FIELDS, "dedicated credit export bundle is incomplete")
        if type(bundle["format"]) is not int or bundle["format"] != 2:
            raise CreditAuditError("credit_audit_invalid", "unsupported credit bundle format")
        row = bundle["decision"]
        _fields(row, DECISION_ROW_FIELDS, "dedicated credit decision row is incomplete")
        payload = strict_json(row["payload"])
        _fields(payload, DECISION_FIELDS, "dedicated credit decision payload is incomplete")
        if (type(row["format"]) is not int or row["format"] != 2 or type(payload["format"]) is not int or payload["format"] != 2
                or row["kind"] != "CREDIT_BORROWED" or payload["kind"] != row["kind"]
                or row["inbox_kind"] != "BORROW" or row["terminal_state"] != "SUCCEEDED"
                or type(row["journal_sealed"]) is not int or row["journal_sealed"] != 1
                or payload["asset"] != "BTC" or payload["physical_commit_at"] is not None
                or content_id(payload) != row["decision_id"]):
            raise CreditAuditError("credit_audit_content_conflict", "dedicated credit decision identity or format differs")
        for field in ("operation_id", "account_id", "command_id", "asset", "amount", "payload_hash", "source_id",
                "market_snapshot_id", "artifact_id", "policy_id", "descriptor_id", "allocation_id", "selected_at", "last_checked_at", "recorded_at"):
            if row[field] != payload[field]:
                raise CreditAuditError("credit_audit_content_conflict", "decision relational and retained payload identities differ")
        if payload["operation_id"] != borrow_operation_id(payload["account_id"], payload["command_id"]):
            raise CreditAuditError("credit_audit_content_conflict", "credit business operation identity differs")
        for record, fields in ((bundle["artifact"], {"artifact_id", "manifest"}),
                (bundle["policy"], {"policy_id", "payload"}),
                (bundle["market"], {"snapshot_id", "content_digest", "payload", "origin", "recorded_at"})):
            _fields(record, fields, "dedicated credit archive row is incomplete")
        if bundle["artifact"]["artifact_id"] != payload["artifact_id"] or bundle["policy"]["policy_id"] != payload["policy_id"]:
            raise CreditAuditError("credit_audit_content_conflict", "credit artifact or policy reference differs")
        manifest = parse_credit_artifact(bundle["artifact"]["manifest"], expected_id=payload["artifact_id"])
        assert_current_credit_artifact(manifest)
        actual_id, _ = runtime_manifest()
        if actual_id != payload["artifact_id"]:
            raise CreditAuditError("credit_audit_engine_mismatch", "matching complete actual credit runtime is required")
        policy = strict_json(bundle["policy"]["payload"])
        _fields(policy, POLICY_FIELDS, "dedicated credit risk policy is incomplete")
        if payload["policy_id"] != "credit-risk-policy:"+sha256(bundle["policy"]["payload"].encode()).hexdigest():
            raise CreditAuditError("credit_audit_content_conflict", "dedicated credit risk policy content differs")
        capability_raw = strict_json(payload["capability_payload"])
        capability = validate_envelope(payload["capability_payload"], expected_authority_id=capability_raw["authority_id"],
            expected_artifact_id=payload["artifact_id"], expected_asset_scales={"USD": 8, "BTC": 8})
        static = capability.static_descriptor
        allocation = static.allocation_for("BTC", static.shard)
        if (capability.capability_id != payload["capability_id"] or static.canonical_payload != payload["static_budget"]
                or static.descriptor_id != payload["descriptor_id"] or allocation.allocation_id != payload["allocation_id"]):
            raise CreditAuditError("credit_audit_content_conflict", "credit capability/static allocation binding differs")
        market_row = bundle["market"]
        digest = sha256(market_row["payload"].encode()).hexdigest()
        if market_row["snapshot_id"] != payload["market_snapshot_id"] or market_row["snapshot_id"] != "market:"+digest or market_row["content_digest"] != digest:
            raise CreditAuditError("credit_audit_content_conflict", "original market snapshot content differs")
        strict_json(market_row["payload"])
        market = MarketSnapshot.from_json(market_row["payload"])
        if market.to_json() != market_row["payload"]:
            raise CreditAuditError("credit_audit_content_conflict", "original market snapshot is not canonical")
        selected, checked, recorded = validate_checkpoints(market, policy, selected_at=payload["selected_at"],
            last_checked_at=payload["last_checked_at"], recorded_at=payload["recorded_at"])
        if utc_checkpoint(market_row["recorded_at"]) > selected:
            raise CreditAuditError("credit_audit_clock_regression", "market publication checkpoint follows original selection")
        _source(payload, capability, selected)
        pre, post = payload["pre_state"], payload["post_state"]
        _fields(pre, PRE_STATE_FIELDS, "actual native credit prestate is incomplete")
        _fields(post, POST_STATE_FIELDS, "actual credit poststate is incomplete")
        if pre["selected_at"] != payload["selected_at"] or pre["market_snapshot_id"] != payload["market_snapshot_id"]:
            raise CreditAuditError("credit_audit_state_mismatch", "actual native selection evidence differs")
        gross = {side: gross_components(state["account"]) for side, state in (("before", pre), ("after", post))}
        if payload["gross_components"] != gross:
            raise CreditAuditError("credit_audit_state_mismatch", "retained gross assets/cash deficits/principal/interest differ")
        for state, version in ((pre, row["pre_version"]), (post, row["post_version"])):
            if type(version) is not int or version != state["account"]["version"]:
                raise CreditAuditError("credit_audit_state_mismatch", "actual account versions differ")
            _state_consistency(state["account"], state["credit"])
            if type(state["account"]["orders"]) is not list or any(order["account_id"] != payload["account_id"] for order in state["account"]["orders"]):
                raise CreditAuditError("credit_audit_state_mismatch", "stored order ownership differs from the credited account")
            _risk_metadata(state["risk"])
        if pre["account"]["halted"] or (pre["account"]["liquidation_state"] is not None and pre["account"]["liquidation_state"]["state"] != "NORMAL"):
            raise CreditAuditError("credit_audit_admission_mismatch", "borrow decision was recorded while exposure was blocked")
        before_risk = replay_risk(pre["account"], market, policy, now=selected)
        after_risk = replay_risk(post["account"], market, policy, now=checked)
        if pre["risk"] != before_risk or post["risk"] != after_risk:
            raise CreditAuditError("credit_audit_risk_mismatch", "actual risk, reserve, quote or model versions do not replay")
        codec = Ledger({"USD": 8, "BTC": 8})
        amount = _scalar(payload["amount"])
        if str(codec._units("BTC", amount)) != payload["amount_units"]:
            raise CreditAuditError("credit_audit_state_mismatch", "borrow native quantity differs from its canonical amount")
        if str(codec._units("BTC", Decimal(before_risk["borrowable"]["BTC"]))) != pre["quote_units"]:
            raise CreditAuditError("credit_audit_risk_mismatch", "pre-borrow conservative quote does not replay")
        step = policy["base_policy"]["rules"]["borrow_limits"]["BTC"]["quantity_step"]
        if str(codec._units("BTC", Decimal(step))) != pre["quantity_step_units"]:
            raise CreditAuditError("credit_audit_risk_mismatch", "versioned borrow quantity step does not replay")
        expected = calculate_borrow_transition(descriptor=static, account_id=payload["account_id"], asset="BTC",
            amount_units=payload["amount_units"], before=pre["credit"], limits=pre["limits"],
            quote_units=pre["quote_units"], quantity_step_units=pre["quantity_step_units"])
        compare_borrow_transition(expected, after=post["credit"], postings=payload["journal"]["postings"])
        if post["limits"] != pre["limits"] or post["account"] != _after_borrow_account(pre["account"], "BTC", amount, expected.wire()["after"]):
            raise CreditAuditError("credit_audit_state_mismatch", "borrow altered unrelated positions/orders/frozen state or limits")
        if Fraction(Decimal(after_risk["available_margin"])) < 0:
            raise CreditAuditError("credit_audit_admission_mismatch", "borrow leaves insufficient initial margin")
        event_id = _key("credit", "account:"+payload["account_id"], payload["command_id"])
        if row["journal_id"] != event_id:
            raise CreditAuditError("credit_audit_content_conflict", "credit journal business identity differs")
        verify_journal(payload["journal"], expected_event_id=event_id, expected_postings=expected.wire()["postings"], journal_head=pre["journal_head"])
        _funding(payload, static)
        receipt = payload["receipt"]
        _fields(receipt, RECEIPT_FIELDS, "original credit result is incomplete")
        _fields(receipt["risk_evidence"], RECEIPT_RISK_FIELDS, "original credit risk receipt is incomplete")
        if any(type(receipt["risk_evidence"][field]) is not int for field in ("market_version", "rule_version", "catalog_version")):
            raise CreditAuditError("credit_audit_invalid", "credit receipt risk versions require exact integer types")
        for field in ("account_id", "command_id", "asset", "amount"):
            if receipt[field] != payload[field]:
                raise CreditAuditError("credit_audit_receipt_mismatch", "original credit result identity differs")
        from .decision_audit import _text
        if (receipt["journal_event_id"] != event_id or type(receipt["account_version"]) is not int
                or receipt["account_version"] != post["credit"]["version"]
                or receipt["principal"] != _text(Fraction(int(post["credit"]["principal_units"]),10**8))
                or receipt["interest"] != _text(Fraction(int(post["credit"]["interest_units"]),10**8))
                or receipt["total"] != _text(Fraction(int(post["credit"]["principal_units"])+int(post["credit"]["interest_units"]),10**8))):
            raise CreditAuditError("credit_audit_receipt_mismatch", "original result gross debt or account version differs")
        risk_receipt = {"market_version": market.version, "market_observed_at": market.observed_at.isoformat(),
            "borrowable_before": before_risk["borrowable"]["BTC"], **{key: after_risk[key] for key in
                ("equity", "initial_margin", "maintenance_margin", "open_order_margin", "available_margin", "rule_id", "rule_version", "catalog_version")}}
        if receipt["risk_evidence"] != risk_receipt:
            raise CreditAuditError("credit_audit_receipt_mismatch", "original financial risk receipt does not replay")
        return {"matches": True, "decision_id": row["decision_id"], "operation_id": payload["operation_id"],
            "risk_before": before_risk, "risk_after": after_risk, "transition": expected.wire(),
            "scope": "dedicated retained credit numerical/operation replay; physical commit/source provenance requires native SQL evidence"}
    except CreditAuditError:
        raise
    except (StorageError, KeyError, ValueError, TypeError, AttributeError, IndexError, OverflowError, RecursionError) as error:
        raise CreditAuditError("credit_audit_invalid", "dedicated credit operation evidence is invalid or unavailable") from error
