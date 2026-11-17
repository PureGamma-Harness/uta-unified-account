"""Reuse immutable independent source verifier against final afe Git blobs only."""
from hashlib import sha256
from pathlib import Path
source=Path(__file__).with_name('verify_source_contract.py').read_bytes()
assert sha256(source).hexdigest()=='dc975ab332433dc9bc5abdcf0848857aa31904b3ca4dde001d020b99cda86da5'
old="CANDIDATE='b58e587bf8eb17c1c8449e65c7368a8fc2ec4a31'"
new="CANDIDATE='afe275e95d832e238e033faa84b3ee5cae1b8431'"
assert source.decode().count(old)==1
exec(compile(source.decode().replace(old,new),str(Path(__file__).with_name('verify_source_contract.py')),'exec'))
