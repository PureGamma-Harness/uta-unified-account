"""Explicit <=64KiB synthetic CMS fixture; never reads actual recipient key."""
from datetime import datetime,timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

MODULE=Path(__file__).resolve().with_name('m0_stream_escrow.py')
spec=importlib.util.spec_from_file_location('synthetic_escrow_fixture',MODULE)
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)

def main():
    directory=Path(sys.argv[1]);e.need(directory.is_absolute() and not directory.exists(),'new_fixture_directory')
    directory.mkdir(mode=0o700);os.umask(0o077)
    started=time.monotonic_ns();report={'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'module_sha256':sha256(MODULE.read_bytes()).hexdigest(),'synthetic_only':True,
        'actual_recipient_private_key_read':False,'actual_financial_SQL_native_profile_Actions':False,
        'production_approved':False,'checks':[]}
    def command(label,argv):
        value=subprocess.run(argv,capture_output=True,timeout=10)
        (directory/(label+'.stdout')).write_bytes(value.stdout);(directory/(label+'.stderr')).write_bytes(value.stderr)
        e.need(value.returncode==0,'fixture_command_failed_'+label)
        return value.stdout
    try:
        toy_key=directory/'toy-private.pem';toy_cert=directory/'toy-public.pem'
        command('toy-keygen',['openssl','req','-x509','-newkey','rsa:2048','-sha256','-days','1','-nodes',
            '-subj','/CN=synthetic-m0-fixture-only','-keyout',str(toy_key),'-out',str(toy_cert)])
        e.need(toy_key.stat().st_mode&0o777==0o600,'toy_key_mode')
        der=command('toy-der',['openssl','x509','-in',str(toy_cert),'-outform','DER'])
        pub=command('toy-pub',['openssl','x509','-in',str(toy_cert),'-pubkey','-noout'])
        spki=subprocess.run(['openssl','pkey','-pubin','-outform','DER'],input=pub,capture_output=True,check=True,timeout=3).stdout
        fingerprint=sha256(spki).hexdigest()
        identity=e.certificate_identity(toy_cert,expected_pem=e.digest_file(toy_cert),expected_spki=fingerprint,expected_der=sha256(der).hexdigest())
        report['openssl_version']=identity['openssl_version']
        binding=dict(format=1,source_commit=e.SOURCE,control_commit='a'*40,controller_sha256='b'*64,
            run_id='123456',run_attempt='1',case='B',stream='driver.stdout',recipient_spki_sha256=fingerprint,capture_complete=True)
        payload=os.urandom(257)+b'\x00\xff\r\nSYNTHETIC-M0-ONLY\n'
        e.need(len(payload)<=65536,'fixture_plaintext_cap')
        raw=directory/'synthetic.stdout';raw.write_bytes(payload)
        cipher=directory/'synthetic.cms';metadata=e.encrypt_closed_stream(raw,cipher,toy_cert,binding)
        result=e.decrypt_authenticated(cipher,toy_cert,toy_key,directory/'quarantine-valid',binding)
        report['checks'].append({'case':'authenticated_roundtrip_exact_binary','passed':result['bytes']==len(payload) and result['sha256']==sha256(payload).hexdigest()})
        printed=command('cms-structure',['openssl','cms','-cmsout','-inform','DER','-in',str(cipher),'-print']).decode('ascii')
        report['checks'].append({'case':'actual_AuthEnvelopedData_AES256GCM_RSAOAEP_SHA256',
            'passed':all(token in printed for token in ('id-smime-ct-authEnvelopedData','aes-256-gcm','rsaesOaep','sha256'))})
        for label,data in [('tampered-tag',cipher.read_bytes()[:-1]+bytes([cipher.read_bytes()[-1]^1])),('truncated',cipher.read_bytes()[:-9])]:
            damaged=directory/(label+'.cms');damaged.write_bytes(data)
            try:e.decrypt_authenticated(damaged,toy_cert,toy_key,directory/('quarantine-'+label),binding)
            except e.EscrowError as error:
                report['checks'].append({'case':label,'passed':str(error)=='authenticated_decrypt_failed_do_not_parse',
                    'private_unaccepted_output_bytes':(directory/('quarantine-'+label)/'unaccepted-container.bin').stat().st_size,
                    'plaintext_parsed_or_published':False})
            else:raise e.EscrowError('tamper_was_accepted')
        try:e.decrypt_authenticated(cipher,toy_cert,toy_key,directory/'quarantine-wrong-binding',dict(binding,run_id='999'))
        except e.EscrowError as error:report['checks'].append({'case':'authenticated_bytes_wrong_run_binding','passed':str(error)=='container_binding_mismatch'})
        else:raise e.EscrowError('wrong_binding_accepted')
        actual_cert=MODULE.parents[1]/'config/m0-stream-recipient-public.pem'
        e.certificate_identity(actual_cert)
        actual_metadata=e.encrypt_closed_stream(raw,directory/'actual-public-recipient-synthetic.cms',actual_cert,dict(binding,recipient_spki_sha256=e.SPKI_SHA))
        report['checks'].append({'case':'actual_public_cert_encrypt_only','passed':True,'private_key_read':False,
            'ciphertext_sha256':actual_metadata['sha256'],'ciphertext_bytes':actual_metadata['bytes'],'public_spki_sha256':e.SPKI_SHA})
        report.update(status='PASS' if all(c['passed'] for c in report['checks']) else 'FAIL',synthetic_original_bytes=len(payload),toy_key_not_published=True)
    except BaseException as error:
        report.update(status='FAIL',error_type=type(error).__name__,error_code=str(error) if isinstance(error,e.EscrowError) else 'private_fixture_failure')
    report.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_monotonic_ns=time.monotonic_ns()-started)
    (directory/'safe-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
