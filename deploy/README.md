# Managed v2 service template

`uta-durable.service` is a review deployment template for a **single Linux host**.
It does not initialize accounts, import custody balances, generate private keys,
publish quotes, activate trading, install a network proxy or grant production
approval. Product/capacity/replication gates remain open.

The development container has no privileged system service manager. System-mode
verification is unavailable (`/run/systemd` permission denied); user-mode
`systemd-analyze verify` parses this template but reports the intentionally
not-yet-installed `/opt/uta/venv/bin/uta-durable` executable. This is not a
successful service deployment. Validate the unchanged unit on the target host
after installing the reviewed wheel, then exercise real stop/restart and cgroup
timeout behavior there. CLI lifecycle tests alone do not certify systemd policy.

Build and install the exact reviewed wheel into `/opt/uta/venv` and verify its
source/artifact manifest. Create a dedicated `uta` OS user. Before starting the
unit, use that same user and [the CLI procedure](../docs/durable-cli.md) to:

1. Explicitly initialize a new empty authority, or inspect/reconcile and take over
   an existing supported sharded authority. Preserve the complete existing
   layout/control/shards and all confirmed events. Stop old ingress/writers.
2. Explicitly upgrade legacy managed audit if required, then check the required
   schema capability and legacy evidence gaps. Do not overwrite an incomplete
   migration or move a managed shard from its canonical path.
3. Initialize a separate nonce authority under `/var/lib/uta-durable/auth` and
   explicitly configure the reviewed private signing profile. Keep its audience,
   nonce/highwater/revocation state with the deployment; do not recreate on start.
4. Provision real deployment certificate/key and signing profile through the
   authorized secret process. These three files must be nonsymlink regular files
   owned by `uta`, mode `0600`. No working signing secret is included in Git.
5. Review the desired shard count, memory, FD/task limits and stop deadline on the
   target host. The template's 256 task limit is not a benchmark or a promise of
   arbitrary shard capacity. Run the actual installed synthetic/TLS/process
   acceptance before enabling the unit.

Install the unit and start it through the host's reviewed service-management
process. It binds only loopback. The external ingress/proxy, certificate
validation, network controls and access to local operator commands require
their own deployment review. Credentials do not authorize OS shell access.

`KillMode=mixed` is intentional: SIGTERM first reaches the coordinator, which
stops accept and drains admitted HTTP handlers while shard workers remain alive.
The workers then stop through their lifecycle pipes. At 120 seconds the service
manager may kill the entire cgroup; this becomes a tested crash-recovery case,
not a claim that every request completed. Choose an adequate deadline for actual
bounded DB waits, HTTP limits, shard count and backlog. The parent never drops a
durable PENDING or releases reservations just because a request timed out.

The process needs its own `/proc` birth identity and
`/proc/sys/kernel/random/boot_id`, CLOCK_BOOTTIME, shared flock, SQLite WAL and
Linux pidfd for registered orphan recovery. Do not add `ProcSubset=pid`, separate
PID namespaces or an inaccessible private network without revalidating those
contracts. The unit deliberately grants no Linux capabilities; it only signals
its own same-user registered workers after verifying their identity.

Listener binding is not financial readiness. Publish the actual complete fresh
snapshot through an authorized local `publish`, wait for all receipts, and then
explicitly `activate`. No trusted pricing process is bundled by this unit.
Stale/missing feeds must not be repaired by changing an old observation time.

For rollback, stop ingress and the unit; preserve the **whole** financial/control
authority plus authentication state, logs and artifact versions. Reconcile
original command IDs, matches, positions, ledger and pending obligations before
forward repair/restart. Do not run an old unfenced binary, disable guards,
recreate nonce state, or restore a backup that discards later confirmed trades.
This template supplies no cross-host replication, RPO/RTO or regional recovery.
