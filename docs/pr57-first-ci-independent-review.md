# Independent PR57 first-CI evidence review

**Limited first-CI evidence: accepted. Production: NO_GO.** The source is `d1fd381bde923dc4010977058b76e34d6162e9a9`; collector SAFE is `a92d94d6f1bc4d76ae09992096d6cb4e1aa68145`. Later local review commits or runtime changes are not covered by these CI runs. This review separates source, provider CI, actual release bytes, installed observations and release qualification.

The [independent evidence](../evidence/reviews/pr57-first-ci-independent/raw-review.json) contains exact pins, hashes, counts and read budgets. No target imports, compilation, SQL, installation, archive extraction, worker/process/PID inspection, network access or CI rerun occurred. Existing private originals remain sealed; no archive payload was copied to disk. Administrative parser corrections were data-reader work, not target/CI retries; every repeated archive member read is charged below.

## First runs and exact source

The retained initial and terminal provider records bind first push run **44320885833** and first PR run **44320956929**, both attempt1 and source d1fd. Each has four Python3.10–3.13 jobs. All **8 jobs and 200 steps succeeded**. Each actual provider job log contains a recorded validation JSON reporting **2,171 tests, zero failures/errors/skips** and successful worker exit. Those logs do not contain the full per-method unittest output; no method-level coverage is inferred from that aggregate alone.

The fixed push and PR Python3.13 unit archives separately provide complete `unittest.txt`, worker results, and before/after source maps. Both report2171/0F/0E/0skip with worker exit0 and unchanged clean sources. Each map has408 entries and each entry matches the local immutable d1fd Git object. The exact unittest payload hashes also match their summaries; each unit ZIP has three verified CRC members.

The two fixed unit texts contain74 explicit plain-ok observations across the37 selected policy, funding, calculator, oracle and source-inventory methods: four admission/credit contract methods, six local funding methods, six funding-obligation methods, nine decimal-kernel methods, six independent-oracle methods and six lease/source-identity methods, each observed once in each archive. This is source-checkout unit coverage, not installed-wheel specialized coverage. Lease observations are empty and not truncated in the two fixed reports; that does not establish a prior intermittent failure's cause or exercise a failure diagnostic branch.

The PR job checkout is provider merge `6e90e86450b4cca93a398acf29ada11ef56fa201`. Retained provider commit metadata gives parents `c3e937a967711cd5cae7293ac3bf63c8260d8528` and d1fd, and a tree exactly equal to the locally verified d1fd tree. That merge commit object is unavailable locally; it was not fetched or read as a local object. Push checkouts identify d1fd directly. The runtime identity is66 files:65 Python modules plus one HTML file, totaling1,456,126 bytes.

## Actual release identity and installed scope

All four selected downloaded artifact sizes and SHA-256 values match their original first-run provider metadata and download facts. The independently streamed release is the push Python3.13 artifact **14435356583**, outer ZIP54,692,909 bytes. Other jobs' independently downloaded binary archives are outside this review.

| Artifact | Actual bytes | SHA-256 |
| --- | ---: | --- |
| Wheel | 394,300 | `a61d2bbb1c5a466be78590fb67ca5f9632168ab849aff463ed934afacad965b8` |
| Source distribution | 54,542,488 | `66dca1e8fdb715a038c54bb90737807116a3572e85e8432a62f68f20e4e66532` |

The wheel has72 verified CRC members and a complete matching RECORD hash/size inventory. All66 runtime members compare literally to Git; version and the three console entry points match the declared package. The source distribution has8,997 visible members. All7,811 tracked regular files, totaling223,620,032 bytes, compare chunk-for-chunk to actual local Git blob output; the exact required source set matches the CI package manifest. Seven explicit generated metadata files total643,382 bytes. No duplicate names, traversal, unsupported links/sparse members or unbounded extra metadata were accepted. Both nested archive hashes match the package and installed reports; gzip and outer ZIP CRC checks completed.

The selected package-report ZIP has19 verified CRC members. Its recorded installed result has8 tests,8 commands with exit0,25 loaded UTA modules, isolated execution and module paths inside the recorded installed site. The unchanged copied CLI helper hash matches both reports and d1fd. The eight command roles are durable help, ops help, demo, acceptance, scenario, durable initialization, inspection and status; the installed CLI unittest text independently reports eight tests and OK. Seven package checks report success, with the actual archive identity independently verified here.

These are bounded recorded installed observations, not a new local installation or comprehensive functional certification. `funding_local`, `funding_obligations`, `perpetual_funding` and `cross_decimal_kernel` are present with exact runtime bytes but absent from the25 recorded installed imports. Their direct installed functional coverage remains **NOT_VERIFIED**. The independent oracle is present with exact source bytes in the sdist, but its installed execution is likewise **NOT_VERIFIED**. Byte equality grants no capability or product permission.

## Independent layered archive-read budget

Before this review's first archive expansion, the integration lead explicitly authorized separate finite layer budgets. The private storage constraint remained unchanged:50 sealed originals totaling75,823,470 bytes, files0400 and directory0500. Reads used O_NOATIME; all original hashes, index/seal and modes were checked before and after streaming. No nested sdist, whole tar or extracted binary payload was materialized on disk.

| Layer | Actual output | Prior cap |
| --- | ---: | ---: |
| Outer ZIP member output, including repeats | 58,808,925 bytes | 67,108,864 bytes |
| Wheel member content | 1,496,856 bytes | 4,194,304 bytes |
| Gzip raw tar stream, including header/PAX/padding | 239,912,960 bytes | 268,435,456 bytes |
| Visible sdist member payload | 224,263,414 bytes | 227,814,336 bytes |
| Visible sdist members | 8,997 | 16,000 |

There are27 unique outer ZIP members with verified CRCs. Across35 reads, eight repeated small metadata reads contribute2,171,836 bytes and are included in the outer total. The sdist had exactly one streaming verification pass. Tracked member reads were bounded by their expected Git size, checked for exact size and compared in64KiB chunks. Each layer had its own counter and stopping condition; container I/O is not represented as retained storage or peak memory.

The raw tar accounting closes exactly:224,263,414 bytes of member payload +13,819,392 header/PAX bytes +1,821,962 alignment-padding bytes +8,192 verified trailing-zero bytes =239,912,960. The nested archives are DEFLATED in the outer ZIP; they were not assumed to be STORED. Source metadata, canonical paths, member sets and per-member bounds were checked while streaming.

The original collector's224,263,414 expanded-byte figure counted tar member payload only. Its original all-layer cumulative expansion guarantee therefore remains **NOT_PROVEN**. This later, explicitly authorized independent per-layer read passes its own caps; it does not retrospectively qualify, rewrite or approve the collector's earlier budget interpretation. The SAFE collector correctly retains that distinction.

## Evidence boundary and remaining gates

The collector's nine SAFE files total101,428 bytes. Their frozen inventory/hashes, source binding and public-only projection were checked; private source-location mappings, worker identifiers, nonces and download URLs are not published. The index is8,473 bytes/SHA-256 `47bb3b19b895e58765e88c1ee86d3b308cc011968b999c7e8b094a7335387f0c`; the369-byte seal is `32ccb8fea9c1835bc21b6457ab046145dc1f4d8f0d7ad492b967c2e8ccaf8d80`.

The integrated source now has its own successful first-CI evidence. It does not inherit production acceptance from that success. Original failed native scopes and unresolved timing causes remain unchanged. Code review, exact byte identity, installed paths, financial concurrency/fault recovery, real matching-to-ledger reconciliation, migration/old-writer fencing, funding encumbrance, loaded-engine binding, model validation, sustained open-loop capacity, liquidity limits and HA are distinct gates. No performance, HA, production or real-funds approval is issued.

The two review files contain administrative evidence only. Reverting them changes no runtime, schema or financial state; deployment/financial rollback remains governed by the separately reviewed authority handover and reconciliation procedures.
