# Controlled decimal Cross calculator candidate

This adds a separate coefficient/exponent calculator for the existing CrossRisk
contract. It does not replace the reference calculator, change the service
default or enable a trading path. All61 existing UTA modules are unchanged.
The new pure hot path uses integer arithmetic and powers of ten rather than
Fraction or reference-calculator arithmetic. Borrow quantities retain floor
steps and strict maintenance limits; risk values gain no new USD rounding.
Service ratio formatting remains in the original service layer.

Independent mathematical CODEe25ae450 checked valuation, gross collateral and
debt components, frozen funds, signed cost dust, IM/MM/status, canonical Decimal
tuples and borrow boundaries. The existing80-digit/exponent/adjusted bounds are
retained; the documented derived alignment bound fits the local power limit.
The versioned tag-test inventory is explicitly62 paths, without relaxing the
artifact validator or rewriting historical61-source plans.

The unique first run atcf8dfca6 passed9 ordered methods and96 successful grid
subtests, with zero failures/errors/skips. Its complete retained8-module load,
68 source/control inputs, actual prefix exit0/reap and both EOFs were checked
by independent RAW780f41f1. The12 manual cases are source classifications, not
12 separately counted executions. No per-vector output archive exists; the
runtime conclusion is that the pinned field/tuple/borrow comparisons and
literal assertions executed successfully, alongside the separate CODE math
review. It is not an independent reconstruction of every runtime vector.

Actual prefix completion was516410354ns; inner loading/comparison was180762356ns.
The later775627832ns field includes post-run source/Git checks, despite its
historical through_raw_fsync name. Tool-reported wall time remains a separate
record. These intervals are not a kernel performance comparison. Earlier
legacy ReserveKernel gains do not apply to this configured Cross candidate.

All11 originals107103 bytes, capture source and full output remain private.
Public evidence contains the cleared stderr and finite projections/hashes.
First normal CI completed; its exact scope is recorded below. Broader differential coverage,
Cross-specific performance, future loaded-engine binding, activation and human
financial approval remain OPEN.

Deployment is limited to a new explicit synthetic calculation scope. No schema
migration, authority handoff, automatic fallback or default activation is added.
The supported-domain/unsupported-input contract must be respected before any
future business effect. Reverting the candidate leaves the original reference
service behavior intact; preserve all first results and confirmed history.
Do not run historical plans against new bytes or reuse sealed output paths.
Trading production, HA, custody, mixed load and10000/s remain NO_GO.


First normal CI is now archived and independently reviewed (0921a23d). Push44296777854 and PR44296832834 both succeeded across all eight jobs. Fixed push/PR Python3.13 logs each ran2135 tests with0 failures/errors/skips; all9 Cross candidate and6 lease-tag methods had actual plain ok records. This does not separately instrument the96 grid callbacks. Each source map's382 pins, actual merge tree and small-package7386 required paths were checked against source667171d1.

Package runtime inventory includes63 files (62 Python modules plus HTML), including the new kernel. Its25-module installed report,8 existing CLI tests and8 commands do not directly import or exercise the new kernel after installation; that acceptance remains OPEN. Private43 originals2160149 bytes and three ZIPs were sealed;18 public files provide cleared finite evidence and independent review. Candidate activation, new loaded-engine binding, Cross performance, sustained capacity and production approval remain OPEN.
