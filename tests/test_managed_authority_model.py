"""Independent bounded safety, executable counterexamples and non-vacuity.

These checks test the finite specifications, not production-code equivalence.
No UTA runtime is imported to construct or validate the model's expected state.
"""
import ast
from dataclasses import asdict
import json
from pathlib import Path
import unittest

from formal import explore_managed_authority as model


EXPECTED_VIOLATIONS = {
    'steal_live_lease': 'overlapping_live_writer_lease_grants_shard0',
    'check_current_lease_without_token_identity': 'stale_generation_or_PID_birth_committed_financial_risk',
    'skip_commit_expiry': 'expired_owner_committed_financial_risk',
    'kill_reused_pid_without_birth': 'orphan_recovery_killed_a_reused_unrelated_PID_birth',
    'kill_orphan_before_lease_expiry': 'orphan_recovery_killed_owner_before_lease_expiry',
    'activate_partial_fanout': 'ACTIVE_with_incomplete_or_unacknowledged_market_fanout',
    'risk_commit_using_only_local_market': 'financial_risk_committed_without_complete_current_global_barrier',
    'release_shared_before_commit': 'prepared_risk_command_released_SHARED_before_commit',
    'terminal_success_before_commit': 'accepted_outcome_was_visible_before_financial_terminal_commit',
    'financial_without_terminal': 'financial_reservation_has_no_same_commit_success_terminal',
    'repeat_original_command': 'original_command_ID_created_financial_effect_twice',
    'repeat_confirmed_fill_after_restart': 'original_confirmed_fill_ID_settled_twice',
    'count_unmatched_liquidation_as_filled': 'unconfirmed_liquidation_changed_position_or_reversed_direction',
    'reverse_liquidation_direction': 'liquidation_reversed_or_expanded_the_initial_position',
    'overfill_order_quantity': 'confirmed_liquidation_overfilled_its_order_quantity',
    'skip_reduce_only_reservation': 'aggregate_reduce_only_reservation_exceeded_remaining_position',
}


class ManagedAuthorityModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.safe = {name: model.run_model(name) for name in ('authority', 'commands')}
        cls.negative = {}
        for name, mutations in (('authority', model.AUTHORITY_MUTANTS), ('commands', model.COMMAND_MUTANTS)):
            cls.negative.update({(name, variant): model.run_model(name, mutant=variant) for variant in mutations})

    def step(self, state, action, transitions, violation):
        found = [after for label, after in transitions(state) if label == action]
        self.assertEqual(len(found), 1, 'missing or ambiguous protocol step ' + action)
        self.assertIsNone(violation(found[0]), action)
        return found[0]

    def test_both_safe_graphs_exhaust_their_entire_declared_state_spaces(self):
        for name, counts in (('authority', (32816, 161256)), ('commands', (1524, 5534))):
            with self.subTest(model=name):
                result = self.safe[name]
                self.assertTrue(result['complete'])
                self.assertIsNone(result['violation'])
                self.assertEqual(result['counterexample'], [])
                self.assertEqual((result['states'], result['transitions']), counts)

    def test_required_recovery_partial_publication_and_lost_reply_states_are_reachable(self):
        authority = self.safe['authority']['coverage']
        commands = self.safe['commands']['coverage']
        for name in ('stopped_orphan_holds_shared_gate', 'partial_fanout_remains_closed',
                     'generation2_risk_commit', 'reused_pid_still_alive', 'valid_orphan_recovery',
                     'new_coordinator_activated_market1'):
            with self.subTest(coverage=name):
                self.assertGreater(authority[name], 0)
        for name in ('durably_queued_without_acceptance', 'committed_command_response_lost',
                     'committed_fill_response_lost', 'partial_liquidation_without_depth',
                     'restart_with_confirmed_partial_fill', 'confirmed_flat_terminal', 'persisted_business_rejection'):
            with self.subTest(coverage=name):
                self.assertGreater(commands[name], 0)

    def test_all_sixteen_negative_variants_have_specific_real_counterexamples(self):
        self.assertEqual(len(self.negative), 16)
        self.assertEqual({variant for _, variant in self.negative}, set(EXPECTED_VIOLATIONS))
        for (_, variant), result in self.negative.items():
            with self.subTest(mutation=variant):
                self.assertFalse(result['complete'])  # Stops at the first bad state.
                self.assertEqual(result['violation'], EXPECTED_VIOLATIONS[variant])
                self.assertTrue(result['counterexample'])

    def test_each_counterexample_replays_actual_edges_and_first_bad_state(self):
        for (name, variant), result in self.negative.items():
            transitions = model.authority_next if name == 'authority' else model.command_next
            violation = model.authority_violation if name == 'authority' else model.command_violation
            state = model.Authority() if name == 'authority' else model.Commands()
            diverged = False
            serialized_trace = json.loads(json.dumps(result['counterexample']))
            for index, recorded in enumerate(serialized_trace):
                with self.subTest(mutation=variant, step=index):
                    matches = [after for action, after in transitions(state, variant)
                               if action == recorded['action'] and json.loads(json.dumps(asdict(after))) == recorded['after']]
                    self.assertEqual(len(matches), 1)
                    if not any(json.loads(json.dumps(asdict(after))) == recorded['after'] and action == recorded['action']
                               for action, after in transitions(state)):
                        diverged = True
                    state = matches[0]
                    actual = violation(state)
                    if index + 1 < len(result['counterexample']):
                        self.assertIsNone(actual)
                    else:
                        self.assertEqual(actual, EXPECTED_VIOLATIONS[variant])
            self.assertTrue(diverged, variant + ' did not actually change a safe transition')

    def test_both_registered_stopped_orphans_expire_before_reap_and_reactivate_new_owners(self):
        state = model.Authority()
        actions = [
            'explicit_activate_complete_current_market',
            'actor0:hold_SHARED_and_prepare_risk_command',
            'shard0:SIGSTOP_registered_old_worker', 'shard1:SIGSTOP_registered_old_worker',
            'coordinator_dies', 'new_coordinator_takes_supervisor_lock',
            'shard0:old_lease_reaches_expiry', 'shard1:old_lease_reaches_expiry',
            'shard0:pidfd_kill_after_rechecking_registered_birth_and_expiry',
            'shard1:pidfd_kill_after_rechecking_registered_birth_and_expiry',
            'shard0:grant_generation2_to_new_PID_birth', 'shard1:grant_generation2_to_new_PID_birth',
            'exclusive_begin_new_market_generation',
            'shard0:commit_actual_market_payload', 'collect_persisted_market_receipt_shard0',
            'shard1:commit_actual_market_payload', 'collect_persisted_market_receipt_shard1',
            'complete_fanout_but_remain_HALTED', 'explicit_activate_complete_current_market',
            'actor3:hold_SHARED_and_prepare_risk_command',
            'actor3:atomic_risk_COMMIT_with_prestate_witness',
        ]
        for action in actions:
            state = self.step(state, action, model.authority_next, model.authority_violation)
        self.assertEqual(tuple(owner.current_generation for owner in state.owners), (2, 2))
        self.assertEqual(state.markets, (1, 1))
        self.assertEqual(state.commit.token_generation, 2)
        self.assertEqual(state.commit.current_generation, 2)

    def test_reused_pid_birth_is_never_selected_for_orphan_kill(self):
        state = model.Authority()
        for action in ('coordinator_dies', 'new_coordinator_takes_supervisor_lock',
                       'shard0:old_worker_observes_parent_death_and_exits',
                       'shard0:same_numeric_PID_reused_with_different_birth', 'shard0:old_lease_reaches_expiry'):
            state = self.step(state, action, model.authority_next, model.authority_violation)
        self.assertEqual(state.owners[0].old_process, model.REUSED_PID)
        self.assertFalse(any(action.startswith('shard0:pidfd_kill') for action, _ in model.authority_next(state)))

    def test_historically_valid_commit_remains_valid_after_later_takeover(self):
        state = model.Authority()
        for action in ('explicit_activate_complete_current_market',
                       'actor0:hold_SHARED_and_prepare_risk_command',
                       'actor0:atomic_risk_COMMIT_with_prestate_witness',
                       'shard0:old_lease_reaches_expiry', 'coordinator_dies',
                       'new_coordinator_takes_supervisor_lock', 'shard0:grant_generation2_to_new_PID_birth'):
            state = self.step(state, action, model.authority_next, model.authority_violation)
        self.assertEqual(state.owners[0].current_generation, 2)
        self.assertEqual(state.commit.current_generation, 1)
        self.assertIsNone(model.authority_violation(state))  # Commit-time, not present-time witness.

    def test_lost_partial_fill_reply_restarts_and_queries_without_repeating_settlement(self):
        state = model.Commands()
        for action in ('COMMIT_intent_and_return_durably_queued_only', 'prepare_FIFO_command0',
                       'COMMIT_reservation_and_immutable_command_terminal_together',
                       'prepare_actual_paired_fill0', 'COMMIT_actual_match_position_and_unique_fill_receipt_together'):
            state = self.step(state, action, model.command_next, model.command_violation)
        self.assertEqual((state.position, state.filled, state.outcome_delivered, state.fill_delivered),
                         (1, (1, 0, 0), 0, 0))
        durable = state.position, state.filled, state.admitted, state.terminal, state.fill_effects
        for action in ('worker_crashes_losing_only_uncommitted_work_and_reply',
                       'restart_generation2_and_reopen_original_command_and_fill_IDs',
                       'query_or_redeliver_original_command_terminal0', 'query_or_redeliver_original_confirmed_fill0'):
            state = self.step(state, action, model.command_next, model.command_violation)
        self.assertEqual((state.position, state.filled, state.admitted, state.terminal, state.fill_effects), durable)
        self.assertFalse(any(action.startswith('prepare_actual_paired_fill') for action, _ in model.command_next(state)))
        for action in ('real_counterparty_replenishes_second_unit_of_depth',
                       'COMMIT_intent_and_return_durably_queued_only', 'prepare_FIFO_command1',
                       'COMMIT_reservation_and_immutable_command_terminal_together',
                       'prepare_actual_paired_fill1', 'COMMIT_actual_match_position_and_unique_fill_receipt_together',
                       'COMMIT_intent_and_return_durably_queued_only', 'prepare_FIFO_command2',
                       'COMMIT_reservation_and_immutable_command_terminal_together'):
            state = self.step(state, action, model.command_next, model.command_violation)
        self.assertEqual((state.position, state.filled, state.fill_effects), (0, (1, 1, 0), (1, 1, 0)))
        self.assertEqual(state.terminal, (model.SUCCEEDED, model.SUCCEEDED, model.REJECTED))
        self.assertEqual(state.admission_effects, (1, 1, 0))

    def test_incomplete_or_unknown_enumerations_never_return_a_false_pass(self):
        with self.assertRaisesRegex(RuntimeError, 'state bound exhausted'):
            model.run_model('authority', max_states=1)
        for name, variant in (('missing', None), ('authority', 'typo'), ('commands', 'typo')):
            with self.subTest(name=name, variant=variant), self.assertRaises(ValueError):
                model.run_model(name, mutant=variant)
        for limit in (True, 0, -1, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                model.run_model('commands', max_states=limit)

    def test_model_implementation_imports_only_its_declared_standard_library_modules(self):
        syntax = ast.parse(Path(model.__file__).read_text())
        imported = {alias.name.split('.')[0] for node in ast.walk(syntax) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported.update(node.module.split('.')[0] for node in ast.walk(syntax)
                        if isinstance(node, ast.ImportFrom) and node.module)
        self.assertEqual(imported, {'collections', 'dataclasses', 'json'})
