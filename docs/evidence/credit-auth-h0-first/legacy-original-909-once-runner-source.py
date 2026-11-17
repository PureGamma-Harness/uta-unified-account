import sys,pathlib,os,secrets,time,json,base64
sys.path.insert(0,sys.argv[1])
from uta.request_signing import NonceStore,RequestAuthenticator,SigningKey,SigningProfile,load_profile,sign_headers,SigningError
from uta.gateway import Credential
root=pathlib.Path(sys.argv[2]);store=NonceStore.initialize(root/'legacy-auth.sqlite3',tenant_id='h0-baseline',producer_binding='9'*64)
now=time.time_ns()//1000000;key=SigningKey('baseline-key',secrets.token_bytes(32),'funding','alice',0,now+60000)
data={'format':1,'tenant_id':'h0-baseline','audience':store.audience,'revision':1,'keys':[{'key_id':key.key_id,'secret_b64':base64.urlsafe_b64encode(key.secret).decode().rstrip('='),'role':key.role,'account_id':key.account_id,'not_before_ms':key.not_before_ms,'expires_at_ms':key.expires_at_ms,'revoked':False}]}
path=root/'private-profile.json';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:json.dump(data,f)
profile=load_profile(path);auth=RequestAuthenticator(store,profile)
headers=sign_headers(profile,key.key_id,timestamp_ms=time.time_ns()//1000000,nonce=secrets.token_urlsafe(24),method='GET',request_target='/auth-baseline',body=b'')
principal=auth.authenticate(headers,method='GET',request_target='/auth-baseline',body=b'');assert type(principal) is Credential
try:auth.authenticate(headers,method='GET',request_target='/auth-baseline',body=b'')
except SigningError as e:assert e.code=='request_replayed'
else:raise AssertionError('expected nonce replay')
with store.database.read_transaction() as c:assert c.execute('SELECT COUNT(*) FROM auth_nonces').fetchone()[0]==1
print(json.dumps({'legacy_actual_positive':True,'credential_return_type':True,'real_replay_refusal':True,'financial_database_opened':False,'synthetic_only':True}))
