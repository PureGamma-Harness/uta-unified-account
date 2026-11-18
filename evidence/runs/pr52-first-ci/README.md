# PR52 first CI: preserved failure

Both first runs at source137562a0f3fcb5e8d8c608746b41ab19349ec6b8 failed, with all eight jobs failing their unit step. Each exact unit original ran2066 tests, with1 failure and16 errors, no skips. All16 ERROR IDs are identical across the eight samples and terminate with the observed CreditAuditError/credit_audit_policy_mismatch. The subprocess test expected73 but observed1 with the same inner exception. This collection does not determine the precise policy-compatibility root cause or assume timing/SH attribution.

The fixed push3.13 and PR3.13 samples were retained. Six additional failed-unit samples were preannounced and approved; each of eight artifact references and payloads was fetched once. Eight ZIPs total782685 bytes/24 members, all CRC and provider digest checks pass. There is no first-run small package report because downstream build/installed steps were skipped; no alternate sample was selected.

Each before/after375-source map was checked against Git source, the actual PR merge parents/tree were checked, and traceback source lines were matched to their exact Git blob. All11 new admission test IDs have plain ok observations in each log; these successes do not override the complete suite failure or replace the historical isolated SQL4 evidence.

58 original files4774514 bytes remain private0700/0600 with a byte seal. Public exports contain finite reviewed fields and opaque hashes. Original logs, worker payloads, references, private bindings, ZIPs and source maps remain private. No source or financial code, target execution, SQL, process lookup or CI rerun occurred. Independent RAW review is pending; production, real-funds, capacity and installed-package acceptance remain NO_GO.

Deployment/rollback: this evidence-only commit changes no runtime, schemas or configuration. Preserve this first failure and all confirmed history while reviewing a separately versioned fix. Roll back evidence presentation only; never erase original results or retry them to green.
