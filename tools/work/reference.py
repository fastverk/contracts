"""Executable contract oracle, NOT an authentication system or fleet service.

SQLite demonstrates atomic request replay and receipt persistence across reopen.
Worker/meter identities and gate decisions are injected test fixtures. No token
meter, subprocess, resource fencing, WorkOrder derivation or external effects.
"""
import re
import sqlite3
import uuid
from contextlib import contextmanager
from fastverk.work.v1 import execution_pb2 as p

MAX = 2**63 - 1
TERMINAL = {p.EXECUTION_STATE_CANCELED, p.EXECUTION_STATE_SUCCEEDED, p.EXECUTION_STATE_FAILED}


def known(message):
    clean = type(message)()
    clean.CopyFrom(message)
    clean.DiscardUnknownFields()
    if clean != message:
        raise ValueError("unsupported fields")


def artifact(ref):
    if not ref.uri or len(ref.sha256) != 32 or not ref.media_type or not ref.schema_version:
        raise ValueError("incomplete artifact reference")


def validate(intent):
    known(intent)
    b = intent.binding
    if not all((b.binding_id, b.attempt_id, b.order.order_id, b.order.as_of, b.context_id, b.profile_ref)):
        raise ValueError("missing binding identity")
    for ref in (b.order.packet, b.input_manifest, b.environment_manifest, b.effect_policy, b.acceptance_policy):
        artifact(ref)
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", b.repository)
            or not re.fullmatch(r"[a-f0-9]{40}", b.source_commit)):
        raise ValueError("repository and immutable commit required")
    if not 0 < intent.token_limit <= MAX:
        raise ValueError("finite signed token limit required")
    if b.HasField("project_id") and not b.project_id:
        raise ValueError("empty project association")


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS executions(owner TEXT, id TEXT, binding TEXT, attempt TEXT, value BLOB,
            PRIMARY KEY(owner,id), UNIQUE(owner,binding,attempt));
          CREATE TABLE IF NOT EXISTS commands(owner TEXT, method TEXT, key TEXT, request BLOB, response BLOB,
            PRIMARY KEY(owner,method,key));
        ''')

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def replay(self, owner, method, key, request, response_type):
        if not owner:
            raise PermissionError("authenticated fixture owner required")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", key):
            raise ValueError("invalid mutation key")
        known(request)
        row = self.db.execute("SELECT request,response FROM commands WHERE owner=? AND method=? AND key=?",
                              (owner, method, key)).fetchone()
        if row:
            # Compare protobuf VALUES, not caller wire bytes. Unknown fields were
            # rejected above; presence and repeated order remain significant.
            if type(request).FromString(row[0]) != request:
                raise ValueError("key reused with changed payload")
            return response_type.FromString(row[1])
        return None

    def remember(self, owner, method, key, request, response):
        self.db.execute("INSERT INTO commands VALUES(?,?,?,?,?)", (owner, method, key,
            request.SerializeToString(), response.SerializeToString()))

    def get(self, owner, execution_id):
        if not owner:
            raise PermissionError("authenticated fixture owner required")
        row = self.db.execute("SELECT value FROM executions WHERE owner=? AND id=?", (owner, execution_id)).fetchone()
        if not row:
            raise LookupError("execution not found")
        return p.WorkExecution.FromString(row[0])

    def save(self, owner, execution):
        self.db.execute("UPDATE executions SET value=? WHERE owner=? AND id=?",
                        (execution.SerializeToString(), owner, execution.execution_id))

    def admit(self, owner, key, intent, gate=p.REFUSAL_REASON_UNSPECIFIED, authorized=True):
        if not authorized:
            raise PermissionError("fixture authorization refused")
        with self.transaction():
            replay = self.replay(owner, "admit", key, intent, p.AdmissionReceipt)
            if replay is not None:
                return replay
            validate(intent)
            if gate not in {p.REFUSAL_REASON_UNSPECIFIED, p.REFUSAL_REASON_HELD, p.REFUSAL_REASON_OVERLAP,
                            p.REFUSAL_REASON_STALE, p.REFUSAL_REASON_LIMIT, p.REFUSAL_REASON_UNSUPPORTED}:
                raise ValueError("unknown gate decision")
            if gate:
                receipt = p.AdmissionReceipt(verdict=p.ADMISSION_VERDICT_REFUSED, refusal=gate, reason="fixture gate refusal")
            else:
                eid = uuid.uuid4().hex
                execution = p.WorkExecution(execution_id=eid, intent=intent, revision=1,
                    state=p.EXECUTION_STATE_ADMITTING, run_name="work-" + eid, task_name="work-" + eid + "-work")
                try:
                    self.db.execute("INSERT INTO executions VALUES(?,?,?,?,?)", (owner, eid,
                        intent.binding.binding_id, intent.binding.attempt_id, execution.SerializeToString()))
                except sqlite3.IntegrityError as error:
                    raise ValueError("attempt already has an operation; recover its original key") from error
                receipt = p.AdmissionReceipt(verdict=p.ADMISSION_VERDICT_ADMITTING, execution=execution)
            self.remember(owner, "admit", key, intent, receipt)
            return receipt

    def acknowledge(self, owner, execution_id, revision, epoch, effective_limit, worker="fixture-worker"):
        if worker != "fixture-worker":
            raise PermissionError("worker role required")
        with self.transaction():
            e = self.get(owner, execution_id)
            if e.revision != revision or e.fence_epoch != epoch:
                raise ValueError("stale worker revision/fence")
            if e.state not in {p.EXECUTION_STATE_ADMITTING, p.EXECUTION_STATE_INDETERMINATE, p.EXECUTION_STATE_CANCEL_REQUESTED}:
                raise ValueError("acknowledgment cannot restart an execution")
            if effective_limit != e.intent.token_limit:
                raise ValueError("effective limit differs")
            e.effective_token_limit = effective_limit
            if e.state != p.EXECUTION_STATE_CANCEL_REQUESTED:
                e.state = p.EXECUTION_STATE_ADMITTED
            e.revision += 1
            self.save(owner, e)
            return e

    def cancel(self, owner, key, intent):
        with self.transaction():
            replay = self.replay(owner, "cancel", key, intent, p.CancellationReceipt)
            if replay is not None:
                return replay
            e = self.get(owner, intent.execution_id)
            if not intent.expected_revision or e.revision != intent.expected_revision:
                raise ValueError("stale cancellation revision")
            if e.state in TERMINAL:
                disposition = p.CANCELLATION_DISPOSITION_ALREADY_TERMINAL
            elif e.state in {p.EXECUTION_STATE_ADMITTING, p.EXECUTION_STATE_ADMITTED, p.EXECUTION_STATE_RUNNING,
                              p.EXECUTION_STATE_INDETERMINATE, p.EXECUTION_STATE_CANCEL_REQUESTED}:
                disposition = p.CANCELLATION_DISPOSITION_REQUESTED
                if e.state != p.EXECUTION_STATE_CANCEL_REQUESTED:
                    e.state = p.EXECUTION_STATE_CANCEL_REQUESTED
                    e.fence_epoch += 1
                    e.revision += 1
                    self.save(owner, e)
            else:
                raise ValueError("unknown execution state")
            receipt = p.CancellationReceipt(disposition=disposition, execution=e)
            self.remember(owner, "cancel", key, intent, receipt)
            return receipt

    def terminal(self, owner, execution_id, revision, epoch, state, worker="fixture-worker", fence_receipt=None):
        if worker != "fixture-worker":
            raise PermissionError("worker role required")
        with self.transaction():
            e = self.get(owner, execution_id)
            if e.revision != revision or e.fence_epoch != epoch:
                raise ValueError("stale worker revision/fence")
            if e.state in TERMINAL or state not in TERMINAL:
                raise ValueError("invalid terminal transition")
            if state == p.EXECUTION_STATE_CANCELED and e.state != p.EXECUTION_STATE_CANCEL_REQUESTED:
                raise ValueError("cancellation not requested")
            if e.state == p.EXECUTION_STATE_CANCEL_REQUESTED and state != p.EXECUTION_STATE_CANCELED:
                raise ValueError("cancel/complete race requires reconciliation, not overwrite")
            if state != p.EXECUTION_STATE_CANCELED and not e.effective_token_limit:
                raise ValueError("unconfirmed execution cannot complete")
            if state == p.EXECUTION_STATE_CANCELED:
                if fence_receipt is None:
                    raise ValueError("fence receipt required")
                artifact(fence_receipt)
                e.fence_receipt.CopyFrom(fence_receipt)
            e.state = state
            e.revision += 1
            self.save(owner, e)
            return e

    def meter(self, owner, key, execution_id, sample, meter="fixture-meter"):
        if meter != "fixture-meter" or sample.meter_authority != meter:
            raise PermissionError("meter identity required")
        with self.transaction():
            # For this one-task oracle the sample identifies the immutable run/task;
            # execution_id is independently checked against that binding below.
            replay = self.replay(owner, "meter:" + execution_id, key, sample, p.WorkExecution)
            if replay is not None:
                return replay
            e = self.get(owner, execution_id)
            if (sample.run_name != e.run_name or sample.task_name != e.task_name
                    or sample.fence_epoch != e.fence_epoch):
                raise ValueError("usage scope or fence mismatch")
            if e.HasField("usage") and e.usage.finality == p.USAGE_FINALITY_FINAL:
                raise ValueError("final usage is immutable")
            if sample.sequence != (e.usage.sequence + 1 if e.HasField("usage") else 1):
                raise ValueError("usage sequence gap or regression")
            if sample.consumed_tokens > MAX or sample.consumed_tokens < e.usage.consumed_tokens:
                raise ValueError("usage regression or overflow")
            if sample.finality not in {p.USAGE_FINALITY_PROVISIONAL, p.USAGE_FINALITY_FINAL}:
                raise ValueError("unknown usage finality")
            if sample.finality == p.USAGE_FINALITY_FINAL:
                if e.state not in TERMINAL:
                    raise ValueError("terminal state required before final meter")
                artifact(sample.drain_evidence)
            # Truthful over-cap observations are retained, never clamped/refused.
            e.usage.CopyFrom(sample)
            e.revision += 1
            self.save(owner, e)
            self.remember(owner, "meter:" + execution_id, key, sample, e)
            return e
