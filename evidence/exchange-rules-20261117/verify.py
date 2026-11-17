"""Read-only official-document/Git/trace checks; never imports the product.

The only write is a new, explicitly supplied result file. Without retained raw
documents the result is PUBLIC_STRUCTURE_ONLY, never an HTTP/raw-byte recheck.
"""
import argparse
import ast
import csv
from datetime import datetime, timezone
from hashlib import sha1, sha256
from html import unescape
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

SOURCE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
BYBIT = 'e39367887e2dca58cd5257bf9c6231ce96be173b'
ALLOWED_HOSTS = {'raw.githubusercontent.com', 'github.com', 'developers.binance.com',
                 'www.cmegroup.com', 'www.bybit.com'}


def visible(raw):
    text = raw.decode('utf8')
    text = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', ' ', text, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', text))).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('new unique output required; original records are immutable')
    base = args.repository / 'evidence/exchange-rules-20261117'
    paths = [base / name for name in ('sources.json', 'rules.csv', 'scope.json', 'verify.py')]
    paths.append(args.repository / 'docs/exchange-rules-20261117/README.md')
    inputs = {str(p.relative_to(args.repository)): sha256(p.read_bytes()).hexdigest() for p in paths}
    checks = []

    def need(ok, name):
        if not ok:
            raise AssertionError(name)
        checks.append(name)

    manifest = json.loads((base / 'sources.json').read_bytes())
    need(manifest['source_commit'] == SOURCE and manifest['source_count'] == 10, 'exact_source_and_ten_documents')
    need(manifest['production_approved'] is False and manifest['financial_rules_signed_off'] is False
         and manifest['independent_review_signed_off'] is False, 'no_financial_or_production_signoff')
    records = manifest['observations']
    ids = {r['source_id'] for r in records}
    need(len(records) == len(ids) == 10, 'unique_source_ids')
    bybit_count = 0
    raw_bytes = 0
    for row in records:
        sid = row['source_id']
        need(bool(re.fullmatch(r'[A-Z0-9-]+', sid)), sid + ':safe_id')
        need(row['http_status'] == 200 and row['retrieval_status'] == 'SUCCESS', sid + ':original_HTTP200')
        need(0 < row['bytes'] <= 4 * 1024**2 and bool(re.fullmatch(r'[0-9a-f]{64}', row['sha256'])), sid + ':bounded_digest')
        for key in ('requested_url', 'resolved_url'):
            url = urlsplit(row[key])
            need(url.scheme == 'https' and url.hostname in ALLOWED_HOSTS and not url.username
                 and not url.password and not url.query, sid + ':' + key + '_official_no_signed_query')
        need(len(row['short_excerpt'].split()) == row['excerpt_word_count'] <= 25,
             sid + ':one_short_excerpt_at_most25words')
        need(row['public_raw_body_included'] is False and row['observation_only'] is True, sid + ':document_only_scope')
        start = datetime.fromisoformat(row['started_at_utc'])
        finish = datetime.fromisoformat(row['finished_at_utc'])
        need(start.tzinfo is not None and finish.tzinfo is not None and finish >= start,
             sid + ':original_capture_interval')
        if row.get('github_commit'):
            bybit_count += 1
            need(row['github_commit'] == BYBIT and row['github_repository'] == 'bybit-exchange/docs'
                 and row['github_metadata_blob_match'] is True,
                 sid + ':fixed_official_repository_commit')
        if args.private_root is not None:
            path = args.private_root / (sid + '.raw')
            need(path.is_file() and not path.is_symlink(), sid + ':retained_regular_raw')
            raw = path.read_bytes()
            need(len(raw) == row['bytes'] and sha256(raw).hexdigest() == row['sha256'], sid + ':original_bytes_SHA256')
            raw_bytes += len(raw)
            text = raw.decode('utf8') if row['excerpt_basis'] == 'raw MDX' else visible(raw)
            need(row['short_excerpt'] in text and all(x.lower() in text.lower() for x in row['semantic_markers']),
                 sid + ':semantic_markers_and_exact_quote')
            if row.get('github_commit'):
                need(sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == row['github_blob_sha1'],
                     sid + ':HTTP_raw_equals_official_Git_blob')
    need(bybit_count == 6, 'exact_six_pinned_Bybit_sources')
    with (base / 'rules.csv').open(newline='') as stream:
        rules = list(csv.DictReader(stream))
    need(len(rules) == 12 and len({r['rule_id'] for r in rules}) == 12, 'twelve_distinct_trace_rules')
    git_files = {}

    def source_file(path):
        if path not in git_files:
            git_files[path] = subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=args.repository)
        return git_files[path]

    for rule in rules:
        rid = rule['rule_id']
        need(all(value for value in rule.values()), rid + ':complete_trace_columns')
        need(set(rule['source_ids'].split(';')) <= ids, rid + ':known_official_sources')
        for test in rule['test_ids'].split(';'):
            file, name = test.split('::')
            nodes = ast.walk(ast.parse(source_file(file), filename=file))
            need(any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name for n in nodes),
                 rid + ':existing_test_' + name)
        for reference in rule['implementation_reference'].split(';'):
            path = reference.strip().split('::', 1)[0]
            need(bool(source_file(path)), rid + ':existing_source_reference_' + path)
    unchanged = subprocess.run(['git', 'diff', '--quiet', SOURCE, '--', 'uta', 'tests', 'pyproject.toml'],
                               cwd=args.repository).returncode == 0
    need(unchanged, 'no_runtime_tests_or_pyproject_change')
    need(inputs == {str(p.relative_to(args.repository)): sha256(p.read_bytes()).hexdigest() for p in paths},
         'public_inputs_unchanged_during_verification')
    result = {'status': 'RETAINED_DOCUMENTS_AND_TRACE_FILE_CHECKS_PASS' if args.private_root else 'PUBLIC_STRUCTURE_ONLY',
              'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'source_commit': SOURCE,
              'official_documents': 10, 'github_pinned_documents': bybit_count, 'trace_rules': len(rules),
              'retained_raw_bytes_checked': raw_bytes, 'private_raw_checked': args.private_root is not None,
              'checks': len(checks), 'check_names': checks, 'public_input_sha256': inputs,
              'referenced_source_file_sha256': {p: sha256(raw).hexdigest() for p, raw in sorted(git_files.items())},
              'no_product_import_SQL_network_or_trading': True, 'existing_tests_executed': False,
              'financial_rules_signed_off': False, 'independent_review_signed_off': False,
              'production_approved': False}
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'checks', 'official_documents', 'trace_rules',
          'retained_raw_bytes_checked', 'private_raw_checked', 'production_approved')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
