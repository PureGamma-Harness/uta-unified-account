import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/"tools"))
from prefix_contract import expected_budget, parse_and_validate, validate
from prefix_synthetic_fixture import fixture


class PrefixContractTests(unittest.TestCase):
    def rejected(self,value):
        actual=validate(value)
        self.assertIs(actual["contract_consistent"],False)
        self.assertTrue(actual["errors"])
        self.assertTrue(all(v is False for v in actual["qualification"].values()))
        self.assertIs(actual["forensic_audit_performed"],False)

    def test_01_hand_computable_gross_budget(self):
        actual=expected_budget(3,2)
        self.assertEqual(actual["remaining_principal_satoshi"],2)
        self.assertEqual(actual["counts"],{"rounds":2,"commands":12,"controls":4,"orders":8,"fills":8,"matches":4,"decisions":16,"credit_events":4,"ledger_events":16})
        self.assertEqual(actual["balances"],{(r["owner"],r["asset"]):r["units"] for r in fixture()["balances"]})
        for asset in ("USD","BTC"):
            self.assertEqual(sum(units for (owner,coin),units in actual["balances"].items() if coin==asset),0)

    def test_02_complete_synthetic_contract_never_issues_real_qualification(self):
        result=parse_and_validate(json.dumps(fixture()))
        self.assertIs(result["contract_consistent"],True,result)
        self.assertTrue(all(v is False for v in result["qualification"].values()))
        for key in ("forensic_audit_performed","real_quiescence_verified","cryptographic_log_chain_verified","raw_source_or_manifest_authenticated","sql_or_original_data_read"):
            self.assertIs(result[key],False)

    def test_03_duplicate_json_key_or_invalid_json_is_structured(self):
        for raw in ('{"schema":1,"schema":2}',b'\xff','{"x":NaN}','[]'):
            self.assertIs(parse_and_validate(raw)["contract_consistent"],False)

    def test_04_exact_integer_strict_incomplete_prefix_boundary(self):
        for n,k in ((3,2.0),(3,True),(3,0),(3,3),(3,4),(True,1),(3.0,2)):
            value=fixture();value["original"].update(planned_rounds=n,completed_prefix_rounds=k);self.rejected(value)

    def test_05_full_schema_missing_or_extra_rejected(self):
        for key in tuple(fixture()):
            value=fixture();del value[key];self.rejected(value)
        value=fixture();value["unregistered"]={};self.rejected(value)

    def test_06_source_version_scope_and_original_state(self):
        for key,item in (("schema","v2"),("scope","production"),("profile","other")):
            value=fixture();value[key]=item;self.rejected(value)
        for state in ("failed","running","unknown"):
            value=fixture();value["original"]["status"]=state;self.rejected(value)

    def test_07_asset_scale_or_version_alias_rejected(self):
        for item in (True,1.0,2):
            value=fixture();value["source"]["model_version"]=item;self.rejected(value)
        value=fixture();value["source"]["asset_scales"]["USD"]=8.0;self.rejected(value)

    def test_08_writer_lifetimes_canonical_and_same_pid_new_birth_legal(self):
        for token in ("0456","４５６","",False,"0"):
            value=fixture();value["quiescence"]["writers"][0]["birth"]=token;self.rejected(value)
        value=fixture();value["quiescence"]["writers"]*=2;self.rejected(value)
        value=fixture();value["quiescence"]["writers"].append({"pid":123,"birth":"457","known_stopped":True})
        self.assertIs(validate(value)["contract_consistent"],True)

    def test_09_boundary_no_unknown_actions_or_boolean_zero(self):
        for key,item in (("unresolved_steps",False),("unresolved_faults",1),("controller_sessions",2),("active_rounds",[3])):
            value=fixture();value["boundary"][key]=item;self.rejected(value)
        value=fixture();value["unknown_actions"]=["response_lost"];self.rejected(value)

    def test_10_round_gap_duplicate_or_unfinished(self):
        for change in (lambda v:v["rounds"].pop(),lambda v:v["rounds"][1].update(sequence=1),lambda v:v["rounds"][1].update(state="ACTIVE")):
            value=fixture();change(value);self.rejected(value)

    def test_11_duplicate_command_identity(self):
        value=fixture();value["commands"][1]=copy.deepcopy(value["commands"][0]);self.rejected(value)

    def test_12_future_foreign_or_unresolved_command(self):
        for update in ({"round":3},{"account":"foreign"},{"result_known":False},{"state":"PENDING"}):
            value=fixture();value["commands"][0].update(update);self.rejected(value)

    def test_13_control_lane_every_origin_effect_and_outcome_checked(self):
        for update in ({"origin":"unknown"},{"asset_impact":True},{"state":"UNKNOWN"},{"result_known":False}):
            value=fixture();value["controls"][0].update(update);self.rejected(value)
        value=fixture();value["controls"].pop();self.rejected(value)

    def test_14_order_direction_quantity_and_reduce_only(self):
        for update in ({"reduce_only":True},{"quantity_satoshi":-2000000},{"filled_satoshi":2000000},{"status":"OPEN"}):
            value=fixture();value["orders"][0].update(update);self.rejected(value)

    def test_15_fill_identity_price_fee_and_unmatched_side(self):
        for update in ({"fee_usd_minor":0},{"price_usd_minor_per_btc":9999999999},{"quantity_satoshi":-1000000}):
            value=fixture();value["fills"][0].update(update);self.rejected(value)
        value=fixture();value["fills"][1]=copy.deepcopy(value["fills"][0]);self.rejected(value)

    def test_16_match_receipt_covers_two_unique_sides(self):
        value=fixture();value["matches"][0]["sell_fill_id"]=value["matches"][0]["buy_fill_id"];self.rejected(value)
        value=fixture();value["matches"][1]["trade_id"]=value["matches"][0]["trade_id"];self.rejected(value)

    def test_17_risk_decision_business_owner_round_and_coverage(self):
        for update in ({"account":"foreign"},{"round":3},{"kind":"UNSUPPORTED"}):
            value=fixture();value["decisions"][0].update(update);self.rejected(value)
        value=fixture();value["decisions"].pop();self.rejected(value)

    def test_18_journal_sequence_posting_ordinal_or_orphan(self):
        value=fixture();value["ledger_events"][1]["sequence"]=1;self.rejected(value)
        value=fixture();value["postings"][1]["ordinal"]=0;self.rejected(value)
        value=fixture();value["postings"][0]["event_id"]="unknown";self.rejected(value)

    def test_19_per_event_currency_conservation(self):
        value=fixture();value["postings"][0]["units"]+=1;self.rejected(value)

    def test_20_compensating_cross_round_fee_shift_cannot_hide_per_fill_error(self):
        value=fixture();first=[r for r in value["postings"] if r["event_id"]=="e:7"]
        second=[r for r in value["postings"] if r["event_id"]=="e:12"]
        first[0]["units"]-=1;first[1]["units"]+=1;second[0]["units"]+=1;second[1]["units"]-=1
        self.rejected(value)

    def test_21_credit_borrow_budget_duplicate_repay_and_gross_debt(self):
        value=fixture();value["credit_events"][1]["amount_satoshi"]=4;self.rejected(value)
        value=fixture();value["credit_events"][-1]=copy.deepcopy(value["credit_events"][-2]);self.rejected(value)
        value=fixture();value["remaining_principal_satoshi"]=0;self.rejected(value)

    def test_22_full_owner_asset_projection_no_hidden_offset_or_duplicate(self):
        value=fixture();value["balances"][0]["units"]-=1;value["balances"][1]["units"]+=1;self.rejected(value)
        value=fixture();value["balances"].append(copy.deepcopy(value["balances"][0]));self.rejected(value)

    def test_23_receipt_incomplete_or_any_qualification_true_refused(self):
        value=fixture();del value["receipt"]["checks"]["independent_reopen_same_watermark"];self.rejected(value)
        for key in tuple(fixture()["receipt"]["qualification"]):
            value=fixture();value["receipt"]["qualification"][key]=True;self.rejected(value)

    def test_24_log_gap_unknown_control_or_changed_end_status(self):
        value=fixture();value["logs"][3]["business_id"]="unknown-control";self.rejected(value)
        value=fixture();value["logs"].pop(2);self.rejected(value)
        value=fixture();value["logs"][-1]["status"]="completed";self.rejected(value)

    def test_25_malformed_nested_fields_and_huge_integer_are_structured(self):
        value=fixture();value["remaining_principal_satoshi"]=10**1000;self.rejected(value)
        value=fixture();value["orders"][0]["step"]={"bad":"shape"};self.rejected(value)
        value=fixture();value["decisions"][0]["business_id"]=[];self.rejected(value)


if __name__=="__main__":
    unittest.main()
