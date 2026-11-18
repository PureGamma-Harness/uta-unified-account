# Independent RAW review of the first f434 pure execution

Decision: **PASS_CONDITIONAL_PURE_ONLY**, independently supported by the sealed
first-run evidence. This is an eight-method pure fixture/envelope result.
It proves no actual native SH capture, loaded production worker equivalence,
five-second recovery, PR37 cap effectiveness or production readiness.

Reviewed source `f434389bc68e17877ec96e5f429e33a543571446`, tree
`a337d4fd5a01d98a0beec8716c2a38b565fb3f3a`, and evidence seal
`bdf291fa27eb9d065d5f773246aa8f7805e9c89d`, tree
`af334be6457f9cb5c44ac4260ed096b09e0c7276`, on 2026-11-18 UTC. Review started
only after the owner supplied that terminal seal. The original two output
directories and owner worktree were read only. The reviewer did not compile,
import or execute any target, rerun a test, install a trace, inspect a process,
open SQLite, use a pidfd/signal/flock or perform a network probe. An independent
metadata reader parsed JSON/base64 and compared hashes and Git blobs; it never
compiled or executed capsule contents.

All 13 host/launcher artifacts were independently compared byte for byte across
their authorized private originals, safe copies and exact sealed Git blobs.
Every length and SHA matched `copy-manifest.json`, whose SHA is
`ecb6f6b1515110adb4e3e223c37eebd965d5b955e19716a0d69297ed18e598c5`.
No first raw file was normalized or rewritten. The seal adds only result
documentation and these copies: the fixture, eight-method selection, original
financial test/AST guard, runtime, old closure, pure plan and driver have no diff
from reviewed source f434.

The immutable capsule contains exactly nine inputs. Each decoded buffer matches
the approved plan's length/SHA, its own capsule pin and the exact f434 Git blob.
The recorded driver SHA is
`e28b7f3272b544f9f65fdb477d6968028f14c506c119536f4113fb61b8ebe101`;
the plan SHA is
`09231bbf87202eac7a18fe8ed088e4f47f62c62171e8ac15afd86e93a2c1c6ab`.
All nine recorded before/after physical metadata maps are exactly equal and
`source_drift` is null. The plan's post-comparison is checked by the pinned
driver and represented by that null drift result; a separate full plan-after
metadata map was not retained. This limits independent inspection of those
individual plan-after fields, while the exact plan bytes are available in Git
and the driver's normal-path drift check is source reviewed.

Original stdout lists each of the eight approved method names exactly once as
`ok`, followed by `Ran 8 tests` and `OK`. The original control END equals the
END embedded in execution.json and records eight tests, zero failures, errors
and skips, an empty forbidden runtime import list, Python 3.12.14 at the declared
absolute executable, isolated/no-site/no-bytecode flags, and actual affinity
`[1]`. The actual SH gate and worker are fake/inert objects in this scope;
the original AST-preservation guard is among the eight executed methods.

| Retained fact | Independent check |
| --- | --- |
| Host attempt | One source/attempt ID across BEGIN, intent, capsule, control END, host trailer and envelope END |
| Native authorization | False throughout the selected scope |
| Host termination | Original actual-host-exit.txt is `0\n`; execution/END record actual reap and both raw pipes at EOF |
| Launcher termination | Actual exit 0 after its owned Popen.wait returned; both launcher streams are empty |
| Selected-method interval | 156769496 ns, consistent with unittest's rounded 0.156 s |
| Whole outer interval | 121644485313750 - 121643836473793 = 648839957 ns from launcher monotonic records |
| Configured host limit | Intent pins `/usr/bin/timeout --signal=KILL 10s`, taskset CPU 1, absolute Python and `-I -S -B` |
| Shared raw accounting | 1910 reserved/written payload bytes plus a 175-byte trailer = 2085 bytes; sticky125 false |
| Capture ceilings | 261632 payload bytes and a separate 512-byte trailer reserve, total ceiling 262144 |

The host and outer intervals have different boundaries and are not financial
throughput measurements. The normal run completed within the configured
ten-second window. It did not trigger timeout, overflow or short-write handling;
those branches retain the static qualification from independent CODE review
`c435067f80bb790fb7879cc7888e413a8c1bd27e`. The evidence contains no measured
native trace count or capacity claim.

Key original hashes are stdout
`e039114326b9caef58934238ee0e8b836e1fbf4ce703af3ff4e291b0f7c3f7d1`,
stderr `69223a50693ff83176d5b5e58673abf25acc0e7c48e7b75e2f15f7de301a9022`,
execution `6d5cf5dd8cac567c854bd7735a7590f67e40b043039729bf73079ddcab16f7c7`
and launcher exit
`042f9a5b9a0059eadd8f5e100ceb2e7091d4202ac88719d725a6186f68f4e65d`.
The companion review JSON records every artifact identity and verified field.

Historical review 00f2c60 and commit47b's unchanged zero-attempt NOT_RUN closure
are preserved; neither is relabeled RED. The separately authorized f434 first
attempt ran selected 47b fixture/test AST under the reviewed envelope. Original
L1456 undo, L1461 capture exhaustion and actual L1525 recovery failures remain
open and separate. This review grants no retry, native run, deployment or real
funds approval. Any native evaluation needs a new explicit root GO, separately
frozen source/runtime and fresh synthetic authority. Rollback leaves the
envelope unused or reverts its test-only additions while preserving all first
evidence; there is no runtime/schema migration in this delivery.
