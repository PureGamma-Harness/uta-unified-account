# Managed read client: HTTPS, snapshots and cursor recovery

This is a small REST client recipe for the managed read capability. It does not submit commands, enable WebSocket delivery, reconstruct unsupported live risk, or approve production use. Use only an individually provisioned read key, its tenant/audience, and a verified TLS endpoint. Do not distribute the server's full signing-key file to a customer client.

## Independent HTTPS request example

The following client builds the documented HMAC bytes directly using the Python standard library. It does not import the exchange's service, schema, signing helper or financial engine. `secret` is the customer's key bytes supplied by an approved private loader; it is not a URL or command-line argument.

```python
import hashlib
import hmac
import http.client
import json
import secrets
import ssl
import time

def read_json(host, port, target, *, tenant, audience, key_id, secret, ca_file=None):
    # Build target once. Sign and send these exact bytes, including query order
    # and percent encoding. Never sort or decode it after computing the MAC.
    timestamp = str(time.time_ns() // 1_000_000)
    nonce = secrets.token_urlsafe(24)
    canonical = json.dumps([
        "UTA-HMAC-SHA256", "1", tenant, audience, key_id, timestamp, nonce,
        "GET", target, hashlib.sha256(b"").hexdigest()
    ], separators=(",", ":"), ensure_ascii=True).encode("ascii")
    headers = {
        "Authorization": "UTA-HMAC-SHA256",
        "X-UTA-Version": "1",
        "X-UTA-Tenant": tenant,
        "X-UTA-Audience": audience,
        "X-UTA-Key-Id": key_id,
        "X-UTA-Timestamp-Ms": timestamp,
        "X-UTA-Nonce": nonce,
        "X-UTA-Signature": hmac.new(secret, canonical, hashlib.sha256).hexdigest(),
    }
    context = ssl.create_default_context(cafile=ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    connection = http.client.HTTPSConnection(host, port, timeout=5, context=context)
    try:
        connection.request("GET", target, headers=headers)
        response = connection.getresponse()
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise RuntimeError("read response exceeds this client's configured bound")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise RuntimeError(f"non-JSON read response, HTTP {response.status}") from None
        if response.status != 200 or not isinstance(payload, dict):
            code = payload.get("error", {}).get("code", "unavailable") if isinstance(payload, dict) else "unavailable"
            raise RuntimeError(f"read failed: HTTP {response.status}, code={code}")
        return payload
    finally:
        connection.close()
```

Every call makes a new nonce, including retries of the same read. This helper deliberately does not disable certificate or hostname verification. The 8 MiB response bound is a sample client policy: a larger valid evidence record requires an explicit reviewed client limit, not truncation or partial acceptance. Handle overload responses that have no JSON body as errors and keep the old cursor.

The helper targets successful read resources, which return 200. It does not interpret 202 command ACKs or mutate command identities. For command outcome recovery, use a new nonce with the original account/command ID under the separate [durable command contract](durable-api.md).

## Initial account reconstruction

1. Read `/v2/accounts/{aid}`. Keep `snapshot.stream_id`, `account_version`, `events_watermark`, `market_snapshot_id` and `policy_ref` with the settled account data.
2. Fetch the account's order and position pages with `at_version=<that version>` and `stream_id=<that stream>`. Save each resource's first `page.until` and pass it on subsequent pages. Build each target once, for example with `urllib.parse.urlencode`; sign the encoded target exactly as sent.
3. If a page returns `view_version_changed` or its stream identity differs, discard the incomplete reconstruction and restart. Market/config references can change without an account-version change; compare them as well when assembling a market-based display. The server does not maintain a snapshot lease between HTTP requests.
4. Do not interpret `risk.status=unsupported`, null reserves, stale/future/missing market, or `local_halt_observed=false` as a trading decision. Settled cash is not spendable cash; debt, order encumbrance and live risk gates are separate.

This recipe can require restarts under frequent writes/publications. It is not a promise that a paginated multi-request reconstruction always completes within a latency target. Such a target needs separate measurement and, if necessary, a reviewed snapshot/subscription protocol.

## Private event catch-up

After a complete account snapshot at event watermark `W`, request:

```text
/v2/accounts/{aid}/events?after=W&limit=100&stream_id=<url-encoded-stream-id>
```

Use the first catch-up response's `page.until` to drain a fixed range. Apply events in sequence order, deduplicate with `(stream_id, sequence)`, and atomically save the applied local state plus `page.next_after` in the client's own durable transaction. On the next range, omit `until` to observe a new watermark. The server's event sequence is global within the shard, while its SQL filters the account before LIMIT: gaps and a final cursor advancing beyond the last private row are expected.

Do not set `at_version` while following an append-only stream through newer account versions. That option is for an unchanged projection, not a request to suppress future account changes. Ledger sequences are a separate cursor domain and cannot be substituted for private-event sequences.

If an HTTP response is lost, retain the last applied cursor and repeat the same range with a **fresh signing nonce**. Duplicate event rows are possible and must not be applied twice. If the client crashes after receiving but before atomically applying/saving the page, resume from the last durable applied cursor. Receipt of JSON alone is not a local commit.

Rebuild on `view_stream_changed` or `view_cursor_ahead`. Never silently reset to zero, assume an ahead cursor was delivered, or combine a restored authority with the old stream. The local stream identity is not an external seal against in-place administrator rollback or whole-machine cloning.

## Operator checks and failure handling

- 401 signing/expiry errors require fixing the key/window/configuration; do not fall back to Bearer. A 409 `request_replayed` requires a new nonce, whereas a 409 view stream/version/cursor error requires the indicated read reconstruction action.
- 503 authentication/database/view errors do not authorize financial repair, key/nonce database reinitialization, deleting audit guards, or using a writer token in the parent. Retain IDs/cursors, investigate and retry within the approved recovery process.
- Risk/admin diagnostics can report `control_observed=false` and `control=null`. Worker liveness is reported separately from persistent financial-readiness observations. Neither diagnostic readiness nor a fresh read snapshot is an individual account risk acceptance.
- Use original asset/decimal strings. Do not convert ledger minor units or money through binary float, net away gross liabilities, or infer missing legacy decision evidence from current prices.

The reader's file preflight must remain `stat(..., follow_symlinks=False)`. Do not add a raw open/fstat/close probe of a published SQLite database: POSIX close on that inode can release other SQLite connections' locks in the same process. The managed view connection itself uses SQLite `mode=ro`, rejects empty/missing files and does not configure journal mode or initialize schema.

This REST recipe prepares a later private delivery protocol; it is not that protocol. There are no subscriptions, delivery ACK persistence, socket backpressure or exactly-once network claims here. Independent read-capability review, capacity acceptance and production approvals remain required.
