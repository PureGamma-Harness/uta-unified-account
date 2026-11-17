# Offline deployment template release fix

PR27 source `37ac3198e9412c7edf89a7842d876fe8113ff68b` omitted the tracked `deploy/review-manifest.template.json` from its source distribution. Seven original CI jobs failed the existing exact-source check; those results remain failures. The separate unit-test failure is not addressed by this packaging change.

Code commit `e486d13d68cde98e1a1246b1274bf92bb3b1a29c` adds one explicit `MANIFEST.in` include. It does not broaden the deployment-directory glob, alter runtime code, change the JSON schema, create a financial capability or activate a service.

One local build and the unchanged exact archive verifier completed on CPU0 in 137.310 seconds under a 180-second whole budget: build36.545s, verification100.672s, both exit0. All6,298 tracked source paths match the sdist byte for byte; all62 runtime files match in wheel and sdist. Version, three entry points and the licensed pinned legacy fixture also pass. The sdist has6,305 regular members including packaging metadata; missing and mismatched source lists are empty. Archive SHA256 and full results are in `evidence/reviews/deployment-sdist-e486-first/`. First build stdout/stderr and binary archives remain in the external original directory with their digests recorded.

This is local package validation of code commit e486d13, not a new remote CI result, installed-package test or production acceptance. The later evidence-only commit is not the source bound by these built artifacts. No original workflow was rerun, no production database was opened and no service was restarted.

To reproduce, check out e486d13 cleanly and build a wheel and sdist with `setuptools.build_meta`, then run `tools/verify_release_archives.py` with that exact commit and the resulting artifacts. The retained one-shot driver uses a fixed already-consumed output path; choose a new external path for a separately labelled reproduction rather than overwrite the original.

Deployment remains offline review only. Use the included template to prepare a manifest for independent approval; authenticity and live storage checks remain open. Rollback reverts the explicit include and retains prior artifacts and evidence. Such a rollback again yields an incomplete source distribution and must not be published as an accepted release. Real-funds, model, multi-node durability and capacity gates remain **NO_GO**.
