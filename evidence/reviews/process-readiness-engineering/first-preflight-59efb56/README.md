# First metadata preflight: failed, partial preparation retained

The exact authorized preflight command ran once and exited1. Original stdout
is empty; original stderr is929 bytes and contains AttributeError at
native_once_common.py:267 because `_sqlite3` has no `__file__` attribute.
No retry, extra interpreter probe or run subcommand followed.

The failure happened after the private0700 runroot and complete read-only
source snapshot were prepared, before preflight.json or final metadata stdout
were written. There is no preflight SHA, persisted actual affinity/birth,
binary/SQLite payload or resource payload. None is reconstructed from an
additional process. The kernel/tool wait recorded0.128415273s; this is not an
internal full-runtime timing measurement.

The retained runroot is `/workspace/readiness-native-once-59efb56-first`.
Its70 regular files are the69 approved sources plus manifest, all mode0400;
source directories are0500. Their1538204 bytes match approved originals.
The business/raw/safe/empty-pycache directories contain no files. All original
69 sources and manifest, old21 SAFE files, first pure20 six files and isolated
pure1 six files retain their before/after hashes. Full inventory and bindings
are in partial-snapshot-and-source-bindings.json.

This metadata failure does not identify an original CI failure cause. Original
pure20 RED and isolated pure1 PASS remain distinct. Actual native case remains0
and no valid approved preflight hash exists. Keep the partial runroot unchanged.
