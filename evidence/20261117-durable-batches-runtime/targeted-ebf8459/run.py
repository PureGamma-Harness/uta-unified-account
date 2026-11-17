from datetime import datetime, timezone
from hashlib import sha256
import json, os
from pathlib import Path
import subprocess
ROOT=Path('/workspace/uta-durable-batch-runtime')
OUT=Path('/tmp/uta-durable-batches-ebf8459')
executables={'python310':'/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10','python312':'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python','python313-sqlite346':'/usr/bin/python3.13'}
modules=('test_durable_batches','test_durable_batch_process','test_managed_retry_gate','test_managed_benchmark','test_durable_commands','test_writer_fence','test_owned_startup','test_startup_write_contention','test_durable_cli')
def sources():
 return {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for folder in ('uta','tests','benchmarks') for p in sorted((ROOT/folder).rglob('*.py'))}
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
for name,python in executables.items():
 before=sources();start=datetime.now(timezone.utc).isoformat()
 argv=[python,'-W','error::ResourceWarning','-m','unittest',*modules,'-v']
 environment=dict(os.environ,PYTHONPATH='tests')
 with (OUT/(name+'.txt')).open('x') as log:
  done=subprocess.run(argv,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT)
 after=sources();raw=(OUT/(name+'.txt')).read_text()
 report={'source_commit':commit,'started_at':start,'ended_at':datetime.now(timezone.utc).isoformat(),'command_argv':argv,'cwd':str(ROOT),'exit_code':done.returncode,'source_sha256':before,'source_sha256_after':after,'source_unchanged':before==after,'log_sha256':sha256(raw.encode()).hexdigest(),'resource_warning_observed':'ResourceWarning:' in raw or 'Exception ignored in:' in raw,'passed':done.returncode==0 and before==after and 'ResourceWarning:' not in raw and 'Exception ignored in:' not in raw,'scope':'focused only, not full release qualification','production_approved':False}
 (OUT/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'runtime':name,'exit_code':done.returncode,'passed':report['passed'],'finished':report['ended_at']}),flush=True)
