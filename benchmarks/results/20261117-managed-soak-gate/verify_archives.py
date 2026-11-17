"""Verify immutable archived JSON/gzip only; no SQLite or process interaction."""
from collections import defaultdict
from fractions import Fraction
import gzip
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
files = events = cases = 0
for folder in ('20261116-managed-smoke', '20261116-managed-smoke-final'):
    base = ROOT / 'benchmarks/results' / folder
    manifest = json.loads((base / 'manifest.json').read_text())
    for name, digest in manifest.get('validation_files_sha256', {}).items():
        assert sha256((base / name).read_bytes()).hexdigest() == digest, name
        files += 1
    for case, record in manifest['cases'].items():
        directory = base / case
        for name, digest in record['sha256'].items():
            assert sha256((directory / name).read_bytes()).hexdigest() == digest, name
            files += 1
        job = json.loads((directory / 'job.json').read_text())
        report = json.loads((directory / 'progress.json').read_text())
        assert job['environment']['commit'] == record['candidate_commit']
        assert report['status'] == 'completed'
        assert report['unresolved_steps'] == report['unresolved_faults'] == 0
        assert all(report[field] is False for field in ('continuous_6h_stability_passed',
            'continuous_24h_stability_passed','capacity_10000_per_s_passed','production_approved'))
        previous, sequence = '0'*64, 0
        segments = json.loads((directory / 'log-segments.json').read_text())['segments']
        for segment in segments:
            path = directory / segment['file']
            assert sha256(path.read_bytes()).hexdigest() == segment['sha256']
            assert segment['first'] == sequence + 1
            with gzip.open(path, 'rt') as stream:
                for line in stream:
                    row = json.loads(line)
                    sequence += 1
                    encoded = json.dumps([sequence,row['kind'],row['payload'],previous],
                                         sort_keys=True,separators=(',',':'),allow_nan=False)
                    digest = sha256(encoded.encode()).hexdigest()
                    assert (row['sequence'],row['previous_hash'],row['event_hash']) == (sequence,previous,digest)
                    previous = digest
            assert sequence == segment['last']
        cold = json.loads((directory / 'cold-audit.json').read_text())
        assert (cold['logs']['events'],cold['logs']['last_hash']) == (sequence,previous)
        with gzip.open(directory / 'financial-snapshot.json.gz', 'rt') as stream:
            data = json.load(stream)['tables']
        rounds = job['planned_rounds']
        assert len(data['uta_orders']) == len(data['uta_fills']) == rounds * 4
        assert len(data['uta_matches']) == rounds * 2
        assert len(data['uta_risk_decisions']) == rounds * 8
        assert len(data['ledger_events']) == 6 + rounds * 5
        assert len({row['trade_id'] for row in data['uta_matches']}) == rounds * 2
        projections, currency, per_event = defaultdict(int), defaultdict(int), defaultdict(int)
        for row in data['ledger_postings']:
            units = int(row['units'])
            projections[row['account'],row['asset']] += units
            currency[row['asset']] += units
            per_event[row['sequence'],row['asset']] += units
        balances = {(row['account'],row['asset']):int(row['units']) for row in data['ledger_balances']}
        assert all(value == 0 for value in currency.values())
        assert all(value == 0 for value in per_event.values())
        assert all(balances.get(key,0) == value for key,value in projections.items())
        assert all(projections.get(key,0) == value for key,value in balances.items())
        for account in job['accounts'][:2]:
            assert balances['customer:'+account,'USD'] == 1_000_000*100_000_000-80_000*rounds
        assert balances['system:fees','USD'] == 160_000*rounds
        assert balances['system:credit-pool','BTC'] == 100_000_000
        assert balances['customer:'+job['accounts'][2],'BTC'] == 100_000_000
        assert not data['uta_positions']
        assert all(Fraction(row['principal']) == Fraction(row['interest']) == 0 for row in data['uta_liabilities'])
        assert all(row['state'] == 'SUCCEEDED' for row in data['uta_command_inbox'])
        assert sum(row['account_id'] is not None for row in data['uta_command_inbox']) == 6*rounds
        decisions = {row['decision_id'] for row in data['uta_risk_decisions']}
        assert all(row['admission_decision_id'] in decisions for row in data['uta_orders'])
        assert all(row['execution_decision_id'] in decisions for row in data['uta_fills'])
        for row in data['uta_fills']:
            assert abs(Fraction(row['quantity'])) == Fraction(1,100)
            assert Fraction(row['price']) == 100 and Fraction(row['fee']) == Fraction(4,10000)
        if 'writer_fence_lease' in data:
            assert all(row['owner_nonce'] is None for row in data['writer_fence_lease'])
        events += sequence
        cases += 1
result = {'archived_cases_verified':cases,'files_sha256_verified':files,'events_rehashed':events,
    'independent_integer_financial_snapshots_verified':cases,'sqlite_connections_opened':0,
    'historical_jobs_rerun':0,'new_smokes_started':0,'long_jobs_started':0,
    'posix_close_release_validated':False,'production_approved':False,
    'scope':'archival integrity and historical synthetic arithmetic only; no live locking test'}
print(json.dumps(result,indent=2))
