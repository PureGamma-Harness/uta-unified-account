
import hashlib,json,time,platform,sys,os
from decimal import Decimal
from pathlib import Path
from uta.reserve_kernel import ReserveInputs,calculate_reserve
from uta.reserve_integer import calculate_integer_reserve
j=json.loads(Path('evidence/reviews/reserve-integer-first/manual-cases.json').read_text())
decimal_fields={'quantity','filled_quantity','limit_price','mark_price','initial_margin_rate','fee_notional','charged_fee','fee_rate'}
values=[ReserveInputs(**{k:Decimal(v) if k in decimal_fields else v for k,v in c['inputs'].items()}) for c in j['cases']]
records=[]
for trial in range(3):
 for name,fn in ([('fraction_reference',calculate_reserve),('integer_candidate',calculate_integer_reserve)] if trial%2==0 else [('integer_candidate',calculate_integer_reserve),('fraction_reference',calculate_reserve)]):
  started=time.perf_counter_ns(); total=0; last=[]
  for n in range(1000):
   for v in values:
    r=fn(v);total+=r.as_tuple().sign
  elapsed=time.perf_counter_ns()-started
  for v in values:last.append(str(fn(v)))
  records.append({'trial':trial,'scope':'PURE_CALCULATION_ONLY','name':name,'completed':len(values)*1000,'elapsed_ns':elapsed,'calls_per_second':len(values)*1000/(elapsed/1e9),'consumer_sign_sum':total,'result_wire_sha256':hashlib.sha256(json.dumps(last,separators=(',',':')).encode()).hexdigest()})
print(json.dumps({'python':sys.version,'platform':platform.platform(),'cpu_affinity':sorted(os.sched_getaffinity(0)),'records':records,'source_unchanged':True,'network_calls':0,'sql_calls':0,'durable_order_acceptance_tested':False,'capacity_10000_per_s_passed':False,'production_approved':False},sort_keys=True))
