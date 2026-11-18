"""Pure fake-scandir boundary fixtures. Never reads old source/proc/job."""
from contextlib import nullcontext
from hashlib import sha256
import importlib.util,json,os,stat,time
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
SPEC=importlib.util.spec_from_file_location('metadata_capture_r2','/tmp/uta-managed-909-fresh-admission-capture-r2.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)
class Bounds(unittest.TestCase):
 def setup_mocks(self,number,dirs=False,deep=False):
  fixed=NS(st_uid=os.geteuid(),st_mode=stat.S_IFDIR|0o700,st_dev=1,st_ino=1)
  file=NS(st_uid=os.geteuid(),st_mode=(stat.S_IFDIR|0o700) if dirs or deep else (stat.S_IFREG|0o600),st_dev=1,st_ino=1,st_size=1,st_blocks=1)
  def scan(fd):
   if deep:return nullcontext(iter([NS(name='child')]))
   return nullcontext((NS(name=str(i)) for i in range(number)) if fd==7 else iter([]))
  opened=[6]
  def op(*args,**kw):
   if deep:opened[0]+=1;return opened[0]
   return 8 if 'dir_fd' in kw else 7
  return fixed,file,scan,op
 def run_case(self,n,dirs=False,deep=False,counter=None):
  fixed,file,scan,op=self.setup_mocks(n,dirs,deep)
  counter=[0] if counter is None else counter
  with patch.object(M.os,'open',side_effect=op) as opened,patch.object(M.os,'fstat',return_value=fixed),patch.object(M.os,'scandir',side_effect=scan),patch.object(M.os,'stat',return_value=file) as stats,patch.object(M.os,'close'):
   error=None;rows=None
   try:rows=M.inventory(Path('/owned-fake'),counter)
   except ValueError as e:error=str(e)
  return error,rows,counter[0],stats.call_count,opened.call_count
 def test_flat_20000_files_exact_accept(self):
  e,rows,count,stats,opened=self.run_case(20000)
  self.assertIsNone(e);self.assertEqual((len(rows),count,stats,opened),(20000,20000,20000,1))
 def test_flat_20001st_file_rejected_before_stat_append(self):
  e,rows,count,stats,opened=self.run_case(20001)
  self.assertEqual(e,'observer_inventory_entry_budget_exceeded');self.assertEqual((count,stats,opened),(20000,20000,1))
 def test_20001_empty_directories_cannot_bypass(self):
  e,rows,count,stats,opened=self.run_case(20001,dirs=True)
  self.assertEqual(e,'observer_inventory_entry_budget_exceeded');self.assertEqual((count,stats,opened),(20000,20000,20001))
 def test_depth_17_rejected_before_opening_child(self):
  e,rows,count,stats,opened=self.run_case(1,deep=True)
  self.assertEqual(e,'observer_inventory_depth_exceeded');self.assertEqual((count,stats,opened),(17,17,17))
 def test_counter_shared_across_multiple_walks(self):
  c=[19999]
  self.assertIsNone(self.run_case(1,counter=c)[0]);self.assertEqual(c,[20000])
  e,rows,count,stats,opened=self.run_case(1,counter=c)
  self.assertEqual(e,'observer_inventory_entry_budget_exceeded');self.assertEqual((count,stats,opened),(20000,0,1))
if __name__=='__main__':unittest.main(verbosity=2)
