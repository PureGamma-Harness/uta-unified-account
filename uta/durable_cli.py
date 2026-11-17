"""Explicit local deployment entry point for the managed durable v2 authority.

No synchronous trading fallback, synthetic funding, credential generation or
automatic authority/authentication database initialization occurs in serve.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
from decimal import Decimal
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import signal
import sqlite3
import ssl
import stat
import sys

from .configuration import load_policy
from .durable_gateway import make_server, producer_binding
from .durable_process import DurableProcessRouter
from .gateway import load_credentials
from .market import MarketSnapshot
from .request_signing import NonceStore, RequestAuthenticator, load_profile
from .service import ServiceError, _amount
from .storage import StorageError


def _emit(value, *, output=None):
    print(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False),
          file=output or sys.stdout, flush=True)


def _integer(lower, upper):
    def parse(value):
        try:
            result = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError("requires an integer") from None
        if not lower <= result <= upper:
            raise argparse.ArgumentTypeError(f"requires an integer in {lower}..{upper}")
        return result
    return parse


def _number(lower, upper):
    def parse(value):
        try:
            result = float(value)
        except ValueError:
            raise argparse.ArgumentTypeError("requires finite seconds") from None
        if not math.isfinite(result) or not lower <= result <= upper:
            raise argparse.ArgumentTypeError(f"requires a finite number in {lower}..{upper}")
        return result
    return parse


def _hash(value):
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("requires the inspected lowercase SHA-256 layout hash")
    return value


def _fee(value):
    try:
        result = Decimal(value)
        _amount(result, "fee_rate")
        if not 0 <= result <= Decimal(".01"):
            raise ValueError("rate out of range")
    except (ValueError, ArithmeticError):
        raise argparse.ArgumentTypeError("requires a finite fee rate in 0..0.01 with at most eight fractional digits") from None
    return result


def _scales(entries):
    result = {}
    for item in entries or ("USD=8",):
        asset, separator, digits = item.partition("=")
        if (not separator or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", asset)
                or asset in result or not re.fullmatch(r"[0-9]{1,2}", digits) or not 0 <= int(digits) <= 18):
            raise ValueError("asset scales require unique ASSET=DIGITS entries in 0..18")
        result[asset] = int(digits)
    if "USD" not in result or not 2 <= result["USD"] <= 8:
        raise ValueError("USD settlement scale must be in 2..8")
    return result


def _private_path(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 1024 * 1024):
            raise ValueError("TLS material requires bounded private regular service-user-owned files")
    finally:
        os.close(descriptor)
    return os.fspath(path)


def _tls(cert, key):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # The callback prevents an encrypted key from opening an interactive prompt.
    context.load_cert_chain(_private_path(cert), _private_path(key), password=lambda: "")
    return context


def _runtime(args):
    return {key: getattr(args, key) for key in ("lease_seconds", "poll_interval", "background_interval",
                                              "account_batch", "matches_per_symbol", "max_attempts", "financial_batch_size")}


def _existing(args):
    return DurableProcessRouter(args.directory, **(_runtime(args) if hasattr(args, "lease_seconds") else {}))


def _auth_binding(store, router):
    if store.producer_binding != producer_binding(router):
        raise ServiceError("authentication_binding_mismatch", "authentication store belongs to another deployment", 409)


def _configured_auth(store, profile):
    with store._transaction(read=True) as connection:
        config = store._config(connection)
    if ((profile.tenant_id, profile.audience) != (store.tenant_id, store.audience)
            or config["revision"] != profile.revision or config["fingerprint"] != profile.fingerprint()):
        raise ServiceError("auth_configuration_required", "run explicit auth-configure with this private profile before serve", 409)


class _StopRequested(BaseException):
    pass


def _serve(args):
    address = ipaddress.ip_address(args.host)
    if address.version != 4 or not address.is_loopback:
        raise ValueError("serve binds only IPv4 loopback addresses")
    server = router = None
    previous = {}
    try:
        # Credentials and TLS material are validated before opening authority.
        if args.profile == "hmac-tls":
            if args.credentials or not all((args.auth_db, args.signing_profile, args.tls_cert, args.tls_key)):
                raise ValueError("hmac-tls requires --auth-db --signing-profile --tls-cert --tls-key and no Bearer credentials")
            profile = load_profile(args.signing_profile)
            context = _tls(args.tls_cert, args.tls_key)
            store = NonceStore(args.auth_db)  # Existing-only: never initialize here.
            _configured_auth(store, profile)
            router = _existing(args)
            _auth_binding(store, router)
            authenticator = RequestAuthenticator(store, profile)
            options = {"auth_profile": "hmac", "authenticator": authenticator,
                       "require_tls": True, "tls_context": context}
        else:
            if not args.credentials or any((args.auth_db, args.signing_profile, args.tls_cert, args.tls_key)):
                raise ValueError("bearer-development requires only --credentials; HMAC/TLS files cannot be silently ignored")
            options = {"auth_profile": "bearer_dev", "credentials": load_credentials(args.credentials)}
            router = _existing(args)
        if not router.decision_audit_required:
            raise ServiceError("decision_audit_upgrade_required", "CLI serve requires an explicitly upgraded required-audit authority", 503)
        server = make_server(router, args.host, args.port, max_workers=args.max_http_workers,
                             request_timeout=args.request_timeout, **options)
        # Binding and all authentication checks finish before any worker/nonce.
        def stop(signum, frame):
            for number in previous:
                signal.signal(number, signal.SIG_IGN)
            raise _StopRequested()
        for number in (signal.SIGTERM, signal.SIGINT):
            previous[number] = signal.signal(number, stop)
        router.start(recovery_timeout=args.recovery_timeout)
        _emit({"event": "listening", "pid": os.getpid(), "host": args.host,
               "port": server.server_port, "profile": args.profile,
               "tls": args.profile == "hmac-tls", "decision_audit_required": True,
               "qualification": "listener bound; queued ACK is not risk acceptance or trading readiness"})
        server.serve_forever(poll_interval=.1)
    except _StopRequested:
        return 0
    finally:
        # The accept loop has exited. Close listener and drain admitted HTTP
        # handlers while financial workers remain alive, then stop workers.
        try:
            if server is not None:
                server.server_close()
        finally:
            if router is not None:
                router.close()
            for number, handler in previous.items():
                signal.signal(number, handler)
    return 0


def _parser():
    parser = argparse.ArgumentParser(prog="uta-durable", description="Local managed durable v2 deployment; real-funds production remains NO-GO")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "inspect", "takeover", "serve", "publish", "activate", "halt", "status", "query",
                 "auth-init", "auth-configure", "upgrade-audit-plan", "upgrade-audit"):
        command = commands.add_parser(name)
        command.add_argument("--directory", type=Path, required=True)
        if name in ("init", "takeover"):
            command.add_argument("--queue-capacity", type=_integer(1, 65536), default=1024)
            command.add_argument("--cancel-reserve", type=_integer(0, 4096), default=16)
            command.add_argument("--market-capacity", type=_integer(1, 64), default=4)
        if name in ("takeover", "upgrade-audit"):
            command.add_argument("--expected-layout-hash", type=_hash, required=True)
        if name in ("publish", "activate", "halt"):
            command.add_argument("--timeout", type=_number(0, 3600), default=10)
        if name in ("auth-init", "auth-configure"):
            command.add_argument("--auth-db", type=Path, required=True)
        if name == "auth-configure":
            command.add_argument("--signing-profile", type=Path, required=True)
        if name == "auth-init":
            command.add_argument("--tenant", required=True)
            command.add_argument("--past-window-ms", type=_integer(1, 300000), default=30000)
            command.add_argument("--future-skew-ms", type=_integer(0, 30000), default=5000)
            command.add_argument("--max-nonces", type=_integer(1, 1000000), default=100000)
        if name == "init":
            command.add_argument("--durable-batches", action="store_true", help="irreversible fresh-layout batch capability")
            command.add_argument("--shards", type=_integer(1, 256), default=1)
            command.add_argument("--asset-scale", action="append")
            command.add_argument("--catalog", type=Path)
            command.add_argument("--risk-rules", type=Path)
            command.add_argument("--fee-rate", type=_fee, default=Decimal(".0004"))
            command.add_argument("--max-price-age", type=_number(.001, 300), default=30)
            command.add_argument("--reserve-cache-size", type=_integer(0, 65536), default=0)
            command.add_argument("--market-cache-size", type=_integer(0, 64), default=0)
        if name == "publish":
            command.add_argument("--snapshot-file", type=Path, required=True)
        if name == "query":
            command.add_argument("--command-id", required=True)
            scope = command.add_mutually_exclusive_group(required=True)
            scope.add_argument("--account-id")
            scope.add_argument("--shard", type=_integer(0, 255))
        if name == "serve":
            command.add_argument("--host", default="127.0.0.1")
            command.add_argument("--port", type=_integer(0, 65535), default=8081)
            command.add_argument("--profile", choices=("hmac-tls", "bearer-development"), default="hmac-tls")
            for field in ("credentials", "auth-db", "signing-profile", "tls-cert", "tls-key"):
                command.add_argument("--" + field, type=Path)
            command.add_argument("--max-http-workers", type=_integer(1, 256), default=16)
            command.add_argument("--request-timeout", type=_number(.1, 60), default=5)
            command.add_argument("--recovery-timeout", type=_number(0, 3600), default=10)
            command.add_argument("--lease-seconds", type=_number(.05, 3600), default=5)
            command.add_argument("--poll-interval", type=_number(.001, 60), default=.02)
            command.add_argument("--background-interval", type=_number(.01, 60), default=.1)
            command.add_argument("--account-batch", type=_integer(1, 1000), default=25)
            command.add_argument("--matches-per-symbol", type=_integer(1, 1000), default=10)
            command.add_argument("--max-attempts", type=_integer(1, 100), default=3)
            command.add_argument("--financial-batch-size", type=int, choices=(0,3,4,5,6,7,8), default=0)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    router = None
    try:
        if args.command == "serve":
            return _serve(args)
        if args.command == "inspect":
            _emit(DurableProcessRouter.inspect_takeover(args.directory))
            return 0
        if args.command == "init":
            if not args.fee_rate.is_finite() or not 0 <= args.fee_rate <= Decimal(".01"):
                raise ValueError("fee rate requires a finite Decimal in 0..0.01")
            router = DurableProcessRouter.initialize(args.directory, args.shards, _scales(args.asset_scale),
                managed=True, bootstrap=None, decision_audit=True, durable_batches=args.durable_batches, fee_rate=args.fee_rate,
                max_price_age=timedelta(seconds=args.max_price_age), **load_policy(args.catalog, args.risk_rules),
                reserve_cache_size=args.reserve_cache_size, market_cache_size=args.market_cache_size,
                queue_capacity=args.queue_capacity, cancel_reserve=args.cancel_reserve, market_capacity=args.market_capacity)
            _emit({"event": "initialized", "decision_audit_required": router.decision_audit_required,
                   "inspection": DurableProcessRouter.inspect_takeover(args.directory)})
            return 0
        if args.command == "takeover":
            router = DurableProcessRouter.take_over(args.directory, managed=True,
                expected_layout_hash=args.expected_layout_hash, decision_audit=True,
                queue_capacity=args.queue_capacity, cancel_reserve=args.cancel_reserve, market_capacity=args.market_capacity)
            _emit({"event": "taken_over", "inspection": DurableProcessRouter.inspect_takeover(args.directory)})
            return 0
        if args.command.startswith("upgrade-audit"):
            name = "plan_decision_audit_upgrade" if args.command.endswith("plan") else "upgrade_decision_audit"
            method = getattr(DurableProcessRouter, name, None)
            if method is None:
                raise ServiceError("audit_upgrade_unavailable", "this release does not include offline audit promotion", 503)
            if args.command.endswith("plan"):
                _emit(method(args.directory))
            else:
                router = method(args.directory, managed=True, expected_layout_hash=args.expected_layout_hash)
                _emit({"event": "audit_upgraded", "decision_audit_required": router.decision_audit_required})
            return 0
        # Remaining commands open existing metadata; none spawns a supervisor.
        if args.command == "auth-configure":
            profile = load_profile(args.signing_profile)
        router = _existing(args)
        if args.command == "status":
            report = router.diagnostics()
            report["observation"] = "external observer: lease fields are persisted; local supervisor pid/report fields may be absent"
            _emit(report)
        elif args.command == "query":
            result = router.status(args.command_id, account_id=args.account_id, shard=args.shard)
            if result is None:
                _emit({"error": {"code": "command_not_found", "message": "no command in the requested scope"}})
                return 4
            _emit(result)
        elif args.command == "publish":
            with args.snapshot_file.open("rb") as source:
                raw = source.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("market snapshot exceeds 1 MiB")
            snapshot = MarketSnapshot.from_json(raw.decode("utf-8"))
            result = router.publish_market(snapshot, timeout=args.timeout)
            _emit(result)
            return 3 if result["publishing"] or result.get("error") else 0
        elif args.command in ("activate", "halt"):
            enabled = args.command == "halt"
            result = router.set_kill_switch(enabled, timeout=args.timeout)
            _emit(result)
            return 3 if result["halted"] != enabled or result.get("error") else 0
        elif args.command == "auth-init":
            store = NonceStore.initialize(args.auth_db, tenant_id=args.tenant, producer_binding=producer_binding(router),
                past_window_ms=args.past_window_ms, future_skew_ms=args.future_skew_ms, max_nonces=args.max_nonces)
            _emit({"event": "auth_initialized", "tenant_id": store.tenant_id, "audience": store.audience,
                   "producer_binding": store.producer_binding, "secret_generated": False})
        elif args.command == "auth-configure":
            store = NonceStore(args.auth_db)
            _auth_binding(store, router)
            store.configure(profile)
            _emit({"event": "auth_configured", "tenant_id": store.tenant_id,
                   "audience": store.audience, "revision": profile.revision})
        return 0
    except KeyboardInterrupt:
        _emit({"error": {"code": "operator_interrupted", "message": "retain and query original command/control IDs"}}, output=sys.stderr)
        return 130
    except (ValueError, OSError, StorageError, sqlite3.Error) as exc:
        _emit({"error": {"code": getattr(exc, "code", type(exc).__name__), "message": str(exc)}}, output=sys.stderr)
        return 2
    finally:
        if router is not None:
            router.close()


if __name__ == "__main__":
    raise SystemExit(main())
