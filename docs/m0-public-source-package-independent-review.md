# Independent review of the public M0 source-package fix

Independent delivery review: **PASS within the scope below**. The single archive-reader invocation used CPU 3, a 15-second outer timeout and 0.935504910 seconds of reader time. It returned exit 0 with no stderr. No build, existing archive verifier or test was rerun.

The reviewed code is `f3a45ade08e63bc99f224017d79b31da9236d840`, with parent `1d727b9d8e121611d0227dbee162192c13a76769`. Author evidence commit `650296dd9dc1ce07256746fcbbe1d4d9bca669b0` is a later documentation/evidence tip, not the source built by the original invocation. This independent branch starts from the code commit; its full index was initialized before sparse checkout, and tracked deletions were excluded from the review commit.

## Code scope

The complete code diff changes only `MANIFEST.in`: three additions, no deletions, and exactly these explicit includes:

- `.github/workflows/independent-m0.yml`
- `.github/workflows/independent-m0-once.yml`
- `config/m0-stream-recipient-public.pem`

The independent reader reconstructed the expected manifest from the parent bytes and those three lines, then compared it with the fixed Git blob. No general PEM or private-key glob was added. The selected certificate is public; its contents were neither printed nor added to this evidence commit. Existing workflow and runtime contents were unchanged by the code fix.

## Independently checked originals

Both archive hashes and lengths were recomputed directly from the retained private originals and matched the first author manifest:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `uta_reference_exchange-0.5.0a1-py3-none-any.whl` | 357,465 | `53ab818ba6225de89b74c3a8a047a93aca905df6d7d7a31c54814835267ad178` |
| `uta_reference_exchange-0.5.0a1.tar.gz` | 43,733,261 | `a6b0d24cb9c3fe25023e97281774c3caa54eeda7afd1c3cd1e75e5dbca113ad4` |

Each of the three public support paths occurs exactly once in the source distribution and matches its fixed Git blob byte for byte. These support files are source-distribution members; none occurs in the wheel. No workflow was executed by reading these members.

Both formats have the exact Git runtime inventory: **62 files, comprising 61 Python files and one HTML asset**. Every runtime payload in both archives was independently compared byte for byte with its fixed Git blob. The original report's 62 runtime hashes also match the independently read Git payloads. There were no duplicate members in either archive, and source members have safe relative paths, regular-file/directory types and one root directory.

The original verifier's ordered **5,839-path required list** equals the fixed Git tree list. Every required path occurs once in the source archive. Both retained input maps have 5,839 entries, with identical raw bytes/SHA-256, equal parsed maps, and path sets equal to the Git tree. Each recorded input Git blob ID and byte length also matches Git tree metadata. Each map is 1,721,576 bytes with SHA-256 `37b98111f2b60929313b5dc838a1fe9391ecded0484f206df6c9154ae8b76127`.

**This independent review did not compare every one of the 5,839 source payloads with Git or recompute all input payload hashes.** Full source payload equality remains the result of the author's first existing-verifier run. The independent payload comparison covers 65 unique Git files: 62 runtime files plus the three public support files. The required-list, archive-member and recorded-blob/size checks cover all 5,839 paths without claiming full independent payload verification.

The committed author `artifact-manifest.json`, `first-result.json` and `admission.json` were independently compared with their retained private originals and are byte-identical. The report and first result agree on all seven true verifier checks, frozen source identity and `production_approved: false`. The original batch remains CPU 4, 180-second budget, **34.871726960 seconds** total, with **24.031178588 seconds** for the existing verifier and 18,294,833,152 free bytes afterward. These durations are original evidence, not new measurements of the build or verifier.

## Boundary, risks and rollback

The original M04 general-CI evidence remains `dc9e42ababfd29106129d85ecd00ae4c38ebbb8c`: all four unit jobs failed and package checks were **NOT_RUN**. This review neither rebuilds that old source nor changes that outcome. Local packaging acceptance does not resolve the outstanding general-CI/unit failures or establish installed-CLI behavior, certificate validity, production readiness or deployment authorization.

The reader did not execute repository Python code, units, an installed CLI, SQL, owner or financial actions, certificate cryptography, network requests, CI, services or long-running operations. It ran only Git reads and standard-library archive, JSON and hash operations. The first invocation and its original result were retained without retry. There is no push, trigger or production GO from this review.

The manifest fix broadens source-distribution selection by exactly the three public support files. Reverting code commit `f3a45ad` removes those three includes; a previously reviewed artifact can be restored by its recorded hash. This manifest-only change requires no database migration or financial compensation. Preserve both the original CI failure evidence and first package result through any rollback.

## Review artifacts

- [First independent reader result](../evidence/m0-public-package-f3a45ad-independent/first-reader-result.json)
- [Invocation, bounds and private-original hashes](../evidence/m0-public-package-f3a45ad-independent/invocation.json)
- [Exact reader source as text](../evidence/m0-public-package-f3a45ad-independent/reader-source.txt)

Archives, input-map originals, raw stdout/stderr and all key material remain outside Git. Only this review document, safe JSON and reader-source text are committed. The result is an independently recorded packaging review within the stated boundary; production approval stays false.
