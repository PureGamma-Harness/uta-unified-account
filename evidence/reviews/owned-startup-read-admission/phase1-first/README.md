# First phase1 pure run: RED, retained without retry

Exact source: `88da96f2ca32a237a47964062b43c26d51a2dec0`; plan SHA256:
`dc3fa71c0cad6f75dc327e29b26f87d57f573a3204e10de376a89a31f9d0f89a`.
Runtime observation files remain the independently reviewed6303ed4 bytes.
Root authorized this one pure run after independent preparation CODE review.
Preparations72dcebf/166ddf9 were never executed and remain zero-attempt records.

The first run returned actual host exit1 and was reaped. Twelve methods ran:
eleven passed, one failed, zero errors. Forty-five of the planned maximum48
small traces were entered;44 completed without failure. Method08 failed in its
first `known` selector, so its remaining three selectors were **not entered**.
Neither48 completed traces nor a green phase1 result is claimed. No retry,
warmup, original suite, SQLite or native worker execution followed the failure.

The failing assertion is frozen fixture line512:
`self.assertEqual(scope.database.commits, 1)`, with `AssertionError: 0 != 1`.
The actual selected `_OwnedStartup._renew` uses `copy(self.database)` for the
control-role renewal. The fake Database stores `commits` as an integer attribute;
incrementing that attribute on a shallow copy does not update the original
object queried by the assertion. This supports a fixture-counter placement
classification by source inspection. It does not establish a runtime telemetry
defect, a failed real COMMIT, or either original PR38 error's cause. The fixture
and runtime are unchanged after this run; independent raw/classification review
is pending at this seal. The known-selector later receipt assertion and the
three unentered wrapper/token/import selectors remain uncovered by this run.

Raw stdout3695B and stderr2640B total6335B, below the shared262144-byte cap with
512-byte trailer reserve. Complete BEGIN, result, END, inner receipt and outer
host intent/exit receipt are retained byte-for-byte. Launcher stdout/stderr are
both empty. Actual affinity was `[1]`; interpreter version, executable SHA and
`-I -S -B` flags matched. All eight inputs matched before and after. Driver target
elapsed was2194145161ns; outer elapsed2351296858ns; unittest reported2.123s.
These timings are run evidence, not a capacity/performance result.

`raw-manifest.json` pins the eight original files and exact copies. Private
source namespaces are0700 and raw files0600. The host receipt contains the
expanded literal argv with `shell:false`, actual exit and completion/reap;
the inner driver does not self-attest the outer command. All data is synthetic.
No capture limit or wall-budget failure occurred; the observed nonzero status
is a retained assertion failure. No output trimming or normalization was used.

Phase2 remains NO_GO. The three earlier conditional baseline RED, original CI
causality UNDETERMINED, and incomplete actor-exclusion/composite-watermark proof
retain their distinct scope. Native, financial, recovery, performance and
production approvals remain false. Any future focused execution requires its
own newly reviewed source and explicit once budget; this first result is not
replaced. Evidence-only rollback removes this added report/copies while keeping
the original private first files and all prior source/evidence immutable.
