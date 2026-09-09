# Execution context conformance

Run `bash tools/conformance/run_context.sh` with `protoc` and Python `protobuf` installed. This generates Python messages in a temporary directory, checks protobuf wire round-trips, and runs an executable reference validator against the textproto corpus. Consumer validators should run the same fixtures with their own generated messages.

The limit is 100 maximal runs of non-White_Space characters, using the explicit Unicode set in `context.proto`. Preserve input exactly, including whitespace and rejected over-limit text. Empty input is valid; unspecified or unknown validation results do not authorize work. Client validation is advisory; servers must recalculate before accepting work.

This additive contract has no served RPC or production validator. Python conformance does not prove Swift, TypeScript, or server adoption. Runtime enforcement, client generation, authorization, idempotency, and durable work receipts remain implementation work. It does not alter existing stored messages.

## Ownership boundaries

`tracker.v1.WorkItemRef` remains provider identity. Desktop WorkspaceService owns repository checkouts and workspace revisions. Spec WorkOrder remains an independently derived obligation record. Agent CRDs retain their schema and task lifecycle. This context can be composed into those consumers through explicit adoption; it replaces none of them. No project, release, or approval authority is inferred from a valid context.
