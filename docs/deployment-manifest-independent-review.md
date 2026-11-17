# Offline deployment declaration: independent bounded review

Reviewed source `ebe9e28d3707042cb51ae8ca818a0d5cc1fe1fc2`, entry point
`tools/check_deployment_manifest.py`, SHA-256
`02be98e4cc3194c1475f7711b7837b4a7885cd6cbf0983e35b1be8d4fdf9fb19`.
This review reads the new tool, tests, template and stated contract. It does
not change the tool or rerun the original seventeen-case suite.

## First finding: malformed numeric JSON escapes the refusal contract

`load_manifest` catches JSONDecodeError, UnicodeDecodeError and RecursionError,
but ordinary ValueError from JSON integer conversion escapes both this handler
and `main`. One authorized fresh synthetic probe on CPU 3 / Python 3.13.5
used a 4,512-byte manifest containing a 4,501-digit integer. With the actual
4,300-digit interpreter limit it produced the original builtins.ValueError,
empty stdout and no return code two. The first raw result retains its exact
exception type and arguments. Full traceback frames were not captured by
that probe and are not reconstructed afterward. This is a stable error-output
contract defect, not a financial authorization bypass.

The probe's measured interval was 4,383,491ns. It read only its new synthetic
manifest; referenced-role content reads and metadata entry were hard-denied.
No SQL, child process, network, worker or signal was used. The new NUL and
unencodable UTF-8 declared-path subcases both returned their exact expected
codes, with all metadata and content reads denied. Their narrow pass does not
upgrade the original recorded b88 full-suite NOT_RUN or c690 results.

A minimal fix can preserve `ManifestError` explicitly and convert ordinary
JSON ValueError into `manifest_json_invalid`. Catching all ValueError without
first preserving ManifestError would also change duplicate-field and
nonfinite-number codes, because ManifestError is a ValueError subclass.
Verify the fixed source separately with this first failing input and preserve
the existing duplicate/nonfinite refusal codes. No retry on unchanged source
was performed.

## Other reviewed boundaries and limits

The manifest schema strictly separates review_synthetic declarations, matching
nonzero source/artifact/rule references, the single-host SQLite WAL/FULL/no
replication declaration, and the synthetic USD Cross spot/linear allowlist.
Unknown fields, unsupported product/storage claims and self-declared approval
are rejected. Directory roles are lexically separate; private files require
the declared owner, mode 0600, one link and distinct inodes. Current symlink
components, changed metadata and artifact group/other writability are rejected.
Normal and typed-refusal reports never authorize activation or production.

These are declaration/lstat checks. Artifact digest, package provenance,
rules contents, secret/profile/TLS contents, actual storage settings and
approval authenticity remain unverified. Two observations are not an atomic
snapshot or a guarantee against concurrent malicious replacement. No runtime,
systemd unit, database, deployment or real-funds path was exercised. The finding
above should be fixed before treating the documented error contract as met;
the tool still cannot constitute production acceptance after that fix.

## Fixed-source limited closure

Fixed source `fb54a5aa0907e9113e1ead75bba93b05e9ad8899`, tool SHA-256
`522899317db7b7d4a1a3369621cbf690a9ff553b45a908121f5ed55c64f63753`,
preserves ManifestError before catching ordinary decoder ValueError and checks
the manifest argument's path encoding before filesystem access. All other
tool functions are AST-identical. There is no remaining specific static
blocker in this refusal-contract change.

The author's separately authorized first fixed-source batch reports 21 tests,
zero failures/errors/skips, unchanged source, CPU 2 / Python 3.12.14 and the
actual 4,300-digit conversion limit. Its measured test interval before result
serialization is 23,842,343ns. It covers the real 4,501-digit input, generic
ValueError, retained duplicate/nonfinite codes, and manifest/declared path
encoding. Six synthetic manifests were read, at most 4,512 bytes; listed
SQL/process/signal APIs were mocked and no forbidden call was recorded.

The independent `verify_fixed_bindings.py` first read passed all 14 Git/AST/
original-evidence checks. It bound the same-process proof, plan, test/tool
Git blobs, fixed driver and raw 21-pass log. The reviewer did not execute that
fixed suite. Original metadata was read with O_NOATIME and unchanged stat
fields were checked. API mocking is not claimed to be a capability sandbox.
The original independent RED, its missing-full-traceback limitation, and the
older f406/c690/b88/ebe9 result scopes remain unchanged. This limited closure
establishes no actual release, storage or approval authenticity and enables
neither activation nor production.
