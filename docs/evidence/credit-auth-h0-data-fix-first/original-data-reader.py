"""Read-only actual constructors on retained original AuthDBs; no authentication."""
import argparse,hashlib,json,pathlib,sys
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--grant',required=True);p.add_argument('--revocation',required=True);p.add_argument('--healthy',required=True);p.add_argument('--result',required=True);a=p.parse_args()
sys.path.insert(0,a.source)
from uta.credit_auth_h0 import CreditNonceStoreV2
from uta.request_signing import SigningError
from uta.storage import StorageError
records=[]
for label,name,want in [('original-grant-red',a.grant,'GRANT_PAYLOAD_COLUMNS'),('original-revocation-red',a.revocation,'REVOCATION_PAYLOAD_COLUMNS'),('original-072-healthy',a.healthy,None)]:
 path=pathlib.Path(name);before=hashlib.sha256(path.read_bytes()).hexdigest();refused=False;reason=None;error_code=None
 try:
  store=CreditNonceStoreV2(path)
  with store._transaction(read=True) as c:store._config(c)
 except SigningError as error:
  refused=True;error_code=error.code
  causes={'retained authentication grant payload differs from columns':'GRANT_PAYLOAD_COLUMNS','retained authentication revocation payload differs from columns':'REVOCATION_PAYLOAD_COLUMNS'}
  reason=causes.get(str(error.__cause__),'UNEXPECTED') if isinstance(error.__cause__,StorageError) else 'UNEXPECTED'
 after=hashlib.sha256(path.read_bytes()).hexdigest()
 records.append({'case':label,'constructor_refused':refused,'typed_error_code':error_code,'reason':reason,'db_main_sha256_before':before,'db_main_sha256_after':after,'db_main_bytes_unchanged':before==after,'expected_behavior_observed':(reason==want and refused) if want is not None else not refused})
report={'source_runtime_commit':'61258109e10f4ea4609e03010d5f25716b2c4256','records':records,'all_expected':all(r['expected_behavior_observed'] and r['db_main_bytes_unchanged'] for r in records),'scope':'read-only actual H0 constructor/config; no HMAC query, repair, data mutation or financial access'}
pathlib.Path(a.result).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
assert report['all_expected']
