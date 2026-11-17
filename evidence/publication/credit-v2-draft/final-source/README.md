# Final source publication attestation

The attached original report checks exact pre-attestation source
89eb068e5bf1b93212a066ea0c36811e02d23fa1 against whole-merged root
7dc8ded3a5f9152251f1ca7a9ee2ba9b6ded986b. It reports 582 current changed
files, 540 newly reachable historical blobs and zero findings. The command was:

```sh
taskset -c 3 python3 scripts/credit_publication_scan.py --base-ref 7dc8ded3a5f9152251f1ca7a9ee2ba9b6ded986b --report /tmp/credit-final-publication.json
```

This final attestation adds only this explanation and the original report; no
runtime, financial rule, test or prior raw result changes. The candidate is the
commit containing this attestation; its exact SHA is recorded in the PR and
integration handoff rather than self-referenced here. Runtime and tests remain
byte-identical to whole merge6c834ff. The preparation manifest retains the
62-runtime-file tree SHA256 ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b.

This is the documented scoped material check, not an independent security audit
or production acceptance. The original synthetic negative-test marker exception
is restricted to its two exact Python paths, fixed hash and assert-not-archived
purpose; it grants no raw/JSON/production credential exception. Private database,
auth/key/TLS, runtime writer nonce and signed URL material remain excluded.

No post-root-merge business change or microtest was run. Full local three-runtime
validation, actual final-source CI8, one independently built fresh package and
same-artifact synthetic smoke/separate six-hour observation remain pending.
Intermediate460 evidence is not inherited. V2 stays default-off, public/CLI new
managed borrowing501 and trading readinessfalse; overall release is NO-GO.
