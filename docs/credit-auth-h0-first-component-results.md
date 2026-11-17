# H0 first actual private-AuthDB component observations

Observed runtime source: `072cc77c5a96b48c81a143020ab8ac6c9a794a9b`, based on exact `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0` in a separate branch. All original431/39/independent design files and their30+12 NOT_RUN histories remain unchanged. These are new author-run component observations, not independent dynamic acceptance, a release or production qualification.

The implementation adds fresh authentication format2 only. It does not install financial HMAC3, source/PENDING/intent, borrowing/repayment execution, an endpoint/TLS listener or READY. The only pre-existing runtime file changed is request_signing.py: real MAC/header and nonce/time/replay/count/insert logic is shared, while the legacy public authenticate signature and Credential return remain. New modules are credit_auth_h0.py and its compiled schema inventory; native-credit, financial-risk, gateway and matching code are unchanged.

## Actual bounded executions

Every batch used CPU4, a separate private result directory, random private keys, no network and a30-second outer watchdog. All completed naturally with no watchdog activation and unchanged source hashes. The clocks below cover child launch to actual child exit, including its result writes; source hashing and final outer metadata serialization are outside that interval. These small cohosted observations are not throughput or latency qualification.

| Source / case | Actual UTC start–finish, 2026-11-17 | Runtime / SQLite | Observed result | Outer seconds |
| --- | --- | --- | --- | --- |
| Original909 real format1 baseline |17:51:54.028664–17:51:54.193591|3.12.14 /3.53.1|actual random-key MAC, Credential return and durable replay refusal|0.164906328|
|072cc77 first H0 batch|17:52:11.862406–17:52:13.042280|3.12.14 /3.53.1|12 methods,0 failures/errors/skips|1.179808433|
|072cc77 first3.10 batch|17:55:10.472587–17:55:11.743396|3.10.22 /3.53.1|12 methods,0 failures/errors/skips|1.270784386|
|072cc77 first3.13 batch|17:55:20.365622–17:55:21.435558|3.13.5 /3.46.1|12 methods,0 failures/errors/skips|1.069842197|

No batch was repeated to obtain a green result. The post-COMMIT reply-loss and pre-COMMIT rollback tests intentionally observe503 UNKNOWN through wrappers around actual transactions; this is part of their passed assertion, not a claim that an unknown business result disappeared. Their original authorities and outputs are retained privately.

## What the12 methods actually exercise

- Fresh exact MAIN schema installation/reopen:34 explicit objects and14 automatic indexes, complete table/index/FK definitions checked on actual connections. The unchanged original909 reader is invoked in a separate real subprocess and rejects the new format. A normal legacy object also encounters fresh format2 at its original self-owned test path; configure/authenticate refuse before mutation. That adversarial fixture retains the original v1 file and is not an upgrade feature.
- An actual malformed nonce-table FK preserves names/columns and original guards but is rejected. Format1 actual authentication still returns Credential and refuses durable replay.
- Real valid-MAC input/role denials commit nonce plus denial audit; a repeat nonce replays, while a wrong MAC produces no mutation. Same CID canonical-equivalent amount returns passive original evidence; changed amount or kind conflicts without replacing it.
- An actual AuthDB COMMIT completes before the test loses its response. No handle is returned; a new issuer and independently current credit.read request recover the original first acceptance. A separate real pre-COMMIT failure rolls back and returns no handle.
- Original-grant revocation followed by another key/grant cannot rebind the old CID. Concurrent actual first-CID requests create one acceptance and an original query; an actual revoke/accept race is adjudicated by AuthDB transaction ordering.
- Strict nonce expiry equality is protected by the actual delete trigger; a later actual-clock request prunes only the expired nonce, while first acceptance remains exact.
- Ordinary handle capacity full still admits a truly authorized query, and an unauthorized query occupies no reserved slot. Nonce/query and acceptance capacities are exercised separately. Audit capacity causes rollback/UNKNOWN instead of a fake committed denial or silent eviction.
- Missing authority never recreates itself. Wrong-object/copy/other-issuer/thread/fork handles fail; fork PID is checked while the parent's registry lock is deliberately held. All retained/exported observations deny financial, source-delivery and execution authorization.

## Limits and remaining gates

This is12 methods per runtime, not a claim that every subcase of the original30+12 design matrix has been executed. In particular, FK corruption was faulted; PK/CHECK/no-replace alternatives were not individually faulted. A grant race ran, while profile-replace/accept competition was not individually injected. Foreign-object/copy/issuer/thread/fork checks ran; arbitrary same-process reflection is outside the trusted-binary boundary. Missing/moved private state ran; symlink, storage-loss, backup rollback and HA are not qualified.

No full repository suite, all-supported CI, package/install acceptance, HTTP/TLS or financial tests ran on H0. The supported-runtime component runs do not include Python3.11 or CI's actual3.13.18. A separate group must review the exact source, actual private evidence and new negative cases before any scope verdict. General legacy behavior beyond these observations requires its own regression verification. H1–H4 and cross-database revoke/execute remain absent.

## Evidence, deployment and rollback

[Evidence index](evidence/credit-auth-h0-first/README.md) contains explicit allowlisted test IDs/statuses, source/stream hashes, runtime, actual clocks/affinity and command templates. Exact original command/cwd, raw stdout/stderr, private runners, random keyfiles and all self-created AuthDBs remain under an operator-private root outside Git. Public metadata redacts only predetermined private command positions; it never regex-redacts secrets from captured raw output. Private raw was not copied to Git. Driver code is retained byte-for-byte and linked by each execution's SHA.

There is no production deployment command or public enable switch in this delivery. Disabled ingress fails before opening files. Initialization accepts only a genuinely new private authority and cannot repair or promote format1. If this branch is omitted, final909 is unaffected. Once an experimental format2 authority contains first acceptances, preserve its original rows and tombstones; disable the ingress and apply a reviewed forward fix rather than deleting records, downgrading its format or resetting it to regain capacity. No real-funds approval follows.
