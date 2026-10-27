# One-order execution data contract

Status: additive wire contract and executable conformance oracle. Not a served
RPC, fleet implementation, authenticated issuer or production release. The
`fastverk.work.v1` package imports nothing and declares no services. Control RPCs
remain with the fleet implementation, not this public data-contract repository.

## Scope and identity

One immutable WorkOrder reference binds one repository-backed attempt to one
fleet run/task. The upstream derived packet is referenced by ID, corpus cursor
and immutable artifact identity, not redefined or imported. Input/environment,
effect and acceptance policies have separate content-addressed references.
The corpus cursor does not pin code; repository commit and environment manifest
are independent. Artifact URIs use an approved resolver; no credentialed fetch of
arbitrary caller URLs is implied.

`binding_id`, `attempt_id`, optional product project association, context ID,
execution ID, run name and task name have distinct meanings. Directory retry
keys and project phases have no execution authority. Referenced policy bytes
must specify permitted effects and evaluator identity/rubric; a model cannot
select itself as authority. Unknown admission fields or state/finality values
fail closed. This revision supports neither child delegation nor non-repository
work. It contains no bids, prices, monetary budgets or payment receipts.

## Admission and replay

Authenticate and authorize the transport principal before reading a cached reply.
Scope mutation keys to principal and method, retain them for the lifetime of the
execution directory, and atomically persist intent, response and reserved stable
run/task identities. Compare known field values including optional presence and
repeated order, not caller wire encoding. Unknown authority fields reject.
Reusing a committed key with changed semantics conflicts. A different key for
the same `(principal, binding_id, attempt_id)` must not create another operation.

An admission receipt records either a refusal or a durable ADMITTING operation.
It is not confirmation that a fleet run exists. Retry returns the original saved
receipt; Get returns current state. Reconcile the same stable run after a timeout
or crash; never call a non-idempotent legacy creator again with a new name.
Replay durability in a database is necessary but does not alone make an external
resource create exactly-once. The fleet adapter must reconcile its persisted
name/UID with the execution authority.

Validate derived packet freshness, spec gate, current overlap, real principal
scope and immutable effects before external admission. The token limit is exact,
positive, run-wide and at most INT64_MAX. Missing/zero is refused rather than
converted into legacy unbounded behavior. The effective cap must equal the
requested cap, or refuse. A packet with unsupported probe constraints must be
refused, not silently weakened. Gate/refusal and resource enforcement remain
runtime responsibilities; references and receipts cannot enforce themselves.

## Cancellation and metering

A new cancel command checks the current nonzero revision after replay lookup.
A successful request records CANCEL_REQUESTED and advances the fence epoch.
It does not establish stopped work or final usage. Workers must honor the epoch
and reject stale updates. A late admission acknowledgment must not reopen work
under an old fence; reconcile its same run under the cancellation request.
CANCELED requires an authenticated stop/fence receipt. A terminal execution cannot
be restarted; cancellation of a completed execution returns ALREADY_TERMINAL
without erasing usage or implying artifact acceptance.

Usage is an authenticated **cumulative run total**, never a delta. It is not
added to a task projection of the same usage. An absent usage message means
unavailable, not zero. Source run/task, meter identity and fence epoch must match.
Sequences start at 1 and advance without gaps; totals never decrease. Reject
changed duplicate/reordered samples and overflow. Retain truthful over-cap
observations as incidents rather than clamping them to the cap or dropping them.

FINAL requires terminal execution plus complete measurement, acknowledged
resource fencing/drain and no unknown outstanding usage. Finality is never
inferred from lifecycle. Final usage is immutable; late observations after a
claimed final meter are reconciliation incidents, not silent updates. Corrections
require a separately versioned correction policy, outside this first contract.
Execution success does not imply artifact acceptance, and final usage does not
imply quality. Acceptance is a separately issued, bound receipt.

## Conformance and limits

Run `bash tools/work/run.sh` with protoc and a compatible Python protobuf runtime.
The suite generates actual messages and exercises a SQLite-backed **contract
oracle**: replay/reopen, concurrent same-key admission, atomic rollback, scoped
lookup, cancellation races, fencing, incomplete/final meters and truthful over-cap
usage. Caller, worker, meter and gate identities are injected fixtures. The oracle
is not production authentication, a spec gate, token counter, resource stopper,
service transport or independently authenticated artifact checker.

CI runs generated Python conformance alongside builds and existing contract tests.
Swift/TypeScript consumers, actual fleet persistence/reconciliation, scoped
credentials, server registration, provider resource fencing and final metering
remain adoption work. No formal runtime proof or distributed-liveness claim is
made. A production implementation must validate referenced bytes and authority,
not merely pass this local oracle.
