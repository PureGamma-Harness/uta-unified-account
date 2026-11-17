"""The actual loaded capture/recovery modules participate in credit identity."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from uta import credit_audit_v2, credit_audit_v2_replay, credit_fifo_v2, existing_services
from uta.credit_artifact import _loaded_modules, credit_artifact_id, credit_code_artifact


class CreditV2CodeBindingTests(unittest.TestCase):
    def test_complete_artifact_covers_capture_replay_fifo_and_real_constructor(self):
        manifest = credit_code_artifact()
        for role in ("uta.credit_audit_v2.CreditAuditV2.complete_borrow",
                     "uta.credit_audit_v2_replay.replay_bundle",
                     "uta.credit_fifo_v2.InternalCreditFIFO.process_one",
                     "uta.existing_services.open_existing_services"):
            self.assertIn(role, manifest["loaded_credit_engine"])
        for name in ("credit_native_v2", "credit_audit_v2", "credit_audit_v2_replay",
                     "credit_fifo_v2", "credit_transition", "credit_v2_payload_contract", "existing_services"):
            self.assertIn(name+".py", manifest["source_files"])

    def test_loaded_capture_replay_or_constructor_patch_changes_actual_engine(self):
        modules = ("credit_audit_v2", "credit_audit_v2_replay", "credit_fifo_v2", "existing_services")
        before = _loaded_modules(modules)
        def replacement(*args, **kwargs):
            return "synthetic patch"
        for owner, attribute in ((credit_audit_v2.CreditAuditV2, "complete_borrow"),
                                 (credit_audit_v2_replay, "replay_bundle"),
                                 (credit_fifo_v2.InternalCreditFIFO, "process_one"),
                                 (existing_services, "open_existing_services")):
            with self.subTest(role=attribute), patch.object(owner, attribute, replacement):
                self.assertNotEqual(_loaded_modules(modules), before)

    def test_queue_native_sql_contract_is_part_of_loaded_identity(self):
        before = _loaded_modules(("credit_fifo_v2",))
        changed = deepcopy(credit_fifo_v2._TABLE_SQL)
        changed["uta_command_config"] += " synthetic alteration"
        with patch.object(credit_fifo_v2, "_TABLE_SQL", changed):
            self.assertNotEqual(_loaded_modules(("credit_fifo_v2",)), before)


if __name__ == "__main__":
    unittest.main()
