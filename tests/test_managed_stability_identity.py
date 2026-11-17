"""Temp metadata/proc-format fixtures and <=3s owned dummy only; no job SQL."""
from copy import deepcopy
import errno
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('stability_identity_prepare', ROOT / 'tools/prepare_managed_stability.py')
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class CohostMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='uta-cohost-metadata-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.job, self.proc = self.root/'job', self.root/'proc'
        self.job.mkdir()
        (self.proc/'sys/kernel/random').mkdir(parents=True)
        (self.proc/'sys/kernel/random/boot_id').write_text(prepare.COHOST_BOOT+'\n')
        self.now = time.time_ns()
        self.meta = dict(environment=dict(commit=prepare.COHOST_SOURCE),
                         configuration=dict(max_directory_bytes=6*1024**3, heartbeat_interval=5))
        self.progress = dict(source_commit=prepare.COHOST_SOURCE, status='running', stored_status='running',
            process_alive=True, directory_bytes=100, observed_ns=self.now-2_000_000_000, heartbeat_age_seconds=.25)
        self.write_metadata()
        # Real self-proc serialization copied into an owned fixture. Only PID,
        # birth and runnable-state tokens are substituted for the literal contract.
        raw_stat = Path('/proc/self/stat').read_text()
        status = Path('/proc/self/status').read_text()
        for pid, birth in (prepare.COHOST_PRODUCER, prepare.COHOST_OBSERVER):
            directory = self.proc/str(pid)
            directory.mkdir()
            fields = raw_stat.rsplit(')', 1)[1].split()
            fields[0], fields[19] = 'S', birth
            (directory/'stat').write_text(f'{pid} (owned-fixture) ' + ' '.join(fields)+'\n')
            (directory/'status').write_text(status)

    def write_metadata(self):
        meta_path=self.job/'job.json'
        meta_path.write_text(json.dumps(self.meta))
        os.utime(meta_path,ns=(self.now-3_000_000_000,self.now-3_000_000_000))
        path = self.job/'progress.json'
        path.write_text(json.dumps(self.progress))
        os.utime(path, ns=(self.now-1_900_000_000, self.now-1_900_000_000))

    def observe(self):
        return prepare.cohost_budget(14*1024**3, _job_root=self.job, _proc_root=self.proc,
                                     _now_ns=self.now, _free_bytes=100*1024**3)

    def test_effective_age_uses_original_report_not_capture_or_file_timestamp(self):
        result = self.observe()
        self.assertEqual(result['effective_heartbeat_age_seconds'], 2.25)
        self.assertEqual(result['producer_progress_age_seconds'], 1.9)
        self.assertTrue(result['metadata_process_gate_passed'])
        self.progress['heartbeat_age_seconds'] = 14
        self.write_metadata()
        os.utime(self.job/'progress.json', ns=(self.now, self.now))
        with self.assertRaisesRegex(ValueError, 'effective_heartbeat_stale'):
            self.observe()

    def test_nonrunning_terminal_and_source_change_are_rejected(self):
        for field, value in [('status','completed'), ('stored_status','paused'),
                             ('process_alive',1), ('source_commit','f'*40)]:
            with self.subTest(field=field):
                previous = self.progress[field]
                self.progress[field] = value
                self.write_metadata()
                with self.assertRaises(ValueError):
                    self.observe()
                self.progress[field] = previous
        self.meta['environment']['commit'] = 'f'*40
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, 'source_changed'):
            self.observe()

    def test_future_stale_and_invalid_clock_or_heartbeat_fail_closed(self):
        for field, value in [('observed_ns',self.now+1), ('observed_ns',self.now-20_000_000_000),
                ('observed_ns',True), ('observed_ns',None), ('heartbeat_age_seconds',float('nan')),
                ('observed_ns',10**100),
                ('heartbeat_age_seconds',float('inf')), ('heartbeat_age_seconds',True), ('heartbeat_age_seconds',-1)]:
            with self.subTest(field=field,value=str(value)):
                previous = self.progress[field]
                self.progress[field] = value
                self.write_metadata()
                with self.assertRaises(ValueError):
                    self.observe()
                self.progress[field] = previous
        self.write_metadata()
        for timestamp in (self.now+1, self.now-20_000_000_000):
            os.utime(self.job/'progress.json', ns=(timestamp,timestamp))
            with self.assertRaises(ValueError):
                self.observe()
        self.write_metadata()
        os.utime(self.job/'job.json',ns=(self.now+1,self.now+1))
        with self.assertRaisesRegex(ValueError,'future'):
            self.observe()

    def test_missing_fields_unstable_read_and_proc_unknown_are_rejected(self):
        path = self.job/'progress.json'
        original = Path.stat
        count = 0
        def changing(target, *args, **kwargs):
            nonlocal count
            if target == path:
                count += 1
                if count == 2:
                    os.utime(path, ns=(self.now-1_000_000_000,self.now-1_000_000_000))
            return original(target, *args, **kwargs)
        with patch.object(Path,'stat',changing), self.assertRaisesRegex(ValueError,'changed_during_read'):
            self.observe()
        self.write_metadata()
        del self.progress['observed_ns']
        self.write_metadata()
        with self.assertRaises(ValueError):
            self.observe()
        self.progress['observed_ns'] = self.now-2_000_000_000
        self.write_metadata()
        (self.proc/str(prepare.COHOST_OBSERVER[0])/'status').unlink()
        with self.assertRaisesRegex(ValueError,'metadata_unavailable'):
            self.observe()

    def test_birth_zombie_uid_and_boot_changes_never_become_healthy(self):
        for pid, _ in (prepare.COHOST_PRODUCER,prepare.COHOST_OBSERVER):
            path=self.proc/str(pid)/'stat'; raw=path.read_text()
            for index,value in ((0,'Z'),(19,'999999999')):
                fields=raw.rsplit(')',1)[1].split(); fields[index]=value
                path.write_text(f'{pid} (owned-fixture) '+' '.join(fields))
                with self.assertRaises(ValueError): self.observe()
                path.write_text(raw)
        status=self.proc/str(prepare.COHOST_PRODUCER[0])/'status'
        raw=status.read_text()
        status.write_text('\n'.join('Uid:\t999999\t999999\t999999\t999999' if line.startswith('Uid:') else line for line in raw.splitlines()))
        with self.assertRaisesRegex(ValueError,'uid_changed'): self.observe()
        status.write_text(raw)
        (self.proc/'sys/kernel/random/boot_id').write_text('other-boot')
        with self.assertRaisesRegex(ValueError,'boot_changed'): self.observe()

    def test_unhealthy_cohost_blocks_before_import_mkdir_popen_or_pidfd(self):
        value=json.loads((ROOT/'benchmarks/profiles/managed-d421df3-pending.json').read_text())
        value['qualification']=dict(status='COMPLETE_ALL_GATES_PASSED',blocked_reason=None,
            all_three_local_passed=True,all_eight_ci_passed=True,independent_new_package_passed=True)
        value['resource_review']=dict(old_observer_floor_approved=True)
        for key in ('plan','amendment'):
            source=ROOT/'benchmarks/plans'/Path(value[key]).name
            target=self.root/source.name; target.write_bytes(source.read_bytes()); value[key]=str(target)
        path=self.root/'profile.json';path.write_text(json.dumps(value))
        self.progress['heartbeat_age_seconds']=14;self.write_metadata()
        def git(command,**kwargs):return value['source_commit']+'\n' if kwargs.get('text') else b''
        with patch.object(prepare,'COHOST_JOB',self.job),patch.object(prepare,'PROC_ROOT',self.proc), \
                patch.object(prepare.time,'time_ns',return_value=self.now), \
                patch.object(prepare.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)), \
                patch.object(prepare.subprocess,'check_output',side_effect=git) as git_probe, \
                patch.object(prepare.importlib,'import_module') as module,patch.object(Path,'mkdir') as mkdir, \
                patch.object(prepare.subprocess,'Popen') as popen,patch.object(prepare.os,'pidfd_open') as pidfd, \
                patch.object(prepare.signal,'pidfd_send_signal') as send:
            with self.assertRaisesRegex(ValueError,'effective_heartbeat_stale'):
                prepare.invoke(path,'smoke-produce',prepare.fingerprint(path))
            for operation in (git_probe,module,mkdir,popen,pidfd,send):operation.assert_not_called()


class SmokePidfdDrainTests(unittest.TestCase):
    def test_unknown_and_protected_expected_identity_has_no_pidfd_or_signal(self):
        with patch.object(prepare.os,'pidfd_open') as opened,patch.object(prepare.signal,'pidfd_send_signal') as sent:
            for identity in ({},dict(pid=4471,birth='210004',boot=prepare.COHOST_BOOT,uid=os.geteuid()),
                    dict(pid=8784,birth='412799',boot=prepare.COHOST_BOOT,uid=os.geteuid()),
                    dict(pid=99999999,birth='1',boot=None,uid=os.geteuid())):
                self.assertFalse(prepare._pidfd_term(identity))
            opened.assert_not_called();sent.assert_not_called()

    def test_owned_dummy_old_birth_and_unknown_do_not_signal_matching_alive_does_and_fd_closes(self):
        beginning=time.monotonic()
        child=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(1.5)'],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True,start_new_session=True)
        try:
            if child.pid in {4471,8784}:
                child.wait(timeout=2)  # Never send any signal to protected numeric PIDs.
                return self.test_owned_dummy_old_birth_and_unknown_do_not_signal_matching_alive_does_and_fd_closes()
            actual=prepare._process_metadata(child.pid)
            identity=dict(pid=child.pid,birth=actual['birth'],uid=os.geteuid(),
                boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
            original_open,original_send=os.pidfd_open,signal.pidfd_send_signal
            descriptors=[]
            def opened(*args):
                descriptor=original_open(*args);descriptors.append(descriptor);return descriptor
            with patch.object(prepare.os,'pidfd_open',side_effect=opened), \
                    patch.object(prepare.signal,'pidfd_send_signal',wraps=original_send) as sent:
                for changes in (dict(birth=str(int(actual['birth'])+1)),dict(boot='other-boot'),dict(uid=os.geteuid()+1)):
                    wrong=dict(identity,**changes)
                    self.assertFalse(prepare._pidfd_term(wrong))
                    self.assertIsNone(child.poll())
                sent.assert_not_called()
                self.assertTrue(prepare._pidfd_term(identity))
                sent.assert_called_once()
                child.wait(timeout=1)
                self.assertEqual(child.returncode,-signal.SIGTERM)
                self.assertFalse(prepare._pidfd_term(identity))
            for descriptor in descriptors:
                with self.assertRaises(OSError) as closed:os.fstat(descriptor)
                self.assertEqual(closed.exception.errno,errno.EBADF)
            self.assertLess(time.monotonic()-beginning,3)
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=1)
            child.stdout.close();child.stderr.close()

    def test_original_drain_requires_boot_uid_and_exact_profile_context(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'observer').mkdir();(root/'control').mkdir()
            (root/'observer/launch.json').write_text(json.dumps(dict(driver_pid=99999999,driver_birth='1')))
            value=dict(smoke_scratch=str(root),source_commit='a'*40)
            with patch.object(prepare.os,'pidfd_open') as opened:
                self.assertFalse(prepare._original_smoke_drain(value,approved_profile_sha256='f'*64))
                (root/'control/outer-budget.json').write_text(json.dumps(dict(profile_sha256='f'*64,source_commit='a'*40)))
                self.assertFalse(prepare._original_smoke_drain(value,approved_profile_sha256='f'*64))
                self.assertFalse(prepare._original_smoke_drain(value,approved_profile_sha256='e'*64))
                opened.assert_not_called()


if __name__=='__main__':unittest.main()
