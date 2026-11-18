"""New focused cases; reuse reviewed independent literal definitions only.

The old author 25 and independent 8 test methods are never executed here.
"""
import ast
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import prefix_contract as candidate

SCRIPT=ROOT/"evidence/reviews/prefix-pure-independent/reference_causality_once.py"
tree=ast.parse(SCRIPT.read_bytes(),filename=str(SCRIPT))
constants={"SOURCE","A","B","C","JOB","FLAGS","CHECK_NAMES","LIMITS"}
functions={"cid","fixture","causal_oracle","move_event"}
nodes=[]
for node in tree.body:
    if isinstance(node,ast.Assign):
        targets={n.id for target in node.targets for n in ast.walk(target) if isinstance(n,ast.Name)}
        if targets and targets<=constants:nodes.append(node)
    elif isinstance(node,ast.FunctionDef) and node.name in functions:nodes.append(node)
reference={}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SCRIPT),"exec"),reference)
fixture=reference["fixture"];cid=reference["cid"];move=reference["move_event"]


class PrefixCausalityFixTests(unittest.TestCase):
    def rejected(self,value):
        result=candidate.validate(value)
        self.assertIs(result["contract_consistent"],False,result)
        self.assertTrue(all(v is False for v in result["qualification"].values()))

    def test_01_repay_before_zero_genesis_debt_exists(self):
        value=fixture();move(value,cid(1,"repay"),4)
        self.assertIs(reference["causal_oracle"](value),False)
        self.rejected(value)

    def test_02_borrow_before_pool_funding(self):
        value=fixture();move(value,"initial-loan",4)
        self.assertIs(reference["causal_oracle"](value),False)
        self.rejected(value)

    def test_03_fee_before_customer_funding(self):
        value=fixture();move(value,"f:"+cid(1,"open-buy"),0)
        self.assertIs(reference["causal_oracle"](value),False)
        self.rejected(value)

    def test_04_unknown_declared_v1_limitation(self):
        value=fixture();value["receipt"]["limitations"].append("UNREGISTERED_APPROVAL_SCOPE")
        self.rejected(value)

    def test_05_independent_deposits_can_commute(self):
        value=fixture();move(value,"deposit-bob-usd",0)
        self.assertIs(reference["causal_oracle"](value),True)
        self.assertIs(candidate.validate(value)["contract_consistent"],True)

    def test_06_each_fill_pair_allows_opposite_side_first(self):
        value=fixture()
        for r in (1,2):
            for first,second in (("open-buy","open-sell"),("close-sell","close-buy")):
                i=next(i for i,row in enumerate(value["ledger_events"]) if row["business_id"]=="f:"+cid(r,first))
                j=next(i for i,row in enumerate(value["ledger_events"]) if row["business_id"]=="f:"+cid(r,second))
                value["ledger_events"][i],value["ledger_events"][j]=value["ledger_events"][j],value["ledger_events"][i]
        for i,row in enumerate(value["ledger_events"],1):row["sequence"]=i
        self.assertIs(reference["causal_oracle"](value),True)
        self.assertIs(candidate.validate(value)["contract_consistent"],True)

    def test_07_legal_terminal_ledger_preserves_all_real_authority_false(self):
        result=candidate.validate(fixture())
        self.assertIs(result["contract_consistent"],True,result)
        self.assertTrue(all(v is False for v in result["qualification"].values()))
        for key in ("forensic_audit_performed","real_quiescence_verified","cryptographic_log_chain_verified",
                    "raw_source_or_manifest_authenticated","sql_or_original_data_read"):
            self.assertIs(result[key],False)

    def test_08_close_before_open_pair_is_not_managed_round_order(self):
        value=fixture();move(value,"f:"+cid(1,"close-buy"),6)
        self.rejected(value)

    def test_09_existing_seed_debt_does_not_waive_round_flat_before_repay(self):
        value=fixture();move(value,cid(1,"repay"),8)
        self.assertIs(reference["causal_oracle"](value),True)
        self.rejected(value)

    def test_10_other_opening_debt_profile_cannot_enter_zero_genesis_contract(self):
        value=fixture();value["source"]["opening_principal_satoshi"]=2
        self.rejected(value)


if __name__=="__main__":
    unittest.main()
