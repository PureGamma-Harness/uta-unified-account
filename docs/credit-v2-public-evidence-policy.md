# Scoped synthetic credit publication material policy

`scripts/credit_publication_scan.py` reads tracked changed files and every newly
reachable history blob against the merge base of PR16. It inspects the two exact
historical source archives in memory, allowing only LICENSE, Python source and
the original public `uta/dashboard.html`; it never extracts them to the workspace.
The manifest records exact paths, byte counts, SHA256 and archive member hashes.

Allowed top-level file types are Python, Markdown, JSON, text and CSV, plus the
two exact source archives. Database/key/TLS files are not allowed. The scan
checks SQLite bytes, private-key/certificate material, credential patterns,
signed/token URLs and non-null sensitive fields in raw text and nested retained
JSON. Locations and value hashes are reported without printing matched values.

The initial report retained four findings for the public historical dashboard
member, which was not in the first archive allowlist. A second stricter raw
field pass found only the fixed sentinel used by the earlier live-registry
nonce-exclusion negative tests. Its hash is explicitly allowed in exactly
`tests/test_credit_artifact.py` and
`evidence/reviews/credit-artifact-fc63938/probe.py`, field nonce, raw Python
category only. Those tests patch a synthetic registry and assert the marker is
absent from artifacts. No actual lease/auth nonce, production path, JSON or raw
output exception is permitted. Initial findings remain in attempts01/02.

The final report at source7cd9edf has zero unresolved findings across365 current
changed files and429 historical blobs. The source-only/archive inventories and
the exact test-sentinel matches remain visible in the report. Four focused
scanner checks verify nested/raw value detection without leaking values,
database/private-material detection, null/hash handling and that the sentinel
exception cannot cover runtime evidence. This publication check does not prove
financial correctness, arbitrary secret absence or a complete security audit.

All retained original databases are owned private temporary files outside Git.
They remain for root review and are never attached to the PR. The final report
and this policy are attestation-only additions after the scanned source commit;
the exact latest draft is scanned again before its push. No original financial
evidence or failed-run bytes are modified to make a material scan pass.

After whole stable91 and independently accepted root5a catalogue integration,
the M3-only scan is explicitly based on exact
5a2961134aedaef9914d4cdd0247bb8795fb9b90. Its report for source1f10a68 checks
379 changed current files and448 newly reachable history blobs, with zero
unresolved findings. This separates already accepted baseline material from
the draft's changes while retaining every original credit result/source
identity. The report is under `stable91-and-catalog/`; no prior report is
rewritten. The narrow verifier-view compatibility edit and its real first red
remain part of the scanned history.
