"""PREP-only binding refresh for unexecuted drafts; never starts a controller."""
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
EV=Path(__file__).resolve().parent
PROFILE=ROOT/'benchmarks/profiles/managed-909acec-v3-smoke02-conditional.json'
CODE=EV/'smoke_controller_v3.py'


def main():
    p=json.loads(PROFILE.read_bytes());p['orchestration_controller_sha256']=sha256(CODE.read_bytes()).hexdigest()
    PROFILE.write_text(json.dumps(p,indent=2)+'\n');ph=sha256(PROFILE.read_bytes()).hexdigest()
    file=EV/'conditional-envelope.json';e=json.loads(file.read_bytes())
    e.update(controller_sha256=p['orchestration_controller_sha256'],profile_sha256=ph)
    for s in e['stages']:
        s['argv'][s['argv'].index('--root-go-profile-sha256')+1]=ph
        s['command_sha256']=sha256(json.dumps(s['argv'],separators=(',',':')).encode()).hexdigest()
    file.write_text(json.dumps(e,indent=2)+'\n')
    print(json.dumps({'controller_sha256':e['controller_sha256'],'profile_sha256':ph,
        'envelope_sha256':sha256(file.read_bytes()).hexdigest(),'executed':False}))


if __name__=='__main__':main()
