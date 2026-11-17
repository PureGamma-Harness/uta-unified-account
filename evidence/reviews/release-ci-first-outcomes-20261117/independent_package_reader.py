"""Read already-built release archives; no build, imports, install, SQL or execution."""
import datetime,hashlib,json,pathlib,subprocess,tarfile,time,zipfile
START=time.monotonic_ns()
SOURCE="e486d13d68cde98e1a1246b1274bf92bb3b1a29c"
REPO=pathlib.Path("/workspace/uta-release-ci-first-outcomes")
ORIGINALS=pathlib.Path("/workspace/uta-deployment-package-e486-once-private")
DEST=REPO/"evidence/reviews/release-ci-first-outcomes-20261117/deployment-package-independent.json"
def git(*a): return subprocess.check_output(["git",*a],cwd=REPO)
def digest(b): return hashlib.sha256(b).hexdigest()
manifest=json.loads((ORIGINALS/"artifact-manifest.json").read_text())
first=json.loads((ORIGINALS/"first-result.json").read_text())
assert manifest["source_commit"]==first["source_commit"]==SOURCE
assert first["passed"] and not first["production_approved"]
assert all(manifest["checks"].values())
change=git("diff","--name-status",SOURCE+"^",SOURCE).decode().strip().splitlines()
assert change==["M\tMANIFEST.in"]
patch=git("diff","--unified=0",SOURCE+"^",SOURCE,"--","MANIFEST.in").decode()
added=[s for s in patch.splitlines() if s.startswith("+") and not s.startswith("+++")]
removed=[s for s in patch.splitlines() if s.startswith("-") and not s.startswith("---")]
assert added==["+include deploy/review-manifest.template.json"] and removed==[]
paths=git("ls-tree","-r","--name-only",SOURCE).decode().splitlines()
assert manifest["sdist_required_files"]==paths and len(paths)==6298
runtime={p for p in paths if p.startswith("uta/") and p.endswith((".py",".html"))}
assert runtime==set(manifest["runtime_files"]) and len(runtime)==62
wanted=runtime|{"deploy/review-manifest.template.json"}
blobs={p:git("show",SOURCE+":"+p) for p in sorted(wanted)}
artifact_observations=[]
for name,record in manifest["artifacts"].items():
    p=ORIGINALS/"dist"/name
    data=p.read_bytes()
    assert len(data)==record["bytes"] and digest(data)==record["sha256"]
    artifact_observations.append({"name":name,"bytes":len(data),"sha256":digest(data)})
wheel=next(ORIGINALS.joinpath("dist").glob("*.whl"))
with zipfile.ZipFile(wheel) as z:
    names=z.namelist()
    assert len(names)==len(set(names))
    assert {n for n in names if n.startswith("uta/") and n.endswith((".py",".html"))}==runtime
    for p in runtime: assert z.read(p)==blobs[p]
source=next(ORIGINALS.joinpath("dist").glob("*.tar.gz"))
found={}
with tarfile.open(source,mode="r|gz") as tf:
    for member in tf:
        parts=pathlib.PurePosixPath(member.name).parts
        if len(parts)<2 or not member.isfile(): continue
        relative="/".join(parts[1:])
        if relative in wanted:
            assert relative not in found
            found[relative]=tf.extractfile(member).read()
assert set(found)==wanted
for p in wanted: assert found[p]==blobs[p]
result={"observed_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"source_commit":SOURCE,"source_parent":git("rev-parse",SOURCE+"^").decode().strip(),"changed_paths":["MANIFEST.in"],"exact_added_line":"include deploy/review-manifest.template.json","artifacts":artifact_observations,"template":{"path":"deploy/review-manifest.template.json","bytes":len(blobs["deploy/review-manifest.template.json"]),"sha256":digest(blobs["deploy/review-manifest.template.json"]),"unique_sdist_member_exact_git_bytes":True},"required_path_list_exact_git_count":len(paths),"runtime_exact_git_bytes_count":len(runtime),"runtime_python_count":sum(p.endswith(".py") for p in runtime),"runtime_html_count":sum(p.endswith(".html") for p in runtime),"root_first_verifier":{"all_checks_true":True,"elapsed_seconds":first["elapsed_seconds"],"artifact_manifest_sha256":digest((ORIGINALS/"artifact-manifest.json").read_bytes()),"first_result_sha256":digest((ORIGINALS/"first-result.json").read_bytes())},"passed":True,"production_approved":False,"gate":"NO_GO","elapsed_ns":time.monotonic_ns()-START,"limits":["Independently checked all 6298 required path names, two archive digests/sizes, the 62 runtime payloads and one template payload against Git.","Other non-runtime payloads were verified by the preserved root verifier; this reader does not claim an independent second comparison of all 6298 payloads.","No build, install, test suite, SQL, worker, workflow rerun or dispatch executed. Original seven package failures remain immutable.","Packaging omission closure does not resolve native capture and readiness observation failures or authorize production."]}
with DEST.open("x") as fp: json.dump(result,fp,indent=2,sort_keys=True); fp.write("\n")
print(json.dumps({"passed":True,"elapsed_ns":result["elapsed_ns"],"runtime_members":len(runtime),"required_paths":len(paths),"template_unique_exact":True,"production_approved":False},sort_keys=True))
