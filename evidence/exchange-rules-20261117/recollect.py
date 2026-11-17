"""Append a fresh official-document capture, preserving all previous evidence.

No credential, cookie, account API or order is used. Raw pages and receipts go
only to a new private directory; this does not change any financial rule.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ALLOWED = {'raw.githubusercontent.com', 'developers.binance.com',
           'www.bybit.com', 'www.cmegroup.com'}
LIMIT = 4 * 1024**2


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if not args.private_output.is_absolute() or args.private_output.exists():
        parser.error('new absolute private output required; never overwrite old observations')
    manifest = json.loads(Path(__file__).with_name('sources.json').read_bytes())
    sources = manifest['observations']
    assert len(sources) == 10
    for row in sources:
        url = urlsplit(row['requested_url'])
        assert url.scheme == 'https' and url.hostname in ALLOWED
        assert not url.query and not url.username and not url.password
    args.private_output.mkdir(mode=0o700)
    observations = []
    for source in sources:
        row = {'source_id': source['source_id'], 'requested_url': source['requested_url'],
               'started_at_utc': now(), 'prior_sha256': source['sha256'],
               'authorization': 'public documentation; no account credential, cookie or order'}
        raw = bytearray()
        begin = time.monotonic_ns()
        row['body_complete'] = False
        try:
            request = Request(row['requested_url'], headers={'User-Agent': 'UTA-Evidence-Research/1.0',
                                                           'Accept': 'text/html,text/plain;q=0.9'})
            with urlopen(request, timeout=20) as response:
                final = urlsplit(response.url)
                assert final.hostname in ALLOWED and not final.username and not final.password and not final.query
                row.update(http_status=response.status, resolved_url=response.url)
                while len(raw) <= LIMIT:
                    block = response.read(min(65536, LIMIT + 1 - len(raw)))
                    if not block:
                        row['body_complete'] = True
                        break
                    raw.extend(block)
                if len(raw) > LIMIT:
                    raise ValueError('official_document_exceeds_4MiB_limit')
            row['retrieval_status'] = 'SUCCESS'
        except HTTPError as error:
            row.update(http_status=error.code, retrieval_status='HTTP_ERROR', error_type=type(error).__name__)
            raw.extend(error.read(LIMIT + 1))
        except BaseException as error:
            row.update(http_status=row.get('http_status'), retrieval_status='UNAVAILABLE',
                       error_type=type(error).__name__, error_digest=sha256(str(error).encode()).hexdigest())
        row.update(finished_at_utc=now(), elapsed_ns=time.monotonic_ns() - begin,
                   bytes=len(raw), sha256=sha256(raw).hexdigest())
        with (args.private_output / (row['source_id'] + '.raw')).open('xb') as stream:
            stream.write(raw)
        with (args.private_output / (row['source_id'] + '.receipt.json')).open('x') as stream:
            json.dump(row, stream, indent=2)
            stream.write('\n')
        observations.append(row)
    with (args.private_output / 'refresh-observations.json').open('x') as stream:
        json.dump(observations, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'documents_requested': len(observations),
                      'successful_complete_bodies': sum(r['retrieval_status'] == 'SUCCESS' and r['body_complete']
                                                        for r in observations),
                      'financial_rule_changes': 0, 'production_approved': False}))
    return int(any(r['retrieval_status'] != 'SUCCESS' or not r['body_complete'] for r in observations))


if __name__ == '__main__':
    raise SystemExit(main())
