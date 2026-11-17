# Preregistered complete V2 legacy refusal and lease handover

These are test-only actual-runtime cases, not executed at this checkpoint.
They change no `uta/` module or capability. SQL execution awaits the parent's
short CPU4 window; no listener, pressure test, or retained/live DB is used.

The first case installs the complete actual synthetic V2 through the real
installer, while generation remains zero and no owner exists. Three actual
archived public sources (899c91d, 45818c0, ad3f5b8), each with the repository's
fixed archive hash and original LICENSE, run in separate child processes using
the canonical same complete database path. The actual loaded storage source
hash is checked. The fence-aware old sources must refuse acquire; the pre-fence
source must refuse its real ledger construction/write attempt. Generation,
owner absence, all selected financial/source/decision rows and FK checks must
remain unchanged. These trusted fixed public fixtures are executable controls;
this does not enable execution of unknown customer audit archives.

Every old source has an actual positive control. Fence-aware binaries acquire
a real uncapped authority and commit an actual account version write. The
pre-fence binary posts and commits a balanced journal in its own separate
unfenced ledger database. A loader/import failure or any child exit other than
zero is a harness failure, not a successful refusal. An old binary's native
missing-UDF SQLite error is recorded as such, never mislabeled as constraint
787 or financial audit validation. Actual negative child phase/error codes are
not yet known and will remain raw evidence if they disagree with the test.

The second case uses the actual boot-clock lease and original source/PENDING
producer commit. A true renew must preserve generation and financial state.
Release and explicit V2 reacquire must advance generation; the old token's
renew and financial processing must fail. A newly constructed existing-only
service group on the real new bound database must settle the original CID
once. Reenqueue and status must return its original receipt without new source,
intent, decision or journal effects. This is a same-process owner handover and
readonly service reopen case, not a process restart, clock-expiry timing proof,
or multi-node ownership proof. The parent owns the separate process-restart
and live-UTC chain. No nonce or token is exported in public raw.

Expected run budget: two cases, sequential on CPU4, disposable own databases,
at most 45 seconds. No run result or production approval is claimed here.

## Actual fixed-source result

Root authorized exact `81cad4e11a2c09313d8b2c61472c42b91e4644ce` after
reviewing the two targets and watchdog contract. One Python 3.12 invocation on
CPU4 ran at 2026-11-17 15:08:59.573791–15:09:11.283561 UTC (11.710 seconds
process, 11.498 seconds unittest), two cases passed, exit 0. The outer new
process-group watchdog was 45 seconds; each of six old-source children had its
own eight-second timeout. There was no forced termination or residual process
group. Temporary old-source directories and fixture databases were cleaned.

Both 899c91d and 45818c0 acquired their actual uncapped positive-control lease
and committed the account version write. Against the complete newly installed
V2, each refused acquire with `fence_guard_corrupt`. Ad3f5b8's independent
unfenced positive ledger committed a balanced journal. Against the complete V2
its actual `ledger_post` failed with `OperationalError`, native **SQLITE_ERROR
1**, `no such function: uta_credit_v2_gate`. This is explicitly an old runtime's
native-function refusal, not a foreign-key constraint, credit decision replay,
or substitute positive control. Actual child source hashes are in raw.

For every complete-capability negative, the selected **12 financial/source/
intent/decision tables** matched their prior snapshots; generation remained
zero with no owner, and the actual FK check was empty. This is not an assertion
that every database byte or every table remained unchanged.

The real boot-clock lease renewed without changing generation or financial
state. Release and explicit V2 reacquire advanced generation 1 to 2. The old
owner's renew and financial attempt failed. A new existing-only service group
on the actual new bound database settled the original pending CID once, then
reenqueue/status returned the original receipt with no further financial
effects. There was exactly one source, one intent and one dedicated decision.

The fixture's exchange clock remained the original static synthetic clock.
The result establishes same-process native lease handover and readonly reopen;
it does not establish process restart, lease expiry timing, live-UTC behavior,
RTO/RPO, multi-node ownership, or production readiness. No nonce or token was
exported. Original earlier prototype-marker tests remain separate evidence.

Raw and full source/test/fixture SHA metadata:
`evidence/runs/credit-v2-complete-legacy-lease/attempt-01/`.
