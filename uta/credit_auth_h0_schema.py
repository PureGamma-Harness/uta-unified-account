"""Compiled fresh format2 authentication schema; import executes no SQL.

Only an explicit fresh AuthDB initializer may execute SCHEMA_SQL in one actual
transaction. This inventory grants no financial or source-delivery authority."""

SCHEMA_SQL = ('CREATE TABLE main.auth_config (\n'
 ' singleton INTEGER PRIMARY KEY CHECK(singleton=1),\n'
 " format INTEGER NOT NULL CHECK(typeof(format)='integer' AND format=2),\n"
 ' canonical_path TEXT NOT NULL, auth_authority_id TEXT NOT NULL,\n'
 ' tenant TEXT NOT NULL, audience TEXT NOT NULL, producer_binding TEXT NOT NULL,\n'
 " domain_id TEXT NOT NULL, domain_epoch INTEGER NOT NULL CHECK(typeof(domain_epoch)='integer' AND "
 'domain_epoch=1),\n'
 ' account_id TEXT NOT NULL,\n'
 " past_window INTEGER NOT NULL CHECK(typeof(past_window)='integer' AND past_window BETWEEN 1 AND 300000),\n"
 " future_skew INTEGER NOT NULL CHECK(typeof(future_skew)='integer' AND future_skew BETWEEN 0 AND 30000),\n"
 " max_nonces INTEGER NOT NULL CHECK(typeof(max_nonces)='integer' AND max_nonces BETWEEN 2 AND 1000000),\n"
 " query_nonce_reserve INTEGER NOT NULL CHECK(typeof(query_nonce_reserve)='integer' AND "
 'query_nonce_reserve>0 AND query_nonce_reserve<max_nonces),\n'
 " max_audit INTEGER NOT NULL CHECK(typeof(max_audit)='integer' AND max_audit BETWEEN 3 AND 1000000),\n"
 " query_audit_reserve INTEGER NOT NULL CHECK(typeof(query_audit_reserve)='integer' AND "
 'query_audit_reserve>0),\n'
 " control_audit_reserve INTEGER NOT NULL CHECK(typeof(control_audit_reserve)='integer' AND "
 'control_audit_reserve>0),\n'
 " max_acceptances INTEGER NOT NULL CHECK(typeof(max_acceptances)='integer' AND max_acceptances BETWEEN 1 "
 'AND 10000),\n'
 " max_grants INTEGER NOT NULL CHECK(typeof(max_grants)='integer' AND max_grants BETWEEN 1 AND 10000),\n"
 " highwater INTEGER NOT NULL CHECK(typeof(highwater)='integer' AND highwater BETWEEN 0 AND "
 '9223372036854775807),\n'
 " revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision BETWEEN 0 AND "
 '9223372036854775807),\n'
 " grant_revision INTEGER NOT NULL CHECK(typeof(grant_revision)='integer' AND grant_revision BETWEEN 0 AND "
 '9223372036854775807),\n'
 ' fingerprint TEXT NOT NULL,\n'
 ' CHECK(query_audit_reserve+control_audit_reserve<max_audit)\n'
 ')',
 'CREATE TABLE main.auth_keys (\n'
 ' key_id TEXT PRIMARY KEY NOT NULL, identity TEXT NOT NULL,\n'
 " role TEXT NOT NULL CHECK(role IN ('admin','reader','funding','risk','trader')),\n"
 ' account_id TEXT,\n'
 " not_before_ms INTEGER NOT NULL CHECK(typeof(not_before_ms)='integer' AND not_before_ms BETWEEN 0 AND "
 '9223372036854775806),\n'
 " expires_at_ms INTEGER NOT NULL CHECK(typeof(expires_at_ms)='integer' AND expires_at_ms>not_before_ms AND "
 'expires_at_ms<=9223372036854775807),\n'
 " revoked INTEGER NOT NULL CHECK(typeof(revoked)='integer' AND revoked IN (0,1)),\n"
 ' UNIQUE(key_id,identity),\n'
 " CHECK((role IN ('reader','funding','trader') AND account_id IS NOT NULL) OR (role IN ('admin','risk') AND "
 'account_id IS NULL))\n'
 ')',
 'CREATE TABLE main.auth_nonces (\n'
 ' key_id TEXT NOT NULL REFERENCES auth_keys(key_id), nonce_hash TEXT NOT NULL,\n'
 " expires_ms INTEGER NOT NULL CHECK(typeof(expires_ms)='integer' AND expires_ms BETWEEN 0 AND "
 '9223372036854775807),\n'
 ' PRIMARY KEY(key_id,nonce_hash)\n'
 ')',
 'CREATE INDEX main.auth_nonce_expiry ON auth_nonces(expires_ms)',
 'CREATE TABLE main.auth_audit (\n'
 " sequence INTEGER PRIMARY KEY CHECK(typeof(sequence)='integer' AND sequence>0),\n"
 ' event TEXT NOT NULL, outcome TEXT NOT NULL, request_kind TEXT NOT NULL,\n'
 ' key_id TEXT, key_identity TEXT, nonce_hash TEXT, request_hash TEXT,\n'
 " request_ms INTEGER CHECK(request_ms IS NULL OR (typeof(request_ms)='integer' AND request_ms BETWEEN 0 AND "
 '9223372036854775807)),\n'
 " server_ms INTEGER CHECK(server_ms IS NULL OR (typeof(server_ms)='integer' AND server_ms BETWEEN 0 AND "
 '9223372036854775807)),\n'
 " revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision BETWEEN 0 AND "
 '9223372036854775807),\n'
 " grant_revision INTEGER NOT NULL CHECK(typeof(grant_revision)='integer' AND grant_revision BETWEEN 0 AND "
 '9223372036854775807),\n'
 ' business_key TEXT, grant_id TEXT, original_acceptance_id TEXT,\n'
 ' FOREIGN KEY(key_id,key_identity) REFERENCES auth_keys(key_id,identity),\n'
 ' FOREIGN KEY(grant_id) REFERENCES auth_credit_grants(grant_id) DEFERRABLE INITIALLY DEFERRED,\n'
 ' FOREIGN KEY(original_acceptance_id) REFERENCES auth_credit_acceptances(acceptance_id) DEFERRABLE '
 'INITIALLY DEFERRED\n'
 ')',
 'CREATE TABLE main.auth_credit_grants (\n'
 ' grant_id TEXT PRIMARY KEY NOT NULL, key_id TEXT NOT NULL REFERENCES auth_keys(key_id),\n'
 " account_id TEXT NOT NULL, asset TEXT NOT NULL CHECK(asset='BTC'),\n"
 " operation TEXT NOT NULL CHECK(operation IN ('credit.borrow','credit.repay','credit.read')),\n"
 " grant_epoch INTEGER NOT NULL UNIQUE CHECK(typeof(grant_epoch)='integer' AND grant_epoch>0),\n"
 ' audit_sequence INTEGER NOT NULL UNIQUE REFERENCES auth_audit(sequence) DEFERRABLE INITIALLY DEFERRED,\n'
 ' payload TEXT NOT NULL,\n'
 ' UNIQUE(grant_id,key_id,account_id,asset,operation,grant_epoch),\n'
 ' UNIQUE(grant_id,key_id,account_id,grant_epoch)\n'
 ')',
 'CREATE TABLE main.auth_credit_grant_revocations (\n'
 ' grant_id TEXT PRIMARY KEY NOT NULL REFERENCES auth_credit_grants(grant_id),\n'
 " revocation_revision INTEGER NOT NULL UNIQUE CHECK(typeof(revocation_revision)='integer' AND "
 'revocation_revision>0),\n'
 ' audit_sequence INTEGER NOT NULL UNIQUE REFERENCES auth_audit(sequence) DEFERRABLE INITIALLY DEFERRED,\n'
 ' payload TEXT NOT NULL\n'
 ')',
 'CREATE TABLE main.auth_credit_acceptances (\n'
 ' acceptance_id TEXT PRIMARY KEY NOT NULL,\n'
 ' domain_id TEXT NOT NULL, tenant TEXT NOT NULL, account_id TEXT NOT NULL, command_id TEXT NOT NULL,\n'
 " kind TEXT NOT NULL CHECK(kind IN ('BORROW','REPAY')),\n"
 ' command_payload TEXT NOT NULL, payload_hash TEXT NOT NULL,\n'
 ' auth_audit_sequence INTEGER NOT NULL UNIQUE REFERENCES auth_audit(sequence),\n'
 ' key_id TEXT NOT NULL, key_identity TEXT NOT NULL, grant_id TEXT NOT NULL,\n'
 " grant_epoch INTEGER NOT NULL CHECK(typeof(grant_epoch)='integer' AND grant_epoch>0),\n"
 " profile_revision INTEGER NOT NULL CHECK(typeof(profile_revision)='integer' AND profile_revision>0),\n"
 " grant_revision INTEGER NOT NULL CHECK(typeof(grant_revision)='integer' AND grant_revision>=grant_epoch),\n"
 " domain_epoch INTEGER NOT NULL CHECK(typeof(domain_epoch)='integer' AND domain_epoch=1),\n"
 ' request_hash TEXT NOT NULL, body_hash TEXT NOT NULL, nonce_hash TEXT NOT NULL,\n'
 " request_ms INTEGER NOT NULL CHECK(typeof(request_ms)='integer' AND request_ms BETWEEN 0 AND "
 '9223372036854775807),\n'
 " auth_checked_server_ms INTEGER NOT NULL CHECK(typeof(auth_checked_server_ms)='integer' AND "
 'auth_checked_server_ms BETWEEN 0 AND 9223372036854775807),\n'
 ' payload TEXT NOT NULL,\n'
 ' UNIQUE(domain_id,tenant,account_id,command_id),\n'
 ' FOREIGN KEY(key_id,key_identity) REFERENCES auth_keys(key_id,identity),\n'
 ' FOREIGN KEY(grant_id,key_id,account_id,grant_epoch)\n'
 '   REFERENCES auth_credit_grants(grant_id,key_id,account_id,grant_epoch)\n'
 ')',
 "CREATE TRIGGER main.auth_audit_no_update BEFORE UPDATE ON auth_audit BEGIN SELECT RAISE(ABORT,'retained "
 "auth evidence is immutable'); END",
 "CREATE TRIGGER main.auth_audit_no_delete BEFORE DELETE ON auth_audit BEGIN SELECT RAISE(ABORT,'retained "
 "auth evidence is immutable'); END",
 'CREATE TRIGGER main.auth_credit_grants_no_update BEFORE UPDATE ON auth_credit_grants BEGIN SELECT '
 "RAISE(ABORT,'retained auth evidence is immutable'); END",
 'CREATE TRIGGER main.auth_credit_grants_no_delete BEFORE DELETE ON auth_credit_grants BEGIN SELECT '
 "RAISE(ABORT,'retained auth evidence is immutable'); END",
 'CREATE TRIGGER main.auth_credit_grant_revocations_no_update BEFORE UPDATE ON auth_credit_grant_revocations '
 "BEGIN SELECT RAISE(ABORT,'retained auth evidence is immutable'); END",
 'CREATE TRIGGER main.auth_credit_grant_revocations_no_delete BEFORE DELETE ON auth_credit_grant_revocations '
 "BEGIN SELECT RAISE(ABORT,'retained auth evidence is immutable'); END",
 'CREATE TRIGGER main.auth_credit_acceptances_no_update BEFORE UPDATE ON auth_credit_acceptances BEGIN '
 "SELECT RAISE(ABORT,'retained auth evidence is immutable'); END",
 'CREATE TRIGGER main.auth_credit_acceptances_no_delete BEFORE DELETE ON auth_credit_acceptances BEGIN '
 "SELECT RAISE(ABORT,'retained auth evidence is immutable'); END",
 'CREATE TRIGGER main.auth_config_no_replace BEFORE INSERT ON auth_config WHEN EXISTS (SELECT 1 FROM '
 "main.auth_config) BEGIN SELECT RAISE(ABORT,'auth identity cannot replace'); END",
 'CREATE TRIGGER main.auth_keys_no_replace BEFORE INSERT ON auth_keys WHEN EXISTS (SELECT 1 FROM '
 "main.auth_keys WHERE key_id=NEW.key_id) BEGIN SELECT RAISE(ABORT,'auth identity cannot replace'); END",
 'CREATE TRIGGER main.auth_nonces_no_replace BEFORE INSERT ON auth_nonces WHEN EXISTS (SELECT 1 FROM '
 "main.auth_nonces WHERE key_id=NEW.key_id AND nonce_hash=NEW.nonce_hash) BEGIN SELECT RAISE(ABORT,'auth "
 "identity cannot replace'); END",
 'CREATE TRIGGER main.auth_audit_no_replace BEFORE INSERT ON auth_audit WHEN EXISTS (SELECT 1 FROM '
 "main.auth_audit WHERE sequence=NEW.sequence) BEGIN SELECT RAISE(ABORT,'auth identity cannot replace'); END",
 'CREATE TRIGGER main.auth_credit_grants_no_replace BEFORE INSERT ON auth_credit_grants WHEN EXISTS (SELECT '
 '1 FROM main.auth_credit_grants WHERE grant_id=NEW.grant_id OR grant_epoch=NEW.grant_epoch OR '
 "audit_sequence=NEW.audit_sequence) BEGIN SELECT RAISE(ABORT,'auth identity cannot replace'); END",
 'CREATE TRIGGER main.auth_credit_grant_revocations_no_replace BEFORE INSERT ON '
 'auth_credit_grant_revocations WHEN EXISTS (SELECT 1 FROM main.auth_credit_grant_revocations WHERE '
 'grant_id=NEW.grant_id OR revocation_revision=NEW.revocation_revision OR audit_sequence=NEW.audit_sequence) '
 "BEGIN SELECT RAISE(ABORT,'auth identity cannot replace'); END",
 'CREATE TRIGGER main.auth_credit_acceptances_no_replace BEFORE INSERT ON auth_credit_acceptances WHEN '
 'EXISTS (SELECT 1 FROM main.auth_credit_acceptances WHERE acceptance_id=NEW.acceptance_id OR '
 'auth_audit_sequence=NEW.auth_audit_sequence OR (domain_id=NEW.domain_id AND tenant=NEW.tenant AND '
 "account_id=NEW.account_id AND command_id=NEW.command_id)) BEGIN SELECT RAISE(ABORT,'auth identity cannot "
 "replace'); END",
 'CREATE TRIGGER main.auth_config_monotonic BEFORE UPDATE ON auth_config WHEN NEW.singleton IS NOT '
 'OLD.singleton OR NEW.format IS NOT OLD.format OR NEW.canonical_path IS NOT OLD.canonical_path OR '
 'NEW.auth_authority_id IS NOT OLD.auth_authority_id OR NEW.tenant IS NOT OLD.tenant OR NEW.audience IS NOT '
 'OLD.audience OR NEW.producer_binding IS NOT OLD.producer_binding OR NEW.domain_id IS NOT OLD.domain_id OR '
 'NEW.domain_epoch IS NOT OLD.domain_epoch OR NEW.account_id IS NOT OLD.account_id OR NEW.past_window IS NOT '
 'OLD.past_window OR NEW.future_skew IS NOT OLD.future_skew OR NEW.max_nonces IS NOT OLD.max_nonces OR '
 'NEW.query_nonce_reserve IS NOT OLD.query_nonce_reserve OR NEW.max_audit IS NOT OLD.max_audit OR '
 'NEW.query_audit_reserve IS NOT OLD.query_audit_reserve OR NEW.control_audit_reserve IS NOT '
 'OLD.control_audit_reserve OR NEW.max_acceptances IS NOT OLD.max_acceptances OR NEW.max_grants IS NOT '
 'OLD.max_grants OR NEW.highwater<OLD.highwater OR NEW.revision<OLD.revision OR '
 "NEW.grant_revision<OLD.grant_revision BEGIN SELECT RAISE(ABORT,'auth identity and limits are immutable; "
 "revisions are monotonic'); END",
 "CREATE TRIGGER main.auth_config_no_delete BEFORE DELETE ON auth_config BEGIN SELECT RAISE(ABORT,'auth "
 "authority cannot disappear'); END",
 'CREATE TRIGGER main.auth_keys_immutable BEFORE UPDATE ON auth_keys WHEN NEW.key_id IS NOT OLD.key_id OR '
 'NEW.identity IS NOT OLD.identity OR NEW.role IS NOT OLD.role OR NEW.account_id IS NOT OLD.account_id OR '
 'NEW.not_before_ms IS NOT OLD.not_before_ms OR NEW.expires_at_ms IS NOT OLD.expires_at_ms OR '
 "NEW.revoked<OLD.revoked BEGIN SELECT RAISE(ABORT,'key identity cannot rebind or unrevoked'); END",
 "CREATE TRIGGER main.auth_keys_no_delete BEFORE DELETE ON auth_keys BEGIN SELECT RAISE(ABORT,'key identity "
 "history is retained'); END",
 "CREATE TRIGGER main.auth_nonces_immutable BEFORE UPDATE ON auth_nonces BEGIN SELECT RAISE(ABORT,'nonce is "
 "immutable'); END",
 'CREATE TRIGGER main.auth_nonces_window BEFORE DELETE ON auth_nonces WHEN OLD.expires_ms >= (SELECT '
 "highwater FROM main.auth_config WHERE singleton=1) BEGIN SELECT RAISE(ABORT,'nonce remains replayable'); "
 'END',
 'CREATE TRIGGER main.auth_credit_grants_no_active_duplicate BEFORE INSERT ON auth_credit_grants WHEN EXISTS '
 '(SELECT 1 FROM main.auth_credit_grants g WHERE g.key_id=NEW.key_id AND g.account_id=NEW.account_id AND '
 'g.asset=NEW.asset AND g.operation=NEW.operation AND NOT EXISTS (SELECT 1 FROM '
 "main.auth_credit_grant_revocations r WHERE r.grant_id=g.grant_id)) BEGIN SELECT RAISE(ABORT,'exact grant "
 "is already active'); END",
 'CREATE TRIGGER main.auth_credit_grant_revoke_order BEFORE INSERT ON auth_credit_grant_revocations WHEN NOT '
 'EXISTS (SELECT 1 FROM main.auth_credit_grants WHERE grant_id=NEW.grant_id AND '
 "grant_epoch<NEW.revocation_revision) BEGIN SELECT RAISE(ABORT,'revocation must follow the original "
 "grant'); END",
 'CREATE TRIGGER main.auth_credit_acceptances_authority BEFORE INSERT ON auth_credit_acceptances WHEN NOT '
 'EXISTS (SELECT 1 FROM main.auth_config WHERE singleton=1 AND domain_id=NEW.domain_id AND tenant=NEW.tenant '
 'AND account_id=NEW.account_id AND domain_epoch=NEW.domain_epoch AND revision=NEW.profile_revision AND '
 "grant_revision=NEW.grant_revision) BEGIN SELECT RAISE(ABORT,'first acceptance differs from actual "
 "authority'); END",
 'CREATE TRIGGER main.auth_credit_acceptances_audit BEFORE INSERT ON auth_credit_acceptances WHEN NOT EXISTS '
 "(SELECT 1 FROM main.auth_audit WHERE sequence=NEW.auth_audit_sequence AND event='nonce_consumed' AND "
 "outcome='FIRST_ACCEPTED' AND key_id=NEW.key_id AND key_identity=NEW.key_identity AND "
 'request_hash=NEW.request_hash AND nonce_hash=NEW.nonce_hash AND request_ms=NEW.request_ms AND '
 'server_ms=NEW.auth_checked_server_ms AND revision=NEW.profile_revision AND '
 "grant_revision=NEW.grant_revision AND grant_id=NEW.grant_id) BEGIN SELECT RAISE(ABORT,'first acceptance "
 "lacks actual nonce audit'); END",
 'CREATE TRIGGER main.auth_credit_acceptances_active_grant BEFORE INSERT ON auth_credit_acceptances WHEN NOT '
 'EXISTS (SELECT 1 FROM main.auth_credit_grants g JOIN main.auth_keys k ON k.key_id=g.key_id WHERE '
 'g.grant_id=NEW.grant_id AND g.grant_epoch=NEW.grant_epoch AND g.key_id=NEW.key_id AND '
 "g.account_id=NEW.account_id AND g.asset='BTC' AND g.operation=CASE NEW.kind WHEN 'BORROW' THEN "
 "'credit.borrow' ELSE 'credit.repay' END AND k.identity=NEW.key_identity AND k.role='funding' AND "
 'k.account_id=NEW.account_id AND k.revoked=0 AND NOT EXISTS (SELECT 1 FROM '
 "main.auth_credit_grant_revocations r WHERE r.grant_id=g.grant_id)) BEGIN SELECT RAISE(ABORT,'first "
 "acceptance has no active exact grant'); END")

OBJECTS = {'auth_config': ('table',
                 'auth_config',
                 'CREATE TABLE auth_config (\n'
                 ' singleton INTEGER PRIMARY KEY CHECK(singleton=1),\n'
                 " format INTEGER NOT NULL CHECK(typeof(format)='integer' AND format=2),\n"
                 ' canonical_path TEXT NOT NULL, auth_authority_id TEXT NOT NULL,\n'
                 ' tenant TEXT NOT NULL, audience TEXT NOT NULL, producer_binding TEXT NOT NULL,\n'
                 ' domain_id TEXT NOT NULL, domain_epoch INTEGER NOT NULL '
                 "CHECK(typeof(domain_epoch)='integer' AND domain_epoch=1),\n"
                 ' account_id TEXT NOT NULL,\n'
                 " past_window INTEGER NOT NULL CHECK(typeof(past_window)='integer' AND past_window BETWEEN "
                 '1 AND 300000),\n'
                 " future_skew INTEGER NOT NULL CHECK(typeof(future_skew)='integer' AND future_skew BETWEEN "
                 '0 AND 30000),\n'
                 " max_nonces INTEGER NOT NULL CHECK(typeof(max_nonces)='integer' AND max_nonces BETWEEN 2 "
                 'AND 1000000),\n'
                 " query_nonce_reserve INTEGER NOT NULL CHECK(typeof(query_nonce_reserve)='integer' AND "
                 'query_nonce_reserve>0 AND query_nonce_reserve<max_nonces),\n'
                 " max_audit INTEGER NOT NULL CHECK(typeof(max_audit)='integer' AND max_audit BETWEEN 3 AND "
                 '1000000),\n'
                 " query_audit_reserve INTEGER NOT NULL CHECK(typeof(query_audit_reserve)='integer' AND "
                 'query_audit_reserve>0),\n'
                 " control_audit_reserve INTEGER NOT NULL CHECK(typeof(control_audit_reserve)='integer' AND "
                 'control_audit_reserve>0),\n'
                 " max_acceptances INTEGER NOT NULL CHECK(typeof(max_acceptances)='integer' AND "
                 'max_acceptances BETWEEN 1 AND 10000),\n'
                 " max_grants INTEGER NOT NULL CHECK(typeof(max_grants)='integer' AND max_grants BETWEEN 1 "
                 'AND 10000),\n'
                 " highwater INTEGER NOT NULL CHECK(typeof(highwater)='integer' AND highwater BETWEEN 0 AND "
                 '9223372036854775807),\n'
                 " revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision BETWEEN 0 AND "
                 '9223372036854775807),\n'
                 " grant_revision INTEGER NOT NULL CHECK(typeof(grant_revision)='integer' AND grant_revision "
                 'BETWEEN 0 AND 9223372036854775807),\n'
                 ' fingerprint TEXT NOT NULL,\n'
                 ' CHECK(query_audit_reserve+control_audit_reserve<max_audit)\n'
                 ')'),
 'auth_keys': ('table',
               'auth_keys',
               'CREATE TABLE auth_keys (\n'
               ' key_id TEXT PRIMARY KEY NOT NULL, identity TEXT NOT NULL,\n'
               " role TEXT NOT NULL CHECK(role IN ('admin','reader','funding','risk','trader')),\n"
               ' account_id TEXT,\n'
               " not_before_ms INTEGER NOT NULL CHECK(typeof(not_before_ms)='integer' AND not_before_ms "
               'BETWEEN 0 AND 9223372036854775806),\n'
               " expires_at_ms INTEGER NOT NULL CHECK(typeof(expires_at_ms)='integer' AND "
               'expires_at_ms>not_before_ms AND expires_at_ms<=9223372036854775807),\n'
               " revoked INTEGER NOT NULL CHECK(typeof(revoked)='integer' AND revoked IN (0,1)),\n"
               ' UNIQUE(key_id,identity),\n'
               " CHECK((role IN ('reader','funding','trader') AND account_id IS NOT NULL) OR (role IN "
               "('admin','risk') AND account_id IS NULL))\n"
               ')'),
 'sqlite_autoindex_auth_keys_1': ('index', 'auth_keys', None),
 'sqlite_autoindex_auth_keys_2': ('index', 'auth_keys', None),
 'auth_nonces': ('table',
                 'auth_nonces',
                 'CREATE TABLE auth_nonces (\n'
                 ' key_id TEXT NOT NULL REFERENCES auth_keys(key_id), nonce_hash TEXT NOT NULL,\n'
                 " expires_ms INTEGER NOT NULL CHECK(typeof(expires_ms)='integer' AND expires_ms BETWEEN 0 "
                 'AND 9223372036854775807),\n'
                 ' PRIMARY KEY(key_id,nonce_hash)\n'
                 ')'),
 'sqlite_autoindex_auth_nonces_1': ('index', 'auth_nonces', None),
 'auth_nonce_expiry': ('index', 'auth_nonces', 'CREATE INDEX auth_nonce_expiry ON auth_nonces(expires_ms)'),
 'auth_audit': ('table',
                'auth_audit',
                'CREATE TABLE auth_audit (\n'
                " sequence INTEGER PRIMARY KEY CHECK(typeof(sequence)='integer' AND sequence>0),\n"
                ' event TEXT NOT NULL, outcome TEXT NOT NULL, request_kind TEXT NOT NULL,\n'
                ' key_id TEXT, key_identity TEXT, nonce_hash TEXT, request_hash TEXT,\n'
                " request_ms INTEGER CHECK(request_ms IS NULL OR (typeof(request_ms)='integer' AND "
                'request_ms BETWEEN 0 AND 9223372036854775807)),\n'
                " server_ms INTEGER CHECK(server_ms IS NULL OR (typeof(server_ms)='integer' AND server_ms "
                'BETWEEN 0 AND 9223372036854775807)),\n'
                " revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision BETWEEN 0 AND "
                '9223372036854775807),\n'
                " grant_revision INTEGER NOT NULL CHECK(typeof(grant_revision)='integer' AND grant_revision "
                'BETWEEN 0 AND 9223372036854775807),\n'
                ' business_key TEXT, grant_id TEXT, original_acceptance_id TEXT,\n'
                ' FOREIGN KEY(key_id,key_identity) REFERENCES auth_keys(key_id,identity),\n'
                ' FOREIGN KEY(grant_id) REFERENCES auth_credit_grants(grant_id) DEFERRABLE INITIALLY '
                'DEFERRED,\n'
                ' FOREIGN KEY(original_acceptance_id) REFERENCES auth_credit_acceptances(acceptance_id) '
                'DEFERRABLE INITIALLY DEFERRED\n'
                ')'),
 'auth_credit_grants': ('table',
                        'auth_credit_grants',
                        'CREATE TABLE auth_credit_grants (\n'
                        ' grant_id TEXT PRIMARY KEY NOT NULL, key_id TEXT NOT NULL REFERENCES '
                        'auth_keys(key_id),\n'
                        " account_id TEXT NOT NULL, asset TEXT NOT NULL CHECK(asset='BTC'),\n"
                        ' operation TEXT NOT NULL CHECK(operation IN '
                        "('credit.borrow','credit.repay','credit.read')),\n"
                        " grant_epoch INTEGER NOT NULL UNIQUE CHECK(typeof(grant_epoch)='integer' AND "
                        'grant_epoch>0),\n'
                        ' audit_sequence INTEGER NOT NULL UNIQUE REFERENCES auth_audit(sequence) DEFERRABLE '
                        'INITIALLY DEFERRED,\n'
                        ' payload TEXT NOT NULL,\n'
                        ' UNIQUE(grant_id,key_id,account_id,asset,operation,grant_epoch),\n'
                        ' UNIQUE(grant_id,key_id,account_id,grant_epoch)\n'
                        ')'),
 'sqlite_autoindex_auth_credit_grants_1': ('index', 'auth_credit_grants', None),
 'sqlite_autoindex_auth_credit_grants_2': ('index', 'auth_credit_grants', None),
 'sqlite_autoindex_auth_credit_grants_3': ('index', 'auth_credit_grants', None),
 'sqlite_autoindex_auth_credit_grants_4': ('index', 'auth_credit_grants', None),
 'sqlite_autoindex_auth_credit_grants_5': ('index', 'auth_credit_grants', None),
 'auth_credit_grant_revocations': ('table',
                                   'auth_credit_grant_revocations',
                                   'CREATE TABLE auth_credit_grant_revocations (\n'
                                   ' grant_id TEXT PRIMARY KEY NOT NULL REFERENCES '
                                   'auth_credit_grants(grant_id),\n'
                                   ' revocation_revision INTEGER NOT NULL UNIQUE '
                                   "CHECK(typeof(revocation_revision)='integer' AND revocation_revision>0),\n"
                                   ' audit_sequence INTEGER NOT NULL UNIQUE REFERENCES auth_audit(sequence) '
                                   'DEFERRABLE INITIALLY DEFERRED,\n'
                                   ' payload TEXT NOT NULL\n'
                                   ')'),
 'sqlite_autoindex_auth_credit_grant_revocations_1': ('index', 'auth_credit_grant_revocations', None),
 'sqlite_autoindex_auth_credit_grant_revocations_2': ('index', 'auth_credit_grant_revocations', None),
 'sqlite_autoindex_auth_credit_grant_revocations_3': ('index', 'auth_credit_grant_revocations', None),
 'auth_credit_acceptances': ('table',
                             'auth_credit_acceptances',
                             'CREATE TABLE auth_credit_acceptances (\n'
                             ' acceptance_id TEXT PRIMARY KEY NOT NULL,\n'
                             ' domain_id TEXT NOT NULL, tenant TEXT NOT NULL, account_id TEXT NOT NULL, '
                             'command_id TEXT NOT NULL,\n'
                             " kind TEXT NOT NULL CHECK(kind IN ('BORROW','REPAY')),\n"
                             ' command_payload TEXT NOT NULL, payload_hash TEXT NOT NULL,\n'
                             ' auth_audit_sequence INTEGER NOT NULL UNIQUE REFERENCES auth_audit(sequence),\n'
                             ' key_id TEXT NOT NULL, key_identity TEXT NOT NULL, grant_id TEXT NOT NULL,\n'
                             " grant_epoch INTEGER NOT NULL CHECK(typeof(grant_epoch)='integer' AND "
                             'grant_epoch>0),\n'
                             " profile_revision INTEGER NOT NULL CHECK(typeof(profile_revision)='integer' "
                             'AND profile_revision>0),\n'
                             " grant_revision INTEGER NOT NULL CHECK(typeof(grant_revision)='integer' AND "
                             'grant_revision>=grant_epoch),\n'
                             " domain_epoch INTEGER NOT NULL CHECK(typeof(domain_epoch)='integer' AND "
                             'domain_epoch=1),\n'
                             ' request_hash TEXT NOT NULL, body_hash TEXT NOT NULL, nonce_hash TEXT NOT '
                             'NULL,\n'
                             " request_ms INTEGER NOT NULL CHECK(typeof(request_ms)='integer' AND request_ms "
                             'BETWEEN 0 AND 9223372036854775807),\n'
                             ' auth_checked_server_ms INTEGER NOT NULL '
                             "CHECK(typeof(auth_checked_server_ms)='integer' AND auth_checked_server_ms "
                             'BETWEEN 0 AND 9223372036854775807),\n'
                             ' payload TEXT NOT NULL,\n'
                             ' UNIQUE(domain_id,tenant,account_id,command_id),\n'
                             ' FOREIGN KEY(key_id,key_identity) REFERENCES auth_keys(key_id,identity),\n'
                             ' FOREIGN KEY(grant_id,key_id,account_id,grant_epoch)\n'
                             '   REFERENCES auth_credit_grants(grant_id,key_id,account_id,grant_epoch)\n'
                             ')'),
 'sqlite_autoindex_auth_credit_acceptances_1': ('index', 'auth_credit_acceptances', None),
 'sqlite_autoindex_auth_credit_acceptances_2': ('index', 'auth_credit_acceptances', None),
 'sqlite_autoindex_auth_credit_acceptances_3': ('index', 'auth_credit_acceptances', None),
 'auth_audit_no_update': ('trigger',
                          'auth_audit',
                          'CREATE TRIGGER auth_audit_no_update BEFORE UPDATE ON auth_audit BEGIN SELECT '
                          "RAISE(ABORT,'retained auth evidence is immutable'); END"),
 'auth_audit_no_delete': ('trigger',
                          'auth_audit',
                          'CREATE TRIGGER auth_audit_no_delete BEFORE DELETE ON auth_audit BEGIN SELECT '
                          "RAISE(ABORT,'retained auth evidence is immutable'); END"),
 'auth_credit_grants_no_update': ('trigger',
                                  'auth_credit_grants',
                                  'CREATE TRIGGER auth_credit_grants_no_update BEFORE UPDATE ON '
                                  "auth_credit_grants BEGIN SELECT RAISE(ABORT,'retained auth evidence is "
                                  "immutable'); END"),
 'auth_credit_grants_no_delete': ('trigger',
                                  'auth_credit_grants',
                                  'CREATE TRIGGER auth_credit_grants_no_delete BEFORE DELETE ON '
                                  "auth_credit_grants BEGIN SELECT RAISE(ABORT,'retained auth evidence is "
                                  "immutable'); END"),
 'auth_credit_grant_revocations_no_update': ('trigger',
                                             'auth_credit_grant_revocations',
                                             'CREATE TRIGGER auth_credit_grant_revocations_no_update BEFORE '
                                             'UPDATE ON auth_credit_grant_revocations BEGIN SELECT '
                                             "RAISE(ABORT,'retained auth evidence is immutable'); END"),
 'auth_credit_grant_revocations_no_delete': ('trigger',
                                             'auth_credit_grant_revocations',
                                             'CREATE TRIGGER auth_credit_grant_revocations_no_delete BEFORE '
                                             'DELETE ON auth_credit_grant_revocations BEGIN SELECT '
                                             "RAISE(ABORT,'retained auth evidence is immutable'); END"),
 'auth_credit_acceptances_no_update': ('trigger',
                                       'auth_credit_acceptances',
                                       'CREATE TRIGGER auth_credit_acceptances_no_update BEFORE UPDATE ON '
                                       "auth_credit_acceptances BEGIN SELECT RAISE(ABORT,'retained auth "
                                       "evidence is immutable'); END"),
 'auth_credit_acceptances_no_delete': ('trigger',
                                       'auth_credit_acceptances',
                                       'CREATE TRIGGER auth_credit_acceptances_no_delete BEFORE DELETE ON '
                                       "auth_credit_acceptances BEGIN SELECT RAISE(ABORT,'retained auth "
                                       "evidence is immutable'); END"),
 'auth_config_no_replace': ('trigger',
                            'auth_config',
                            'CREATE TRIGGER auth_config_no_replace BEFORE INSERT ON auth_config WHEN EXISTS '
                            "(SELECT 1 FROM main.auth_config) BEGIN SELECT RAISE(ABORT,'auth identity cannot "
                            "replace'); END"),
 'auth_keys_no_replace': ('trigger',
                          'auth_keys',
                          'CREATE TRIGGER auth_keys_no_replace BEFORE INSERT ON auth_keys WHEN EXISTS '
                          '(SELECT 1 FROM main.auth_keys WHERE key_id=NEW.key_id) BEGIN SELECT '
                          "RAISE(ABORT,'auth identity cannot replace'); END"),
 'auth_nonces_no_replace': ('trigger',
                            'auth_nonces',
                            'CREATE TRIGGER auth_nonces_no_replace BEFORE INSERT ON auth_nonces WHEN EXISTS '
                            '(SELECT 1 FROM main.auth_nonces WHERE key_id=NEW.key_id AND '
                            "nonce_hash=NEW.nonce_hash) BEGIN SELECT RAISE(ABORT,'auth identity cannot "
                            "replace'); END"),
 'auth_audit_no_replace': ('trigger',
                           'auth_audit',
                           'CREATE TRIGGER auth_audit_no_replace BEFORE INSERT ON auth_audit WHEN EXISTS '
                           '(SELECT 1 FROM main.auth_audit WHERE sequence=NEW.sequence) BEGIN SELECT '
                           "RAISE(ABORT,'auth identity cannot replace'); END"),
 'auth_credit_grants_no_replace': ('trigger',
                                   'auth_credit_grants',
                                   'CREATE TRIGGER auth_credit_grants_no_replace BEFORE INSERT ON '
                                   'auth_credit_grants WHEN EXISTS (SELECT 1 FROM main.auth_credit_grants '
                                   'WHERE grant_id=NEW.grant_id OR grant_epoch=NEW.grant_epoch OR '
                                   "audit_sequence=NEW.audit_sequence) BEGIN SELECT RAISE(ABORT,'auth "
                                   "identity cannot replace'); END"),
 'auth_credit_grant_revocations_no_replace': ('trigger',
                                              'auth_credit_grant_revocations',
                                              'CREATE TRIGGER auth_credit_grant_revocations_no_replace '
                                              'BEFORE INSERT ON auth_credit_grant_revocations WHEN EXISTS '
                                              '(SELECT 1 FROM main.auth_credit_grant_revocations WHERE '
                                              'grant_id=NEW.grant_id OR '
                                              'revocation_revision=NEW.revocation_revision OR '
                                              'audit_sequence=NEW.audit_sequence) BEGIN SELECT '
                                              "RAISE(ABORT,'auth identity cannot replace'); END"),
 'auth_credit_acceptances_no_replace': ('trigger',
                                        'auth_credit_acceptances',
                                        'CREATE TRIGGER auth_credit_acceptances_no_replace BEFORE INSERT ON '
                                        'auth_credit_acceptances WHEN EXISTS (SELECT 1 FROM '
                                        'main.auth_credit_acceptances WHERE acceptance_id=NEW.acceptance_id '
                                        'OR auth_audit_sequence=NEW.auth_audit_sequence OR '
                                        '(domain_id=NEW.domain_id AND tenant=NEW.tenant AND '
                                        'account_id=NEW.account_id AND command_id=NEW.command_id)) BEGIN '
                                        "SELECT RAISE(ABORT,'auth identity cannot replace'); END"),
 'auth_config_monotonic': ('trigger',
                           'auth_config',
                           'CREATE TRIGGER auth_config_monotonic BEFORE UPDATE ON auth_config WHEN '
                           'NEW.singleton IS NOT OLD.singleton OR NEW.format IS NOT OLD.format OR '
                           'NEW.canonical_path IS NOT OLD.canonical_path OR NEW.auth_authority_id IS NOT '
                           'OLD.auth_authority_id OR NEW.tenant IS NOT OLD.tenant OR NEW.audience IS NOT '
                           'OLD.audience OR NEW.producer_binding IS NOT OLD.producer_binding OR '
                           'NEW.domain_id IS NOT OLD.domain_id OR NEW.domain_epoch IS NOT OLD.domain_epoch '
                           'OR NEW.account_id IS NOT OLD.account_id OR NEW.past_window IS NOT '
                           'OLD.past_window OR NEW.future_skew IS NOT OLD.future_skew OR NEW.max_nonces IS '
                           'NOT OLD.max_nonces OR NEW.query_nonce_reserve IS NOT OLD.query_nonce_reserve OR '
                           'NEW.max_audit IS NOT OLD.max_audit OR NEW.query_audit_reserve IS NOT '
                           'OLD.query_audit_reserve OR NEW.control_audit_reserve IS NOT '
                           'OLD.control_audit_reserve OR NEW.max_acceptances IS NOT OLD.max_acceptances OR '
                           'NEW.max_grants IS NOT OLD.max_grants OR NEW.highwater<OLD.highwater OR '
                           'NEW.revision<OLD.revision OR NEW.grant_revision<OLD.grant_revision BEGIN SELECT '
                           "RAISE(ABORT,'auth identity and limits are immutable; revisions are monotonic'); "
                           'END'),
 'auth_config_no_delete': ('trigger',
                           'auth_config',
                           'CREATE TRIGGER auth_config_no_delete BEFORE DELETE ON auth_config BEGIN SELECT '
                           "RAISE(ABORT,'auth authority cannot disappear'); END"),
 'auth_keys_immutable': ('trigger',
                         'auth_keys',
                         'CREATE TRIGGER auth_keys_immutable BEFORE UPDATE ON auth_keys WHEN NEW.key_id IS '
                         'NOT OLD.key_id OR NEW.identity IS NOT OLD.identity OR NEW.role IS NOT OLD.role OR '
                         'NEW.account_id IS NOT OLD.account_id OR NEW.not_before_ms IS NOT OLD.not_before_ms '
                         'OR NEW.expires_at_ms IS NOT OLD.expires_at_ms OR NEW.revoked<OLD.revoked BEGIN '
                         "SELECT RAISE(ABORT,'key identity cannot rebind or unrevoked'); END"),
 'auth_keys_no_delete': ('trigger',
                         'auth_keys',
                         'CREATE TRIGGER auth_keys_no_delete BEFORE DELETE ON auth_keys BEGIN SELECT '
                         "RAISE(ABORT,'key identity history is retained'); END"),
 'auth_nonces_immutable': ('trigger',
                           'auth_nonces',
                           'CREATE TRIGGER auth_nonces_immutable BEFORE UPDATE ON auth_nonces BEGIN SELECT '
                           "RAISE(ABORT,'nonce is immutable'); END"),
 'auth_nonces_window': ('trigger',
                        'auth_nonces',
                        'CREATE TRIGGER auth_nonces_window BEFORE DELETE ON auth_nonces WHEN OLD.expires_ms '
                        '>= (SELECT highwater FROM main.auth_config WHERE singleton=1) BEGIN SELECT '
                        "RAISE(ABORT,'nonce remains replayable'); END"),
 'auth_credit_grants_no_active_duplicate': ('trigger',
                                            'auth_credit_grants',
                                            'CREATE TRIGGER auth_credit_grants_no_active_duplicate BEFORE '
                                            'INSERT ON auth_credit_grants WHEN EXISTS (SELECT 1 FROM '
                                            'main.auth_credit_grants g WHERE g.key_id=NEW.key_id AND '
                                            'g.account_id=NEW.account_id AND g.asset=NEW.asset AND '
                                            'g.operation=NEW.operation AND NOT EXISTS (SELECT 1 FROM '
                                            'main.auth_credit_grant_revocations r WHERE '
                                            "r.grant_id=g.grant_id)) BEGIN SELECT RAISE(ABORT,'exact grant "
                                            "is already active'); END"),
 'auth_credit_grant_revoke_order': ('trigger',
                                    'auth_credit_grant_revocations',
                                    'CREATE TRIGGER auth_credit_grant_revoke_order BEFORE INSERT ON '
                                    'auth_credit_grant_revocations WHEN NOT EXISTS (SELECT 1 FROM '
                                    'main.auth_credit_grants WHERE grant_id=NEW.grant_id AND '
                                    'grant_epoch<NEW.revocation_revision) BEGIN SELECT '
                                    "RAISE(ABORT,'revocation must follow the original grant'); END"),
 'auth_credit_acceptances_authority': ('trigger',
                                       'auth_credit_acceptances',
                                       'CREATE TRIGGER auth_credit_acceptances_authority BEFORE INSERT ON '
                                       'auth_credit_acceptances WHEN NOT EXISTS (SELECT 1 FROM '
                                       'main.auth_config WHERE singleton=1 AND domain_id=NEW.domain_id AND '
                                       'tenant=NEW.tenant AND account_id=NEW.account_id AND '
                                       'domain_epoch=NEW.domain_epoch AND revision=NEW.profile_revision AND '
                                       "grant_revision=NEW.grant_revision) BEGIN SELECT RAISE(ABORT,'first "
                                       "acceptance differs from actual authority'); END"),
 'auth_credit_acceptances_audit': ('trigger',
                                   'auth_credit_acceptances',
                                   'CREATE TRIGGER auth_credit_acceptances_audit BEFORE INSERT ON '
                                   'auth_credit_acceptances WHEN NOT EXISTS (SELECT 1 FROM main.auth_audit '
                                   "WHERE sequence=NEW.auth_audit_sequence AND event='nonce_consumed' AND "
                                   "outcome='FIRST_ACCEPTED' AND key_id=NEW.key_id AND "
                                   'key_identity=NEW.key_identity AND request_hash=NEW.request_hash AND '
                                   'nonce_hash=NEW.nonce_hash AND request_ms=NEW.request_ms AND '
                                   'server_ms=NEW.auth_checked_server_ms AND revision=NEW.profile_revision '
                                   'AND grant_revision=NEW.grant_revision AND grant_id=NEW.grant_id) BEGIN '
                                   "SELECT RAISE(ABORT,'first acceptance lacks actual nonce audit'); END"),
 'auth_credit_acceptances_active_grant': ('trigger',
                                          'auth_credit_acceptances',
                                          'CREATE TRIGGER auth_credit_acceptances_active_grant BEFORE INSERT '
                                          'ON auth_credit_acceptances WHEN NOT EXISTS (SELECT 1 FROM '
                                          'main.auth_credit_grants g JOIN main.auth_keys k ON '
                                          'k.key_id=g.key_id WHERE g.grant_id=NEW.grant_id AND '
                                          'g.grant_epoch=NEW.grant_epoch AND g.key_id=NEW.key_id AND '
                                          "g.account_id=NEW.account_id AND g.asset='BTC' AND "
                                          "g.operation=CASE NEW.kind WHEN 'BORROW' THEN 'credit.borrow' ELSE "
                                          "'credit.repay' END AND k.identity=NEW.key_identity AND "
                                          "k.role='funding' AND k.account_id=NEW.account_id AND k.revoked=0 "
                                          'AND NOT EXISTS (SELECT 1 FROM main.auth_credit_grant_revocations '
                                          "r WHERE r.grant_id=g.grant_id)) BEGIN SELECT RAISE(ABORT,'first "
                                          "acceptance has no active exact grant'); END")}

COLUMNS = {'auth_config': ((0, 'singleton', 'INTEGER', 0, None, 1, 0),
                 (1, 'format', 'INTEGER', 1, None, 0, 0),
                 (2, 'canonical_path', 'TEXT', 1, None, 0, 0),
                 (3, 'auth_authority_id', 'TEXT', 1, None, 0, 0),
                 (4, 'tenant', 'TEXT', 1, None, 0, 0),
                 (5, 'audience', 'TEXT', 1, None, 0, 0),
                 (6, 'producer_binding', 'TEXT', 1, None, 0, 0),
                 (7, 'domain_id', 'TEXT', 1, None, 0, 0),
                 (8, 'domain_epoch', 'INTEGER', 1, None, 0, 0),
                 (9, 'account_id', 'TEXT', 1, None, 0, 0),
                 (10, 'past_window', 'INTEGER', 1, None, 0, 0),
                 (11, 'future_skew', 'INTEGER', 1, None, 0, 0),
                 (12, 'max_nonces', 'INTEGER', 1, None, 0, 0),
                 (13, 'query_nonce_reserve', 'INTEGER', 1, None, 0, 0),
                 (14, 'max_audit', 'INTEGER', 1, None, 0, 0),
                 (15, 'query_audit_reserve', 'INTEGER', 1, None, 0, 0),
                 (16, 'control_audit_reserve', 'INTEGER', 1, None, 0, 0),
                 (17, 'max_acceptances', 'INTEGER', 1, None, 0, 0),
                 (18, 'max_grants', 'INTEGER', 1, None, 0, 0),
                 (19, 'highwater', 'INTEGER', 1, None, 0, 0),
                 (20, 'revision', 'INTEGER', 1, None, 0, 0),
                 (21, 'grant_revision', 'INTEGER', 1, None, 0, 0),
                 (22, 'fingerprint', 'TEXT', 1, None, 0, 0)),
 'auth_keys': ((0, 'key_id', 'TEXT', 1, None, 1, 0),
               (1, 'identity', 'TEXT', 1, None, 0, 0),
               (2, 'role', 'TEXT', 1, None, 0, 0),
               (3, 'account_id', 'TEXT', 0, None, 0, 0),
               (4, 'not_before_ms', 'INTEGER', 1, None, 0, 0),
               (5, 'expires_at_ms', 'INTEGER', 1, None, 0, 0),
               (6, 'revoked', 'INTEGER', 1, None, 0, 0)),
 'auth_nonces': ((0, 'key_id', 'TEXT', 1, None, 1, 0),
                 (1, 'nonce_hash', 'TEXT', 1, None, 2, 0),
                 (2, 'expires_ms', 'INTEGER', 1, None, 0, 0)),
 'auth_audit': ((0, 'sequence', 'INTEGER', 0, None, 1, 0),
                (1, 'event', 'TEXT', 1, None, 0, 0),
                (2, 'outcome', 'TEXT', 1, None, 0, 0),
                (3, 'request_kind', 'TEXT', 1, None, 0, 0),
                (4, 'key_id', 'TEXT', 0, None, 0, 0),
                (5, 'key_identity', 'TEXT', 0, None, 0, 0),
                (6, 'nonce_hash', 'TEXT', 0, None, 0, 0),
                (7, 'request_hash', 'TEXT', 0, None, 0, 0),
                (8, 'request_ms', 'INTEGER', 0, None, 0, 0),
                (9, 'server_ms', 'INTEGER', 0, None, 0, 0),
                (10, 'revision', 'INTEGER', 1, None, 0, 0),
                (11, 'grant_revision', 'INTEGER', 1, None, 0, 0),
                (12, 'business_key', 'TEXT', 0, None, 0, 0),
                (13, 'grant_id', 'TEXT', 0, None, 0, 0),
                (14, 'original_acceptance_id', 'TEXT', 0, None, 0, 0)),
 'auth_credit_grants': ((0, 'grant_id', 'TEXT', 1, None, 1, 0),
                        (1, 'key_id', 'TEXT', 1, None, 0, 0),
                        (2, 'account_id', 'TEXT', 1, None, 0, 0),
                        (3, 'asset', 'TEXT', 1, None, 0, 0),
                        (4, 'operation', 'TEXT', 1, None, 0, 0),
                        (5, 'grant_epoch', 'INTEGER', 1, None, 0, 0),
                        (6, 'audit_sequence', 'INTEGER', 1, None, 0, 0),
                        (7, 'payload', 'TEXT', 1, None, 0, 0)),
 'auth_credit_grant_revocations': ((0, 'grant_id', 'TEXT', 1, None, 1, 0),
                                   (1, 'revocation_revision', 'INTEGER', 1, None, 0, 0),
                                   (2, 'audit_sequence', 'INTEGER', 1, None, 0, 0),
                                   (3, 'payload', 'TEXT', 1, None, 0, 0)),
 'auth_credit_acceptances': ((0, 'acceptance_id', 'TEXT', 1, None, 1, 0),
                             (1, 'domain_id', 'TEXT', 1, None, 0, 0),
                             (2, 'tenant', 'TEXT', 1, None, 0, 0),
                             (3, 'account_id', 'TEXT', 1, None, 0, 0),
                             (4, 'command_id', 'TEXT', 1, None, 0, 0),
                             (5, 'kind', 'TEXT', 1, None, 0, 0),
                             (6, 'command_payload', 'TEXT', 1, None, 0, 0),
                             (7, 'payload_hash', 'TEXT', 1, None, 0, 0),
                             (8, 'auth_audit_sequence', 'INTEGER', 1, None, 0, 0),
                             (9, 'key_id', 'TEXT', 1, None, 0, 0),
                             (10, 'key_identity', 'TEXT', 1, None, 0, 0),
                             (11, 'grant_id', 'TEXT', 1, None, 0, 0),
                             (12, 'grant_epoch', 'INTEGER', 1, None, 0, 0),
                             (13, 'profile_revision', 'INTEGER', 1, None, 0, 0),
                             (14, 'grant_revision', 'INTEGER', 1, None, 0, 0),
                             (15, 'domain_epoch', 'INTEGER', 1, None, 0, 0),
                             (16, 'request_hash', 'TEXT', 1, None, 0, 0),
                             (17, 'body_hash', 'TEXT', 1, None, 0, 0),
                             (18, 'nonce_hash', 'TEXT', 1, None, 0, 0),
                             (19, 'request_ms', 'INTEGER', 1, None, 0, 0),
                             (20, 'auth_checked_server_ms', 'INTEGER', 1, None, 0, 0),
                             (21, 'payload', 'TEXT', 1, None, 0, 0))}

INDEXES = {'sqlite_autoindex_auth_keys_1': ('auth_keys', ('key_id',), 1, 'pk'),
 'sqlite_autoindex_auth_keys_2': ('auth_keys', ('key_id', 'identity'), 1, 'u'),
 'sqlite_autoindex_auth_nonces_1': ('auth_nonces', ('key_id', 'nonce_hash'), 1, 'pk'),
 'auth_nonce_expiry': ('auth_nonces', ('expires_ms',), 0, 'c'),
 'sqlite_autoindex_auth_credit_grants_1': ('auth_credit_grants', ('grant_id',), 1, 'pk'),
 'sqlite_autoindex_auth_credit_grants_2': ('auth_credit_grants', ('grant_epoch',), 1, 'u'),
 'sqlite_autoindex_auth_credit_grants_3': ('auth_credit_grants', ('audit_sequence',), 1, 'u'),
 'sqlite_autoindex_auth_credit_grants_4': ('auth_credit_grants',
                                           ('grant_id',
                                            'key_id',
                                            'account_id',
                                            'asset',
                                            'operation',
                                            'grant_epoch'),
                                           1,
                                           'u'),
 'sqlite_autoindex_auth_credit_grants_5': ('auth_credit_grants',
                                           ('grant_id', 'key_id', 'account_id', 'grant_epoch'),
                                           1,
                                           'u'),
 'sqlite_autoindex_auth_credit_grant_revocations_1': ('auth_credit_grant_revocations',
                                                      ('grant_id',),
                                                      1,
                                                      'pk'),
 'sqlite_autoindex_auth_credit_grant_revocations_2': ('auth_credit_grant_revocations',
                                                      ('revocation_revision',),
                                                      1,
                                                      'u'),
 'sqlite_autoindex_auth_credit_grant_revocations_3': ('auth_credit_grant_revocations',
                                                      ('audit_sequence',),
                                                      1,
                                                      'u'),
 'sqlite_autoindex_auth_credit_acceptances_1': ('auth_credit_acceptances', ('acceptance_id',), 1, 'pk'),
 'sqlite_autoindex_auth_credit_acceptances_2': ('auth_credit_acceptances', ('auth_audit_sequence',), 1, 'u'),
 'sqlite_autoindex_auth_credit_acceptances_3': ('auth_credit_acceptances',
                                                ('domain_id', 'tenant', 'account_id', 'command_id'),
                                                1,
                                                'u')}

FOREIGN_KEYS = {'auth_config': (),
 'auth_keys': (),
 'auth_nonces': (('auth_keys', 'key_id', 'key_id', 0, 'NO ACTION', 'NO ACTION', 'NONE'),),
 'auth_audit': (('auth_credit_acceptances',
                 'original_acceptance_id',
                 'acceptance_id',
                 0,
                 'NO ACTION',
                 'NO ACTION',
                 'NONE'),
                ('auth_credit_grants', 'grant_id', 'grant_id', 0, 'NO ACTION', 'NO ACTION', 'NONE'),
                ('auth_keys', 'key_id', 'key_id', 0, 'NO ACTION', 'NO ACTION', 'NONE'),
                ('auth_keys', 'key_identity', 'identity', 1, 'NO ACTION', 'NO ACTION', 'NONE')),
 'auth_credit_grants': (('auth_audit', 'audit_sequence', 'sequence', 0, 'NO ACTION', 'NO ACTION', 'NONE'),
                        ('auth_keys', 'key_id', 'key_id', 0, 'NO ACTION', 'NO ACTION', 'NONE')),
 'auth_credit_grant_revocations': (('auth_audit',
                                    'audit_sequence',
                                    'sequence',
                                    0,
                                    'NO ACTION',
                                    'NO ACTION',
                                    'NONE'),
                                   ('auth_credit_grants',
                                    'grant_id',
                                    'grant_id',
                                    0,
                                    'NO ACTION',
                                    'NO ACTION',
                                    'NONE')),
 'auth_credit_acceptances': (('auth_audit',
                              'auth_audit_sequence',
                              'sequence',
                              0,
                              'NO ACTION',
                              'NO ACTION',
                              'NONE'),
                             ('auth_credit_grants',
                              'account_id',
                              'account_id',
                              2,
                              'NO ACTION',
                              'NO ACTION',
                              'NONE'),
                             ('auth_credit_grants',
                              'grant_epoch',
                              'grant_epoch',
                              3,
                              'NO ACTION',
                              'NO ACTION',
                              'NONE'),
                             ('auth_credit_grants',
                              'grant_id',
                              'grant_id',
                              0,
                              'NO ACTION',
                              'NO ACTION',
                              'NONE'),
                             ('auth_credit_grants', 'key_id', 'key_id', 1, 'NO ACTION', 'NO ACTION', 'NONE'),
                             ('auth_keys', 'key_id', 'key_id', 0, 'NO ACTION', 'NO ACTION', 'NONE'),
                             ('auth_keys', 'key_identity', 'identity', 1, 'NO ACTION', 'NO ACTION', 'NONE'))}
