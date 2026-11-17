"""Publish allowed recovery metadata with explicit redaction; never open a DB.

Original case directories remain untouched. Database/lock/WAL/SHM bundles are
excluded, and original/public byte hashes distinguish sanitized derivatives.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

WRITER_NONCE = re.compile(r"worker:[0-9a-f]{32}\Z")
UUID_VALUE = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
HEX_SESSION = re.compile(r"[0-9a-f]{32}\Z")
SECRET_KEYS = {"owner_nonce", "coordinator", "nonce", "authorization", "auth_token",
               "access_token", "refresh_token", "api_key", "password", "secret"}


class Redactor:
    def __init__(self):
        self.labels = {}
        self.counts = {}

    def label(self, category, value):
        key = (category, value)
        if key not in self.labels:
            self.labels[key] = f"REDACTED_{category}_{1+sum(k[0] == category for k in self.labels)}"
        self.counts[category] = self.counts.get(category, 0)+1
        return self.labels[key]

    def value(self, value, key=None):
        if isinstance(value, dict):
            # Native code-artifact payloads contain source/loaded-code constants,
            # not live lease credentials. Preserve their exact content identity.
            if {"source_files", "loaded_engine", "source_digest"} <= value.keys():
                return value
            return {name: self.value(item, name) for name, item in value.items()}
        if isinstance(value, list):
            return [self.value(item) for item in value]
        if isinstance(value, str):
            if key and key.lower() in SECRET_KEYS and value:
                return self.label("PRIVATE_IDENTIFIER", value)
            if WRITER_NONCE.fullmatch(value):
                return self.label("PRIVATE_IDENTIFIER", value)
            if UUID_VALUE.fullmatch(value):
                return self.label("BOOT_OR_SESSION_ID", value)
            if key in ("id", "session_id", "job_id") and HEX_SESSION.fullmatch(value):
                return self.label("SESSION_ID", value)
            if value.startswith(("{", "[")):
                try:
                    parsed = json.loads(value)
                except ValueError:
                    return value
                sanitized = self.value(parsed)
                if sanitized != parsed:
                    return json.dumps(sanitized, sort_keys=True, separators=(",", ":"))
        return value

    def data(self, source):
        data = source.read_bytes()
        if not data:
            return data
        text = data.decode("utf-8")
        if source.suffix == ".jsonl":
            values = [json.loads(line) for line in text.splitlines()]
            sanitized = [self.value(value) for value in values]
            return ("".join(json.dumps(value, sort_keys=True)+"\n" for value in sanitized).encode()
                    if sanitized != values else data)
        try:
            value = json.loads(text)
        except ValueError:
            if WRITER_NONCE.search(text):
                raise ValueError("unstructured nonce-bearing evidence requires explicit review")
            return data
        sanitized = self.value(value)
        return (json.dumps(sanitized, indent=2, sort_keys=True)+"\n").encode() if sanitized != value else data


def archive(cases, output):
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    redactor, manifest, retained = Redactor(), {}, {}
    for label, source in cases:
        source = Path(source).absolute()
        destination = output/label
        files = [path for path in sorted(source.rglob("*")) if path.is_file() and "authority" not in path.relative_to(source).parts]
        external = [Path(str(source)+suffix) for suffix in (".console.stdout.json", ".console.stderr.txt", ".live-outer-pidfd.json")]
        for path in files+[path for path in external if path.exists()]:
            relative = str(path.relative_to(source)) if path in files else "external/"+path.name
            target = destination/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            before = path.read_bytes()
            after = redactor.data(path)
            target.write_bytes(after)
            manifest[str(target.relative_to(output))] = {
                "private_original_path": str(path), "private_original_bytes": len(before),
                "private_original_sha256": sha256(before).hexdigest(),
                "public_bytes": len(after), "public_sha256": sha256(after).hexdigest(),
                "redacted_derivative": after != before}
        # Copy database byte fingerprints from the ALREADY RETAINED manifest.
        # This command does not open any DB, lock, WAL or SHM file.
        original_manifest = next(source.glob("manifest-after-*.json"))
        references = json.loads(original_manifest.read_text())["files"]
        retained[label] = {"private_authority_path": str(source/"cohort/authority"),
                           "files_from_original_manifest": {name: value for name, value in references.items()
                                                            if name.startswith("cohort/authority/")},
                           "included_database_bytes": False}
    (output/"private-authority-references.json").write_text(json.dumps(retained, indent=2, sort_keys=True)+"\n")
    manifest["private-authority-references.json"] = {
        "public_bytes": (output/"private-authority-references.json").stat().st_size,
        "public_sha256": sha256((output/"private-authority-references.json").read_bytes()).hexdigest(),
        "redacted_derivative": False}
    report = {"format": 1, "files": manifest, "redaction_counts": redactor.counts,
              "included_database_bytes": False,
              "policy": "Live writer/coordinator/auth identifiers, host boot UUIDs and cohost session IDs are replaced by stable labels. Code-artifact manifests remain unchanged. Original raw files are private and unchanged; their hashes are witnesses, not public-file checksums."}
    (output/"public-manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--large", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = archive((("1k", args.contract), ("250k", args.large)), args.output)
    print(json.dumps({"public_files": len(report["files"]), "redaction_counts": report["redaction_counts"], "included_database_bytes": False}))


if __name__ == "__main__":
    main()
