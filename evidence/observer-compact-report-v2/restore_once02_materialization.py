"""Root-authorized source materialization only. Never invokes the adapter."""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'c076b0dc1feb765686de9c78683a4e4bea5429e2'
HEAD = '22e3f9a54607f70ef61edf4ba4c1e2b45ac4f2bd'
LAUNCHER = 'evidence/observer-compact-report-v2/launch_adapter_second_once.py'
OUT = ROOT / 'evidence/observer-compact-report-v2/once02-materialization-recovery'
NATIVE_OUTPUT = Path('/workspace/uta-observer-v2-adapter-runs/read1-c076b0d-once02')


def git(*args):
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=ROOT,
        stdin=0, stderr=subprocess.PIPE)


def seal(name, value):
    fd = os.open(OUT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


if git('rev-parse', 'HEAD').decode().strip() != HEAD:
    raise RuntimeError('materialization_HEAD_changed')
launcher_raw = (ROOT / LAUNCHER).read_bytes()
tree = ast.parse(launcher_raw)
inputs = ast.literal_eval(next(node.value for node in tree.body if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == 'INPUTS' for target in node.targets)))
if len(inputs) != 8 or git('diff', '--', *inputs) or git('diff', '--cached', '--', *inputs):
    raise RuntimeError('eight_clean_approved_source_paths_required')


def fresh_output():
    if NATIVE_OUTPUT.exists() or NATIVE_OUTPUT.is_symlink():
        raise RuntimeError('once02_path_already_exists_no_retry')


def snapshot():
    result = {}
    flags = {row[2:]: row[0] for row in git('ls-files', '-t', '--', *inputs).decode().splitlines()}
    for name, checksum in inputs.items():
        expected = git('show', SOURCE + ':' + name)
        if sha256(expected).hexdigest() != checksum:
            raise RuntimeError('approved_Git_hash_changed:' + name)
        path = ROOT / name
        row = {'Git_blob_bytes': len(expected), 'Git_blob_sha256': checksum, 'index_flag': flags[name]}
        if not path.exists() and not path.is_symlink():
            row['materialized'] = False
        else:
            details = path.lstat()
            if not stat.S_ISREG(details.st_mode) or path.is_symlink():
                raise RuntimeError('source_not_regular:' + name)
            actual = path.read_bytes()
            if actual != expected:
                raise RuntimeError('source_WIP_must_not_be_overwritten:' + name)
            row.update(materialized=True, actual_bytes=len(actual), actual_sha256=sha256(actual).hexdigest(),
                stat={'dev': details.st_dev, 'ino': details.st_ino, 'mode': oct(stat.S_IMODE(details.st_mode)), 'uid': details.st_uid})
        result[name] = row
    return result


fresh_output()
before = snapshot()
protected = {}
for row in git('ls-files', '-t', '--', 'docs', 'evidence').decode().splitlines():
    if row[0] != 'H': continue
    name, path = row[2:], ROOT / row[2:]
    if path.is_symlink(): raise RuntimeError('protected_doc_symlink')
    if path.is_file(): protected[name] = sha256(path.read_bytes()).hexdigest()
OUT.mkdir(mode=0o700, exist_ok=False)
seal('before.json', {'source': SOURCE, 'HEAD': HEAD, 'inputs': before,
    'protected_materialized_docs_evidence': protected, 'actual_probe_executions_started': 0,
    'native_output_exists': False, 'launcher_sha256': sha256(launcher_raw).hexdigest(),
    'root_authorization': 'restore only approved clean eight inputs and preserve other docs/evidence; no adapter invocation'})
# Retain existing materialized documents explicitly: sparse expansion must not
# silently remove unselected first evidence while adding the approved inputs.
patterns = ['/' + name for name in dict.fromkeys([*inputs, LAUNCHER, *protected])]
git('sparse-checkout', 'add', '--', *patterns)
git('restore', '--source=' + SOURCE, '--worktree', '--', *inputs)
after = snapshot()
fresh_output()
protected_unchanged = all((ROOT / name).is_file() and sha256((ROOT / name).read_bytes()).hexdigest() == checksum
    for name, checksum in protected.items())
complete = all(row['materialized'] and row['index_flag'] == 'H' for row in after.values())
seal('after.json', {'source': SOURCE, 'HEAD': git('rev-parse', 'HEAD').decode().strip(), 'inputs': after,
    'all_eight_materialized_and_byte_equal_approved_Git': complete,
    'protected_docs_evidence_unchanged': protected_unchanged, 'protected_file_count': len(protected),
    'launcher_sha256_unchanged': sha256((ROOT / LAUNCHER).read_bytes()).hexdigest() == sha256(launcher_raw).hexdigest(),
    'native_output_exists': False, 'actual_probe_executions_started': 0, 'adapter_invoked': False,
    'source_content_or_runtime_version_changed': False, 'production_approved': False})
if not complete or not protected_unchanged: raise RuntimeError('materialization_incomplete_no_adapter_authorized_to_start')
print(json.dumps({'source': SOURCE, 'eight_materialized': complete, 'protected_files': len(protected),
    'protected_unchanged': protected_unchanged, 'actual_probe_executions': 0, 'once02_exists': False}, sort_keys=True))
