"""Collect only synthetic financial/checkpoint evidence; never export auth keys."""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--case', action='append', required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source_root))
from benchmarks.run_managed_soak import audit_job

# This whitelist excludes the auth database/profile/private keys entirely.
TABLES = ('uta_accounts','uta_orders','uta_fills','uta_matches','uta_positions',
    'uta_liabilities','uta_command_inbox','ledger_events','ledger_postings',
    'ledger_balances','credit_commands','uta_audit_capability','uta_market_history',
    'uta_code_artifacts','uta_risk_policies','uta_risk_decisions','writer_fence_events')
manifest = {'synthetic': True, 'real_funds': False, 'cases': {},
            'excluded': ['private/', 'auth database', 'TLS private key', 'signing profile'],
            'capacity_10000_per_s_passed': False, 'production_approved': False}
for item in args.case:
    name, path = item.split('=', 1)
    source, target = Path(path), args.output / name
    target.mkdir(parents=True, exist_ok=True)
    for filename in ('job.json','progress.json','log-segments.json','bootstrap-plan.json'):
        shutil.copyfile(source / filename, target / filename)
    shutil.copytree(source / 'logs', target / 'logs', dirs_exist_ok=True)
    audit = audit_job(source)
    (target / 'cold-audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    connection = sqlite3.connect((source / 'managed/shard-0000.sqlite3').absolute().as_uri()+'?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    connection.execute('BEGIN')
    financial = {'synthetic': True, 'tables': {table: [dict(row) for row in connection.execute('SELECT * FROM "'+table+'" ORDER BY rowid')] for table in TABLES}}
    connection.close()
    connection = sqlite3.connect((source / 'managed/router.sqlite3').absolute().as_uri()+'?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    financial['router_pool_sources'] = [dict(row) for row in connection.execute('SELECT * FROM router_pool_sources')]
    connection.close()
    with (target / 'financial-snapshot.json.gz').open('wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as output:
            output.write((json.dumps(financial, sort_keys=True, separators=(',',':'))+'\n').encode())
    report = json.loads((source/'progress.json').read_text())
    job = json.loads((source/'job.json').read_text())
    manifest['cases'][name] = {'candidate_commit': job['environment']['commit'],
        'duration': job['configuration']['duration'], 'status': report['status'],
        'actual_elapsed': report['elapsed_seconds'], 'faults': report['fault_signals'],
        'sha256': {str(p.relative_to(target)): sha256(p.read_bytes()).hexdigest()
                   for p in sorted(target.rglob('*')) if p.is_file()}}
args.output.mkdir(parents=True, exist_ok=True)
(args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps({name: record['status'] for name,record in manifest['cases'].items()}))
