# Independent CODE review: recovery-readiness failure message

PASS_STATIC_NO_BLOCKER for 6ab8b8f10e2ebcc63ef190a1652576eec8942db2,
parent 16f64fec1d2fba638ea99a6414cf8778f9638537. This two-file patch adds a
finite message to the existing assertion. It is not a readiness correction or
an explanation of the historical failure, and does not authorize CI or execution.

Only the two exact candidate paths and parent test source were read as source,
using an isolated exact-path sparse checkout. Primary AST/data input is 39,133
bytes, below the 1MiB review bound. Both candidate physical files match Git.
No other repository blob content, actual diagnostic report, quote, SQL, actor,
target import, test, PID/proc query, signal, network or CI was accessed or run.

The assigned diagnostics expression is AST-identical to the old assertion's
single call. The method still contains two total diagnostics calls: its earlier
rejection observation and this existing recovery observation. The assertion
still uses exactly financial_ready from the recovery result; the message uses
that same local object. Restoring only this two-statement tail to the former
assertion makes the entire test module AST identical to its parent. All other
methods, imports, formatter, quotes, waiting, predicate, cleanup and timing
remain unchanged. No other file is in the diff, so the parent's 67 runtime
members and 29 funding-pure tests are unchanged without rereading their blobs.

The unchanged formatter has 22 exact native-string reason codes and maps any
other text/value to the literal other. It copies only five top-level bool/None
flags, two control bool/None flags, finite control/reason codes, six worker-gate
count groups and two row-count/truncation fields. It inspects at most two native
worker dictionaries. Constructed JSON contains only its fixed keys, accepted
codes, booleans, None and bounded counts. It copies no PID/birth/account/path,
timestamp, nonce, raw exception text or arbitrary input field. Projection errors
return a fixed constant JSON string without serializing the exception.

The formatter is evaluated as an ordinary assertion message even on success;
it neither calls diagnostics nor mutates the report or assertion value. The
original financial_ready expression is evaluated first. An existing false
value remains a failure, with a finite message; no retry, wait or alternate
observation is introduced. These are source/data findings, not formatter or
actual guard-test execution results.

The delivery document retains first push FAIL and first PR SUCCESS, leaves the
missing final observation UNDETERMINED, and separates any future result from
the earlier source/run. Its historical log statements were supplied by root's
collector and were not recollected here. A passing new CI would not establish
why the earlier observation failed.

No static CODE blocker prevents root from deciding a separate first normal CI.
Readiness correctness, independent funding comparison, HA/capacity and real
funds remain separate gates. Rollback reverts only the two test lines and new
document; no data, authority, runtime, fixture, lease, TTL or timeout changes.
