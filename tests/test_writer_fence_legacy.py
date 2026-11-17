"""Real pre-fencing source compatibility; no git history is needed in CI."""
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError


class LegacyBinaryFenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy_directory = TemporaryDirectory()
        fixture = Path(__file__).parent / 'fixtures'
        cls.provenance = json.loads((fixture / 'legacy_ad3f5b8_provenance.json').read_text())
        archive = fixture / 'legacy_ad3f5b8_uta.tar.gz'
        if sha256(archive.read_bytes()).hexdigest() != cls.provenance['archive_sha256']:
            raise AssertionError('legacy source archive checksum mismatch')
        cls.legacy_root = Path(cls.legacy_directory.name)
        with tarfile.open(archive) as source:
            for member in source.getmembers():
                path = PurePosixPath(member.name)
                if (path.is_absolute() or '..' in path.parts or
                    not (member.name == 'LICENSE' or path.parts[0] == 'uta') or
                    not (member.isfile() or member.isdir()) or member.size > 2_000_000):
                    raise AssertionError('unsafe legacy source archive member')
                target = cls.legacy_root.joinpath(*path.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as original, target.open('wb') as output:
                        shutil.copyfileobj(original, output)
        if sha256((cls.legacy_root / 'uta/storage.py').read_bytes()).hexdigest() != cls.provenance['storage_sha256']:
            raise AssertionError('legacy storage source checksum mismatch')

    @classmethod
    def tearDownClass(cls):
        cls.legacy_directory.cleanup()

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Database(Path(self.directory.name) / 'exchange.sqlite3')
        self.exchange = ExchangeService(self.database, {'USD': 8})
        for account in ('alice','bob'):
            self.exchange.create_account(account)
            self.exchange.deposit(account, 'seed', 'USD', D(1000))
        self.exchange.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {'USD': AssetSpec(D(1),D(1))}, {'BTC-PERP': InstrumentSpec(D(100),D('.1'),D('.05'))}))
        self.exchange.set_kill_switch(False)
        Matcher(self.exchange)
        CreditService(self.exchange)
        self.exchange.submit_order('alice','buy','BTC-PERP',D(1),D(100))
        self.exchange.submit_order('bob','sell','BTC-PERP',D(-1),D(100))

    def snapshot(self):
        with self.database.read_transaction() as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'writer_fence_%' ORDER BY name")]
            return {name: [tuple(row) for row in connection.execute('SELECT * FROM "'+name+'" ORDER BY rowid')]
                    for name in tables if name != 'sqlite_sequence'}

    def test_real_old_process_objects_cannot_write_after_management_activation(self):
        script = r'''
import sys,json
sys.path.insert(0,sys.argv[1])
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
from uta.storage import Database
from uta.service import ExchangeService
from uta.matching import Matcher
from uta.ledger import Posting
import uta.storage
service=ExchangeService(Database(sys.argv[2]),{'USD':8})
matcher=Matcher(service)
print(json.dumps({'ready':True,'storage_sha256':sha256(Path(uta.storage.__file__).read_bytes()).hexdigest(),'fence_loaded':'uta.writer_fence' in sys.modules}),flush=True)
sys.stdin.readline()
operations=[('deposit',lambda:service.deposit('alice','legacy-deposit','USD',D(1))),('order',lambda:service.submit_order('alice','legacy-order','BTC-PERP',D(1),D(100))),('ledger',lambda:service.ledger.post('legacy-ledger',[Posting('external','USD',D(-1)),Posting('customer:alice','USD',D(1))])),('match',lambda:matcher.match_once('BTC-PERP'))]
results=[]
for name,operation in operations:
 try:
  operation();results.append({'operation':name,'wrote':True})
 except BaseException as error:
  causes=[];current=error
  while current is not None:
   causes.append(type(current).__name__+': '+str(current));current=current.__cause__
  results.append({'operation':name,'error':type(error).__name__,'message':str(error),'causes':causes})
print(json.dumps(results),flush=True)
'''
        process = subprocess.Popen([sys.executable,'-I','-c',script,str(self.legacy_root),self.database.path],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            ready = json.loads(process.stdout.readline())
            self.assertEqual(ready['storage_sha256'],self.provenance['storage_sha256'])
            self.assertFalse(ready['fence_loaded'])
            WriterFence(self.database).enable('legacy-test')
            before = self.snapshot()
            output,error = process.communicate('run\n',timeout=15)
            self.assertEqual(process.returncode,0,error)
            results = json.loads(output)
            self.assertTrue(all(not item.get('wrote') for item in results),results)
            self.assertTrue(all(any('uta_writer_fence_v1' in cause for cause in item['causes']) for item in results),results)
            self.assertEqual(self.snapshot(),before)
        finally:
            if process.poll() is None:
                process.kill();process.wait()

    def test_old_binary_started_after_activation_cannot_initialize_a_writer(self):
        WriterFence(self.database).enable('legacy-cold')
        before = self.snapshot()
        script = r'''
import sys,json
sys.path.insert(0,sys.argv[1])
from uta.storage import Database
from uta.service import ExchangeService
try:
 ExchangeService(Database(sys.argv[2]),{'USD':8})
 print(json.dumps({'initialized':True}))
except BaseException as error:
 causes=[]
 while error is not None:
  causes.append(str(error));error=error.__cause__
 print(json.dumps({'causes':causes}))
'''
        result = subprocess.run([sys.executable,'-I','-c',script,str(self.legacy_root),self.database.path],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        evidence = json.loads(result.stdout)
        self.assertFalse(evidence.get('initialized'),evidence)
        self.assertTrue(any('uta_writer_fence_v1' in cause for cause in evidence['causes']),evidence)
        self.assertEqual(self.snapshot(),before)

    def test_current_writer_settles_real_match_and_new_tables_get_persistent_guards(self):
        fence = WriterFence(self.database)
        fence.enable('new-worker')
        token = fence.acquire('worker',10)
        bound = self.database.for_writer(token)
        current = ExchangeService(bound,{'USD':8})
        matcher = Matcher(current)
        self.assertEqual(matcher.match_once('BTC-PERP')['confirmed_trades'],1)
        self.assertEqual(matcher.verify(strict=True)['paired_fills'],2)
        self.assertGreater(current.ledger.verify(),0)
        with bound.transaction() as connection:
            connection.execute('CREATE TABLE new_financial_state(id INTEGER PRIMARY KEY,amount TEXT)')
            connection.execute("INSERT INTO new_financial_state VALUES(1,'2')")
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT actions FROM writer_fence_guard_tables WHERE name='new_financial_state'").fetchone()[0],'IUD')
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND tbl_name='new_financial_state'").fetchone()[0],3)
        script = r'''
import sys,json
sys.path.insert(0,sys.argv[1])
from uta.storage import Database
try:
 with Database(sys.argv[2]).transaction() as connection:
  connection.execute("INSERT INTO new_financial_state VALUES(2,'3')")
 print(json.dumps({'wrote':True}))
except BaseException as error:
 print(json.dumps({'error':str(error)}))
'''
        result = subprocess.run([sys.executable,'-I','-c',script,str(self.legacy_root),self.database.path],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('uta_writer_fence_v1',json.loads(result.stdout)['error'])
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM new_financial_state').fetchone()[0],1)

    def test_missing_guard_is_rejected_without_startup_or_upgrade_repair(self):
        fence = WriterFence(self.database)
        fence.enable('missing-guard')
        token = fence.acquire('worker',10)
        with sqlite3.connect(self.database.path) as raw:
            name = raw.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'writer_fence_data_%' LIMIT 1").fetchone()[0]
            raw.execute('DROP TRIGGER "'+name+'"')
        for operation in (fence.status,lambda:fence.enable('missing-guard'),fence.upgrade_guards,
                          lambda:ExchangeService(self.database.for_writer(token),{'USD':8})):
            with self.assertRaises(WriterFenceError) as caught:
                operation()
            self.assertEqual(caught.exception.code,'fence_guard_corrupt')
        with sqlite3.connect(self.database.path) as raw:
            self.assertIsNone(raw.execute('SELECT name FROM sqlite_master WHERE name=?',(name,)).fetchone())

    def test_all_guard_metadata_disappearing_cannot_be_misidentified_as_old_format(self):
        fence = WriterFence(self.database)
        fence.enable('missing-metadata')
        with sqlite3.connect(self.database.path) as raw:
            raw.execute('DROP TABLE writer_fence_guard_config')
            raw.execute('DROP TABLE writer_fence_guard_tables')
        for operation in (fence.status,fence.upgrade_guards):
            with self.assertRaises(WriterFenceError) as caught:
                operation()
            self.assertEqual(caught.exception.code,'fence_guard_corrupt')

    def test_trigger_checks_expiry_during_reused_sql_statement_and_rolls_back(self):
        now = [1_000_000_000]
        base = Database(self.database.path,fence_clock_ns=lambda:now[0],fence_boot_id='trigger-test-boot')
        fence = WriterFence(base)
        fence.enable('expiry-trigger')
        token = fence.acquire('worker',1)
        before = self.snapshot()
        with self.assertRaises(WriterFenceError) as caught:
            with base.for_writer(token).transaction() as connection:
                sql = "UPDATE uta_accounts SET version=version+1 WHERE account_id=?"
                connection.execute(sql,('alice',))
                now[0] = fence.database._fence_clock_ns() + 1_000_000_000
                connection.execute(sql,('bob',))
        self.assertEqual(caught.exception.code,'lease_expired')
        self.assertIsInstance(caught.exception.__cause__,sqlite3.IntegrityError)
        self.assertEqual(self.snapshot(),before)

    def test_python_only_managed_format_requires_explicit_offline_upgrade(self):
        now = 1_000_000_000
        base = Database(self.database.path,fence_clock_ns=lambda:now,fence_boot_id='old-managed-boot')
        # Exact first-version metadata columns; this fixture deliberately has
        # no SQL data guards, matching the first managed deployment format.
        with sqlite3.connect(self.database.path) as raw:
            raw.execute('CREATE TABLE writer_fence_authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1),authority_id TEXT NOT NULL,canonical_path TEXT NOT NULL)')
            raw.execute('CREATE TABLE writer_fence_lease (singleton INTEGER PRIMARY KEY CHECK(singleton=1),generation INTEGER NOT NULL CHECK(generation>=0),owner_nonce TEXT,owner_pid INTEGER,boot_id TEXT NOT NULL,expires_ns INTEGER NOT NULL,observed_ns INTEGER NOT NULL)')
            raw.execute('CREATE TABLE writer_fence_events (sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,authority_id TEXT NOT NULL,owner_nonce TEXT,generation INTEGER NOT NULL,owner_pid INTEGER,boot_id TEXT NOT NULL,observed_ns INTEGER NOT NULL,expires_ns INTEGER NOT NULL)')
            raw.execute('INSERT INTO writer_fence_authority VALUES(1,1,?,?)',('old-managed',base.path))
            raw.execute('INSERT INTO writer_fence_lease VALUES(1,0,NULL,NULL,?,?,?)',('old-managed-boot',now,now))
            raw.execute("INSERT INTO writer_fence_events VALUES(1,'enabled','old-managed',NULL,0,NULL,'old-managed-boot',?,?)",(now,now))
            # Literal schema emitted by c05e10f, independent of the current
            # runtime's schema constants. The first format already had these
            # six control protections even though it had no data SQL guards.
            for table in ('writer_fence_authority','writer_fence_events'):
                for action in ('UPDATE','DELETE'):
                    raw.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'fence authority and audit are immutable'); END")
            raw.execute("CREATE TRIGGER writer_fence_lease_no_delete BEFORE DELETE ON writer_fence_lease BEGIN SELECT RAISE(ABORT,'managed lease cannot be deleted'); END")
            raw.execute("CREATE TRIGGER writer_fence_lease_monotonic BEFORE UPDATE ON writer_fence_lease WHEN NEW.generation<OLD.generation BEGIN SELECT RAISE(ABORT,'fence generation cannot regress'); END")
        fence = WriterFence(base)
        self.assertEqual(fence.status()['guard_format'],0)
        for operation in (lambda:fence.enable('old-managed'),lambda:fence.acquire('worker',1)):
            with self.assertRaises(WriterFenceError) as caught:
                operation()
            self.assertEqual(caught.exception.code,'fence_upgrade_required')
        upgraded = fence.upgrade_guards()
        self.assertEqual((upgraded['guard_format'],upgraded['generation']),(1,1))
        token = fence.acquire('new-worker',1)
        self.assertEqual(token.generation,2)
        ExchangeService(base.for_writer(token),{'USD':8}).deposit('alice','upgraded','USD',D(1))
        self.assertEqual(self.exchange.account('alice')['balances']['USD'],'1001')
