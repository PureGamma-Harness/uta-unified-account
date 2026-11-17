"""Controlled metadata-allocation unknown, no physical OOM/SQL/process/load."""
import json,os,sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tests.test_managed_output_budget import OutputIntegrationTests
os.sched_setaffinity(0,{3})
started=monotonic()
case=OutputIntegrationTests()
with TemporaryDirectory() as directory:
    events,producer=case.exercise_one_collect(Path(directory),measure_error=MemoryError('controlled metadata allocation unknown'),control_size=0)
result={'reviewed_source':'c27ced8306009106f9da720179fa53b1080f2c91','control_kind':'explicit measurement MemoryError injected into actual supervisor flow, all children mocked',
    'producer_drain_calls':producer.terminate_owned.call_count,'events':events,
    'expected':'metadata unknown must request owned official drain before technical logging',
    'physical_OOM_or_SQL_or_service_or_child_process_exercised':False,'wall_seconds':monotonic()-started}
assert result['producer_drain_calls']==0
Path(__file__).with_name('memory-unknown-red.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(1)
