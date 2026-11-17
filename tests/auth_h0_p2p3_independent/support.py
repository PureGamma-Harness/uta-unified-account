"""Independent, opt-in AuthDB probe support; importing this file creates no DB.

MAC expected bytes are literal protocol arrays, independent of product signers.
All credentials and exact requests are retained only under a fresh private root.
"""
import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace

SOURCE_REF = '912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
RUNTIME_REF = '5750e12d60dbf7f8414b4e837e076a60c93a23bc'
FLAGS = ('financial_authorized', 'source_delivery_authorized', 'execution_authorized')
TABLES = ('auth_config', 'auth_keys', 'auth_nonces', 'auth_audit',
          'auth_credit_grants', 'auth_credit_grant_revocations', 'auth_credit_acceptances')


class NotCompleted(Exception):
    """Observed prefix retained; original planned target has not completed."""


class TechnicalUnknown(Exception):
    """A technical or process outcome cannot be claimed as passed."""


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def save(path, data):
    """Exclusive, private, fsynced record. Never repair an earlier outcome."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def source_hashes(source):
    assert source.is_absolute()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source,
                                   text=True).strip() == SOURCE_REF
    assert subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True) == ''
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only',
                                     RUNTIME_REF, '--', 'uta'], cwd=source, text=True).splitlines()
    assert len(names) == 64
    result = {}
    for name in names:
        raw = (source / name).read_bytes()
        assert raw == subprocess.check_output(['git', 'show', RUNTIME_REF + ':' + name], cwd=source)
        result[name] = hashlib.sha256(raw).hexdigest()
    return result


def bind_source(source):
    hashes = source_hashes(source)
    sys.path.insert(0, str(source))
    from uta.credit_auth_h0 import CreditNonceStoreV2, CreditHmacIngressV2
    from uta.request_signing import SigningError
    return SimpleNamespace(Store=CreditNonceStoreV2, Issuer=CreditHmacIngressV2,
                           SigningError=SigningError, hashes=hashes)


def unchanged(source, hashes):
    return all(sha(source / name) == value for name, value in hashes.items())


def observe(issuer, handle, *, release=False):
    value = dict(issuer.inspect(handle))
    assert all(value[name] is False for name in FLAGS)
    if release:
        issuer.release(handle)
    return value


def snapshot(path):
    """Read only this probe's completed/current own DB at one logical snapshot."""
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_PRAGMA,
                   sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION}
        c.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        data = {}
        for name in TABLES:
            cur = c.execute('SELECT * FROM main.' + name + ' ORDER BY 1')
            columns = [item[0] for item in cur.description]
            data[name] = [dict(zip(columns, row)) for row in cur.fetchall()]
        assert c.execute('PRAGMA main.foreign_key_check').fetchall() == []
        c.rollback()
    return data


class WireReference:
    """No product canonicalizer, key object, context, verifier or signer oracle."""

    def __init__(self, profile_path, request_root):
        profile = json.loads(profile_path.read_bytes())
        self.tenant = profile['tenant_id']
        self.audience = profile['audience']
        self.keys = {row['key_id']: row for row in profile['keys']}
        self.request_root = request_root
        request_root.mkdir(mode=0o700)
        self.count = 0

    def signed(self, cid, *, lookup=False, key='funding'):
        row = self.keys[key]
        account = row['account_id']
        method = 'GET' if lookup else 'POST'
        target = '/v2/accounts/' + account + ('/credit/commands/' + cid if lookup else '/borrow')
        body = b'' if lookup else canonical({'command_id': cid, 'asset': 'BTC', 'amount': '0.4'}).encode('ascii')
        stamp = str(time.time_ns() // 1000000)
        nonce = secrets.token_urlsafe(24)
        # Literal array and field order from public wire contract, not product helpers.
        message = json.dumps(['UTA-HMAC-SHA256', '1', self.tenant, self.audience, key,
                              stamp, nonce, method, target, hashlib.sha256(body).hexdigest()],
                             separators=(',', ':'), ensure_ascii=True).encode('ascii')
        encoded = row['secret_b64']
        secret = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
        headers = {'Authorization': 'UTA-HMAC-SHA256', 'X-UTA-Version': '1',
                   'X-UTA-Tenant': self.tenant, 'X-UTA-Audience': self.audience,
                   'X-UTA-Key-Id': key, 'X-UTA-Timestamp-Ms': stamp,
                   'X-UTA-Nonce': nonce, 'X-UTA-Signature': hmac.new(secret, message, hashlib.sha256).hexdigest()}
        self.count += 1
        save(self.request_root / ('private-request-' + str(self.count) + '.json'),
             {'headers': headers, 'method': method, 'request_target': target,
              'body_base64': base64.b64encode(body).decode('ascii')})
        return headers, {'method': method, 'request_target': target, 'body': body}


class Fixture:
    def __init__(self, api, root):
        self.api, self.root = api, root
        root.mkdir(mode=0o700)
        self.path, self.profile = root / 'auth.sqlite3', root / 'private-profile.json'
        self.scope = {'tenant_id': 'independent-tenant', 'producer_binding': '8' * 64,
                      'domain_id': 'independent-domain', 'domain_epoch': 1,
                      'account_id': 'independent-account', 'enabled': True}
        store = api.Store.initialize(self.path, **{key: value for key, value in self.scope.items()
                                                  if key not in ('enabled', 'domain_epoch')})
        expires = time.time_ns() // 1000000 + 3600000
        save(self.profile, {'format': 1, 'tenant_id': self.scope['tenant_id'],
             'audience': store.audience, 'revision': 1,
             'keys': [{'key_id': key, 'secret_b64': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='),
                       'role': 'reader' if key == 'reader' else 'funding',
                       'account_id': self.scope['account_id'], 'not_before_ms': 0,
                       'expires_at_ms': expires, 'revoked': False}
                      for key in ('funding', 'reader', 'ungranted')]})
        # Default max_handles=256/query_handle_reserve=32; no override of either.
        self.issuer = api.Issuer(self.path, self.profile, **self.scope)
        for revision, (identity, key, operation) in enumerate(
                [('borrow', 'funding', 'credit.borrow'), ('read', 'funding', 'credit.read'),
                 ('repay', 'funding', 'credit.repay'), ('reader', 'reader', 'credit.read')]):
            result = self.issuer.store.put_grant('g-' + identity, key_id=key,
                account_id=self.scope['account_id'], asset='BTC', operation=operation,
                expected_grant_revision=revision)
            assert result['grant_epoch'] == revision + 1
        self.wire = WireReference(self.profile, root / 'parent-private-requests')
        save(root / 'private-descriptor.json', {'database': str(self.path),
             'profile': str(self.profile), 'scope': self.scope})

    def call(self, cid, *, lookup=False, key='funding'):
        headers, request = self.wire.signed(cid, lookup=lookup, key=key)
        return (self.issuer.lookup if lookup else self.issuer.capture)(headers, **request)


def identity(pid):
    proc = Path('/proc') / str(pid)
    raw = (proc / 'stat').read_text()
    fields = raw[raw.rfind(')') + 2:].split()
    return {'pid': pid, 'birth': fields[19], 'state': fields[0], 'ppid': int(fields[1]),
            'uid': proc.stat().st_uid, 'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def same_process(expected, actual):
    return all(expected[key] == actual[key] for key in ('pid', 'birth', 'uid', 'boot'))


def report_base(source, api, start, begin):
    return {'source_commit': SOURCE_REF, 'runtime_commit': RUNTIME_REF,
            'source_validation_scope': '64 runtime files and Git HEAD; public evidence may be sparse',
            'runtime_hashes_before': api.hashes, 'source_unchanged': unchanged(source, api.hashes),
            'started_at': start, 'finished_at': utc(), 'elapsed_ns_before_report_write': time.monotonic_ns() - begin,
            'python': sys.version, 'sqlite': sqlite3.sqlite_version,
            'affinity': sorted(os.sched_getaffinity(0)), 'financial_authority_claimed': False,
            'financial_objects_or_public_endpoint': False, 'production_approved': False}
