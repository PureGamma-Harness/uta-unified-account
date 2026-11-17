"""M0 closed-stream evidence escrow using system OpenSSL CMS, never trading keys.

Import is pure. Encryption is explicit; only fixed caller-owned closed streams
are eligible. GCM authenticates bytes/binding, not the author's identity.
"""
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys

MAGIC=b'M0STREAM\0'
SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
CERT_SHA='3140279eb39d7873fdcbd23fb46b71f987d43a12184087a791c5b2073b5f1fed'
SPKI_SHA='de01fcb8516224fd3d91f442899d582c4fcaa5aadfac8e91b45f680307ed3ab1'
DER_SHA='93e081eb110b196c355e0b6a3d91358ef530d7b8a98d6a3b392f47e64229c783'
STREAMS=('driver.stdout','driver.stderr','case-owner.stdout','case-owner.stderr')
CAP=32*1024**2
HEADER_CAP=4096

class EscrowError(Exception):pass

def need(value,code):
    if not value:raise EscrowError(code)

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def parse_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate_header_key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(EscrowError('nonfinite_header')))

def digest_file(path):
    h=sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(65536):h.update(block)
    return h.hexdigest()

def validate_binding(value):
    need(set(value)=={'format','source_commit','control_commit','controller_sha256','run_id','run_attempt','case','stream','recipient_spki_sha256','capture_complete'},'binding_fields')
    need(type(value['format']) is int and value['format']==1,'binding_format')
    need(value['source_commit']==SOURCE,'binding_source')
    need(re.fullmatch('[0-9a-f]{40}',value['control_commit']) is not None,'binding_control')
    need(re.fullmatch('[0-9a-f]{64}',value['controller_sha256']) is not None,'binding_controller_hash')
    need(re.fullmatch('[1-9][0-9]{0,30}',value['run_id']) is not None and value['run_attempt']=='1','binding_run_attempt')
    need(value['case'] in ('B','P') and value['stream'] in STREAMS,'binding_case_stream')
    need(re.fullmatch('[0-9a-f]{64}',value['recipient_spki_sha256']) is not None,'binding_recipient')
    need(type(value['capture_complete']) is bool,'binding_capture_complete')
    return True

def container_header(binding,size,digest):
    validate_binding(binding)
    need(type(size) is int and 0<=size<=CAP,'stream_size')
    need(re.fullmatch('[0-9a-f]{64}',digest) is not None,'stream_digest')
    header=canonical(dict(binding,stream_bytes=size,stream_sha256=digest))
    need(len(header)<=HEADER_CAP,'header_cap')
    return MAGIC+struct.pack('>I',len(header))+header

def validate_decrypted_container(path,expected):
    """Only call after OpenSSL decrypt returned zero, on private quarantine.

    Failed authentication may leave output bytes. This function is not a
    substitute for a successful authenticated decrypt and never publishes data.
    """
    validate_binding(expected)
    with Path(path).open('rb') as stream:
        need(stream.read(len(MAGIC))==MAGIC,'container_magic')
        raw=stream.read(4);need(len(raw)==4,'container_header_length')
        size=struct.unpack('>I',raw)[0];need(0<size<=HEADER_CAP,'container_header_cap')
        raw=stream.read(size);need(len(raw)==size,'container_header_truncated')
        header=parse_json(raw)
        need(set(header)==set(expected)|{'stream_bytes','stream_sha256'},'container_fields')
        need(canonical({key:header[key] for key in expected})==canonical(expected),'container_binding_mismatch')
        length=header['stream_bytes'];need(type(length) is int and 0<=length<=CAP,'container_stream_length')
        digest=sha256();seen=0
        while block:=stream.read(min(65536,length-seen+1)):
            seen+=len(block);need(seen<=length,'container_trailing_bytes');digest.update(block)
        need(seen==length and digest.hexdigest()==header['stream_sha256'],'container_stream_hash')
    return {'binding_valid':True,'bytes':seen,'sha256':digest.hexdigest(),'plaintext_published':False}

def certificate_identity(certificate, *, expected_pem=CERT_SHA, expected_spki=SPKI_SHA, expected_der=DER_SHA):
    need(digest_file(certificate)==expected_pem,'recipient_pem_changed')
    version=subprocess.run(['openssl','version'],capture_output=True,check=True,timeout=3).stdout.decode('ascii').strip()
    need(version.startswith('OpenSSL 3.'),'openssl3_required')
    der=subprocess.run(['openssl','x509','-in',str(certificate),'-outform','DER'],capture_output=True,check=True,timeout=3).stdout
    pub=subprocess.run(['openssl','x509','-in',str(certificate),'-pubkey','-noout'],capture_output=True,check=True,timeout=3).stdout
    spki=subprocess.run(['openssl','pkey','-pubin','-outform','DER'],input=pub,capture_output=True,check=True,timeout=3).stdout
    need(sha256(der).hexdigest()==expected_der and sha256(spki).hexdigest()==expected_spki,'recipient_der_or_spki_changed')
    return {'openssl_version':version,'openssl_executable_sha256':digest_file(Path(shutil.which('openssl')).resolve()),
        'public_certificate_pem_sha256':expected_pem,'public_certificate_der_sha256':expected_der,'public_spki_der_sha256':expected_spki}

def encrypt_closed_stream(path,output,certificate,binding):
    """Caller must prove all owned producers closed before this operation.

    No plaintext container copy is created. Pipe writes are bounded in memory;
    an external owned-process watchdog must cover a blocked pipe/OpenSSL I/O.
    There is no fallback if OAEP-SHA256 or CMS AES256GCM is unsupported.
    """
    validate_binding(binding)
    need(output.parent.is_dir() and not output.exists() and not output.is_symlink(),'new_cipher_output')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as source:
        before=os.fstat(source.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_size<=CAP,'closed_stream_file')
        identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
        digest=sha256()
        while block:=source.read(65536):digest.update(block)
        header=container_header(binding,before.st_size,digest.hexdigest());source.seek(0)
        command=['openssl','cms','-encrypt','-binary','-outform','DER','-aes-256-gcm','-recip',str(certificate),
            '-keyopt','rsa_padding_mode:oaep','-keyopt','rsa_oaep_md:sha256','-keyopt','rsa_mgf1_md:sha256']
        outfd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        error_path=output.with_suffix('.openssl-private-stderr')
        with os.fdopen(outfd,'wb') as target,error_path.open('xb') as errors:
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=target,stderr=errors,start_new_session=False)
            copied=sha256();seen=0
            try:
                process.stdin.write(header)
                while block:=source.read(65536):
                    seen+=len(block);need(seen<=before.st_size,'stream_changed_during_copy');copied.update(block);process.stdin.write(block)
                process.stdin.close();need(process.wait(timeout=5)==0,'cms_encrypt_failed')
            except BaseException:
                if process.stdin and not process.stdin.closed:process.stdin.close()
                if process.poll() is None:
                    process.kill();process.wait(timeout=2)
                raise
            target.flush();os.fsync(target.fileno())
        after=os.fstat(source.fileno())
        need(identity==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and seen==before.st_size and copied.digest()==digest.digest(),'stream_changed_during_encrypt')
    need(output.stat().st_size<=before.st_size+65536,'cipher_overhead_cap')
    # Parse DER without printing ciphertext, private paths or original contents.
    checked=subprocess.run(['openssl','cms','-cmsout','-inform','DER','-in',str(output),'-noout'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
    need(checked.returncode==0,'cms_der_invalid')
    return {'name':output.name,'bytes':output.stat().st_size,'sha256':digest_file(output),
        'recipient_spki_sha256':binding['recipient_spki_sha256'],'algorithm':'CMS_AUTH_ENVELOPED_DATA_AES256GCM_RSA_OAEP_SHA256',
        'origin_authenticated_by_recipient_encryption':False}

def decrypt_authenticated(ciphertext,certificate,private_key,quarantine,expected):
    """Offline only: failed GCM may produce bytes; never parse them on failure.

    Key ownership remains with the offline caller. Runner code never calls this
    function and never receives the actual workspace private recipient key.
    """
    need(quarantine.is_absolute() and not quarantine.exists() and quarantine.parent.is_dir(),'new_private_quarantine')
    quarantine.mkdir(mode=0o700);plain=quarantine/'unaccepted-container.bin'
    fd=os.open(plain,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as target,(quarantine/'openssl-private-stderr').open('xb') as errors:
        observed=subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER','-in',str(ciphertext),
            '-recip',str(certificate),'-inkey',str(private_key)],stdout=target,stderr=errors,timeout=5)
        target.flush();os.fsync(target.fileno())
    need(observed.returncode==0,'authenticated_decrypt_failed_do_not_parse')
    verified=validate_decrypted_container(plain,expected)
    return dict(verified,authenticated_decrypt_exit_zero=True,quarantine=str(quarantine),original_contents_not_published=True)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--encrypt-case',type=Path)
    parser.add_argument('--check-public-recipient',type=Path)
    args=parser.parse_args(argv)
    if args.check_public_recipient is not None:
        need(args.encrypt_case is None,'exclusive_crypto_mode')
        directory=args.check_public_recipient
        need(directory.is_absolute() and directory.parent.parent==Path(os.environ['RUNNER_TEMP']) and not directory.exists(),'new_synthetic_probe_path')
        directory.mkdir(mode=0o700)
        certificate=Path(__file__).resolve().parents[1]/'config/m0-stream-recipient-public.pem'
        identity=certificate_identity(certificate)
        raw=directory/'synthetic.stdout';raw.write_bytes(b'M0-SYNTHETIC-PUBLIC-RECIPIENT-CAPABILITY-ONLY\n')
        binding={'format':1,'source_commit':SOURCE,'control_commit':'0'*40,'controller_sha256':'0'*64,
            'run_id':'1','run_attempt':'1','case':'B','stream':'driver.stdout','recipient_spki_sha256':SPKI_SHA,'capture_complete':False}
        cipher=directory/'synthetic.cms';encrypt_closed_stream(raw,cipher,certificate,binding)
        printed=subprocess.run(['openssl','cms','-cmsout','-inform','DER','-in',str(cipher),'-print'],capture_output=True,check=True,timeout=3).stdout
        need(all(label in printed for label in (b'id-smime-ct-authEnvelopedData',b'aes-256-gcm',b'rsaesOaep',b'sha256')),'requested_crypto_protocol_not_observed')
        print(json.dumps(dict(identity,status='PUBLIC_RECIPIENT_CAPABILITY_VERIFIED',synthetic_only=True,private_key_read=False,
            crypto_protocol='CMS_AUTH_ENVELOPED_DATA_AES256GCM_RSA_OAEP_SHA256',no_protocol_fallback=True)))
        return 0
    if args.encrypt_case is None:
        print(json.dumps({'status':'PREP_ONLY','execution_authorized':False}));return 0
    path=args.encrypt_case;info=path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o600 and info.st_size<=16384,'descriptor_owner')
    value=parse_json(path.read_bytes())
    need(set(value)=={'format','case','private','public','control_commit','controller_sha256','run_id','run_attempt','parent_pid','parent_birth_ticks','closed_producers','capture_complete','aggregate_existing_bytes','aggregate_cap','cleanup_cap'},'descriptor_fields')
    need(type(value['format']) is int and value['format']==1 and value['closed_producers'] is True,'closed_producers_unproven')
    need(type(value['parent_pid']) is int and os.getppid()==value['parent_pid'],'descriptor_parent')
    fields=Path(f'/proc/{os.getppid()}/stat').read_text().rsplit(')',1)[1].split()
    need(int(fields[19])==value['parent_birth_ticks'] and fields[0] not in ('Z','X'),'descriptor_parent_birth')
    need(os.getsid(0)==os.getpgrp()==os.getpid(),'escrow_owned_session')
    root=Path(__file__).resolve().parents[1];certificate=root/'config/m0-stream-recipient-public.pem'
    public_identity=certificate_identity(certificate)
    private=Path(value['private']);public=Path(value['public']);name=value['case']
    need(name in ('B','P') and path==private/f'escrow-context-{name}.json','escrow_case_path')
    need(private.parent==public.parent==Path(os.environ['RUNNER_TEMP']) and private.is_absolute(),'escrow_runner_temp')
    staged=private/f'escrow-{name}';staged.mkdir(mode=0o700)
    paths={'driver.stdout':private/name/'driver.stdout','driver.stderr':private/name/'driver.stderr',
        'case-owner.stdout':private/f'case-owner-{name}.stdout','case-owner.stderr':private/f'case-owner-{name}.stderr'}
    existing=value['aggregate_existing_bytes'];need(type(existing) is int and existing>=0,'aggregate_bytes_type')
    need(type(value['aggregate_cap']) is int and value['aggregate_cap']==96*1024**2 and type(value['cleanup_cap']) is int and value['cleanup_cap']==32*1024**2,'escrow_budget_changed')
    total=sum(p.stat().st_size for p in paths.values() if p.is_file())
    need(existing+total+4*65536<=value['aggregate_cap'],'escrow_output_headroom')
    records=[];failures=[]
    eligible=public/f'escrow-{name}-safe';eligible.mkdir(mode=0o700)
    def checkpoint(status):
        result={'case':name,'status':status,'files':records,'failures':failures,'recipient':public_identity,
            'raw_stream_scope':list(STREAMS),'all_transitive_native_streams_claimed':False,
            'origin_authenticated_by_recipient_encryption':False,'private_keys_on_runner':False}
        output=private/f'escrow-completed-{name}.json';partial=output.with_suffix('.json.part')
        fd=os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as target:target.write(canonical(result));target.flush();os.fsync(target.fileno())
        os.replace(partial,output)
        return result
    for stream,original in paths.items():
        try:
            complete=value['capture_complete'][stream];need(type(complete) is bool,'capture_proof_type')
            binding={'format':1,'source_commit':SOURCE,'control_commit':value['control_commit'],'controller_sha256':value['controller_sha256'],
                'run_id':value['run_id'],'run_attempt':value['run_attempt'],'case':name,'stream':stream,'recipient_spki_sha256':SPKI_SHA,'capture_complete':complete}
            record=encrypt_closed_stream(original,staged/(stream+'.cms'),certificate,binding)
            records.append(record)
            if not complete:failures.append({'stream':stream,'code':'captured_prefix_only'})
            # Journal first, then expose only complete cipher atomically. A
            # later stream timeout preserves every prior completed ciphertext.
            checkpoint('IN_PROGRESS')
            os.rename(staged/record['name'],eligible/record['name'])
        except BaseException as error:
            failures.append({'stream':stream,'code':str(error) if isinstance(error,EscrowError) else 'unclassified_private_escrow_failure'})
    # Partial invalid .cms and OpenSSL stderr remain private.
    result=checkpoint('PASS' if not failures and len(records)==4 else 'UNKNOWN')
    print(json.dumps({'status':result['status'],'case':name,'encrypted_closed_streams':len(records)}))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'UNKNOWN','error_code':str(error) if isinstance(error,EscrowError) else 'unclassified_private_failure'}));raise SystemExit(1)
