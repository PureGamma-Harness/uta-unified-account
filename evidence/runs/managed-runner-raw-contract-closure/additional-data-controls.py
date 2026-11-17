"""Independent bounded JSON-only contract controls; no collector or benchmark."""
from copy import deepcopy
from hashlib import sha256
import gzip
import json
from pathlib import Path
import signal
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools import run_managed_variants as runner
from tests.test_managed_variant_runner import COMMIT, raw_fixture


def rehash(root):
    path = root / 'manifest.json'
    manifest = json.loads(path.read_text())
    for name in manifest['files']:
        data = (root / name).read_bytes()
        manifest['files'][name] = {'bytes':len(data), 'sha256':sha256(data).hexdigest()}
    path.write_text(json.dumps(manifest)+'\n')


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('pure data budget')))
    signal.setitimer(signal.ITIMER_REAL, 2)
    started = time.monotonic()
    records = []
    for control in ('float_nanoseconds', 'boolean_sequence_and_noncanonical_ID',
                    'rejected_receipt_wrong_identity', 'boolean_count_false_as_zero'):
        with TemporaryDirectory(prefix='uta-independent-raw-types-') as temporary:
            root = Path(temporary)
            hashes = raw_fixture(root)
            compressed = root / 'arrivals.jsonl.gz'
            rows = [json.loads(line) for line in gzip.decompress(compressed.read_bytes()).splitlines()]
            if control == 'float_nanoseconds':
                rows[0]['latency_ns'] = float(rows[0]['latency_ns'])
                rows[0]['observed_completion_ns'] = float(rows[0]['observed_completion_ns'])
            elif control == 'boolean_sequence_and_noncanonical_ID':
                rows[1]['sequence'] = True
                rows[1]['command_id'] = rows[1]['receipt']['command_id'] = 'bench:True'
                rows[1]['order_id'] = 'order:True'
            elif control == 'rejected_receipt_wrong_identity':
                rows[9]['receipt']['command_id'] = 'different-original-CID'
                rows[9]['receipt']['account_id'] = 'different-account'
            else:
                path = root / 'summary.json'
                summary = json.loads(path.read_text())
                summary['counts']['financial_success_late'] = False
                path.write_text(json.dumps(summary)+'\n')
            compressed.write_bytes(gzip.compress(b''.join((json.dumps(row)+'\n').encode() for row in rows)))
            rehash(root)
            try:
                result = runner.recompute(root,runner.schedule()[0],hashes,COMMIT)
            except Exception as error:
                outcome = {'accepted':False,'error_type':type(error).__name__,'message':str(error)}
            else:
                outcome = {'accepted':True,'technical_and_deadline_passed':result['technical_and_deadline_passed']}
            records.append({'control':control,'outcome':outcome})
    report = {'source_commit':'673d3195b65cdb9e3fed2fd1b18dbad789d99b46',
        'controls':records,'elapsed_seconds':time.monotonic()-started,
        'SQL_collector_build_install_service_or_benchmark_executed':False,
        'original_jobs_accessed':False,'production_approved':False}
    (OUT/'additional-data-controls.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    signal.setitimer(signal.ITIMER_REAL,0)
    print(json.dumps(report,sort_keys=True))


if __name__=='__main__':
    main()
