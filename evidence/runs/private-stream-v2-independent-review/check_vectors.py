"""Static V2 closure: Git blobs, JSON and finite arithmetic only. No UTA import."""
from pathlib import Path
from hashlib import sha1,sha256
from datetime import datetime,timezone
import base64,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[3]
OLD='c68aabe82ce78ab10a3c886894ce8dc9952302d1'
V2='5348ab36d9aa254428c032e7523aa77ae8bed2d2'
REVIEW='f7a86b5a7a53476fb277272b0d5cb7c679d73540'


def blob(commit,name):return subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
def client_close(code):return code in {1000,1001,1002,1003,1007,1008,1009,1010,1011,1012,1013,1014,3000,3003,3008} or 4000<=code<=4999
def server_close(code):return client_close(code) and code!=1010
def plain_payload(raw):
    raw=bytes.fromhex(raw);assert raw[1]&128
    size=raw[1]&127;assert size<126 and len(raw)==6+size
    return bytes(value^raw[2+i%4] for i,value in enumerate(raw[6:]))
def whole_wire(size):return size+(2 if size<=125 else 4 if size<=65535 else 10)


def main(output):
    fixture_name='tests/fixtures/managed_private_stream_v2_contract.json'
    data=json.loads(blob(V2,fixture_name));cases={c['id']:c for c in data['cases']}
    assert len(cases)==len(data['cases'])==28
    assert set(cases)=={f'WS-V2-C{i:03}' for i in range(31,59)}
    assert data['status']=='DESIGN_NOT_IMPLEMENTED'
    assert data['amends_design_commit']==OLD and data['review_commit']==REVIEW
    assert data['runtime_tests_executed']==data['websocket_or_sql_operations_executed']==0
    assert all(c['execution_status']=='NOT_RUN_REQUIREMENT' for c in cases.values())
    old_names=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',OLD],cwd=ROOT,text=True).splitlines()
    assert len(old_names)==5
    old_hashes={}
    for name in old_names:
        original=blob(OLD,name);assert original==blob(V2,name)==(ROOT/name).read_bytes()
        old_hashes[name]=sha256(original).hexdigest()
    results=[]
    def record(number,result):results.append({'case':f'WS-V2-C{number:03}','calculated':result,'runtime_verified':False})
    case=cases['WS-V2-C031'];i=case['input'];e=case['expected']
    chars=i['ascii_json_wrapper_bytes']+i['codepoint_count']
    size=i['ascii_json_wrapper_bytes']+i['codepoint_count']*len(i['unicode_codepoint'].encode('utf-8'))
    assert chars==e['python_character_count'] and size==e['utf8_byte_count']
    assert chars<=i['old_python_character_limit']<size
    record(31,{'characters':chars,'UTF8_bytes':size})
    for number in (32,33,34):
        c=cases[f'WS-V2-C{number:03}'];assert c['input']['expected_BLOB_length_NOT_RUN']>c['input']['cap_bytes']
        assert c['expected']['raw_column_selected_into_python'] is False and c['expected']['decoder_called'] is False and c['expected']['cursor_advanced'] is False
        record(number,{'declared_length_over_cap':True,'no_SQL_executed':True})
    c=cases['WS-V2-C035'];assert c['input']['sqlite_typeof']!='text' and c['expected']['coerce_to_str_or_repair'] is False
    record(35,{'non_TEXT_not_coerced':True})
    c=cases['WS-V2-C036'];i=c['input'];e=c['expected'];canonical=i['canonical_key'];alias=i['alias_key']
    decoded=base64.b64decode(canonical,validate=True);assert decoded==base64.b64decode(alias,validate=True) and len(decoded)==16
    assert base64.b64encode(decoded).decode('ascii')==canonical!=alias and decoded.hex()==i['signed_challenge_hex']
    for key,field in ((canonical,'canonical_accept'),(alias,'alias_accept')):
        accept=base64.b64encode(sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')).digest()).decode('ascii');assert accept==e[field]
    assert e['alias_http_status']==400 and e['alias_nonce_consumed'] is False
    record(36,{'canonical_key_reencoding_unique':True,'same_decoded_alias_rejected_by_contract':True})
    for number,code in ((37,1004),(38,1010)):
        c=cases[f'WS-V2-C{number:03}'];assert int.from_bytes(plain_payload(c['input']['client_frame_hex']),'big')==code
        if number==37:assert not client_close(code) and c['expected']['close_code']==1002
        else:assert client_close(code) and not server_close(code) and c['expected']['server_close_code']==1000
        record(number,{'incoming_close':code,'client_profile_accepts':client_close(code),'server_encoder_accepts':server_close(code)})
    c=cases['WS-V2-C039'];assert c['input']['server_encoder_requested_code']==1010 and not server_close(1010) and c['expected']['wire_bytes_emitted']==0
    record(39,{'server_1010_not_encoded':True})
    c=cases['WS-V2-C040'];body=plain_payload(c['input']['client_frame_hex']);assert body.hex()==c['input']['unmasked_payload_hex'] and len(body)==1 and c['expected']['close_code']==1002
    record(40,{'one_byte_close_invalid':True})
    c=cases['WS-V2-C041'];header=bytes.fromhex(c['input']['client_header_hex']);assert header[0]&15==8 and header[1]&127==126 and int.from_bytes(header[2:4],'big')==126>125 and not c['expected']['payload_allocated']
    record(41,{'declared_control_length':126,'early_protocol_reject':True})
    c=cases['WS-V2-C042'];header=bytes.fromhex(c['input']['client_header_hex']);assert int.from_bytes(header[2:10],'big')==2**63==c['input']['declared_payload_length'] and header[2]&128
    record(42,{'uint64_high_bit_invalid':True})
    for number in range(43,49):
        c=cases[f'WS-V2-C{number:03}'];size=c['input']['json_utf8_payload_bytes'];wire=whole_wire(size);e=c['expected']
        assert wire==e['whole_wire_frame_bytes'] and wire-size==e['RFC_header_bytes'] and (wire<=c['input']['whole_wire_cap_bytes']) is e['may_enqueue']
        record(number,{'payload':size,'header':wire-size,'wire_bytes':wire,'fits':wire<=262144})
    c=cases['WS-V2-C049'];i=c['input'];e=c['expected'];pending=sum(i['application_frames_wire_bytes']);built=pending+i['additional_being_encoded_wire_bytes'];total=built+sum(i['control_reserve_frames_wire_bytes'])
    assert pending==e['application_pending_wire_bytes']==524288 and built==e['three_application_buffers_bytes']==786432 and total==e['wire_buffers_with_control_reserve_bytes']==786686
    assert not e['bounds_total_RSS_or_TLS_kernel_bytes'];record(49,{'application_pending':pending,'application_three_buffers':built,'plus_control_reserve':total,'RSS_proven':False})
    c=cases['WS-V2-C050'];i=c['input'];assert i['current_application_wire_bytes']+i['next_application_wire_bytes']>524288 and i['current_application_frames']+1>2 and not c['expected']['next_enqueued']
    record(50,{'bytes_and_count_overflow_rejected':True})
    for number,start,budget,deadline in [(51,'first_frame_byte_monotonic_ms','configured_header_budget_ms','header_absolute_deadline_ms'),(52,'first_frame_byte_monotonic_ms','configured_frame_budget_ms','frame_absolute_deadline_ms'),(53,'accepted_monotonic_ms','configured_total_budget_ms','handshake_absolute_deadline_ms')]:
        c=cases[f'WS-V2-C{number:03}'];value=c['input'][start]+c['input'][budget];assert value==c['expected'][deadline]
        record(number,{'fixed_deadline_ms':value,'real_scheduling_measured':False})
    c=cases['WS-V2-C054'];i=c['input'];d=i['auth_check_requested_ms']+i['auth_result_budget_ms'];assert d==c['expected']['auth_result_deadline_ms']==350<i['late_result_arrives_ms'] and not c['expected']['late_result_can_reauthorize_closed_session']
    record(54,{'auth_absolute_result_deadline_ms':d,'late_result_does_not_reauthorize':True})
    c=cases['WS-V2-C055'];assert c['input']['original_pong_deadline_ms']==c['expected']['pong_deadline_after_other_progress_ms']==800 and not c['expected']['unsolicited_pong_is_protocol_error'];record(55,{'pong_deadline_not_extended':800})
    c=cases['WS-V2-C056'];i=c['input'];d=i['application_frame_first_byte_ms']+i['original_frame_write_budget_ms'];assert d==c['expected']['original_frame_write_deadline_ms']==600 and not c['expected']['inject_close_mid_application_payload'] and not c['expected']['next_application_frame_may_start'];record(56,{'original_write_deadline_ms':d,'no_close_interleave':True})
    c=cases['WS-V2-C057'];assert plain_payload(c['input']['client_empty_close_hex'])==b'' and all(client_close(code) for code in c['input']['private_close_code_examples']) and c['expected']['server_reply_close_code']==1000;record(57,{'empty_and_private_close_profile_valid':True,'server_response_code':1000})
    c=cases['WS-V2-C058'];codes=c['input']['tested_codes'];assert [code for code in codes if client_close(code)]==c['expected']['client_accepted_codes'];assert [code for code in codes if server_close(code)]==c['expected']['server_encoder_accepted_codes'];record(58,{'client_codes':[code for code in codes if client_close(code)],'server_codes':[code for code in codes if server_close(code)]})
    assert len(results)==28
    names=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',V2],cwd=ROOT,text=True).splitlines()
    inputs={name:sha256(blob(V2,name)).hexdigest() for name in names}
    assert len(names)==5 and all(not name.startswith('uta/') for name in names)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'reviewed_amendment':V2,'original_design':OLD,'original_independent_review':REVIEW,'original_five_files_byte_identical':True,'original_five_file_sha256':old_hashes,'v2_five_file_sha256':inputs,'original_requirements_unchanged':30,'new_requirement_vectors':28,'literal_arithmetic_results':results,'R1_R5_design_conditions':'CLOSED for the stated narrow policy only; implementation gates remain open','SQL_socket_or_network_operations':0,'production_approved':False,'runtime_deadline_or_memory_proven':False}
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('reviewed_amendment','original_five_files_byte_identical','new_requirement_vectors','R1_R5_design_conditions','SQL_socket_or_network_operations','runtime_deadline_or_memory_proven')}))

if __name__=='__main__':main(sys.argv[1])
