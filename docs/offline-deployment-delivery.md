# Offline deployment review delivery

This branch is stacked above recovery delivery6010e92. Relative to that base it
adds an offline declaration checker, tests, a deliberately refused template and
review documentation. It does not change trading runtime files, the package
configuration or the two systemd service units. The deployment README adds the
checker to the review workflow.

Fixed toolfb54a5a recorded21 focused passes on Python3.12.14. Independent review
first retained a Python3.13.5 case where an oversized JSON integer escaped as a
plain ValueError. The fix returns the stable refusal response and preserves
duplicate/nonfinite JSON error codes. Manifest and declared-path NUL/UTF8 cases
also have explicit refusal coverage. The original error arguments were retained;
its full traceback was not captured and is not reconstructed. Independent
review9226dd5 bound the fixed source and its original test records without
rerunning that suite. Integrated CI must validate the combined delivery tree.

The tool checks a synthetic-review declaration and filesystem metadata. It does
not read declared secret, profile, database or wheel contents, verify actual
artifact/rule digests, inspect live storage or authenticate an approval. Success
therefore supplies no trading or production activation authority. Single-host
WAL/FULL and replication=none are declared constraints, not measured durability
or HA results; unsupported products/modes and claimed real-funds enablement are
refused.

Deployment consists only of installing the review tool and using a fresh
declaration under the documented synthetic scope. Rollback removes it from that
review workflow, preserving original declarations and evidence. It does not
modify financial storage, credentials or service processes. Complete operation
and refusal rules are in `docs/offline-deployment-manifest.md`.
