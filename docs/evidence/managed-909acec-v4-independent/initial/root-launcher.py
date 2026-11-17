"""Root's one-phase conditional delegation; run only after exact static review."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import time

def dump(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return sha256(raw).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--phase', required=True, choices=('long-preflight','long-start'))
    p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--expected-spec-sha256', required=True)
    p.add_argument('--expected-runner-sha256', required=True)
    p.add_argument('--independent-review-commit', required=True)
    p.add_argument('--outer-output', required=True, type=Path)
    args = p.parse_args()
    os.umask(0o077)
    raw = args.spec.read_bytes()
    assert sha256(raw).hexdigest() == args.expected_spec_sha256
    spec = json.loads(raw)
    assert spec['phase'] == args.phase
    runner = args.spec.parent/'run_one_long_phase.py'
    assert sha256(runner.read_bytes()).hexdigest() == args.expected_runner_sha256 == spec['runner_sha256']
    profile = Path(spec['profile_file'])
    assert sha256(profile.read_bytes()).hexdigest() == spec['profile_sha256']
    assert spec['source_commit'] == '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
    args.outer_output.mkdir(mode=0o700, exist_ok=False)
    wall, boot = time.time_ns(), time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    root = {'authorized': True, 'scope':'ONE_EXACT_LONG_PHASE_NO_NEXT_PHASE',
            'phase':args.phase,'source_commit':spec['source_commit'],
            'spec_sha256':args.expected_spec_sha256,'runner_sha256':args.expected_runner_sha256,
            'profile_sha256':spec['profile_sha256'],'command_sha256':spec['command_sha256'],
            'private_output':spec['private_output'],
            'long_scratch':json.loads(profile.read_bytes())['long_scratch'],
            'source_boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'issued_wall_ns':wall,'issued_boottime_ns':boot,
            'valid_until_wall_ns':wall+180*10**9,'valid_until_boottime_ns':boot+180*10**9,
            'independent_review_commit':args.independent_review_commit,
            'root_decision':'Only this exact phase once, conditional on a new57e capture, f31 dual-clock/resource guard, durable exact three-SHA phase GO and immediate Popen. No next phase or retry after UNKNOWN.',
            'production_approved':False,'financial_6h_passed':False}
    approval = args.outer_output/'root-approved-phase.json'
    record_hash = dump(approval, root)
    argv = [json.loads(profile.read_bytes())['python'],'-B',str(runner),
            '--spec',str(args.spec),'--root-approved-phase-record',str(approval),
            '--expected-root-record-sha256',record_hash]
    stdout_path, stderr_path = args.outer_output/'runner.stdout', args.outer_output/'runner.stderr'
    with stdout_path.open('xb') as out, stderr_path.open('xb') as err:
        child = subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                                 start_new_session=True,close_fds=True)
        stat = Path('/proc')/str(child.pid)/'stat'
        birth = stat.read_text().rsplit(')',1)[1].split()[19]
        dump(args.outer_output/'root-launcher-Popen.json', {
            'pid':child.pid,'birth':birth,'uid':os.geteuid(),'argv':argv,
            'started_utc':datetime.now(timezone.utc).isoformat(),
            'boot':root['source_boot'],'root_approval_sha256':record_hash})
        # The reviewed runner enforces its own wait and phase bounds and stops
        # only owned wrapper children. An unknown detached start is never retried.
        watchdog = None
        try:
            code = child.wait(timeout=180)
        except subprocess.TimeoutExpired:
            watchdog = 'ROOT_RUNNER_TIMEOUT_UNKNOWN_DO_NOT_REPEAT'
            # This process is still our unreaped new session leader. Detached
            # supervisors are outside it and must be queried before any action.
            os.killpg(child.pid, signal.SIGTERM)
            try:
                code = child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                code = child.wait(timeout=2)
        out.flush(); err.flush(); os.fsync(out.fileno()); os.fsync(err.fileno())
    stdout, stderr = stdout_path.read_bytes(), stderr_path.read_bytes()
    hashes = {name:{'bytes':len(data),'sha256':sha256(data).hexdigest()}
              for name,data in [('stdout',stdout),('stderr',stderr)]}
    value = json.loads(stdout) if code == 0 and watchdog is None and stdout else None
    endpoint = {'wall_ns':time.time_ns(),'boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME)}
    result = {'phase':args.phase,'runner_exit_code':code,'root_watchdog_reason':watchdog,
              'all_descendant_cleanup_proved':False,'raw_private_only':hashes,
              'root_post_stream_close_fsync_read_hash_parse_endpoint':endpoint,
              'result':value,'financial_6h_passed':False,'production_approved':False,
              'next_phase_authorized':False,'serialization_follows_measured_endpoint':True}
    dump(args.outer_output/'root-phase-attestation.json', result)
    print(json.dumps(result), flush=True)
    return code

if __name__ == '__main__':
    raise SystemExit(main())
