from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json, os, shutil, subprocess, stat, tarfile

os.sched_setaffinity(0, {3})
repo = Path('/workspace/uta-observer-delivery')
plan_path = Path('/workspace/uta-scratch-review-20261117-round2.json')
assert sha256(plan_path.read_bytes()).hexdigest() == '385a25d719cccc28018684bf6d9c23b98760a390fca5b56e726e5cef06146383'
plan = json.loads(plan_path.read_bytes())
output = Path('/workspace/uta-safe-scratch-cleanup/fifth-completed-reviews')
output.mkdir(exist_ok=False)
package = Path('/tmp/uta-release-dbc93e5-oor3dlj4')
rows = plan['worktrees']
trees = [Path(row['absolute_path']) for row in rows]
derived = [Path(row['absolute_path']) for row in plan['package_derived_directories']]
assert len(trees) == len(set(trees)) == 15
assert derived == [package / 'build-source', package / 'sdist-unpacked']

def git(*args, cwd=repo):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()

def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def package_remaining_metadata():
    result = {}
    for parent, dirs, files in os.walk(package, followlinks=False):
        parent = Path(parent)
        dirs[:] = [name for name in dirs if parent / name not in derived]
        for name in dirs + files:
            path = parent / name
            info = path.lstat()
            result[str(path.relative_to(package))] = [info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns, info.st_ino,
                os.readlink(path) if path.is_symlink() else None]
    return result

def visible_usage(paths):
    found, inaccessible, readable = [], 0, 0
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        links = [proc / 'cwd', proc / 'exe']
        try:
            links += list((proc / 'fd').iterdir())
        except OSError:
            inaccessible += 1
        for link in links:
            try:
                value = os.readlink(link)
                readable += 1
            except OSError:
                inaccessible += 1
                continue
            if any(value == str(p) or value.startswith(str(p) + '/') for p in paths):
                found.append([proc.name, str(link), value])
    return {'matches': found, 'readable_links': readable,
            'inaccessible_links': inaccessible,
            'inaccessible_processes_not_claimed_unused': True}

protected = [repo, Path('/workspace/uta-credit-v2-py310-candidate'),
             Path('/workspace/uta-credit-internal-v2'),
             Path('/workspace/uta-package-independent-dbc93e5'),
             Path('/workspace/uta-credit-v2-hmac-plan')]
for row, path in zip(rows, trees):
    assert path.is_dir() and not path.is_symlink() and path not in protected
    assert not any(word in str(path) for word in ('freeze', 'soak-runs', 'observer-runs'))
    assert git('rev-parse', 'HEAD', cwd=path) == row['HEAD'] == git('rev-parse', row['branch_ref'])
    assert git('rev-parse', 'HEAD^{tree}', cwd=path) == row['tree']
    assert git('status', '--porcelain', '--untracked-files=all', cwd=path) == ''
    ignored = git('ls-files', '--others', '--ignored', '--exclude-standard', cwd=path).splitlines()
    assert all('__pycache__/' in name or name.endswith('.pyc') for name in ignored)
for path in derived:
    assert path.is_dir() and not path.is_symlink()
archives = plan['retained_new_dbc_original_archives']
assert len(archives) == 16
for row in archives:
    path = Path(row['absolute_path'])
    assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']

# Recheck every original archived file in both derived trees before deletion.
archive_matches = []
for archive, destination in [(package / 'frozen-source.tar.gz', derived[0]),
        (package / 'artifacts/uta_reference_exchange-0.5.0a1.tar.gz', derived[1])]:
    count = 0
    with tarfile.open(archive, 'r:gz') as stream:
        for member in stream:
            relative = Path(member.name)
            assert not relative.is_absolute() and '..' not in relative.parts
            if member.isfile():
                actual = destination / relative
                assert actual.is_file() and not actual.is_symlink()
                data = stream.extractfile(member).read()
                assert len(data) == actual.stat().st_size and sha256(data).hexdigest() == digest(actual)
                count += 1
            else:
                assert member.isdir()
    archive_matches.append({'derived': str(destination), 'regular_files_exact': count})
assert [row['regular_files_exact'] for row in archive_matches] == [5159, 5166]
usage = visible_usage(trees + derived)
assert usage['matches'] == []
remaining = package_remaining_metadata()
# Keep the private metadata inventory external; only counts/equality are public.
(output / 'remaining-private-metadata-before.json').write_text(json.dumps(remaining, indent=2) + '\n')
before = {'started_at': datetime.now(timezone.utc).isoformat(),
    'plan_sha256': sha256(plan_path.read_bytes()).hexdigest(),
    'free_before': shutil.disk_usage('/workspace').free,
    'worktrees': rows, 'derived_directories': plan['package_derived_directories'],
    'retained_original_archives': archives, 'archive_member_recheck': archive_matches,
    'remaining_package_entries': len(remaining), 'visible_process_scan': usage,
    'owner_confirmation': 'All fifteen completed owners/root explicitly released dependencies; current candidate, reviewer, HMAC and all frozen/long-job sources excluded.',
    'no_original_archive_raw_database_auth_tls_or_job_deleted': True,
    'production_approved': False}
(output / 'before.json').write_text(json.dumps(before, indent=2) + '\n')
for row, path in zip(rows, trees):
    assert git('status', '--porcelain', '--untracked-files=all', cwd=path) == ''
    subprocess.run(['git', 'worktree', 'remove', '--force', str(path)], cwd=repo,
                   check=True, stdout=subprocess.DEVNULL)
    assert git('rev-parse', row['branch_ref']) == row['HEAD']
    assert git('rev-parse', row['HEAD'] + '^{tree}') == row['tree']
for path in derived:
    shutil.rmtree(path)
for row in archives:
    path = Path(row['absolute_path'])
    assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
assert package_remaining_metadata() == remaining
after = {'finished_at': datetime.now(timezone.utc).isoformat(),
    'removed_completed_clean_worktrees': len(rows),
    'all_named_refs_heads_and_trees_preserved': True,
    'removed_rebuildable_directories': [str(p) for p in derived],
    'all_16_original_archives_byte_exact_after': True,
    'remaining_package_metadata_inventory_unchanged': True,
    'remaining_package_entries': len(remaining),
    'free_before': before['free_before'], 'free_after': shutil.disk_usage('/workspace').free,
    'no_original_archive_raw_database_auth_tls_or_job_touched': True,
    'production_approved': False}
(output / 'after.json').write_text(json.dumps(after, indent=2) + '\n')
print(json.dumps(after))
