# Pure funding holds: reviewed first evidence, push failure retained

The exact tested source is16f64fec1d2fba638ea99a6414cf8778f9638537.
First push44353030187 failed its Python3.12 unit job; first PR44353143243
succeeded. Across both attempts1, seven jobs succeeded and one failed, with
183 successful steps, one failed step and16 skipped steps. All eight summaries
report2200 tests; only push3.12 reports one failure and worker exit1.

Collector6cd4c01d and independent RAW423c6af5 retained both outcomes. Three
complete logs, push3.13, PR3.13 and failing push3.12, each show all29 new funding
methods strict plain ok:87 method observations, not an all-version per-method
transcript. Their six410-entry before/after maps match exact source Git.
The sole reported failure is ProcessReadinessTests at test_process_readiness.py
line200, checking financial_ready after recovery. The original observation
contains no diagnostic message, and its cause remains UNDETERMINED. The passing
PR run does not replace this failed source gate. Diagnostic successor PR64
preserves its own separate source and cannot retrospectively explain the failure.

This delivery adds evidence and documentation only after16f64fec: runtime,
tests, tools, benchmarks, formal models and workflow remain unchanged. Runtime
67 files/1479474B and literal V4=66 Python files remain the reviewed pure model.
It computes supplied USD data only, with activation_permission=false; no
admission, payment, APPLIED, durable action ownership or service hook is enabled.

All64 original files,75584560B, were independently hashed with0400 permissions
and10 directories0500. Four small ZIPs/28 members have CRC verification.
The binary54814960B was checked only at outer hash and central metadata;
wheel/raw-tar inner payload, CRC and content qualification remain NOT_VERIFIED.
Small package reports match67 runtime hashes and7844 required source paths.
Installed8 tests/8 commands are limited evidence;25 module paths are not content
hashes, and new pure/funding components are absent from that direct-test list.

Deploy only the documented fresh synthetic engineering boundary. There is no
financial migration or activation. Rollback returns to the matching complete
pre-pure deployment and source inventory; reverting a single correction does
not produce an accepted deployment. Preserve and reconcile all confirmed
obligations, trades, positions and journals. Independent V3 reference/full-field
execution, readiness cause, D2, capacity, HA and real-funds gates remain OPEN.
