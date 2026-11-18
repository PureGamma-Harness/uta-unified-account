"""N=3/K=2 hand-case builder; no SQL, real receipts or finance-core imports."""
from prefix_contract import SOURCE, QUALIFICATION, CHECKS


def fixture():
    job="manual-n3-k2";a="managed-soak-alice";b="managed-soak-bob";c="managed-soak-credit"
    value={"schema":"uta.synthetic_prefix_contract_input.v1","scope":"synthetic_json_contract_only",
        "profile":"909-three-account-usd-btc8-linear-synthetic",
        "original":{"job_id":job,"source_commit":SOURCE,"status":"paused","planned_rounds":3,"completed_prefix_rounds":2},
        "source":{"synthetic_only":True,"model_version":1,"asset_scales":{"USD":8,"BTC":8},"manifest_claimed_verified":True},
        "quiescence":{"synthetic_declaration_only":True,"writers":[{"pid":123,"birth":"456","known_stopped":True}]},
        "boundary":{"controller_sessions":1,"unresolved_steps":0,"unresolved_faults":0,"active_rounds":[],"ended_status":"paused"},
        "unknown_actions":[],"positions":[],"remaining_principal_satoshi":2,
        **{name:[] for name in ("rounds","commands","controls","orders","fills","matches","decisions","credit_events","ledger_events","postings","balances","logs")}}
    def cid(r,step):return f"ms:{job}:r{r:09d}:{step}"
    def journal(kind,business,rows):
        seq=len(value["ledger_events"])+1;eid=f"e:{seq}"
        value["ledger_events"].append({"sequence":seq,"event_id":eid,"kind":kind,"business_id":business})
        for ordinal,(owner,asset,units) in enumerate(rows):
            value["postings"].append({"event_id":eid,"ordinal":ordinal,"owner":owner,"asset":asset,"units":units})
        return eid
    def log(kind,r=None,state=None,bid=None):
        i=len(value["logs"])+1;value["logs"].append({"sequence":i,"previous_sequence":i-1,"kind":kind,"round":r,"status":state,"business_id":bid})
    for account,business in ((a,"deposit-alice-usd"),(b,"deposit-bob-usd"),(c,"deposit-credit-usd")):
        journal("DEPOSIT",business,[("customer:"+account,"USD",100000000000000),("system:custody","USD",-100000000000000)])
    journal("DEPOSIT","deposit-credit-btc",[("customer:"+c,"BTC",100000000),("system:custody","BTC",-100000000)])
    pool=journal("POOL_FUNDED","initial-pool",[("system:credit-pool","BTC",100000000),("system:credit-capital","BTC",-100000000)])
    loan=journal("BORROWED","initial-loan",[("customer:"+c,"BTC",6),("system:credit-pool","BTC",-6),
        ("liability:principal:"+c,"BTC",-6),("system:credit-principal-receivable","BTC",6)])
    value["credit_events"]=[{"command_id":"initial-pool","kind":"POOL_FUNDED","amount_satoshi":100000000,"journal_event_id":pool},
        {"command_id":"initial-loan","kind":"BORROWED","amount_satoshi":6,"journal_event_id":loan}]
    log("INITIALIZED");log("CONTROLLER_STARTED")
    for r in (1,2):
        log("ROUND_STARTED",r);value["rounds"].append({"sequence":r,"state":"DONE"})
        for suffix,kind,origin,logkind in (("market","PUBLISH_MARKET","ROUND_FEED","CONTROL_MARKET_TERMINAL"),
                ("activate","SET_HALT","ROUND_ACTIVATION","CONTROL_ACTIVATION_TERMINAL")):
            control_id=f"ctl:{job}:r{r:09d}:{suffix}"
            value["controls"].append({"control_id":control_id,"round":r,"kind":kind,"origin":origin,"state":"SUCCEEDED","result_known":True,"asset_impact":False})
            log(logkind,r,bid=control_id)
        for step,owner in (("open-buy",a),("open-sell",b),("cancel-partial",a),("close-sell",a),("close-buy",b),("repay",c)):
            value["commands"].append({"command_id":cid(r,step),"round":r,"step":step,"account":owner,"state":"SUCCEEDED","result_known":True})
        for step,owner,qty,filled,status,reduce in (("open-buy",a,2000000,1000000,"CANCELLED",False),
                ("open-sell",b,-1000000,-1000000,"FILLED",False),("close-sell",a,-1000000,-1000000,"FILLED",True),
                ("close-buy",b,1000000,1000000,"FILLED",True)):
            oid=cid(r,step);fid="f:"+oid
            value["orders"].append({"order_id":oid,"account":owner,"round":r,"step":step,"quantity_satoshi":qty,"filled_satoshi":filled,"status":status,"reduce_only":reduce})
            value["fills"].append({"fill_id":fid,"order_id":oid,"account":owner,"quantity_satoshi":filled,"price_usd_minor_per_btc":10000000000,"fee_usd_minor":40000,"realized_pnl_usd_minor":0})
            for kind,bid,prefix in (("ORDER_ACCEPTED",oid,"order"),("FILL_CONFIRMED",fid,"fill")):
                value["decisions"].append({"decision_id":f"d:{prefix}:{oid}","kind":kind,"business_id":bid,"account":owner,"round":r})
            journal("FILL_FEE",fid,[("customer:"+owner,"USD",-40000),("system:fees","USD",40000)])
        for phase,buy,sell in (("open","open-buy","open-sell"),("close","close-buy","close-sell")):
            value["matches"].append({"trade_id":f"m:{job}:{r}:{phase}","round":r,"phase":phase,"buy_fill_id":"f:"+cid(r,buy),"sell_fill_id":"f:"+cid(r,sell),"quantity_satoshi":1000000,"price_usd_minor_per_btc":10000000000})
        repayment=journal("REPAID",cid(r,"repay"),[("customer:"+c,"BTC",-2),("system:credit-pool","BTC",2),
            ("liability:principal:"+c,"BTC",2),("system:credit-principal-receivable","BTC",-2)])
        value["credit_events"].append({"command_id":cid(r,"repay"),"kind":"REPAID","amount_satoshi":2,"journal_event_id":repayment})
        log("ROUND_DONE",r)
    log("CONTROLLER_ENDED",state="paused")
    value["balances"]=[{"owner":owner,"asset":asset,"units":units} for owner,asset,units in (
        ("customer:"+a,"USD",99999999840000),("customer:"+b,"USD",99999999840000),("customer:"+c,"USD",100000000000000),
        ("system:fees","USD",320000),("system:custody","USD",-300000000000000),("customer:"+c,"BTC",100000002),
        ("system:credit-pool","BTC",99999998),("liability:principal:"+c,"BTC",-2),("system:credit-principal-receivable","BTC",2),
        ("system:custody","BTC",-100000000),("system:credit-capital","BTC",-100000000))]
    value["receipt"]={"schema":"uta.completed_prefix_forensic_receipt.v1","mode":"completed_prefix_forensic",
        "scope":"quiescent_completed_prefix_only_original_job_incomplete","execution_status":"PREFIX_VERIFIED",
        "audit_authorization":"GRANTED","original_source_commit":SOURCE,"original_job_status":"paused",
        "planned_rounds":3,"completed_prefix_rounds":2,"reviewed_manifest_sha256":"a"*64,"checks":{key:True for key in CHECKS},
        "qualification":dict(QUALIFICATION),"limitations":["ORIGINAL_JOB_INCOMPLETE","NO_PRODUCTION_APPROVAL"],
        "new_original_data_write":False,"receipt_is_original_strict_cold":False}
    return value
