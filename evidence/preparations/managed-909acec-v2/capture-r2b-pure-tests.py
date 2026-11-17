"""Pure fake-directory and literal-clock vectors; no old proc/source/job reads."""
import importlib.util,unittest
from pathlib import Path
S=importlib.util.spec_from_file_location('previous_bounds','/tmp/uta-managed-909-capture-r2-boundary-tests.py')
B=importlib.util.module_from_spec(S);S.loader.exec_module(B)
S2=importlib.util.spec_from_file_location('final_metadata_capture','/tmp/uta-managed-909-fresh-admission-capture-r2b.py')
M=importlib.util.module_from_spec(S2);S2.loader.exec_module(M)
B.M=M
Bounds=B.Bounds
class Clocks(unittest.TestCase):
 def vector(self):
  n=1_794_936_000_000_000_000
  return [n-1_000_000_000,n,n-2_000_000_000,n-3_000_000_000,n-1_900_000_000,n-2_900_000_000,1.,2.]
 def test_normal_and_minimum_heartbeat_lifetime(self):
  v=self.vector();p,l,ep,el,until=M.validate_clocks(*v)
  self.assertEqual((p,l,ep,el),(2.,3.,3.,5.));self.assertEqual(until-v[1],12_000_000_000)
 def test_rollback_latest_is_future_even_while_producer_is_past(self):
  v=self.vector();v[1]-=2_500_000_000;v[0]=v[1]-1;v[2]=v[1]-1;v[4]=v[1]-1;v[3]=v[1]+500_000_000;v[5]=v[1]-1
  with self.assertRaisesRegex(ValueError,'clock_from_future'):M.validate_clocks(*v)
 def test_final_now_cannot_precede_capture_started(self):
  v=self.vector();v[0]=v[1]+1
  with self.assertRaisesRegex(ValueError,'clock_from_future'):M.validate_clocks(*v)
 def test_all_four_original_timestamps_future_rejected(self):
  for field in (2,3,4,5):
   v=self.vector();v[field]=v[1]+1
   with self.subTest(field=field),self.assertRaisesRegex(ValueError,'clock_from_future'):M.validate_clocks(*v)
 def test_negative_nan_bool_heartbeat_and_stale_values_rejected(self):
  for val in (-1,float('nan'),True,31):
   v=self.vector();v[7]=val
   with self.subTest(value=val),self.assertRaises(ValueError):M.validate_clocks(*v)
 def test_producer_clock_skew_and_capture_ttl_rejected(self):
  for field in (0,2,4):
   v=self.vector();v[field]-=20_000_000_000
   with self.subTest(field=field),self.assertRaises(ValueError):M.validate_clocks(*v)
if __name__=='__main__':unittest.main(verbosity=2)
