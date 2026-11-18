# Independent finite Cross oracle and public golden data

This adds an independently derived, test-only two-asset valuation oracle for
the existing decimal candidate. It calls no production reference calculator,
collateral-discount, borrow-limit, floor or ceil helper. Positive borrow quotes
are found by enumerating all permitted finite unit quantities:20 USD candidates
and10 BTC candidates. The pure candidate is checked against those exact
Fraction values, rather than another implementation of its quotient formula.

Five methods contain538 successful checks:512 deterministic seed cases,
6 tier/freeze cases,8 MM/reserve cases,8 hostile-context repeats and4 strict
zero/equal-rate borrow cases. These are checks, not538 distinct input states.
The specialization uses USD/BTC collateral and debt, frozen balances, interest,
cash deficit, signed linear position/cost dust and reserves. Individual
asset quotes cannot be drawn jointly: USD20 plus BTC0.5 at100 exceeds the
fixture's total-debt cap50. The zero sentinel never proves account safety.

Manual strict boundaries precede execution: USD10 with loan LTV1 and IM/MM0
allows at most9 whole USD; USD10.01 allows10. With IM=MM10%, USD11 allows9,
while USD11.01 allows10. A quote leaving equity exactly equal to MM rejects.

The initial 536 proposal and later metadata-archive gap are retained. First
complete source283dec8e actually passed its five methods/538 comparisons but
exited1 after fsync(1) on an inherited pipe. Independent RAW2eeda6da preserves
that FIRSTFAIL and withdraws the earlier terminal-compatibility CODE conclusion.
Its original vectors and controls remain private and are not relabeled.

The pipe-v2 sourcebb2a2cf1 removes only the two invalid pipe fsync calls.
JSON files and parent-owned regular raw files still fsync; the parent still
requires actual prefix exit0, wait/reap, both EOFs and source bindings. Independent
CODE924eca04 reviewed the minimal correction. Root observed new actual exit0
on432dc7; independent RAW7de83651 checked13 originals957060B/13 archive CRCs,
70 before/after source/control pins, all five actual IDs,538 financial maps,
534 provenance maps and complete vector bytes. This is limited synthetic
pure acceptance, not complete Cross or production acceptance.

Only the new synthetic vectors file is explicitly approved for publication:
evidence/golden/cross-decimal-pipe-v2/vectors.json,866704B,
SHA25617364d12847d5f118cc62f0e301a45180e8ccd353a38010e3cf3582a917afd97.
Its closed recursive schema, canonical original JSON bytes, public seed inputs,
fixed metadata and every rational risk/quote/feasible-list value were independently
checked without importing target code. No arbitrary text, private path, PID,
nonce or runtime/control binding is present. Other originals and the old
failure's vector file remain private. The new financial vector groups equal
the old groups, while execution identities and overall outcomes remain distinct.

Inner435803752ns, prefix762947166ns, host-to-receipt872419490ns and tool wall
0.808035368s are separate observations. They do not establish kernel speed,
end-to-end latency or capacity. Six read-only Git control children are separate
from the sole target prefix;20+2s is cooperative, not a blocked-I/O hard bound.

All62 UTA files, reference/default selection and original service routes remain
unchanged relative to PR51. The70 actually executed input bytes remain unchanged
after delivery integration. No database, account authority, product, policy
format or installed-engine activation changes. First public normal CI is pending.

Reproduce only with a new approved namespace and its exact retained source/plan;
do not reuse sealed output paths or historical plans with new bytes. Rollback
removes these validation files and preserves first failures and golden/source
records. Broader model domains, simultaneous borrowing, service integration,
loaded-engine binding, inverse/options/PM, precision-tail calibration, SQL,
matching, performance, HA and real-funds/production enablement remain OPEN.
