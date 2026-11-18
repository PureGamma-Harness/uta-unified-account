"""One pure independent review; no SQL, service, state, signals or load."""
from dataclasses import replace
from decimal import Context, Decimal, Inexact, Overflow, Rounded, localcontext
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace
from wire_contract_v2 import canonical_wire_from_expected_tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from uta.reserve_kernel import ReserveInputs, calculate_reserve
from uta import reserve_integer

spec = importlib.util.spec_from_file_location("frozen_independent_oracle", HERE / "frozen_fraction_oracle.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)

FIELDS = ("quantity", "filled_quantity", "limit_price", "mark_price",
          "initial_margin_rate", "fee_notional", "charged_fee", "fee_rate")
failures, totals = [], {"manual_terms": 0, "oracle_values_and_wire": 0,
                        "fallback_or_exception_compatibility": 0,
                        "fast_path": 0, "fallback_path": 0}
wire_digest = hashlib.sha256()
delegations = 0


def delegate(value):
    global delegations
    delegations += 1
    return calculate_reserve(value)


reserve_integer.calculate_reserve = delegate


def economic(values):
    return ReserveInputs(**{key: Decimal(value) if key in FIELDS else value
                            for key, value in values.items()})


def record_failure(case, problem, **details):
    failures.append({"case": case, "problem": problem, **details})


def eligible(inputs):
    if not isinstance(inputs, ReserveInputs) or type(inputs.usd_scale) is not int:
        return False
    if not 0 <= inputs.usd_scale <= 18:
        return False
    for field in FIELDS:
        value = getattr(inputs, field)
        if type(value) is not Decimal or not value.is_finite():
            return False
        digits = value.as_tuple()
        if len(digits.digits) > 38 or not -18 <= digits.exponent <= 18:
            return False
    return True


def run_value(case, values):
    expected_fraction = oracle.independent_terms(values)["total"]
    expected_wire = oracle.independent_wire(expected_fraction)
    expected_tuple = Decimal(expected_wire).as_tuple()
    expected_wire = canonical_wire_from_expected_tuple(expected_tuple)
    inputs = economic(values)
    start = delegations
    actual = reserve_integer.calculate_integer_reserve(inputs)
    reference = calculate_reserve(inputs)
    fallback = not eligible(inputs)
    if delegations - start != int(fallback):
        record_failure(case, "wrong_branch", delegated=delegations - start, expected=int(fallback))
    totals["fallback_path" if fallback else "fast_path"] += 1
    for name, result in (("candidate", actual), ("unchanged_reference", reference)):
        if (Fraction(result) != expected_fraction or result.as_tuple() != expected_tuple
                or str(result) != expected_wire):
            record_failure(case, "oracle_or_wire_disagreement", implementation=name,
                           expected=expected_wire, actual=str(result),
                           expected_tuple=list(expected_tuple), actual_tuple=list(result.as_tuple()))
    wire_digest.update(json.dumps({"case": case, "values": values,
                                  "expected": expected_wire, "actual": str(actual)},
                                 sort_keys=True).encode() + b"\n")
    totals["oracle_values_and_wire"] += 1


def outcome(function, inputs):
    try:
        value = function(inputs)
    except Exception as error:
        return {"error_type": type(error).__name__, "error_text": str(error)}
    return {"wire": str(value), "tuple": list(value.as_tuple())}


manual = json.loads((HERE / "frozen-manual-cases.json").read_text())["cases"]
for case in manual:
    terms = oracle.independent_terms(case["inputs"])
    for term, expected in case["manual_terms"].items():
        if terms[term] != Fraction(Decimal(expected)):
            record_failure(case["name"], "frozen_manual_term_disagreement", term=term,
                           expected=expected, actual=str(terms[term]))
        totals["manual_terms"] += 1

base = dict(manual[0]["inputs"])
vectors = [("manual/" + case["name"], case["inputs"]) for case in manual]
boundaries = ["0", "-0.000000000000000000", "1E-18", "-1E-18", "1E18", "-1E18",
              "9" * 38, "-" + "9" * 38, "9" * 38 + "E-18", "9" * 38 + "E18",
              "1E-19", "1E19", "9" * 39]
for field in FIELDS:
    for literal in boundaries:
        for scale in (0, 18):
            for reduce_only in (False, True):
                value = dict(base)
                value.update({field: literal, "usd_scale": scale, "reduce_only": reduce_only})
                vectors.append((f"boundary/{field}/{literal}/{scale}/{reduce_only}", value))
for sign in ("", "-"):
    for exponent in (-18, 18):
        value = {name: sign + "9" * 38 + "E" + str(exponent) for name in FIELDS}
        value.update(reduce_only=False, usd_scale=18)
        vectors.append((f"all_fields_extreme/{sign}/{exponent}", value))
wide = dict(base)
wide.update(quantity="9" * 38 + "E18", filled_quantity="-" + "9" * 38 + "E18",
            limit_price="9" * 38 + "E18", mark_price="-" + "9" * 38 + "E-18",
            initial_margin_rate="9" * 38 + "E18", fee_notional="9" * 38 + "E18",
            charged_fee="-" + "9" * 38 + "E-18", fee_rate="9" * 38 + "E18", usd_scale=18)
vectors.append(("wide_intermediate_products", wide))
tiny = {name: "1E-18" for name in FIELDS}
tiny.update(filled_quantity="0", mark_price="0", fee_notional="0", charged_fee="0",
            reduce_only=False, usd_scale=18)
vectors.append(("54_fractional_places_with_18_place_fee_ceiling", tiny))
rng = random.Random(44186589062)
for index in range(400):
    value = {name: str(Decimal((rng.randrange(2),
                              tuple(map(int, str(rng.randrange(10**rng.randrange(1, 39))))),
                              rng.randrange(-18, 19)))) for name in FIELDS}
    value.update(reduce_only=bool(rng.randrange(2)), usd_scale=rng.randrange(19))
    vectors.append((f"seeded/{index}", value))

for precision in (1, 2, 9, 28):
    hostile = Context(prec=precision, Emin=-2, Emax=2)
    hostile.traps[Inexact] = hostile.traps[Rounded] = hostile.traps[Overflow] = True
    with localcontext(hostile):
        for name, value in vectors:
            try:
                run_value(f"precision/{precision}/{name}", value)
            except Exception as error:
                record_failure(f"precision/{precision}/{name}", "unexpected_exception",
                               error_type=type(error).__name__, error_text=str(error))

class DecimalChild(Decimal):
    pass

normal = economic(base)
fallbacks = []
for field in FIELDS:
    for index, value in enumerate((1, "1", 0.5, Fraction(1, 3), DecimalChild("1"),
                                   Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"),
                                   Decimal("-Infinity"), None)):
        fallbacks.append((f"field/{field}/{index}", replace(normal, **{field: value})))
for index, value in enumerate((True, False, -1, 19, 0.5, Decimal(2), "2", None)):
    fallbacks.append((f"scale/{index}", replace(normal, usd_scale=value)))
fallbacks.extend((("duck", SimpleNamespace(**normal.__dict__)) if hasattr(normal, "__dict__")
                  else ("duck", SimpleNamespace(**{name: getattr(normal, name)
                                                   for name in (*FIELDS, "reduce_only", "usd_scale")})),
                 ("missing_object", None)))
for name, inputs in fallbacks:
    before = delegations
    actual = outcome(reserve_integer.calculate_integer_reserve, inputs)
    expected = outcome(calculate_reserve, inputs)
    if actual != expected or delegations - before != 1:
        record_failure(name, "fallback_value_exception_or_delegation_disagreement",
                       actual=actual, expected=expected, delegations=delegations - before)
    totals["fallback_or_exception_compatibility"] += 1

result = {"schema": "uta.reserve_integer_independent_pure.v1",
          "frozen_oracle_commit": "d5a2ac9d1fc24b386c707d6e33b8c3ddc45969d1",
          "source_commit": "057fa65d1d79ae1855e551e73b6f58eeb375197b",
          "wire_contract_revision": "v2 standard Decimal(expected_tuple).__str__",
          "seed": 44186589062, "vectors_per_context": len(vectors),
          "contexts": [1, 2, 9, 28], "totals": totals,
          "value_and_wire_digest": wire_digest.hexdigest(),
          "failures": failures, "passed": not failures,
          "sql_service_financial_state_load": "NOT_RUN",
          "production_approved": False, "persistent_10k_pass": False}
print(json.dumps(result, sort_keys=True))
raise SystemExit(int(bool(failures)))
