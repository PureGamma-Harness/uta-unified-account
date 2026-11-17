"""Read only two finished independent revocation-probe AuthDBs and Git/source bytes."""
from contextlib import closing
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--before',type=Path,required=True)
parser.add_argument('--after',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args = parser.parse_args()
started = datetime.now(timezone.utc).isoformat(); mono = time.monotonic_ns()
ref = '072cc77c5a96b48c81a143020ab8ac6c9a794a9b'
def snapshot(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        allowed = {sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_PRAGMA,
                   sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_TRANSACTION}
        def authorizer(action,*_):return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY
        c.set_authorizer(authorizer)
        tables = ['auth_config','auth_keys','auth_nonces','auth_audit','auth_credit_grants',
                  'auth_credit_grant_revocations','auth_credit_acceptances']
        rows = {name:c.execute('SELECT * FROM main.'+name+' ORDER BY 1').fetchall() for name in tables}
        columns = {name:[row[1] for row in c.execute('PRAGMA main.table_info('+name+')')] for name in tables}
        catalogue = c.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name').fetchall()
        fk = c.execute('PRAGMA main.foreign_key_check').fetchall()
        query_only = c.execute('PRAGMA query_only').fetchone()[0]
        c.rollback()
    return rows,columns,catalogue,fk,query_only
before,bcols,bcat,bfk,bqo = snapshot(args.before)
after,acols,acat,afk,aqo = snapshot(args.after)
assert bcols == acols and bcat == acat and bfk == afk == [] and bqo == aqo == 1
revocations = [dict(zip(bcols['auth_credit_grant_revocations'],row)) for row in before['auth_credit_grant_revocations']]
revocations_after = [dict(zip(acols['auth_credit_grant_revocations'],row)) for row in after['auth_credit_grant_revocations']]
differences = [(b['grant_id'],name) for b,a in zip(revocations,revocations_after) for name in b if b[name] != a[name]]
assert differences == [('independent-grant-0','payload')]
assert before['auth_keys'] == after['auth_keys']
assert before['auth_credit_grants'] == after['auth_credit_grants']
old_audit = {row[0]:row for row in before['auth_audit']}
new_audit = {row[0]:row for row in after['auth_audit']}
assert all(new_audit[seq] == row for seq,row in old_audit.items())
old_acceptances = {row[0]:row for row in before['auth_credit_acceptances']}
new_acceptances = {row[0]:row for row in after['auth_credit_acceptances']}
assert all(new_acceptances[identity] == row for identity,row in old_acceptances.items())
paths = subprocess.check_output(['git','ls-tree','-r','--name-only',ref,'--','uta'],cwd=args.source,text=True).splitlines()
runtime = []
for name in paths:
    current = (args.source/name).read_bytes()
    assert current == subprocess.check_output(['git','show',ref+':'+name],cwd=args.source)
    runtime.append({'path':name,'sha256':hashlib.sha256(current).hexdigest()})
result = {'runtime_code_commit':ref,'source_head_at_postcheck':subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.source,text=True).strip(),
 'runtime_pre_and_post_hashes_also_retained_by_probe_launcher':True,'all_current_runtime_bytes_equal_observed_commit':True,
 'runtime_files':runtime,'runtime_file_count':len(runtime),
 'two_finished_private_databases_read_only':True,'query_only_verified':True,
 'consistent_transaction_per_database':True,'statement_authorizer_reads_only':True,
 'both_exact_catalogues_equal':True,'both_foreign_key_checks_empty':True,
 'only_revocation_table_delta_is_one_payload':True,'all_key_rows_unchanged':True,
 'all_original_audit_rows_unchanged':True,'all_original_acceptance_rows_unchanged':True,
 'all_grant_rows_unchanged':True,'before_table_counts':{k:len(v) for k,v in before.items()},
 'after_table_counts':{k:len(v) for k,v in after.items()},
 'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
 'outer_monotonic_ns_before_output_write':time.monotonic_ns()-mono,
 'sql_mode':'SELECT and PRAGMA in one read-only snapshot per finished independent database',
 'financial_scope':False,'production_approved':False}
args.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='runtime_files'}))
