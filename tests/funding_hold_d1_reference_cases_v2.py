"""Version2 closed synthetic 1024-seed proposal; definitions, never run.

The generator imports neither the oracle nor production.  It constructs raw
wire data, with expectation limited to the declared OK/REJECT/UNSUPPORTED
partition.  Financial expectations live separately in hand-entered cases.
"""
from hashlib import sha256
import json


FAMILIES = ("identity", "stage", "aggregate", "decompose", "backing",
            "wait", "shared_action", "bounds")
LEG = 10 ** 38
MAX_TIME = 2 ** 63 - 1


def clone(value):
    return json.loads(json.dumps(value, ensure_ascii=True, allow_nan=False))


def scope(scale=2, account="synthetic-account"):
    return {"authority_id": "synthetic-authority", "authority_generation": "gen-1",
            "account_id": account, "usd_scale": scale, "settlement_asset": "USD"}


def key(serial=0, account="synthetic-account"):
    return {"schema": 1, "authority_id": "synthetic-authority",
            "authority_generation": "gen-1", "symbol": "SYNTH-" + str(serial),
            "period_end": "2026-01-01T08:00:00+00:00", "interval_seconds": 28800,
            "settlement_asset": "USD", "account_id": account,
            "rule_scope_id": "synthetic-funding-rule-v1"}


def duty_id(value):
    # The published economic-key serialization, not a production helper.
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "funding-duty:v1:" + sha256(raw.encode("ascii")).hexdigest()


def ref(value, kind, digit="a"):
    return {"kind": kind, "digest": digit * 64, "duty_id": duty_id(value),
            "rule_scope_id": value["rule_scope_id"]}


def stage(value, kind, amount=0):
    result = {"kind": kind, "amount_units": amount, "exposure_ref": None,
              "cap_ref": None, "final_ref": None}
    if kind == "EXPOSURE_RATE_PENDING":
        result.update(exposure_ref=ref(value, "EXPOSURE", "a"),
                      cap_ref=ref(value, "CAP", "b"))
    elif kind.startswith("FINAL_"):
        result["final_ref"] = ref(value, "FINAL_CUT", "c")
    return result


def state(serial=0, kind="FINAL_PAYABLE", amount=1200, scale=2, cap=None,
          account="synthetic-account", key_value=None):
    value = key(serial, account) if key_value is None else clone(key_value)
    initial = stage(value, "REGISTERED_UNASSESSED")
    result = {"key": value, "usd_scale": scale, "revision": 0,
              "active": initial, "history": [], "activation_permission": False}
    if kind == "REGISTERED_UNASSESSED":
        return result
    result.update(active=stage(value, kind, amount), history=[initial], revision=1)
    if cap is not None:
        result["history"].append(stage(value, "EXPOSURE_RATE_PENDING", cap))
        result["revision"] = 2
    return result


def base(scale=2, accounting=10000, risk=10000, cash=10000, frozen=0,
         im=2000, mm=1000, reserve=3000):
    return {"scope": scope(scale), "accounting_equity_units": accounting,
            "risk_equity_units": risk, "initial_margin_units": im,
            "maintenance_margin_units": mm, "order_reserve_units": reserve,
            "cash_units": cash, "spot_frozen_units": frozen,
            "funding_components": "EXCLUDED"}


def policy():
    return {"format": 1, "policy_id": "synthetic-wait-30s-q4",
            "clock_policy": "TRUSTED_UTC_PERSISTENT_HIGH_WATERMARK",
            "max_wait_us": 30000000, "min_query_interval_us": 5000000,
            "max_query_attempts": 4,
            "expiry_action": "DEFAULT_REVIEW_PRESERVE_DEBT_FREEZE_AND_OUTBOX"}


def policy_digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(raw.encode("ascii")).hexdigest()


def wait_record(serial=0, start=0, attempts=0, highwater=None, default=False):
    last = None if attempts == 0 else start + (attempts - 1) * 5000000
    observed = max(start, last if last is not None else start) if highwater is None else highwater
    return {"action": {"scope": scope(), "allocation_id": "allocation-" + str(serial)},
            "policy": policy(), "revision": attempts, "started_us": start,
            "deadline_us": start + 30000000, "observed_highwater_us": observed,
            "attempts": attempts, "last_dispatch_us": last,
            "default_review": default}


def request(case_id, op, data):
    return {"schema": 2, "case_id": case_id, "op": op, "input": data}


def stage_request(case_id, current, proposed):
    return request(case_id, "stage_advance", {"state": current, "proposed": proposed,
                   "expected_revision": current["revision"],
                   "expected_active_stage": clone(current["active"])})


def aggregate_request(case_id, states, scale=2):
    return request(case_id, "aggregate", {"states": states, "scope": scope(scale),
                   "basis_complete": True})


def payment_request(case_id, states, cash=10000, frozen=0, prior=True, quote=True, scale=2):
    return request(case_id, "payment_precondition", {"states": states,
                   "scope": scope(scale), "own_duty_id": duty_id(states[0]["key"]),
                   "cash_units": cash, "spot_frozen_units": frozen,
                   "prior_confirmed_settlements_clear": prior,
                   "quote_available": quote, "basis_complete": True})


def wait_request(case_id, record, now=None, dispatch=True):
    return request(case_id, "wait_preview", {"record": record,
                   "now_us": record["observed_highwater_us"] if now is None else now,
                   "expected_revision": record["revision"],
                   "expected_policy_digest": policy_digest(record["policy"]), "dispatch_query": dispatch})


def _valid(family, variant, case_id):
    scale = 2 + variant % 7
    if family == "identity":
        if variant >= 48:
            return request(case_id, "action_identity", {"action": {
                "scope": scope(scale), "allocation_id": "allocation-" + str(variant)}})
        if variant >= 32:
            item = policy()
            item["policy_id"] = "synthetic-policy-" + str(variant)
            item["min_query_interval_us"] = (1, 5000000)[variant % 2]
            item["max_query_attempts"] = 1 + variant % 4
            return request(case_id, "policy_identity", {"policy": item})
        value = key(variant)
        value["interval_seconds"] = (1, 28800, 86400)[variant % 3]
        value["period_end"] = ("2024-02-29T00:00:00+00:00",
                               "2026-01-01T00:00:00+00:00")[variant % 2]
        if variant == 31:
            value["account_id"] = "A" * 128
        return request(case_id, "duty_identity", {"key": value})
    if family == "stage":
        cap = (600, 1, LEG - 1, 0)[variant % 4]
        if variant % 8 < 4:
            current = state(variant, "REGISTERED_UNASSESSED", scale=scale)
            kind = ("EXPOSURE_RATE_PENDING", "FINAL_PAYABLE", "FINAL_RECEIVABLE",
                    "FINAL_ZERO")[variant % 4]
            amount = 0 if kind == "FINAL_ZERO" else max(cap, 1)
        else:
            current = state(variant, "EXPOSURE_RATE_PENDING", cap, scale)
            kind = ("FINAL_PAYABLE", "FINAL_RECEIVABLE", "FINAL_ZERO")[variant % 3]
            amount = min(cap, 246) if kind != "FINAL_ZERO" else 0
            if amount == 0:
                kind = "FINAL_ZERO"
        return stage_request(case_id, current, stage(current["key"], kind, amount))
    if family in ("aggregate", "bounds"):
        count = 1000 if variant == 63 else (0, 1, 2, 4, 8, 16)[variant % 6]
        amount = LEG - 1 if family == "bounds" else (variant + 1) * 17
        states = []
        for index in range(count):
            kind = ("FINAL_PAYABLE", "EXPOSURE_RATE_PENDING", "FINAL_RECEIVABLE",
                    "FINAL_ZERO")[index % 4]
            states.append(state(index, kind, 0 if kind == "FINAL_ZERO" else amount, scale))
        return aggregate_request(case_id, states, scale)
    if family == "decompose":
        cash = -250 if variant % 5 == 0 else 10000 + variant
        frozen = 0 if cash < 0 else (variant % 4) * 1000
        b = base(scale, accounting=(-1 if variant % 3 == 0 else 1) * (10000 + variant),
                 risk=500 - variant * 29, cash=cash, frozen=frozen,
                 im=variant * 13, mm=variant * 5, reserve=variant * 7)
        states = [state(0, "FINAL_PAYABLE", 1200 + variant, scale),
                  state(1, "EXPOSURE_RATE_PENDING", variant * 3, scale),
                  state(2, "FINAL_RECEIVABLE", 2000 + variant, scale)]
        return request(case_id, "decompose", {"base": b, "states": states,
                       "basis_complete": True})
    if family == "backing":
        own = (1200, 500, LEG - 1, 1)[variant % 4]
        cash = (10000, 300, -LEG + 1, 1)[variant % 4]
        frozen = 9500 if variant % 8 == 0 else 0
        states = [state(0, "FINAL_PAYABLE", own, scale),
                  state(1, "EXPOSURE_RATE_PENDING", 1000, scale),
                  state(2, "FINAL_RECEIVABLE", 900, scale)]
        return payment_request(case_id, states, cash, frozen, variant % 3 != 0,
                               variant % 2 == 0, scale)
    if family == "wait":
        attempts = variant % 5
        record = wait_record(variant, start=variant * 100000000, attempts=attempts,
                             default=attempts == 4)
        now = record["observed_highwater_us"] + (0, 4999999, 5000000, 30000000)[variant % 4]
        if variant == 62:
            record["revision"] = MAX_TIME - 1
        if variant == 60:
            record["revision"] = MAX_TIME
        if variant == 63:
            record.update(default_review=True, revision=MAX_TIME)
            now = record["observed_highwater_us"]
        return wait_request(case_id, record, now, variant % 3 != 0)
    if family == "shared_action":
        records = [wait_record(index, attempts=variant % 4) for index in range(variant % 9)]
        return request(case_id, "wait_records", {"records": records})
    raise ValueError("unknown declared generator family")


def _negative(family, variant, case_id):
    option = variant % 8
    status = "REJECT"
    if family == "identity":
        q = _valid(family, variant % 32, case_id)
        value = q["input"]["key"]
        changes = (("schema", True), ("interval_seconds", True),
                   ("interval_seconds", 0), ("interval_seconds", 86401),
                   ("period_end", "2026-01-01T08:00:00Z"),
                   ("period_end", "2026-02-29T08:00:00+00:00"),
                   ("account_id", "A" * 129), ("settlement_asset", "USDT"))
        name, replacement = changes[option]
        value[name] = replacement
        if variant >= 32 and option == 4:
            value["period_end"] = "1969-12-31T00:00:00+00:00"
        if variant >= 32 and option == 5:
            value["interval_seconds"] = 28800
            value["period_end"] = "2026-01-01T07:59:59+00:00"
        if option == 7:
            status = "UNSUPPORTED"
        return q, status
    if family == "stage":
        current = state(0, "EXPOSURE_RATE_PENDING", 600)
        proposed = stage(current["key"], "FINAL_PAYABLE", 246)
        q = stage_request(case_id, current, proposed)
        if option == 0:
            q["input"]["expected_revision"] = 0
        elif option == 1:
            field = "exposure_ref" if variant >= 32 else "cap_ref"
            q["input"]["expected_active_stage"][field]["digest"] = "d" * 64
        elif option == 2:
            if variant >= 32:
                q["input"]["expected_active_stage"]["amount_units"] = 599
            else:
                proposed["amount_units"] = 601
        elif option == 3:
            q = stage_request(case_id, state(0, "FINAL_PAYABLE", 246), proposed)
            if variant >= 32:
                q["input"]["expected_active_stage"]["kind"] = "FINAL_RECEIVABLE"
        elif option == 4:
            proposed["amount_units"] = 0
        elif option == 5:
            current["active"]["cap_ref"] = None
        elif option == 6:
            proposed["final_ref"]["duty_id"] = duty_id(key(999))
        else:
            if variant >= 32:
                del q["input"]["expected_active_stage"]
                q["input"]["expected_active_ref"] = clone(current["active"]["cap_ref"])
            else:
                proposed["kind"] = "APPLIED"
            status = "UNSUPPORTED"
        return q, status
    if family == "aggregate":
        states = [state(0, "FINAL_PAYABLE", 1200)]
        q = aggregate_request(case_id, states)
        if option == 0:
            states.append(clone(states[0]))
        elif option == 1:
            other_key = key(0)
            other_key["rule_scope_id"] = "different-approved-rule-v2"
            states.append(state(kind="FINAL_PAYABLE", amount=700, key_value=other_key))
        elif option == 2:
            q["input"]["basis_complete"] = False
        elif option == 3:
            states[0] = state(0, "REGISTERED_UNASSESSED")
        elif option == 4:
            states[0]["usd_scale"] = 8
        elif option == 5:
            # Only eight such boundary cases; no broad Cartesian expansion.
            q["input"]["states"] = [state(i, "FINAL_ZERO", 0) for i in range(1001)]
        elif option == 6:
            states[0]["active"]["amount_units"] = LEG
        else:
            states[0]["active"]["amount_units"] = -1
        return q, status
    if family == "decompose":
        q = request(case_id, "decompose", {"base": base(),
                    "states": [state()], "basis_complete": True})
        b = q["input"]["base"]
        if option == 0:
            b["funding_components"] = "INCLUDED"
        elif option == 1:
            b["cash_units"] = True
        elif option == 2:
            b["initial_margin_units"] = -1
        elif option == 3:
            b["scope"]["usd_scale"] = 9
        elif option == 4:
            b["spot_frozen_units"] = 10001
        elif option == 5:
            b["cash_units"] = 1.0
        elif option == 6:
            del b["funding_components"]
        else:
            b["unstated_netting"] = True
        return q, status
    if family == "backing":
        q = payment_request(case_id, [state()])
        d = q["input"]
        if option == 0:
            d["own_duty_id"] = duty_id(key(999))
        elif option == 1:
            d["states"][0] = state(kind="FINAL_RECEIVABLE")
        elif option == 2:
            d["spot_frozen_units"] = -1
        elif option == 3:
            d["spot_frozen_units"] = 10001
        elif option == 4:
            d["prior_confirmed_settlements_clear"] = 1
        elif option == 5:
            d["quote_available"] = "true"
        elif option == 6:
            d["basis_complete"] = False
        else:
            d["cash_units"] = LEG
        return q, status
    if family == "wait":
        record = wait_record(start=100000000, attempts=1)
        q = wait_request(case_id, record)
        d = q["input"]
        if option == 0:
            d["now_us"] -= 1
        elif option == 1:
            d["expected_revision"] += 1
        elif option == 2:
            changed = clone(record["policy"])
            changed["max_wait_us"] += 1
            d["expected_policy_digest"] = policy_digest(changed)
        elif option == 3:
            record["started_us"] = MAX_TIME
        elif option == 4:
            record["last_dispatch_us"] = record["deadline_us"]
        elif option == 5:
            if variant >= 32:
                record["revision"] = MAX_TIME
                d["expected_revision"] = MAX_TIME
                d["now_us"] = record["observed_highwater_us"] + 1
            else:
                d["now_us"] = True
        elif option == 6:
            del record["policy"]["clock_policy"]
        else:
            record["policy"]["min_query_interval_us"] = 0
        return q, status
    if family == "shared_action":
        first = wait_record()
        second = clone(first)
        q = request(case_id, "wait_records", {"records": [first, second]})
        if option == 1:
            second["policy"]["policy_id"] = "different-policy"
        elif option == 2:
            first.update(attempts=1, last_dispatch_us=0, revision=1)
        elif option == 3:
            second["action"]["scope"]["usd_scale"] = 8
        elif option == 4:
            second["action"]["claim_generation"] = 2
        elif option == 5:
            second["policy"]["restart_extension"] = 1
        elif option == 6:
            second["policy"]["max_query_attempts"] = 0
        elif option == 7:
            second["policy"]["max_wait_us"] = True
        return q, status
    if family == "bounds":
        if variant < 32:
            q = aggregate_request(case_id, [state()])
            active = q["input"]["states"][0]["active"]
            values = (LEG, -LEG, True, 1.5, "1200", None, [], {})
            active["amount_units"] = values[option]
            return q, status
        operations = ("QTY_MARK_RATE_CAP", "QTY_MARK_RATE_FINAL", "BORROWABLE",
                      "LIVE_VALUATION", "NEW_IM_MM", "MULTI_CURRENCY",
                      "LEDGER_ACK_APPLY", "WHOLE_PERIOD_COMMIT")
        return request(case_id, "unsupported", {"operation": operations[option]}), "UNSUPPORTED"
    raise ValueError("unknown declared generator family")


def case_for_seed(seed):
    if type(seed) is not int or not 0 <= seed < 1024:
        raise ValueError("closed public seed domain is 0 through 1023")
    partition = "valid" if seed < 512 else "negative"
    local = seed % 512
    family = FAMILIES[local // 64]
    variant = local % 64
    case_id = "D1V2-SEED-" + str(seed).zfill(4)
    if partition == "valid":
        q, status = _valid(family, variant, case_id), "OK"
    else:
        q, status = _negative(family, variant, case_id)
    return {"seed": seed, "family": family, "partition": partition,
            "expected_status": status, "request": q,
            "hash_wire": "CODE_CONTRACT_IMPLEMENTED_NOT_RUN", "activation_permission": False}


def iter_cases():
    for seed in range(1024):
        yield case_for_seed(seed)
