"""CODE-only finite controller negative fixtures; never run by native entry."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmarks import cross_pilot_native_host as host
from benchmarks import pilot_owned_workers as adapter


class NativeHostGuardContracts(unittest.TestCase):
    def test_protected_ids_reject_before_any_proc_path(self):
        with patch.object(host,'Path',side_effect=AssertionError('unexpected proc access')) as paths:
            for pid in host.DENY:
                with self.subTest(pid=pid),self.assertRaises(ValueError):host.identity(pid)
            paths.assert_not_called()
        for pid in (True,0,-1):
            with self.assertRaises(ValueError):host.allowed(pid)

    def test_same_numeric_pid_cannot_alias_different_birth_or_nonce(self):
        info=dict(pid=999999,start_ticks=1234,boot_id='synthetic-boot',uid=1000)
        birth=dict(host_session='synthetic-session',cohort=0,shard=0,owner_nonce='synthetic-worker')
        held=dict(host_session='synthetic-session',cohort=0,shard=0,owner_nonce='synthetic-worker',
            held_pidfd=True,registered=True,gates_still_closed=True,birth_identity=deepcopy(info))
        host.registered_birth_matches(birth,held,info,'synthetic-session',0,0)
        for field,value in [('start_ticks',1235),('boot_id','other-boot'),('uid',1001)]:
            bad=deepcopy(held);bad['birth_identity'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                host.registered_birth_matches(birth,bad,info,'synthetic-session',0,0)
        bad=deepcopy(held);bad['owner_nonce']='wrong-worker'
        with self.assertRaises(ValueError):host.registered_birth_matches(birth,bad,info,'synthetic-session',0,0)

    def test_ack_prerequisites_are_typed_true_and_gates_closed(self):
        info=dict(pid=999999,start_ticks=1234,boot_id='synthetic-boot',uid=1000)
        birth=dict(host_session='synthetic-session',cohort=0,shard=0,owner_nonce='synthetic-worker')
        good=dict(host_session='synthetic-session',cohort=0,shard=0,owner_nonce='synthetic-worker',
            held_pidfd=True,registered=True,gates_still_closed=True,birth_identity=info)
        for field in ('held_pidfd','registered','gates_still_closed'):
            for value in (False,1,'true'):
                bad=deepcopy(good);bad[field]=value
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    host.registered_birth_matches(birth,bad,info,'synthetic-session',0,0)


class NativeControllerDeltaContracts(unittest.TestCase):
    def test_001_unverified_candidate_is_closed_never_adopted_or_signalled(self):
        base=dict(pid=999999,ppid=888888,start_ticks=1234,boot_id='synthetic-boot',uid=1000,state='S')
        birth=dict(owned_Popen_pid=999999,host_session='session',cohort=0,shard=0,owner_nonce='nonce')
        held=dict(host_session='session',cohort=0,shard=0,owner_nonce='nonce',held_pidfd=True,
                  registered=True,gates_still_closed=True,birth_identity={k:base[k] for k in host.STABLE})
        for field,value in [('ppid',777777),('uid',1001),('start_ticks',1235),('boot_id','other')]:
            owned={};errors=[];bad={**base,field:value}
            with self.subTest(field=field),patch.object(host.os,'pidfd_open',return_value=77), \
                 patch.object(host,'identity',return_value=bad),patch.object(host,'dead',return_value=False), \
                 patch.object(host.os,'geteuid',return_value=1000),patch.object(host.os,'close') as close, \
                 patch.object(host.signal,'pidfd_send_signal') as signal_call:
                with self.assertRaises(ValueError):
                    host.adopt_verified_child(owned,'0:0',birth,held,888888,66,'session',0,0,errors)
                self.assertEqual(owned,{})
                close.assert_called_once_with(77);signal_call.assert_not_called()
        owned={};errors=[]
        with (patch.object(host.os,'pidfd_open',return_value=77),patch.object(host,'identity',side_effect=OSError('fake partial candidate')),
              patch.object(host.os,'close') as close,patch.object(host.signal,'pidfd_send_signal') as signal_call):
            with self.assertRaises(OSError):host.adopt_verified_child(owned,'0:0',birth,held,888888,66,'session',0,0,errors)
            self.assertEqual(owned,{});close.assert_called_once_with(77);signal_call.assert_not_called()

    def test_002_slow_setup_or_stop_record_cannot_spawn_or_signal_past_deadline(self):
        calls=[]
        def delayed_setup_check():calls.append('late stop/fsync check')
        with patch.object(adapter,'monotonic',return_value=12.0),patch.object(adapter.subprocess,'Popen') as popen:
            with self.assertRaises(AssertionError):adapter.guarded_popen(delayed_setup_check,12.0,80.0,args=['never-executed'])
            popen.assert_not_called()
        self.assertEqual(calls,['late stop/fsync check'])
        with patch.object(host,'monotonic_ns',return_value=82_000_000_000),patch.object(host.signal,'pidfd_send_signal') as send:
            with self.assertRaises(TimeoutError):host.signal_owned_before_deadline(77,82_000_000_000)
            send.assert_not_called()
        with patch.object(adapter,'monotonic',return_value=81.0),patch.object(adapter,'monotonic_ns',return_value=82_000_000_000), \
             patch.object(adapter.signal,'pidfd_send_signal') as send:
            with self.assertRaises(TimeoutError):adapter.signal_owned_before_deadline(77,83.0,82_000_000_000)
            send.assert_not_called()

    def test_003_broken_gate_close_is_sticky_but_all_owned_resources_continue(self):
        events=[]
        class BrokenGate:
            closed=False
            @property
            def raw(self):return self
            def flush(self):events.append('flush');raise BrokenPipeError('fake flush')
            def close(self):events.append('gate raw close');raise BrokenPipeError('fake close')
        class ClosedGate:closed=True
        class Handle:
            def send_bytes(self,data):events.append('stop send')
            def close(self):events.append('handle close')
        class Process:
            def __init__(self,pid,stdin):self.pid,self.stdin=pid,stdin
            def wait(self,timeout):events.append('wait '+str(self.pid));return 0
        errors=[];bad=BrokenGate()
        try:bad.flush()
        except BrokenPipeError:errors.append('start_stdin_flush_BrokenPipeError')
        host.close_stdin_no_flush(bad,errors,'parent_stdin')
        host.cleanup_call(errors,'subsequent_wait',lambda:events.append('host wait still reached'))
        self.assertEqual(errors,['start_stdin_flush_BrokenPipeError','parent_stdin_raw_close_BrokenPipeError'])
        owner=adapter.OwnedWorkers.__new__(adapter.OwnedWorkers)
        owner.binding={'outer_cleanup_deadline_ns':82_000_000_000};owner.cleanup_receipts=None;owner.cleanup_errors=[]
        owner.directory=Path('/synthetic-not-used');owner.router=type('Router',(),{'close':lambda self:events.append('router close')})()
        def entry(shard,gate):
            return dict(shard=shard,process=Process(999990+shard,gate),pidfd=77+shard,gate_released=False,
                stdin_gate_released=False,fds=[11+shard],raw_files=[Handle()],cleanup_errors=list(errors) if shard==0 else [],
                stop=Handle(),gate=Handle(),ready=Handle())
        owner.owned=[entry(0,bad),entry(1,ClosedGate())]
        with patch.object(adapter,'monotonic',return_value=1.0),patch.object(adapter.os,'close',side_effect=lambda fd:events.append('fd '+str(fd))), \
             patch.object(adapter,'private_json'),patch.object(adapter.signal,'pidfd_send_signal') as send:
            receipts=owner.close(deadline=2.0)
            send.assert_not_called()
        self.assertIn('wait 999990',events);self.assertIn('wait 999991',events)
        self.assertIn('fd 77',events);self.assertIn('fd 78',events);self.assertIn('router close',events)
        self.assertEqual(receipts[0]['cleanup_error'],'start_stdin_flush_BrokenPipeError')
        self.assertTrue(receipts[0]['reaped']);self.assertEqual(receipts[0]['actual_exit'],0)
        self.assertIsNotNone(receipts[0]['cleanup_error'])  # Late successful wait cannot wash the earlier failure green.


if __name__=='__main__':unittest.main()
