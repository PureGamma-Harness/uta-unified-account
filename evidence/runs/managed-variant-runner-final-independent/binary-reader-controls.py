"""Small independent binary-reader bounds, no archive bomb or benchmark."""
import io
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools import run_managed_variants as runner


class Probe(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.requested_sizes = []
    def readline(self, size=-1):
        self.requested_sizes.append(size)
        return super().readline(size)


started = time.monotonic()
records = []
for name, content, options, expected_reads in [
        ('201st_row_rejected_before_202nd_read', b'{}\n'*202, {}, 201),
        ('oversize_line_rejected_before_decode', b'x'*65537, {}, 1),
        ('aggregate_byte_limit_rejected', (b'{"f":"'+b'x'*32+b'"}\n')*2,
         {'maximum_total_bytes':64}, 2)]:
    probe = Probe(content)
    with patch.object(runner.gzip, 'open', return_value=probe):
        try:
            runner.bounded_arrivals(io.BytesIO(), **options)
        except runner.GateError as error:
            message = str(error)
        else:
            raise AssertionError('invalid bounded stream accepted')
    assert len(probe.requested_sizes) == expected_reads
    assert all(0 < size <= 65537 for size in probe.requested_sizes)
    records.append({'control':name,'read_count':len(probe.requested_sizes),
        'maximum_requested_read_bytes':max(probe.requested_sizes),'rejection':message})
result = {'source_commit':'673d3195b65cdb9e3fed2fd1b18dbad789d99b46',
    'controls':records,'elapsed_seconds':time.monotonic()-started,
    'SQL_service_benchmark_or_pressure_executed':False,'production_approved':False}
(OUT/'binary-reader-controls.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,sort_keys=True))
