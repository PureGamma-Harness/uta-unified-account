# PR40 first CI: directed raw evidence export

This follow-up exports the already collected first failed push/Python3.10 unit
ZIP and connector-decoded job log so the evidence can be checked offline. It
adds files after first safe seal `f9702630a0edd95469a9c03de8c93c75a2810451`;
all five files in that seal remain byte-for-byte unchanged. Its manifest's
`original_zip_payloads_exported: false` describes that original seal. The new
[raw export manifest](../evidence/reviews/pr40-first-ci-independent/raw-first-push-python310/raw-export-manifest.json)
records this later, directed export.

The exact-head push remains **FAIL**: run44241282705, attempt1, head
`a2434bdfe711ead1d202f6c1527e527f73e2dfa2`, Python3.10 job134589520971.
The unit original records2061 tests,1FAIL,0ERROR,0skip and worker exit1.
The unique failure is the bounded SH capture precondition at
`tests/test_durable_faults.py:1461`; the twelve new selector IDs are individually
`ok`. The separate PR-event success remains metadata qualification; no PR-merge
unit originals or raw counts have been added. See the unchanged
[first CI review](pr40-first-ci-independent.md) and unit audit for the analysis.

## Exported originals and decoding boundary

- [Unit artifact14400281526](../evidence/reviews/pr40-first-ci-independent/raw-first-push-python310/push-unit-3.10-14400281526-connector.zip):89541 original ZIP bytes, SHA256 `f40438ac07ed26de922157137dc0fceb00f50436238623add809b7db6883b906`, equal to the provider digest. This is the successful connector transfer, not the earlier empty direct-download file.
- [Saved job log](../evidence/reviews/pr40-first-ci-independent/raw-first-push-python310/push-job-134589520971-connector-decoded.log):27619 bytes, SHA256 `c911b71b643d460dea097873f9e210be370d0f25d946b9b70c8ec6a9b1ed2cc4`. These are the exact bytes first saved from the connector's decoded text response, including its UTF-8 BOM/newlines. They are not claimed to be the original HTTP wire bytes.
- The ZIP's [summary.json](../evidence/reviews/pr40-first-ci-independent/raw-first-push-python310/unit-members/summary.json), [worker-result.json](../evidence/reviews/pr40-first-ci-independent/raw-first-push-python310/unit-members/worker-result.json), and [unittest.txt](../evidence/reviews/pr40-first-ci-independent/raw-first-push-python310/unit-members/unittest.txt) are also extracted byte-for-byte for direct inspection. All three CRCs, sizes and SHA256 hashes are recorded in the new manifest.

Before copying, the exact ZIP, its three decoded members and saved log were
checked for the manifest's finite PEM/private-key, GitHub-token, signed-URL,
credential-header, token-assignment and literal nonce-value patterns. There
were no matches. This is a bounded pattern check of these specified synthetic
CI payloads. No arbitrary private directory was scanned or exported. Private
transport headers, signed references, redirect/403 receipts, the private ledger,
and the earlier zero-byte failed download remain private and unchanged. The
successful small package remains report-only in the existing safe audit; its
archive and any wheel/sdist payload are not included.

## Offline integrity check

From the repository root, this standard-library-only snippet checks the six
manifest-listed files and verifies every exported ZIP member against its CRC,
SHA256 and separate extracted copy. It reads evidence only and runs no UTA code
or test. Source-map and test-count details remain visible in the raw JSON/logs
and the existing unit audit.

```sh
python - <<'PY'
import hashlib, json, pathlib, zipfile, zlib
root = pathlib.Path('.')
base = root / 'evidence/reviews/pr40-first-ci-independent/raw-first-push-python310'
manifest = json.loads((base / 'raw-export-manifest.json').read_text())
for item in manifest['files']:
    data = (root / item['path']).read_bytes()
    assert len(data) == item['bytes'], item['path']
    assert hashlib.sha256(data).hexdigest() == item['sha256'], item['path']
archive_path = root / manifest['unit_artifact']['export_path']
archive_bytes = archive_path.read_bytes()
assert hashlib.sha256(archive_bytes).hexdigest() == manifest['unit_artifact']['provider_sha256']
with zipfile.ZipFile(archive_path) as archive:
    assert archive.namelist() == [m['archive_member'] for m in manifest['members']]
    for member in manifest['members']:
        data = archive.read(member['archive_member'])
        assert len(data) == member['bytes']
        assert format(zlib.crc32(data) & 0xffffffff, '08x') == member['crc32']
        assert hashlib.sha256(data).hexdigest() == member['sha256']
        assert data == (root / member['export_path']).read_bytes()
print('directed first-CI raw integrity: OK')
PY
```

This export performed no network read/download, CI rerun, target import, SQL,
local test, new push, matching smoke or benchmark. Snapshot remains default OFF;
production, real funds and snapshot-mode SQLite/settlement/performance approval
remain outside this evidence.
