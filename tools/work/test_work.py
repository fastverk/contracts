"""Wire and persistent contract-oracle tests. No external service exercised."""
import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from reference import Store, p, validate, MAX, TERMINAL


def ref(label="fixture"):
    return p.ArtifactRef(uri="https://example.invalid/" + label, sha256=b"x" * 32,
                         size_bytes=0, media_type="application/octet-stream", schema_version="v1")


def intent():
    return p.WorkExecutionIntent(token_limit=100, binding=p.WorkBinding(
        binding_id="binding-1", attempt_id="attempt-1", context_id="context-1", profile_ref="fixture-profile",
        repository="example/repository", source_commit="a"*40,
        order=p.WorkOrderRef(order_id="order-1", as_of="opaque-corpus-cursor", packet=ref("packet")),
        input_manifest=ref("input"), environment_manifest=ref("environment"),
        effect_policy=ref("effects"), acceptance_policy=ref("acceptance")))


class WorkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "oracle.sqlite"
        self.store = Store(self.path)
        self.intent = intent()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def admit(self):
        return self.store.admit("owner", "admit-key", self.intent).execution

    def ack(self):
        e = self.admit()
        return self.store.acknowledge("owner", e.execution_id, e.revision, e.fence_epoch, 100)

    def usage(self, e, count=20, seq=1, finality=p.USAGE_FINALITY_PROVISIONAL):
        return p.TokenUsage(consumed_tokens=count, sequence=seq, finality=finality,
                            run_name=e.run_name, task_name=e.task_name,
                            meter_authority="fixture-meter", fence_epoch=e.fence_epoch)

    def cancel(self, e, key="cancel-key"):
        return self.store.cancel("owner", key, p.CancelIntent(execution_id=e.execution_id,
                                                            expected_revision=e.revision, reason="stop"))

    def test_import_free_data_contract_and_no_financial_fields(self):
        self.assertFalse(p.DESCRIPTOR.dependencies)
        self.assertFalse(p.DESCRIPTOR.services_by_name)
        for message in p.DESCRIPTOR.message_types_by_name.values():
            self.assertFalse(set(message.fields_by_name) & {"price", "bid", "currency", "payment", "settlement"})

    def test_wire_and_text_roundtrip_with_optional_presence(self):
        from google.protobuf import text_format
        for project in (None, "project-1"):
            source = intent()
            if project is not None:
                source.binding.project_id = project
            decoded = p.WorkExecutionIntent.FromString(source.SerializeToString())
            self.assertEqual(decoded, source)
            self.assertEqual(decoded.binding.HasField("project_id"), project is not None)
            self.assertEqual(text_format.Parse(text_format.MessageToString(source), p.WorkExecutionIntent()), source)

    def test_zero_missing_negative_and_overflow_limits_refused(self):
        for limit in (0, 2**63, 2**64-1):
            self.intent.token_limit = limit
            with self.assertRaises(ValueError):
                self.store.admit("owner", "key", self.intent)
        with self.assertRaises(ValueError):
            self.intent.token_limit = -1

    def test_large_integer_limit_is_exact(self):
        self.intent.token_limit = MAX
        e = self.admit()
        self.assertEqual(e.intent.token_limit, MAX)
        self.assertEqual(p.WorkExecution.FromString(e.SerializeToString()).intent.token_limit, MAX)

    def test_binding_artifact_and_repo_pins_required(self):
        self.intent.binding.environment_manifest.sha256 = b"short"
        with self.assertRaisesRegex(ValueError, "artifact"):
            validate(self.intent)
        self.intent.binding.environment_manifest.CopyFrom(ref())
        self.intent.binding.source_commit = "main"
        with self.assertRaisesRegex(ValueError, "commit"):
            validate(self.intent)

    def test_unknown_admission_fields_fail_closed(self):
        self.intent.ParseFromString(self.intent.SerializeToString() + b"\x98\x06\x01")
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            self.admit()

    def test_admitting_is_not_confirmed_admission_or_zero_usage(self):
        e = self.admit()
        self.assertEqual(e.state, p.EXECUTION_STATE_ADMITTING)
        self.assertEqual(e.effective_token_limit, 0)
        self.assertFalse(e.HasField("usage"))
        self.assertFalse(e.HasField("acceptance_receipt"))

    def test_lost_reply_replays_original_and_get_reads_current(self):
        initial = self.store.admit("owner", "admit-key", self.intent)
        current = self.store.acknowledge("owner", initial.execution.execution_id, 1, 0, 100)
        replay = self.store.admit("owner", "admit-key", self.intent)
        self.assertEqual(replay, initial)
        self.assertEqual(self.store.get("owner", current.execution_id), current)
        self.assertNotEqual(replay.execution.state, current.state)

    def test_replay_survives_database_reopen(self):
        first = self.store.admit("owner", "admit-key", self.intent)
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.admit("owner", "admit-key", self.intent), first)

    def test_changed_payload_and_different_key_same_attempt_conflict(self):
        self.admit()
        self.intent.token_limit = 99
        with self.assertRaisesRegex(ValueError, "changed payload"):
            self.admit()
        self.intent.token_limit = 100
        with self.assertRaisesRegex(ValueError, "already has an operation"):
            self.store.admit("owner", "different-key", self.intent)

    def test_optional_presence_is_part_of_replay(self):
        self.admit()
        self.intent.binding.project_id = ""
        with self.assertRaisesRegex(ValueError, "changed payload"):
            self.admit()

    def test_reordered_wire_fields_have_same_values(self):
        initial = self.store.admit("owner", "admit-key", self.intent)
        # Reorder top-level token_limit and binding on the wire.
        encoded = p.WorkExecutionIntent(binding=self.intent.binding).SerializeToString()
        reordered = p.WorkExecutionIntent.FromString(b"\x10\x64" + encoded)
        self.assertEqual(reordered, self.intent)
        self.assertEqual(self.store.admit("owner", "admit-key", reordered), initial)

    def test_auth_checked_before_cached_reply_and_other_owner_not_found(self):
        e = self.admit()
        with self.assertRaises(PermissionError):
            self.store.admit("owner", "admit-key", self.intent, authorized=False)
        with self.assertRaises(LookupError):
            self.store.get("other", e.execution_id)
        other = self.store.admit("other", "admit-key", self.intent)
        self.assertNotEqual(other.execution.execution_id, e.execution_id)

    def test_gate_refusal_replays_without_creating_run(self):
        first = self.store.admit("owner", "held-key", self.intent, gate=p.REFUSAL_REASON_HELD)
        self.assertEqual(first.verdict, p.ADMISSION_VERDICT_REFUSED)
        self.assertFalse(first.HasField("execution"))
        self.assertEqual(self.store.admit("owner", "held-key", self.intent), first)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM executions").fetchone()[0], 0)

    def test_parallel_same_key_creates_one_operation(self):
        def invoke(_):
            store = Store(self.path)
            try:
                return store.admit("owner", "parallel", intent())
            finally:
                store.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            replies = list(pool.map(invoke, range(4)))
        self.assertTrue(all(r == replies[0] for r in replies))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM executions").fetchone()[0], 1)

    def test_execution_and_replay_are_one_transaction(self):
        with patch.object(self.store, "remember", side_effect=RuntimeError("crash before commit")):
            with self.assertRaises(RuntimeError):
                self.admit()
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM executions").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM commands").fetchone()[0], 0)
        self.assertEqual(self.admit().revision, 1)

    def test_effective_cap_cannot_be_changed_by_provider(self):
        e = self.admit()
        with self.assertRaisesRegex(ValueError, "effective limit"):
            self.store.acknowledge("owner", e.execution_id, 1, 0, 101)

    def test_cancel_is_requested_not_stopped_or_final(self):
        e = self.ack()
        receipt = self.cancel(e)
        self.assertEqual(receipt.disposition, p.CANCELLATION_DISPOSITION_REQUESTED)
        self.assertEqual(receipt.execution.state, p.EXECUTION_STATE_CANCEL_REQUESTED)
        self.assertEqual(receipt.execution.fence_epoch, 1)
        self.assertFalse(receipt.execution.HasField("usage"))
        self.assertEqual(self.cancel(e), receipt)  # replay before stale CAS

    def test_stale_cancel_revision_refuses_without_mutation(self):
        e = self.ack()
        with self.assertRaisesRegex(ValueError, "stale cancellation"):
            self.store.cancel("owner", "stale", p.CancelIntent(execution_id=e.execution_id, expected_revision=1))
        self.assertEqual(self.store.get("owner", e.execution_id), e)

    def test_cancel_fences_late_worker_ack_and_can_reconcile_same_run(self):
        e = self.admit()
        canceled = self.cancel(e).execution
        with self.assertRaisesRegex(ValueError, "stale worker"):
            self.store.acknowledge("owner", e.execution_id, e.revision, 0, 100)
        reconciled = self.store.acknowledge("owner", e.execution_id, canceled.revision, 1, 100)
        self.assertEqual(reconciled.state, p.EXECUTION_STATE_CANCEL_REQUESTED)
        self.assertEqual(reconciled.run_name, e.run_name)

    def test_completed_execution_does_not_mean_acceptance(self):
        e = self.ack()
        done = self.store.terminal("owner", e.execution_id, e.revision, 0, p.EXECUTION_STATE_SUCCEEDED)
        self.assertFalse(done.HasField("acceptance_receipt"))
        receipt = self.cancel(done)
        self.assertEqual(receipt.disposition, p.CANCELLATION_DISPOSITION_ALREADY_TERMINAL)
        self.assertEqual(receipt.execution, done)

    def test_cancel_complete_race_cannot_overwrite(self):
        e = self.ack()
        pending = self.cancel(e).execution
        with self.assertRaisesRegex(ValueError, "race"):
            self.store.terminal("owner", e.execution_id, pending.revision, 1, p.EXECUTION_STATE_SUCCEEDED)

    def test_cancel_requires_fence_ack_then_final_meter(self):
        e = self.cancel(self.ack()).execution
        with self.assertRaisesRegex(ValueError, "fence receipt"):
            self.store.terminal("owner", e.execution_id, e.revision, 1, p.EXECUTION_STATE_CANCELED)
        stopped = self.store.terminal("owner", e.execution_id, e.revision, 1, p.EXECUTION_STATE_CANCELED,
                                      fence_receipt=ref("fence"))
        self.assertFalse(stopped.HasField("usage"))
        final = self.usage(stopped, 23, finality=p.USAGE_FINALITY_FINAL)
        final.drain_evidence.CopyFrom(ref("drain"))
        closed = self.store.meter("owner", "final", e.execution_id, final)
        self.assertEqual(closed.usage.consumed_tokens, 23)
        self.assertEqual(closed.state, p.EXECUTION_STATE_CANCELED)

    def test_final_usage_requires_terminal_drain_evidence(self):
        e = self.ack()
        usage = self.usage(e, finality=p.USAGE_FINALITY_FINAL)
        with self.assertRaisesRegex(ValueError, "terminal"):
            self.store.meter("owner", "meter", e.execution_id, usage)
        done = self.store.terminal("owner", e.execution_id, e.revision, 0, p.EXECUTION_STATE_SUCCEEDED)
        with self.assertRaisesRegex(ValueError, "artifact"):
            self.store.meter("owner", "meter", e.execution_id, usage)
        usage.drain_evidence.CopyFrom(ref("drain"))
        final = self.store.meter("owner", "meter", done.execution_id, usage)
        self.assertEqual(final.usage.finality, p.USAGE_FINALITY_FINAL)
        self.assertEqual(self.store.meter("owner", "meter", e.execution_id, usage), final)

    def test_usage_cumulative_not_additive_and_never_clamped(self):
        e = self.ack()
        self.store.meter("owner", "m1", e.execution_id, self.usage(e, 60))
        observed = self.store.meter("owner", "m2", e.execution_id, self.usage(e, 110, seq=2))
        self.assertEqual(observed.usage.consumed_tokens, 110)  # over-cap incident remains visible
        self.assertEqual(observed.intent.token_limit, 100)

    def test_meter_regression_gap_scope_fence_identity_refused(self):
        e = self.ack()
        self.store.meter("owner", "m1", e.execution_id, self.usage(e, 20))
        for usage in (self.usage(e, 19, seq=2), self.usage(e, 21, seq=3),
                      self.usage(e, MAX+1, seq=2), self.usage(e, 21, seq=2, finality=999)):
            with self.assertRaises(ValueError):
                self.store.meter("owner", "bad", e.execution_id, usage)
        usage = self.usage(e, 21, seq=2)
        usage.run_name = "wrong-run"
        with self.assertRaisesRegex(ValueError, "scope"):
            self.store.meter("owner", "bad", e.execution_id, usage)
        usage.run_name = e.run_name
        usage.fence_epoch = 99
        with self.assertRaisesRegex(ValueError, "fence"):
            self.store.meter("owner", "bad", e.execution_id, usage)
        with self.assertRaises(PermissionError):
            self.store.meter("owner", "bad", e.execution_id, self.usage(e), meter="caller")

    def test_final_usage_immutable_and_late_meter_not_silently_applied(self):
        e = self.ack()
        done = self.store.terminal("owner", e.execution_id, e.revision, 0, p.EXECUTION_STATE_SUCCEEDED)
        usage = self.usage(done, 40, finality=p.USAGE_FINALITY_FINAL, seq=1)
        usage.drain_evidence.CopyFrom(ref("drain"))
        self.store.meter("owner", "final", e.execution_id, usage)
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.store.meter("owner", "late", e.execution_id, self.usage(done, 50, seq=2))
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.get("owner", e.execution_id).usage.consumed_tokens, 40)

    def test_unknown_states_and_finality_do_not_authorize(self):
        self.assertNotIn(999, TERMINAL)
        self.assertNotIn(p.EXECUTION_STATE_UNSPECIFIED, TERMINAL)
        e = self.ack()
        with self.assertRaisesRegex(ValueError, "finality"):
            self.store.meter("owner", "unknown", e.execution_id, self.usage(e, finality=p.USAGE_FINALITY_UNSPECIFIED))


if __name__ == "__main__":
    unittest.main()
