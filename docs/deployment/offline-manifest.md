# Offline deployment manifest source inspection

This optional engineering preflight compares explicit files on disk with a
recognized manifest whose SHA-256 the caller supplies separately. Every result
contains `NOT_PRODUCTION_APPROVAL`. A match establishes only the bytes read for
the selected pins. The program cannot determine whether the supplied digest came
from a trusted reviewer, signature, or release channel.

## Invocation and trust boundary

Run the standalone script with Python's standard library. It does not import UTA,
load a financial model, contact a database or network, inspect a process, start a
worker, or run a deployment or rollback.

```sh
python3 -I -S tools/inspect_deployment_manifest.py \
  --source-root /explicit/local/source \
  --manifest evidence/integrations/funding-hold-v3/combined-manifest.json \
  --expected-manifest-sha256 "$REVIEWED_EXTERNAL_MANIFEST_SHA256"
```

`REVIEWED_EXTERNAL_MANIFEST_SHA256` must be supplied from an independently trusted
external record. It is not read by the checker from the environment. Do not fill
it by hashing the candidate manifest, reading an adjacent `.sha256`, or trusting
the manifest's own declaration. The CLI requires exactly 64 lowercase hex digits
and compares the manifest bytes before parsing them. It neither verifies a
signature nor upgrades the supplied value into authenticated authority. Even a
matching result keeps `expected_digest_trust` and `manifest_authentication`
explicitly `NOT_VERIFIED`.

The documented invocation uses Python's isolated mode without site startup, so
local module shadows, user site packages, and site startup hooks are excluded.

`--manifest` is a canonical relative path within the selected source root, using
ASCII path components and `/`. Absolute paths, `..`, `.`, empty components,
backslashes and symlinks are rejected. The source root and each directory in its
absolute path are also opened without following symlinks. Choose a quiescent,
owned source directory: directory changes during inspection reject the result.

## Recognized closed schemas

`funding-hold-v3-combined-source/v1` recognizes every required field of the
combined manifest at source commit
`2b1b2a6d493c3258ce0446b45959f76318cb17d6`, including review commit IDs,
verification pin arrays, expected test counts, and declared execution and
production states. All these metadata fields are required and type checked.
They remain declarations: the checker does not run reviews, test execution,
first CI, activation, capacity assessment, or financial validation.

The schema requires the exact 67 explicit V4 runtime paths, 66 Python paths,
three market-control overlay paths with the declared overlay origin, and 64
remaining paths with the declared base origin. Count and byte totals must agree
with individual pins. Only these 67 runtime files are read and compared.
`verification_source_pins` are structurally checked, not opened or validated
against source bytes. Unlisted actual files and imports are not enumerated or
certified; inventory completeness remains `NOT_VERIFIED`.

`offline-deployment-synthetic-source/v1` is a separate, explicitly labeled
`SYNTHETIC_FIXTURE_ONLY` profile for hand specified test fixtures. It requires
`purpose: SYNTHETIC_TEST_ONLY`, a declared source basis, and explicit pins and
totals. It cannot claim to have inspected the combined V4 inventory.

Neither v1 schema has an extension bag. Unknown top-level or pin keys, missing
keys, unknown schema versions, duplicate JSON keys, duplicate paths, and native
JSON booleans in integer fields are rejected. A future schema or extension needs
an explicit versioned implementation and review. Do not silently discard new
metadata or guess its meaning. Currency precision and other financial fields
are outside both schemas; adding one produces a rejection, not financial
validation.

## Bounds and output

The checker opens only the manifest and named runtime pins. It does not walk the
repository, archives, or other source trees. The bounds are 128 explicit files
including the manifest, 2 MiB per runtime file, 256 KiB for the manifest, and
16 MiB of total streams including the manifest. Manifest validation also limits
verification pin declarations within the explicit-file bound. JSON nesting is
limited to 12, object keys to 64, nodes to 4,096, and string lengths to 512.

Directory traversal uses descriptor-relative opens and `O_NOFOLLOW`; regular
files are required. Nonblocking opens allow nonregular objects such as FIFOs to
be rejected without waiting for a writer. File identity, mode, size, link count,
mtime and ctime are compared with `fstat` before and after each bounded read.
Directories opened for traversal are checked for changes. This detects changes
during those reads; it does not lock files or prevent changes after inspection,
and sequential file observations are not an atomic repository snapshot.

Output is one bounded JSON object with fixed public reason codes, declared
source-basis commits, manifest hash, validated relative paths, missing and
mismatched pins, and counts. It never emits file contents, absolute private
paths, OS exception text, environment values, process IDs, or signing keys.
Exit codes are:

| Code | Result | Meaning |
| --- | --- | --- |
| 0 | `STATIC_PIN_MATCH` | All selected runtime bytes matched this recognized manifest. |
| 1 | `STATIC_PIN_MISMATCH` | One or more selected runtime pins were missing, changed, unreadable, or rejected. |
| 2 | `REJECTED` | Arguments, manifest digest/schema, root, or inspection stability could not be accepted. |

Every result explicitly leaves active binary/loaded code, runtime configuration,
health, signature and financial authority, lease/fencing, journal/replay,
restore/RPO, and deployment/rollback readiness unverified. The tool issues no GO,
does not reseal artifacts, and cannot establish a recoverable checkpoint.

## Packaging and removal

This milestone adds a standalone tool, synthetic fixtures, test definitions and
this document in an independent branch based on `2b1b2a6`. It does not change the
runtime inventory, CI configuration, benchmark entrances, or the frozen first-CI
candidate. Review and select the tool separately before any future packaging.

Adopting it means distributing this script through the chosen engineering tool
channel and supplying separately reviewed manifest digests. Rollback of this
addition means ceasing its use and removing the added tool, fixtures, test
definitions, and document. There is no database schema, journal, balance, lease,
configuration, or service change to reverse. Application deployment, production
rollback, and data restoration remain separate procedures requiring their own
evidence and authorization.

Validation supplied by this milestone: source review and artifact metadata only.
Checker execution, compilation, imports, test discovery and tests are **NOT_RUN**.
