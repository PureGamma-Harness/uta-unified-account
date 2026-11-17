# Independent package review: bb34b5f

**PASS for this exact package scope.** Source is
`bb34b5fb4397f485c04fe440557b24bb28d1cae2`, reviewed independently from the
clean frozen `/workspace/uta-observer-freeze-bb34b5f` source. This report does
not accept full local QA, remote CI, smoke, long-run, HA, real-funds or10,000/s
capacity gates. The experimental runner and its timing-footer amendment are
absent from this candidate; its separate NO_GO remains unchanged.

## Actual artifact and source identity

| Artifact | Bytes | Independently recomputed SHA256 |
|---|---:|---|
| `uta_reference_exchange-0.5.0a1-py3-none-any.whl` | 279432 | `89c9e7503223d8ac519aa5ed6707786d6aecbc45483137d5af90b0488f026cc6` |
| `uta_reference_exchange-0.5.0a1.tar.gz` | 29129419 | `9e2f05cc187ba0bed1e145a33b38627e50a9ac2351023558578d2dde150d0e2e` |

Both actual originals match the original artifact manifest. All2,536 tracked
files are present with exact source bytes in the sdist, whose2,543 regular
members include build metadata. The52 runtime Python/HTML files match frozen
source, wheel, sdist and the actual installed site. The independently hashed
runtime tree is
`e6e06e44c1f7bb6e36fc614a5f03a679ba3b21efd1ba9a712584c6730f14a792`.
The frozen source was clean and at the exact SHA before and after the review.
No production function was imported to supply an expected result.

The original execution record has15 named commands with actual exit0 and
CPU2. Original installed records bind this same source and both artifacts,
isolated interpreter, cleared PYTHONPATH,8 functional tests,8 console commands
and3 read-view tests. Actual copied helper hashes match the frozen tests;
actual8/3 test logs end OK without resource/unraisable warnings. Original
sdist-only logs independently show legacy7, archival1 and release-verifier19,
all OK. These are reviews of actual original results, not newly rerun tests.

## Negative controls close the actual artifact gap

The generic omission collector's permissive contract identified in independent
RUN-R5 remains a separate tooling issue. Its declarations alone were not
accepted here: complete original verifier reports and actual archive contents
were independently checked for this release.

| Actual negative case | Required false checks; all other checks true | Missing | Unmodified positive side |
|---|---|---|---|
| wheel runtime omission | `wheel_runtime_exact` | wheel member `uta/failure_diagnostics.py`; sdist missing list empty | Original sdist SHA exactly matches the positive manifest |
| sdist runtime omission | `sdist_runtime_exact`, `sdist_required_files_exact` | exactly `uta/failure_diagnostics.py`; mismatched list empty | Original wheel SHA exactly matches the positive manifest |
| each of6 tracked ZIP omissions | `sdist_required_files_exact` | exactly that ZIP; mismatched list empty | Original wheel SHA exactly matches the positive manifest |

For both runtime cases, the actual negative bytes/hash match the raw verifier
report and collector record, source/runtime map/tree match the positive
manifest, and the recorded actual exit is1. Independent pure ZIP/tar member
hash comparisons prove the entire negative archive differs from the actual
positive only by the intended omitted file. Version, unrelated runtime and
all remaining verifier checks stay true. Thus the earlier mixed-input risk
is excluded for these actual eight negative controls; the generic collector
is not declared fixed.

All6 tracked historical CI ZIPs are byte-identical between source and positive
sdist. Their three original members are hashed independently, and their227,
217 or208 historical source inputs are independently recomputed against the
corresponding original Git blobs. Original PR merge identifiers and the
original failures/errors remain unchanged. Historical artifacts do not
qualify bb34's current CI. Each ZIP negative report binds the same positive
wheel, exact runtime map/tree, expected one-member missing list and actual
negative archive bytes/hash. Six negative tar archives were not each fully
member-diffed; their complete original reports and artifact hashes were
checked. This narrower check is stated explicitly in the ZIP subreview.

## MANIFEST and milestone review

The MANIFEST amendment adds only `*.jsonl.gz` and `*.patch` to the existing
`evidence/` inclusion list. The three affected tracked files are the incident's
public classification/timeline gzip streams and its directory-walk patch.
All three are now included byte-for-byte; none is a live database or auth/TLS
asset. The complete tracked-file equality check detects an omitted additional
file rather than relying only on this extension list.

The new milestone document correctly leaves production, new full local/CI,
60-second matching/settlement/restart smoke and a new preregistered six-hour
run pending. It preserves the original763 partial failure and a35 remote
failures; it excludes new borrowing, unused WS listener integration, native
credit V2 and the performance runner. Its rollback preserves original job
state and irreversible writer capability and requires a fresh synthetic
environment instead of replaying an older writer into marked storage.
No package-scope blocker was found in that document or the MANIFEST change.

## Evidence, reproducibility and limits

All review files are under
`evidence/reviews/package-bb34b5f-independent/`. The standard-library
`verify_actual_package.py` performs read-only hashes and archive parsing,
explicitly pins itself to CPU2, enforces20s wall/18s CPU bounds and imports no
UTA or SQL module. Its actual successful review took1.021s. The separately
delegated six-ZIP review took0.829s on CPU2. Neither ran a service, collector,
SQL operation or test suite. All original package commands remain original
and were not rerun. The original binaries and private work directories stay
external; only safe original JSON reports/test logs and hash indexes are
copied. No authentication files, TLS keys, financial DBs or signed URLs were
published.

The first pure review script incorrectly assumed16 root execution records;
the actual complete named set has15. Its original script and transcribed tool
AssertionError are retained, and the reviewer assertion was corrected to the
explicit15-name set before the successful pure review. This was a reviewer
script mistake, not an original package failure or a replaced benchmark run.

To reproduce the pure review while the original external artifacts remain:

```sh
python -B evidence/reviews/package-bb34b5f-independent/verify_actual_package.py
```

The output includes exact input hashes and remains package-scope only.
Deploy only through the independent full-candidate gates. Rollback for this
review commit is docs/evidence-only and affects no runtime, balances, schema,
processes or original results. Keep all original artifacts and negative
controls. No live deployment or financial activation approval is implied.
