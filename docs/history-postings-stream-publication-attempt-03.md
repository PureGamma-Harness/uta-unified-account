# Attempt 03 publication addendum

The exact preparation, observed evidence and independent review have been copied to this publication branch without changing their bytes. The commit mapping is recorded in `history-postings-stream-publication-attempt-03.json`. All runtime and test files remain identical to the previous publication head `78e8091`.

Independent review `ed14e5e` accepts 234 pure file/AST/rational checks of the bounded observation. It does not execute the benchmark or grant runtime enablement. N4096 wall block-ratio median is 0.995974254, close to parity, and its third block is 2.178530% slower. Both this mixed result and all earlier failed or slower observations remain visible. `ordered_postings=False` stays the default; Draft PR20 remains separate R&D.

A wording correction to the immutable author report: its phrase “outside 15s budget” is inaccurate. The retained outer measured elapsed is 2.423153440 seconds, which is within the 15-second observed budget. Final outer metadata serialization follows that recorded endpoint. Neither observation proves a hard OS quota. The original report and raw files are preserved unchanged.

No further performance run was performed for publication. No data migration is required. Rollback is leaving the option false or omitting this branch; no production, 10k/s, recovery RTO or main-merge approval follows.
