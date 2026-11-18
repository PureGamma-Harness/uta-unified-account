"""Read ZIP/provider metadata/Git blobs only; never execute tests or touch SQLite."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile
import zlib

BASE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
HEAD='e4396b4b1fd9c2e3a138e48a045feffe158705cc'
MERGE='289ca5d05585ba5fd981a6e11ac2cf8b98d6672e'
ZIP_SHA='9ea4bae56cd6c2697cd613972bbcbf56c0fc3bffbd3c720313fc740ca66eaffc'
CASE='test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers'
CORE=('uta','tests','formal','tools','.github/workflows')


def sha(value):return hashlib.sha256(value).hexdigest()
def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo)
def tree(repo,commit):
    result={}
    for line in git(repo,'ls-tree','-r',commit).decode().splitlines():
        meta,path=line.split('\t',1);mode,kind,blob=meta.split()
        result[path]={'mode':mode,'kind':kind,'blob':blob}
    return result

def blobs(repo,identities):
    ids=sorted(set(identities))
    raw=git_batch(repo,ids);stream=io.BytesIO(raw);result={}
    for wanted in ids:
        header=stream.readline().decode().strip().split()
        if len(header)!=3 or header[0]!=wanted or header[1]!='blob':raise ValueError('Git blob identity/type missing')
        data=stream.read(int(header[2]))
        if stream.read(1)!=b'\n':raise ValueError('Git batch boundary mismatch')
        result[wanted]=data
    if stream.read():raise ValueError('unexpected Git batch suffix')
    return result

def git_batch(repo,ids):
    value=subprocess.run(['git','cat-file','--batch'],cwd=repo,input=('\n'.join(ids)+'\n').encode(),capture_output=True,check=True)
    return value.stdout


def audit(folder,repo):
    raw=folder/'raw';zipbytes=(raw/'pr311-original-artifact-plugin.zip').read_bytes()
    checks={'original_provider_ZIP_size_SHA':len(zipbytes)==92276 and sha(zipbytes)==ZIP_SHA}
    with zipfile.ZipFile(io.BytesIO(zipbytes)) as archive:
        infos=archive.infolist()
        checks['exact_three_members']=len(infos)==3 and {x.filename for x in infos}=={'summary.json','worker-result.json','unittest.txt'}
        checks['all_ZIP_CRC_valid']=archive.testzip() is None
        members={info.filename:archive.read(info) for info in infos}
        member_index=[{'name':info.filename,'bytes':info.file_size,'compressed_bytes':info.compress_size,
                      'crc32':f'{info.CRC:08x}','sha256':sha(members[info.filename]),
                      'CRC_recomputed_equal':(zlib.crc32(members[info.filename])&0xffffffff)==info.CRC} for info in infos]
    summary=json.loads(members['summary.json']);worker=json.loads(members['worker-result.json'])
    log=members['unittest.txt'].decode();lines=log.splitlines()
    checks['standalone_metadata_is_original_ZIP_members']=all((raw/name).read_bytes()==members[name] for name in ('summary.json','worker-result.json'))
    checks['raw_testlog_matches_summary']=sha(members['unittest.txt'])==summary['test_log_sha256']=='8510a40145092742b23a75b66ba545e83f01ea4b461f26b51444b180cc8821b9'
    counts={'tests_run':1801,'failures':0,'errors':1,'skipped':0,'expected_failures':0,'unexpected_successes':0}
    checks['summary_worker_exact_counts']=all(type(summary[k]) is int and type(worker[k]) is int and summary[k]==worker[k]==v for k,v in counts.items())
    checks['original_error_not_relabelled']=summary['passed'] is False and summary['unittest_passed'] is False and worker['unittest_passed'] is False and summary['production_approved'] is False
    checks['raw_unit_footer_and_unique_ERROR']=len(re.findall(r'^ERROR:',log,re.M))==1 and not re.findall(r'^FAIL:',log,re.M) and re.search(r'^Ran 1801 tests in 400\.673s$',log,re.M) is not None and log.rstrip().endswith('FAILED (errors=1)')
    checks['exact_error_location_and_first_EX']=f'ERROR: {CASE} (test_durable_process.DurableProcessTests.{CASE})' in log and 'line 424' in log and 'publication = self.router.publish_market(self.market(2), timeout=4)' in log and 'line 1395' in log and 'line 267' in log and 'uta.service.ServiceError: router control gate did not become available before timeout' in log
    checks['sibling_durable_fault_case_passed']=any(line.startswith('test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover ') and line.endswith('... ok') for line in lines)
    case_line=next(i for i,line in enumerate(lines) if line.startswith(CASE+' '))
    thread_start=next(i for i in range(case_line+1,len(lines)) if lines[i].startswith('Exception in thread uta-process-supervisor:'))
    thread_end=next(i for i in range(thread_start,len(lines)) if lines[i].startswith('sqlite3.OperationalError: locking protocol'))
    thread_text='\n'.join(lines[thread_start:thread_end+1])
    checks['adjacent_original_supervisor_error_retained']=all(x in thread_text for x in ('_supervise','_spawn','_record_process','_connect','PRAGMA journal_mode = WAL','sqlite3.OperationalError: locking protocol'))
    checks['source_before_after_348_unchanged']=len(summary['source_sha256'])==len(summary['source_sha256_after'])==348 and summary['source_sha256']==summary['source_sha256_after'] and summary['source_unchanged'] is True and summary['tracked_source_clean_before'] is True and summary['tracked_source_clean_after'] is True
    trees={label:tree(repo,commit) for label,commit in (('909',BASE),('e439',HEAD))}
    objects=blobs(repo,[trees[label][path]['blob'] for path in summary['source_sha256'] for label in trees])
    source_index=[]
    for path,expected in summary['source_sha256'].items():
        row={'path':path,'CI_before':expected,'CI_after':summary['source_sha256_after'][path]}
        for label in trees:
            entry=trees[label][path]
            row[label+'_mode']=entry['mode'];row[label+'_blob']=entry['blob'];row[label+'_sha256']=sha(objects[entry['blob']])
        row['all_equal']=row['CI_before']==row['CI_after']==row['909_sha256']==row['e439_sha256'] and row['909_mode']==row['e439_mode'] and row['909_blob']==row['e439_blob']
        source_index.append(row)
    checks['all_348_inputs_match_both_local_Git_sources']=all(row['all_equal'] is True for row in source_index)
    core={label:{p:v for p,v in entries.items() if any(p==prefix or p.startswith(prefix+'/') for prefix in CORE)} for label,entries in trees.items()}
    checks['all_320_tracked_core_blobs_modes_paths_same']=len(core['909'])==len(core['e439'])==320 and core['909']==core['e439']
    provider=json.loads((folder/'provider-metadata-safe.json').read_text())
    checks['provider_run_attempt1_PR22_head_base']=provider['run']['id']==44162304965 and type(provider['run']['run_attempt']) is int and provider['run']['run_attempt']==1 and provider['run']['event']=='pull_request' and provider['run']['conclusion']=='failure' and provider['run']['head_sha']==HEAD and provider['pr']['number']==22 and provider['pr']['base_sha']==BASE and provider['pr']['head_sha']==HEAD and provider['pr']['merge_commit_sha']==MERGE
    artifacts=provider['artifacts'];artifact=next(a for a in artifacts if a['id']==14365340388)
    checks['provider_bytes_digest_match_original_ZIP']=len(artifacts)==10 and artifact['name']=='uta-unit-validation-python-3.11' and artifact['size_in_bytes']==len(zipbytes) and artifact['digest']=='sha256:'+sha(zipbytes) and artifact['workflow_run']['head_sha']==HEAD
    expected_jobs={'test (3.10)':'success','test (3.11)':'failure','test (3.12)':'success','test (3.13)':'success'}
    checks['four_jobs_only_311_failed']={job['name']:job['conclusion'] for job in provider['jobs']}==expected_jobs
    failed=next(j for j in provider['jobs'] if j['id']==134319073058)
    steps={s['number']:s for s in failed['steps']}
    checks['311_unit_failed_compile_and_packages_skipped']=steps[5]['conclusion']=='failure' and steps[6]['conclusion']=='success' and all(steps[n]['conclusion']=='skipped' for n in range(7,21)) and steps[21]['conclusion']=='success' and steps[22]['conclusion']=='skipped'
    checks['actual_CI_runtime_merge_identity']=summary['code_commit']==MERGE and summary['python'].startswith('3.11.18 ') and summary['sqlite']=='3.46.1'
    checks['zero_byte_initial_download_not_replaced']=(raw/'initial-ghapi-zero-byte.zip').read_bytes()==b''
    privacy_markers=(b'-----BEGIN PRIVATE KEY-----',b'-----BEGIN RSA PRIVATE KEY-----',b'-----BEGIN EC PRIVATE KEY-----',b'X-Amz-Signature=',b'sig=')
    checks['no_private_key_or_signed_download_marker_in_saved_text']=all(marker not in content for marker in privacy_markers for content in (members['summary.json'],members['worker-result.json'],members['unittest.txt']))
    return {'evidence_integrity_accepted':all(value is True for value in checks.values()),'checks':checks,
      'source_index':source_index,'ZIP_members':member_index,'CI_unit_gate':'NO_GO: original 1801/0FAIL/1ERROR',
      'original_supervisor_error_line_range_1based':[thread_start+1,thread_end+1],
      'local_merge_object_present':subprocess.run(['git','cat-file','-e',MERGE+'^{commit}'],cwd=repo,capture_output=True).returncode==0,
      'local_CI_checkout_or_reproduction_claimed':False,'root_cause':'UNPROVEN; original associated thread error retained without temporal attribution',
      'scope':'archive CRC/hash, provider GET metadata and local Git blob reads only; no tests, SQLite, service, process fault, original jobs, CI retry or timeout change',
      'production_approved':False}

if __name__=='__main__':
    import sys
    here=Path(__file__).resolve().parent
    print(json.dumps(audit(here,Path(sys.argv[1]) if len(sys.argv)>1 else here.parents[2]),indent=2))
