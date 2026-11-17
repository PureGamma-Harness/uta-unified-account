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
