# Managed durable deployment CLI

`uta-durable` (or `python -m uta.durable_cli`) operates the durable v2 process
authority. It never delegates an unsupported command to the v1 synchronous
service. This remains a local, synthetic/authorized-data deployment surface:
**real-funds production is NO-GO**. Native TLS and signatures do not establish
replication, capital calibration, external custody, capacity or launch approval.

## Initialize or explicitly migrate

```sh
uta-durable init --directory ./managed --shards 2 --asset-scale USD=8 \
  --catalog ./catalog.json --risk-rules ./rules.json
uta-durable inspect --directory ./managed
```

Catalog and rules use the existing versioned configuration formats and must be
supplied together. Omitting both explicitly selects the existing reference
policy; it does not authorize additional products. Scales default to `USD=8`.
New layouts always require decision audit/schema 3 and start halted. Initialization
creates no account, deposit, loan, market quote, private key, signing secret or
automatic synthetic liquidity. Public live funding/account creation is not
silently enabled. Use an independently authorized offline bootstrap/migration
procedure when accounts and custody-confirmed funding must be imported.

`init` refuses a nonempty directory. For an existing legacy **sharded** authority,
halt ingress and old writers, back up/reconcile storage, inspect the actual
descriptor, and invoke:

```sh
uta-durable takeover --directory ./existing \
  --expected-layout-hash HASH_FROM_INSPECTION
```

The hash is checked before takeover changes control state. Takeover retains the
existing policy and accepted financial data, enables managed fencing and required
audit explicitly, and stays halted. It is not an importer for an arbitrary single
SQLite file. Interrupted takeover is recovered through its recorded protocol;
do not delete files or initialize over a partial authority.

An already managed authority with a legacy audit gap uses its separate offline
promotion, after stopping its coordinator:

```sh
uta-durable upgrade-audit-plan --directory ./existing
uta-durable upgrade-audit --directory ./existing \
  --expected-layout-hash HASH_FROM_PLAN
```

Promotion is explicit, resumable and remains halted. Its original immutable
configuration bytes and legacy evidence gaps are retained. A release without
that runtime capability returns `audit_upgrade_unavailable`; it never uses a
fallback. Active coordinators and mismatched layouts are rejected by the
runtime. `inspect` is the read-only inspection surface; ordinary runtime opens
can intentionally persist a protective global halt if damaged state is found.

## HMAC and native TLS by default

Initialize authentication separately; the auth parent directory must exist and
belong to the operator. The command creates an empty replay authority and returns
its audience, not a secret:

```sh
uta-durable auth-init --directory ./managed --auth-db ./auth/nonces.sqlite3 \
  --tenant exchange-local
```

Prepare a private signing-profile file using keys supplied through an authorized
secret-management process. Its existing format is:

```json
{
  "format": 1,
  "tenant_id": "exchange-local",
  "audience": "AUDIENCE_RETURNED_BY_AUTH_INIT",
  "revision": 1,
  "keys": [{
    "key_id": "operator-v1",
    "secret_b64": "EXTERNAL_BASE64URL_SECRET_WITHOUT_PADDING",
    "role": "admin",
    "account_id": null,
    "not_before_ms": 0,
    "expires_at_ms": 2000000000000,
    "revoked": false
  }]
}
```

This is a template, not a usable embedded credential. Secrets require 32..128
bytes. Configure explicit roles and account scopes; give customers their own
trader/reader/funding keys. Persist the reviewed profile as a separate action:

```sh
uta-durable auth-configure --directory ./managed --auth-db ./auth/nonces.sqlite3 \
  --signing-profile ./auth/profile.json
uta-durable serve --directory ./managed --auth-db ./auth/nonces.sqlite3 \
  --signing-profile ./auth/profile.json --tls-cert ./tls/server.crt \
  --tls-key ./tls/server.key --host 127.0.0.1 --port 8081
```

Profiles, certificate and key must be regular nonsymlink files owned by the
service user, with no group/other permission bits (for example mode 0600).
TLS requires 1.2 or newer. The key must load without an interactive password
prompt. The server binds only an IPv4 loopback literal because the underlying
gateway supports that boundary. An external deployment needs its separately
reviewed network/TLS forwarding topology; this CLI does not open a public bind.

`serve` requires an existing authentication database and an already configured
exact profile revision/fingerprint. A profile change needs a new explicit
`auth-configure`; startup does not silently rotate keys or create a nonce store.
It validates private material and deployment binding, binds the listener, and
only then starts financial workers. A bind/auth/TLS failure therefore starts no
worker and consumes no request nonce. The `listening` JSON event reports binding,
not trading readiness or risk acceptance. Fresh authorities still have no market
and remain halted until an explicit publication and activation complete.

Signing covers the exact method, raw target, body, tenant, audience, key ID, time
and nonce. Use the existing `uta.request_signing.sign_headers` client helper and
send those exact bytes. Each retry needs a fresh signed-request nonce while
retaining the **original business command ID**. Consumed nonces survive process
restart; replay returns `request_replayed` (409). `auth-init` optionally sets the
bounded immutable replay window/capacity through `--past-window-ms`,
`--future-skew-ms` and `--max-nonces`. No signing secret is printed by this CLI.

For an isolated loopback development environment only, opt in explicitly:

```sh
uta-durable serve --directory ./managed --profile bearer-development \
  --credentials ./private-development-credentials.json
```

That file uses the existing private credential-array format. It is plaintext
loopback development authentication; it cannot be selected by an HMAC failure.
HMAC/TLS files cannot be silently ignored under this profile. Required financial
audit remains enforced even in this development authentication profile.

## Quotes, controls and outcomes

Operator commands act on existing worker processes; they do not start a second
supervisor:

```sh
uta-durable publish --directory ./managed --snapshot-file ./trusted-snapshot.json
uta-durable activate --directory ./managed
uta-durable halt --directory ./managed
uta-durable status --directory ./managed
uta-durable query --directory ./managed --account-id ACCOUNT --command-id ORIGINAL_ID
```

`publish` reads the full existing `MarketSnapshot` JSON, including its actual
version and observation time. It never refreshes a timestamp or creates prices.
Old or inconsistent quotes remain subject to the authoritative worker's rules.
Incomplete publication/activation is reported as incomplete and stays protected;
query original control receipts and resolve the condition before activation.
Use `--shard` instead of `--account-id` for an explicitly scoped control query.

The short-lived `status` observer has no local worker objects. Persisted lease
fields are useful observations; absent local PID/report fields and `ready=false`
are not proof that another coordinator is absent. The signed server's
`/v2/worker-health` observes its own actual workers. Neither is a financial receipt.
CLI `query` exposes the raw durable record: PENDING is only queued; SUCCEEDED,
REJECTED and QUARANTINED are terminal facts. The HTTP API additionally labels
terminal acknowledgements separately. No queued record means risk acceptance.

## Shutdown, failures and recovery

SIGTERM/SIGINT stop acceptance, close the listener and drain admitted HTTP
handlers **before** stopping workers. The runtime then joins/stops its children;
durable pending commands are preserved. A later `serve` reacquires ownership and
recovers that work under the existing fencing protocol. The CLI does not release
in-transit reservations or erase a nonce merely because its parent stopped.
For any lost response, query the original command ID using a fresh request nonce.

Exit codes are 0 for a completed command/observation or orderly server stop, 2
for validation/runtime error, 3 for incomplete control fanout, 4 for a missing
scoped command, and 130 for an interrupted short-lived operator action. Errors
are JSON on stderr; argparse usage errors use its standard text. Startup error
does not authorize reinitializing or rolling back acknowledged financial state.

Rollback means stopping ingress, preserving inbox/auth/history files, and using
a release compatible with managed fencing, schema 3 and replay metadata. Old
unfenced financial writers, schema downgrades and deleting the directory are not
rollback procedures. Verify financial, command and nonce outcomes before
reactivation. Retain original failure output rather than replacing it with a
later successful run.

Run `python -m unittest discover -s tests -p 'test_durable_cli.py' -v`. Acceptance
uses real separate CLI/worker PIDs, native TLS with a trusted synthetic test
certificate, HMAC requests, SIGTERM, parent restart, persistent pending/nonce
recovery and occupied-port failure. These short tests do not satisfy the separate
24-hour stability, capacity, disaster-recovery or real-funds launch gates.
