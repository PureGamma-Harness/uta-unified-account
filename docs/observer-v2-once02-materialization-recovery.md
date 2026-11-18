# Approved materialization recovery, adapter still not started

Root ruled that the original once02 metadata preflight failure must remain
separate from a native adapter failure: actual probe invocation count was0,
and the fresh output path had not been created. That original traceback and
launcher remain in seal `22e3f9a54607f70ef61edf4ba4c1e2b45ac4f2bd`.

Following root's explicit recovery scope, the clean approved eight inputs
were verified against source `c076b0dc1feb765686de9c78683a4e4bea5429e2`.
No WIP was overwritten. Their exact sparse patterns and original launcher
were added, and only those eight inputs were explicitly restored from the
approved Git source. Already materialized57 document/evidence files were
also retained in the sparse selection so the operation could not hide them;
every one remained byte-identical. No source content or runtime version
changed, and no old run output was opened or changed.

The O_EXCL before/after records under
`evidence/observer-compact-report-v2/once02-materialization-recovery` contain
each input's Git length/hash, physical presence, index H/S flag and restored
file stat/length/hash, plus original launcher hash and protected-file hashes.
Before recovery two inputs were skipped; afterward all eight are regular,
materialized H entries and byte-equal to approved source. The once02 output
still does not exist, and actual probe execution count remains0.

This repairs source availability only. It is not an adapter, null-device,
pipe, finance or stability test. Root separately allowed a second metadata
preflight and completion of the **original one** actual adapter authorization
at exactly `read1-c076b0d-once02`, retaining all original limits and stopping
after any actual first failure. No second actual-probe budget is created.
