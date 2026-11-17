"""D1 pure/fake tests; KB files, no SQL/native/crypto/services."""
import errno
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('d1_controller',ROOT/'tools/independent_m0_controller.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class D1Contract(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix='m0-d1-pure-');self.addCleanup(self.tmp.cleanup)
        self.private=Path(self.tmp.name)/'private';self.public=Path(self.tmp.name)/'public'
        self.private.mkdir(mode=0o700);self.public.mkdir(mode=0o700)
    def value(self):
        return dict(kind='M0_RESOURCE_DIAGNOSTIC',version=1,phase='CASE_B',scope='PRIVATE_ROOT',operation='ENTRY_LSTAT',
            errno=2,catalogue_label='UNKNOWN',unknown_relative_path_sha256='a'*64,primary_code='resource_missing_non_aux')
    def run_missing(self,path,phase='CASE_B'):
        original=FileNotFoundError(errno.ENOENT,'SECRET_KEY_NONCE_HEADER',str(path))
        def check():
            try:
                m._mark_resource_error(original,'PRIVATE_ROOT','ENTRY_LSTAT',path);raise original
            except FileNotFoundError:
                m.need(False,'resource_missing_non_aux')
        with self.assertRaises(m.ResourceHealthFailure) as caught:m.resource_health_check(self.private,self.public,phase,check)
        return caught.exception,original
    def test_primary_context_is_kept_and_only_safe_fields_published(self):
        target=self.private/'B/SECRET_KEY_NONCE_HEADER.tmp'
        failure,original=self.run_missing(target)
        self.assertEqual(str(failure),'resource_missing_non_aux');self.assertIs(failure.primary_error.__context__,original)
        path=self.public/'resource-diagnostic-CASE_B.json';raw=path.read_bytes();v=json.loads(raw)
        self.assertNotIn(b'SECRET_KEY_NONCE_HEADER',raw);self.assertNotIn(str(self.private).encode(),raw)
        self.assertEqual(v['errno'],2);self.assertEqual(v['scope'],'PRIVATE_ROOT');self.assertEqual(v['operation'],'ENTRY_LSTAT')
        self.assertEqual(v['unknown_relative_path_sha256'],sha256(b'PRIVATE_ROOT\0B/SECRET_KEY_NONCE_HEADER.tmp').hexdigest())
        self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertLessEqual(len(raw),4096)
    def test_known_router_label_does_not_relax_permission_failure(self):
        authority=self.private/'B/workload/authority';authority.mkdir(parents=True)
        main=authority/'router.sqlite3';main.write_bytes(b'synthetic');aux=authority/'router.sqlite3-shm';aux.write_bytes(b'synthetic')
        real=Path.lstat;removed=False
        def lstat(path,*a,**k):
            nonlocal removed
            if path==aux and not removed:
                removed=True;raise PermissionError(errno.EACCES,'SECRET',str(path))
            return real(path,*a,**k)
        with patch.object(Path,'lstat',lstat):
            with self.assertRaises(m.ResourceHealthFailure):m.resource_health_check(self.private,self.public,'CASE_B',lambda:m.resource_usage(self.private,self.public))
        v=json.loads((self.public/'resource-diagnostic-CASE_B.json').read_text())
        self.assertEqual(v['catalogue_label'],'AUTH_ROUTER_SHM');self.assertIsNone(v['unknown_relative_path_sha256'])
        self.assertEqual(v['primary_code'],'RESOURCE_PERMISSION_ERROR');self.assertEqual(v['errno'],13)
    def test_allowed_recovered_shard_sidecar_does_not_write_a_failure(self):
        authority=self.private/'B/workload/authority';authority.mkdir(parents=True)
        (authority/'shard-0000.sqlite3').write_bytes(b'm');aux=authority/'shard-0000.sqlite3-shm';aux.write_bytes(b'x')
        real=Path.lstat;removed=False
        def lstat(path,*a,**k):
            nonlocal removed
            if path==aux and not removed:removed=True;path.unlink();raise FileNotFoundError(errno.ENOENT,'synthetic',str(path))
            return real(path,*a,**k)
        with patch.object(Path,'lstat',lstat):
            value=m.resource_health_check(self.private,self.public,'CASE_B',lambda:m.resource_usage(self.private,self.public))
        self.assertEqual(value['normal'],1);self.assertFalse(list(self.public.iterdir()))
    def test_first_o_excl_record_is_not_overwritten(self):
        self.run_missing(self.private/'first.tmp');path=self.public/'resource-diagnostic-CASE_B.json';raw=path.read_bytes()
        failure,original=self.run_missing(self.private/'second.tmp')
        self.assertEqual(failure.diagnostic_status,'ALREADY_RECORDED');self.assertEqual(path.read_bytes(),raw)
    def test_phase_records_are_separate(self):
        self.run_missing(self.private/'case.tmp','CASE_B');self.run_missing(self.private/'escrow.tmp','ESCROW_B')
        self.assertEqual(len(list(self.public.iterdir())),2)
    def test_record_failure_keeps_primary_and_reports_unavailable(self):
        with patch.object(m,'write_resource_diagnostic',side_effect=PermissionError('SECONDARY_SECRET')):
            failure,original=self.run_missing(self.private/'first.tmp')
        self.assertEqual(str(failure),'resource_missing_non_aux');self.assertIs(failure.primary_error.__context__,original)
        self.assertEqual(failure.diagnostic_status,'UNAVAILABLE');self.assertFalse(list(self.public.iterdir()))
    def test_fsync_failure_quarantines_prefix_and_preserves_primary(self):
        with patch.object(m.os,'fsync',side_effect=OSError(errno.EIO,'SECONDARY_SECRET')):
            failure,original=self.run_missing(self.private/'first.tmp')
        self.assertEqual(failure.diagnostic_status,'UNAVAILABLE');self.assertIs(failure.primary_error.__context__,original)
        self.assertFalse(list(self.public.iterdir()));self.assertTrue((self.private/'resource-diagnostic-incomplete-CASE_B.json').is_file())
    def test_cleanup_budget_is_not_bypassed_for_diagnostics(self):
        with patch.object(m,'_diagnostic_cleanup_bytes',return_value=m.CLEANUP_RESERVE):
            failure,original=self.run_missing(self.private/'first.tmp')
        self.assertEqual(failure.diagnostic_status,'UNAVAILABLE');self.assertFalse(list(self.public.iterdir()))
    def test_complete_diagnostic_is_charged_to_cleanup(self):
        self.run_missing(self.private/'first.tmp');size=(self.public/'resource-diagnostic-CASE_B.json').stat().st_size
        self.assertEqual(m.resource_usage(self.private,self.public),dict(normal=0,escrow=0,cleanup=size,total=size))
    def test_schema_rejects_extra_sensitive_fields_and_nonexact_errno(self):
        for change in ({'path':'SECRET_KEY'},{'headers':'SECRET'},{'nonce':'SECRET'},{'errno':True},{'errno':2.0},{'errno':float('nan')},{'errno':-1},{'errno':4096},{'version':True},{'phase':'SECRET'},{'scope':'SECRET'},{'operation':'SECRET'},{'catalogue_label':'SECRET'},{'primary_code':'SECRET'}):
            with self.subTest(change=change):
                with self.assertRaises(m.GateError):m.validate_resource_diagnostic(dict(self.value(),**change))
    def test_public_manifest_requires_exact_versioned_diagnostic(self):
        self.run_missing(self.private/'first.tmp');path=self.public/'resource-diagnostic-CASE_B.json'
        record=dict(name=path.name,bytes=path.stat().st_size,sha256=m.digest(path))
        m.public_write(self.public,'manifest.json',dict(files=[record],source_commit=m.SOURCE,private_authorities_requests_keys_nonces_signatures_streams_not_uploaded=True))
        self.assertTrue(m.verify_public(self.public))
        value=json.loads(path.read_text());value['key']='SECRET';path.write_text(json.dumps(value))
        manifest=json.loads((self.public/'manifest.json').read_text());manifest['files'][0].update(bytes=path.stat().st_size,sha256=m.digest(path));(self.public/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(m.GateError):m.verify_public(self.public)
    def test_four_original_streams_are_never_modified(self):
        case=self.private/'B';case.mkdir();paths=[case/'driver.stdout',case/'driver.stderr',self.private/'case-owner-B.stdout',self.private/'case-owner-B.stderr']
        for n,path in enumerate(paths):path.write_bytes(b'original-'+bytes([n]))
        before=[path.read_bytes() for path in paths];self.run_missing(self.private/'first.tmp')
        self.assertEqual([path.read_bytes() for path in paths],before)
    def test_ordinary_gate_error_never_echoes_unrecognized_text(self):
        primary=m.GateError('SECRET_KEY_NONCE_HEADER')
        def check():raise primary
        with self.assertRaises(m.ResourceHealthFailure) as caught:m.resource_health_check(self.private,self.public,'CASE_B',check)
        self.assertIs(caught.exception.primary_error,primary);self.assertEqual(str(caught.exception),'UNCLASSIFIED_RESOURCE_ERROR')
        self.assertNotIn(b'SECRET_KEY_NONCE_HEADER',(self.public/'resource-diagnostic-CASE_B.json').read_bytes())
    def test_success_does_not_write_or_change_return_value(self):
        expected=object();self.assertIs(m.resource_health_check(self.private,self.public,'CASE_B',lambda:expected),expected)
        self.assertFalse(list(self.public.iterdir()))
    def test_permission_primary_identity_and_errno_are_preserved(self):
        path=self.private/'B/SECRET.tmp';original=PermissionError(errno.EACCES,'SECRET_KEY_NONCE_HEADER',str(path))
        def check():
            m._mark_resource_error(original,'PRIVATE_ROOT','ENTRY_LSTAT',path);raise original
        with self.assertRaises(m.ResourceHealthFailure) as caught:m.resource_health_check(self.private,self.public,'ESCROW_B',check)
        self.assertIs(caught.exception.primary_error,original);self.assertEqual(str(caught.exception),'RESOURCE_PERMISSION_ERROR')
        value=json.loads((self.public/'resource-diagnostic-ESCROW_B.json').read_text());self.assertEqual(value['errno'],13)
    def test_public_path_does_not_receive_private_database_label(self):
        target=self.public/'case-B-safe/B/workload/authority/router.sqlite3-shm'
        self.run_missing(target);value=json.loads((self.public/'resource-diagnostic-CASE_B.json').read_text())
        self.assertEqual(value['catalogue_label'],'UNKNOWN');self.assertIsNotNone(value['unknown_relative_path_sha256'])
    def test_secondary_quarantine_failure_cannot_replace_primary_or_poison_public(self):
        with patch.object(m.os,'fsync',side_effect=OSError(errno.EIO,'SECONDARY')),patch.object(m.os,'rename',side_effect=PermissionError('SECONDARY')):
            failure,original=self.run_missing(self.private/'first.tmp')
        self.assertIs(failure.primary_error.__context__,original);self.assertEqual(failure.diagnostic_status,'UNAVAILABLE')
        self.assertFalse(list(self.public.iterdir()))
    def test_nested_diagnostic_name_is_not_an_alternative_schema_route(self):
        folder=self.public/'case-B-safe';folder.mkdir();path=folder/'resource-diagnostic-CASE_B.json';path.write_text(json.dumps(self.value()))
        record=dict(name='case-B-safe/'+path.name,bytes=path.stat().st_size,sha256=m.digest(path))
        m.public_write(self.public,'manifest.json',dict(files=[record],source_commit=m.SOURCE,private_authorities_requests_keys_nonces_signatures_streams_not_uploaded=True))
        with self.assertRaises(m.GateError):m.verify_public(self.public)
    def test_optional_prefix_collection_cannot_replace_primary_failure(self):
        with patch.object(m.os,'fsync',side_effect=OSError(errno.EIO,'SECONDARY')),patch.object(m.os,'rename',side_effect=PermissionError('SECONDARY')),patch.object(Path,'unlink',side_effect=PermissionError('SECONDARY')):
            failure,original=self.run_missing(self.private/'first.tmp')
        self.assertIs(failure.primary_error.__context__,original)
        path=self.private/'resource-diagnostic-incomplete-CASE_B.json'
        m.validate_resource_diagnostic(json.loads(path.read_bytes()))
        self.assertFalse((self.public/'resource-diagnostic-CASE_B.json').exists())
        records=[];self.assertEqual(m.collect_resource_diagnostics(self.public,records),'COMPLETE')
        self.assertEqual(records,[]);self.assertEqual(str(failure),'resource_missing_non_aux')
        self.assertEqual(failure.diagnostic_status,'UNAVAILABLE')
        m.public_write(self.public,'manifest.json',dict(files=records,source_commit=m.SOURCE,private_authorities_requests_keys_nonces_signatures_streams_not_uploaded=True))
        self.assertTrue(m.verify_public(self.public))
    def test_link_failure_keeps_full_staging_private(self):
        with patch.object(m.os,'link',side_effect=PermissionError('SECONDARY')):
            failure,original=self.run_missing(self.private/'first.tmp')
        self.assertIs(failure.primary_error.__context__,original);self.assertEqual(failure.diagnostic_status,'UNAVAILABLE')
        self.assertFalse(list(self.public.iterdir()))
        m.validate_resource_diagnostic(json.loads((self.private/'resource-diagnostic-incomplete-CASE_B.json').read_bytes()))
    def test_close_failure_cannot_publish_full_staging(self):
        fdopen=m.os.fdopen
        class CloseFailure:
            def __init__(self,*a,**k):self.stream=fdopen(*a,**k)
            def __enter__(self):return self.stream.__enter__()
            def __exit__(self,*a):self.stream.__exit__(*a);raise OSError(errno.EIO,'SECONDARY_CLOSE')
        with patch.object(m.os,'fdopen',CloseFailure):failure,original=self.run_missing(self.private/'first.tmp')
        self.assertIs(failure.primary_error.__context__,original);self.assertEqual(failure.diagnostic_status,'UNAVAILABLE')
        self.assertFalse(list(self.public.iterdir()))
    def test_committed_record_survives_private_alias_cleanup_failure(self):
        with patch.object(Path,'unlink',side_effect=PermissionError('SECONDARY')):failure,original=self.run_missing(self.private/'first.tmp')
        self.assertEqual(failure.diagnostic_status,'RECORDED');records=[]
        self.assertEqual(m.collect_resource_diagnostics(self.public,records),'COMPLETE');self.assertEqual(len(records),1)
        size=(self.public/'resource-diagnostic-CASE_B.json').stat().st_size
        self.assertEqual(m.resource_usage(self.private,self.public),dict(normal=0,escrow=0,cleanup=2*size,total=2*size))
    def test_single_alias_headroom_cannot_fund_two_alias_publication(self):
        raw=(json.dumps(self.value(),sort_keys=True,separators=(',',':'))+'\n').encode()
        with patch.object(m,'_diagnostic_cleanup_bytes',return_value=m.CLEANUP_RESERVE-len(raw)):
            with self.assertRaisesRegex(m.GateError,'diagnostic_cleanup_cap'):m.write_resource_diagnostic(self.private,self.public,self.value())
        self.assertFalse(list(self.public.iterdir()));self.assertFalse(list(self.private.iterdir()))

if __name__=='__main__':unittest.main()
