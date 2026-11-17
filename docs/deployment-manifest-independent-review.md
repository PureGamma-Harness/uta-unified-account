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
