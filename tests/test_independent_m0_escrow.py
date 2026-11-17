"""Pure contract/negative tests. Real crypto has its separate tiny fixture."""
from contextlib import redirect_stdout
from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
e=load('pure_escrow',ROOT/'tools/m0_stream_escrow.py')
c=load('pure_escrow_controller',ROOT/'tools/independent_m0_controller.py')

class EscrowContract(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix='m0-pure-escrow-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.binding=dict(format=1,source_commit=e.SOURCE,control_commit='a'*40,
            controller_sha256='b'*64,run_id='123456',run_attempt='1',case='B',stream='driver.stdout',
            recipient_spki_sha256=e.SPKI_SHA,capture_complete=True)
        self.plain=self.root/'container.bin';self.raw=b'synthetic-only\x00\xff\r\n'
        self.plain.write_bytes(e.container_header(self.binding,len(self.raw),sha256(self.raw).hexdigest())+self.raw)
    def test_complete_binary_stream_container(self):
        self.assertEqual(e.validate_decrypted_container(self.plain,self.binding)['bytes'],len(self.raw))
    def test_empty_stream_is_still_authenticated(self):
        self.plain.write_bytes(e.container_header(self.binding,0,sha256(b'').hexdigest()))
        self.assertEqual(e.validate_decrypted_container(self.plain,self.binding)['bytes'],0)
    def test_no_arguments_default_is_prep_without_openssl(self):
        with patch.object(e.subprocess,'run',side_effect=AssertionError('openssl')),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(e.main([]),0)
        self.assertEqual(json.loads(out.getvalue())['status'],'PREP_ONLY')
    def test_cross_run_control_case_stream_recipient_binding_rejected(self):
        for field,value in [('run_id','999'),('control_commit','c'*40),('controller_sha256','d'*64),('case','P'),('stream','driver.stderr'),('recipient_spki_sha256','e'*64)]:
            with self.subTest(field=field):
                expected=dict(self.binding,**{field:value})
                with self.assertRaisesRegex(e.EscrowError,'container_binding_mismatch'):e.validate_decrypted_container(self.plain,expected)
    def test_changed_raw_bytes_rejected(self):
        self.plain.write_bytes(self.plain.read_bytes()[:-1]+b'x')
        with self.assertRaisesRegex(e.EscrowError,'container_stream_hash'):e.validate_decrypted_container(self.plain,self.binding)
    def test_container_trailing_bytes_rejected(self):
        with self.plain.open('ab') as stream:stream.write(b'x')
        with self.assertRaises(e.EscrowError):e.validate_decrypted_container(self.plain,self.binding)
    def test_oversized_header_before_allocation(self):
        self.plain.write_bytes(e.MAGIC+struct.pack('>I',e.HEADER_CAP+1))
        with self.assertRaisesRegex(e.EscrowError,'container_header_cap'):e.validate_decrypted_container(self.plain,self.binding)
    def test_bool_and_extra_header_binding_fields_rejected(self):
        for binding in (dict(self.binding,format=True),dict(self.binding,run_attempt=1),dict(self.binding,private_nonce='synthetic')):
            with self.subTest(binding=binding):
                with self.assertRaises(e.EscrowError):e.container_header(binding,0,sha256(b'').hexdigest())
    def test_failed_authentication_never_parses_partial_plaintext(self):
        quarantine=self.root/'quarantine'
        def failed(argv,**kwargs):
            kwargs['stdout'].write(b'UNAUTHENTICATED-PARTIAL')
            return SimpleNamespace(returncode=4)
        with patch.object(e.subprocess,'run',failed),patch.object(e,'validate_decrypted_container',side_effect=AssertionError('must not parse')):
            with self.assertRaisesRegex(e.EscrowError,'authenticated_decrypt_failed_do_not_parse'):
                e.decrypt_authenticated(self.root/'dummy.cms',self.root/'public.pem',self.root/'toy-key-only.pem',quarantine,self.binding)
        self.assertEqual((quarantine/'unaccepted-container.bin').read_bytes(),b'UNAUTHENTICATED-PARTIAL')
        self.assertEqual((quarantine/'unaccepted-container.bin').stat().st_mode&0o777,0o600)
        self.assertEqual(quarantine.stat().st_mode&0o777,0o700)
    def test_modified_recipient_rejected_before_openssl(self):
        cert=self.root/'not-recipient.pem';cert.write_bytes(b'synthetic')
        with patch.object(e.subprocess,'run',side_effect=AssertionError('must reject first')):
            with self.assertRaisesRegex(e.EscrowError,'recipient_pem_changed'):e.certificate_identity(cert)
    def test_stream_symlink_rejected_before_crypto(self):
        link=self.root/'link';link.symlink_to(self.plain)
        with patch.object(e.subprocess,'Popen',side_effect=AssertionError('crypto')):
            with self.assertRaises(OSError):e.encrypt_closed_stream(link,self.root/'out.cms',self.root/'public.pem',self.binding)
    def test_resource_compartments_are_disjoint(self):
        private=self.root/'private';public=self.root/'public';private.mkdir();public.mkdir()
        (private/'authority.sqlite').write_bytes(b'123')
        cipher=public/'escrow-B-safe';cipher.mkdir();(cipher/'driver.stdout.cms').write_bytes(b'12345')
        (private/'escrow-completed-B.json').write_bytes(b'12')
        self.assertEqual(c.resource_usage(private,public),dict(normal=3,escrow=5,cleanup=2,total=10))
    def test_escrow_namespace_cannot_hold_db(self):
        private=self.root/'private';public=self.root/'public';private.mkdir();public.mkdir()
        cipher=public/'escrow-B-safe';cipher.mkdir();(cipher/'authority.sqlite').write_bytes(b'')
        with self.assertRaisesRegex(c.GateError,'escrow_file_scope'):c.resource_usage(private,public)
    def test_new_budget_is_explicit_and_legacy_record_preserved(self):
        self.assertEqual(c.MIN_FREE,2348810240);self.assertEqual(c.LEGACY_MIN_FREE,2214592512)
        self.assertEqual(c.TOTAL_CAP,192*1024**2);self.assertEqual(c.AGGREGATE_CAP,64*1024**2)
        self.assertEqual(c.ESCROW_CAP,96*1024**2);self.assertEqual(c.CLEANUP_RESERVE,32*1024**2)
    def test_no_sql_or_product_import(self):
        self.assertFalse(any(n=='uta' or n.startswith('uta.') or n=='sqlite3' for n in sys.modules))
    def helper_fixture(self, failed_stream=None):
        private=self.root/'private';public=self.root/'public';private.mkdir();public.mkdir();(private/'B').mkdir()
        for stream in e.STREAMS:
            path=private/'B'/stream if stream.startswith('driver.') else private/('case-owner-B.'+stream.split('.')[-1])
            path.write_bytes(b'synthetic-closed')
        descriptor=private/'escrow-context-B.json'
        descriptor.write_text(json.dumps(dict(format=1,case='B',private=str(private),public=str(public),control_commit='a'*40,
            controller_sha256='b'*64,run_id='123456',run_attempt='1',parent_pid=os.getppid(),parent_birth_ticks=88,
            closed_producers=True,capture_complete={name:True for name in e.STREAMS},aggregate_existing_bytes=0,
            aggregate_cap=c.ESCROW_CAP,cleanup_cap=c.CLEANUP_RESERVE)));descriptor.chmod(0o600)
        actual_read=Path.read_text
        def read(path,*args,**kwargs):
            if str(path)==f'/proc/{os.getppid()}/stat':return '123 (synthetic) '+' '.join(['S']+['0']*18+['88'])
            return actual_read(path,*args,**kwargs)
        def encrypt(path,output,certificate,binding):
            if binding['stream']==failed_stream:raise e.EscrowError('synthetic_encrypt_failure')
            output.write_bytes(b'synthetic-cipher-'+binding['stream'].encode())
            return dict(name=output.name,bytes=output.stat().st_size,sha256=e.digest_file(output),recipient_spki_sha256=e.SPKI_SHA,
                algorithm='CMS_AUTH_ENVELOPED_DATA_AES256GCM_RSA_OAEP_SHA256',origin_authenticated_by_recipient_encryption=False)
        with patch.object(Path,'read_text',read),patch.object(e.os,'getsid',return_value=os.getpid()),patch.object(e.os,'getpgrp',return_value=os.getpid()),\
                patch.object(e,'certificate_identity',return_value={'public_spki_der_sha256':e.SPKI_SHA}),patch.object(e,'encrypt_closed_stream',encrypt),\
                patch.dict(os.environ,{'RUNNER_TEMP':str(self.root)}),redirect_stdout(io.StringIO()):
            code=e.main(['--encrypt-case',str(descriptor)])
        return code,private,public,json.loads((private/'escrow-completed-B.json').read_text())
    def test_four_closed_streams_are_exact_allowlist(self):
        code,private,public,result=self.helper_fixture()
        self.assertEqual(code,0);self.assertEqual(result['status'],'PASS')
        self.assertEqual({p.name for p in (public/'escrow-B-safe').iterdir()},{name+'.cms' for name in e.STREAMS})
        self.assertFalse(result['all_transitive_native_streams_claimed']);self.assertFalse(result['origin_authenticated_by_recipient_encryption'])
        self.assertEqual(c.resource_usage(private,public)['escrow'],sum(p.stat().st_size for p in (public/'escrow-B-safe').iterdir()))
    def test_one_encrypt_failure_preserves_other_three_and_unknown(self):
        code,private,public,result=self.helper_fixture('driver.stderr')
        self.assertEqual(code,1);self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(len(result['files']),3)
        self.assertEqual(len(list((public/'escrow-B-safe').iterdir())),3)
        self.assertTrue((private/'B/driver.stderr').is_file())
    def test_closed_producers_required_before_owner_or_crypto(self):
        result=c.escrow_closed_case(SimpleNamespace(),Path('/synthetic'),self.root,self.root,'B',{},
            {'control_commit':'a'*40},[3],lambda:None)
        self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['error_code'],'closed_case_producers_unproven')
    def test_ciphertext_manifest_allows_only_fixed_stream_names(self):
        public=self.root/'public-manifest';public.mkdir()
        folder=public/'escrow-B-safe';folder.mkdir();cipher=folder/'driver.stdout.cms';cipher.write_bytes(b'synthetic')
        record=dict(name='escrow-B-safe/driver.stdout.cms',bytes=cipher.stat().st_size,sha256=e.digest_file(cipher))
        c.public_write(public,'manifest.json',dict(files=[record],source_commit=c.SOURCE,private_authorities_requests_keys_nonces_signatures_streams_not_uploaded=True))
        self.assertTrue(c.verify_public(public))
        (folder/'private.sqlite.cms').write_bytes(b'synthetic')
        with self.assertRaises(c.GateError):c.verify_public(public)

if __name__=='__main__':unittest.main()
