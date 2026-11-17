"""Read-only tracked-diff/history material scan for the synthetic credit draft.

This is a scoped publication check, not a general secret scanner/security audit.
Findings contain hashes/locations only, never matched credentials or nonce data.
"""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile


ALLOWED_SUFFIXES = (".py", ".md", ".json", ".txt", ".csv")
SOURCE_ARCHIVES = frozenset({"tests/fixtures/legacy_credit_45818c0_uta.tar.gz",
                           "tests/fixtures/legacy_credit_899c91d_uta.tar.gz"})
SENSITIVE_KEYS = frozenset({"owner_nonce", "nonce", "api_key", "api_secret", "secret",
    "private_key", "signing_key", "access_token", "refresh_token", "x-uta-nonce", "x-api-key"})
PATTERNS = {
    "private_key_or_tls_material": re.compile(rb"-----BEGIN (?:[A-Z ]*PRIVATE KEY|CERTIFICATE)-----"),
    "github_credential": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "aws_access_identifier": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "signed_or_token_url": re.compile(rb"https?://[^\s\"<>]+[?&](?:X-Amz-Signature|X-Goog-Signature|access_token|client_secret|signature|token|sig)=[^\s\"<>]+", re.I),
}


def git(*arguments, input=None):
    return subprocess.check_output(["git", *arguments], input=input)


def inspect_bytes(path, data, *, blob=None):
    found = []
    def note(category, *, location=None, value=None):
        item = {"path": path, "category": category}
        if blob is not None: item["blob"] = blob
        if location is not None: item["location"] = location
        if value is not None: item["value_sha256"] = sha256(value.encode()).hexdigest()
        found.append(item)
    if data.startswith(b"SQLite format 3\x00"):
        note("database_bytes")
    for category, pattern in PATTERNS.items():
        for match in pattern.finditer(data):
            note(category, location={"line": data[:match.start()].count(b"\n")+1})
    if path.endswith(".json"):
        try: document = json.loads(data)
        except (ValueError, UnicodeError): return found
        pending = [(document, "$", 0)]
        while pending:
            value, at, depth = pending.pop()
            if depth > 64:
                note("json_depth_exceeded", location=at)
                continue
            if isinstance(value, dict):
                for key, child in value.items():
                    child_at = at+"."+key
                    if key.lower() in SENSITIVE_KEYS and isinstance(child, str) and child:
                        note("nonnull_sensitive_json_field", location=child_at, value=child)
                    pending.append((child, child_at, depth+1))
            elif isinstance(value, list):
                pending.extend((child, at+"["+str(index)+"]", depth+1) for index, child in enumerate(value))
            elif isinstance(value, str) and value[:1] in ("{", "[") and len(value) <= 16*1024*1024:
                try: child = json.loads(value)
                except ValueError: continue
                pending.append((child, at+"<retained-json>", depth+1))
    return found


def inspect_archive(path, data, *, blob=None):
    found, members = [], []
    if path not in SOURCE_ARCHIVES:
        return [{"path": path, "category": "archive_not_explicitly_allowed"}], members
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            if member.isdir(): continue
            if (not member.isfile() or member.name.startswith("/") or ".." in Path(member.name).parts
                    or not (member.name == "LICENSE" or member.name.startswith("uta/") and member.name.endswith(".py"))
                    or member.size > 32*1024*1024):
                found.append({"path": path, "category": "nonpublic_source_archive_member", "member": member.name})
                continue
            raw = archive.extractfile(member).read()
            members.append({"path": member.name, "bytes": len(raw), "sha256": sha256(raw).hexdigest()})
            found.extend(inspect_bytes(path+":"+member.name, raw, blob=blob))
    return found, members


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--report", required=True)
    options = parser.parse_args()
    base = git("merge-base", options.base_ref, "HEAD").decode().strip()
    head = git("rev-parse", "HEAD").decode().strip()
    tracked = set(git("ls-files", "-z").decode().split("\0"))
    changed = sorted(set(git("diff", "--name-only", "-z", base, "HEAD").decode().split("\0")) & tracked - {""})
    findings, inventory = [], []
    for path in changed:
        data = Path(path).read_bytes()
        if not path.endswith(ALLOWED_SUFFIXES) and path not in SOURCE_ARCHIVES:
            findings.append({"path": path, "category": "file_type_not_allowed"})
        item = {"path": path, "bytes": len(data), "sha256": sha256(data).hexdigest()}
        if path in SOURCE_ARCHIVES:
            result, members = inspect_archive(path, data)
            findings.extend(result)
            item["source_archive_members"] = members
        else: findings.extend(inspect_bytes(path, data))
        inventory.append(item)
    objects = {}
    for line in git("rev-list", "--objects", base+".."+head).decode().splitlines():
        identity, _, path = line.partition(" ")
        if path: objects[identity] = path
    checks = git("cat-file", "--batch-check", input=("\n".join(objects)+"\n").encode()).decode().splitlines()
    historical_blobs = 0
    for line in checks:
        identity, kind, size = line.split()
        if kind != "blob": continue
        historical_blobs += 1
        path = objects[identity]
        data = git("cat-file", "blob", identity)
        if path in SOURCE_ARCHIVES:
            result, _ = inspect_archive(path, data, blob=identity)
        else: result = inspect_bytes(path, data, blob=identity)
        findings.extend(result)
    report = {"format": 1, "scope": "tracked changed files and newly reachable history blobs; source archives inspected in memory; no private DB/auth/key reads",
        "head": head, "base_ref": options.base_ref, "merge_base": base,
        "allowed_suffixes": list(ALLOWED_SUFFIXES), "explicit_source_archives": sorted(SOURCE_ARCHIVES),
        "files": inventory, "current_file_count": len(inventory), "historical_blob_count": historical_blobs,
        "findings": findings, "finding_count": len(findings), "passed": not findings,
        "limitations": "pattern/typed-field publication check only; hashes, public financial synthetic rows and code metadata are allowed; not independent security or production acceptance"}
    Path(options.report).write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({key: report[key] for key in ("head", "merge_base", "current_file_count", "historical_blob_count", "finding_count", "passed")}, sort_keys=True))
    if findings:
        print(json.dumps(findings[:20], indent=2))
    raise SystemExit(0 if not findings else 1)


if __name__ == "__main__":
    main()
