"""Pure in-memory file, root-GO hash and clock fixtures; never invoke a phase."""
from copy import deepcopy
from hashlib import sha256
import importlib.util,json
from pathlib import Path
import unittest
from unittest.mock import patch
S=importlib.util.spec_from_file_location('guard','/tmp/uta-managed-909-consume-guard.py');G=importlib.util.module_from_spec(S);S.loader.exec_module(G)
class Guard(unittest.TestCase):
 def fixture(self):
  p={'source_commit':G.SOURCE,'python':'/exact/python','source_root':'/exact/source',
   'qualification':{'status':'COMPLETE_ALL_GATES_PASSED','blocked_reason':None,'all_three_local_passed':True,'all_eight_ci_passed':True,'independent_new_package_passed':True},
   'resource_review':{'old_observer_floor_approved':True}}
  self.pr=json.dumps(p).encode();ph=sha256(self.pr).hexdigest()
  self.cmd=('/exact/python','-B','/exact/source/tools/prepare_managed_stability.py','--profile','/profile.json','--invoke','smoke-observe','--root-go-profile-sha256',ph,'--record','synthetic.json')
  self.w=1_794_936_000_000_000_000;self.b=70_000_000_000_000
  self.r={'source_commit':G.SOURCE,'status':'ADMISSION_METADATA_COMPONENT_PASS_NOT_PHASE_GO','profile_sha256':ph,
   'phase':'smoke-observe','phase_command_sha256':G.command_sha256(self.cmd),'source_boot':G.BOOT,
   'captured_wall_ns':self.w,'captured_boottime_ns':self.b,'valid_until_wall_ns':self.w+10_000_000_000,'valid_until_boottime_ns':self.b+10_000_000_000,
   'original_progress_observed_ns':self.w-2_000_000_000,'original_latest_observed_ns':self.w-3_000_000_000,
   'original_progress_mtime_ns':self.w-2_000_000_000,'original_latest_mtime_ns':self.w-3_000_000_000,
   'original_progress_heartbeat_age_seconds':1.,'original_latest_heartbeat_age_seconds':2.,'fresh_free_bytes':17_448_304_640}
  self.go={'authorized':True,'phase':'smoke-observe','profile_sha256':ph,'command_sha256':G.command_sha256(self.cmd)}
 def call(self,wall=None,boot=None,go=None):
  raw=json.dumps(self.r).encode();self.go['snapshot_sha256']=sha256(raw).hexdigest()
  files={'/profile.json':self.pr,'/snapshot.json':raw}
  with patch.object(Path,'read_bytes',lambda p:files[str(p)]):
   return G.consume_guard('/profile.json',self.cmd,'/snapshot.json',self.go if go is None else go,
    now_wall_ns=self.w+1_000_000_000 if wall is None else wall,now_boottime_ns=self.b+1_000_000_000 if boot is None else boot,current_boot=G.BOOT)
 def test_matching_immutable_binding_and_fresh_dual_clocks(self):
  self.fixture();v=self.call();self.assertTrue(v['fresh_admission_check_passed']);self.assertFalse(v['phase_execution_performed'])
 def test_profilehash_alone_cannot_grant_phase(self):
  self.fixture()
  with self.assertRaisesRegex(ValueError,'specific_phase_root_GO_missing'):self.call(go={'profile_sha256':self.go['profile_sha256']})
 def test_each_exact_root_GO_hash_must_match(self):
  for field in ('profile_sha256','snapshot_sha256','command_sha256'):
   self.fixture();bad=deepcopy(self.go);bad[field]='0'*64
   with self.subTest(field=field),self.assertRaises(ValueError):self.call(go=bad)
 def test_wall_rollback_below_capture_cannot_extend(self):
  self.fixture()
  with self.assertRaisesRegex(ValueError,'clock_rolled_back'):self.call(wall=self.w-1)
 def test_boot_rollback_and_elapsed_over15_reject_even_if_wall_looks_fresh(self):
  for offset in (-1,16_000_000_000):
   self.fixture();self.r['valid_until_boottime_ns']=self.b+100_000_000_000
   with self.subTest(offset=offset),self.assertRaisesRegex(ValueError,'clock_rolled_back'):self.call(boot=self.b+offset)
 def test_original_latest_future_and_recomputed_hb_expired_reject(self):
  self.fixture();self.r['original_latest_observed_ns']=self.w+2_000_000_000
  with self.assertRaisesRegex(ValueError,'timestamp_from_future'):self.call()
  self.fixture();self.r['original_latest_heartbeat_age_seconds']=29.
  with self.assertRaisesRegex(ValueError,'heartbeat_or_mtime_stale'):self.call()
 def test_snapshot_expiry_and_phase_replay_reject(self):
  self.fixture()
  with self.assertRaisesRegex(ValueError,'admission_expired'):self.call(wall=self.w+10_000_000_000)
  self.fixture();self.r['phase']='smoke-produce'
  with self.assertRaisesRegex(ValueError,'phase_snapshot_binding'):self.call()
if __name__=='__main__':unittest.main(verbosity=2)
