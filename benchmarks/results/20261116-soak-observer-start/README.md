# Independent read-only observer launch: 24h result remains pending

The immutable producer remains `88755a9f2ba3bb672ca5d354b3037796f00c6611`, PID4471, with its original actual start **2026-11-16T21:36:13.820942Z** and original deadline **2026-11-17T21:36:13.820942Z**. No producer source, authority, financial event or original clock was changed.

The independent observer is source `f96dfd8d6b1ca6f5ae28ac771c886baf4fdeb30e`, detached PID**8784**, actually started at **2026-11-16T22:10:01.547046Z**. It requests 86,400 observer seconds at one real observation per60s, bounded to64MiB. It can finish earlier only when the producer has actually elapsed24h and all final review prerequisites and complete log audit succeed; observer approval fields remain false. Its own elapsed time is never substituted for producer time.

This retained early prefix has two real observations. The latest one at `2026-11-16T22:11:01.672372+00:00` independently reads **522 completed roundtrips, 1044 actual matching receipts and 2088 paired fill legs**. Producer PID birth matches, proc state is `S`, heartbeat age is 0.925s, and no observer alerts are present. Its real producer age is only 2087.851s, so all 24h/capacity/production acceptance remains false. In-flight golden differences are explicitly indeterminate, not automatic financial faults.

The old paused preliminary PID3968 is independently identified as proc stateZ with alive=false. Its retained producer status may report historical /proc identity as alive; the observer result overrides that diagnostic interpretation without restarting either producer or editing either database.

Exact immutable sources are publicly reachable and ls-remote proof is retained:

- Producer: https://github.com/PureGamma-Harness/uta-unified-account/tree/experiment/soak-24h-20261116
- Observer: https://github.com/PureGamma-Harness/uta-unified-account/tree/experiment/soak-observer-20261116

The 13 original selfcheck outputs were generated on the exact frozen observer checkout. They include real read-only authority byte preservation, PID reuse/Z/X, original-time/source binding, mid-round handling, complete final gzip coverage, stale full-replay rejection and staging outside the producer's directory scan.

Only this launch and early prefix are committed. Continuing observations remain private under `/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9/observer-20261116T221001Z-f96dfd8`. Hourly checkpoint files are generated from actual periodic checks. Raw temporary files are staged outside the job on the same filesystem and atomically renamed into stable observer paths, so the observer cannot make producer directory scans chase disappearing temporary files. Producer source887 is unchanged and remains cache0, low-rate, co-hosted, single-host stability; this observes no acceptance of later managed modules.
