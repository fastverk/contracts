# Product project directory contract

This defines user work identity without a repository requirement. It is separate from desktop `fastverk.workspace.v1.ProjectSpec`, which provisions repository workspaces, and from provider `tracker.v1.WorkItemRef`. No calls dispatch agents or grant provider access. Parent placement, origins, imports, sharing, outcome edits, and deletion are deferred.

## Transport and authorization

The initial HTTP binding uses POST `/api/product/projects/create`, `/get`, `/list`, and `/rename`, with binary `application/x-protobuf` requests and responses matching the service methods. Success is HTTP 200. Non-success returns binary `ProjectError`, never a success envelope. Request bodies are bounded by the serving implementation. Unknown/missing error codes fail closed.

| Code | HTTP | gRPC |
| --- | --- | --- |
| INVALID_ARGUMENT | 400 | INVALID_ARGUMENT |
| UNAUTHENTICATED | 401 | UNAUTHENTICATED |
| PERMISSION_DENIED | 403 | PERMISSION_DENIED |
| NOT_FOUND | 404 | NOT_FOUND |
| CONFLICT | 409 | ABORTED |
| UNAVAILABLE | 503 | UNAVAILABLE |
| INTERNAL | 500 | INTERNAL |

Authorization precedes all storage reads, including replay. Identity comes from verified issuer and subject, never request data. Missing and inaccessible project IDs return indistinguishable NOT_FOUND. PERMISSION_DENIED is reserved for directory-level policy and reveals no project existence. Unconfigured or unavailable storage cannot masquerade as an empty directory. Reads are strongly consistent per page; pagination is not a snapshot. A token only selects a continuation inside the server-derived principal partition and confers no access.

## Mutation rules

Names are trimmed at both ends using exactly Unicode White_Space: U+0009..U+000D, U+0020, U+0085, U+00A0, U+1680, U+2000..U+200A, U+2028, U+2029, U+202F, U+205F, U+3000. Store internal text unchanged. Validate 1..200 Unicode scalar values after trimming. Outcome is optional verbatim text, at most 4000 scalar values. Empty outcome is distinct from absent. Reject invalid input without truncation.

Create assigns a stable opaque URL-safe ID and revision 1. Rename preserves ID/outcome and atomically compares its required nonzero expected revision before incrementing once, including same-name renames. Overflow must fail rather than wrap. Reuse of a name is allowed; names are not identity.

Both writes require a 1..128 ASCII alphanumeric/underscore/hyphen replay key. Scope replay records to authenticated principal and method. Persist the mutation and original response atomically. Compare decoded known-field values, including original untrimmed name and optional outcome presence; wire order and unknown fields do not change identity. A matching replay returns the original response even after later edits; changed payload conflicts. Check replay before rename revision validation. Keep records for the lifetime of the directory; no implicit replay expiration.

The serving proposal uses the web host's existing verified authentication and DynamoDB client, a dedicated table, partition-scoped consistent queries, and atomic mutation/replay transactions. This repository neither provisions that table nor implements those guarantees.

## Validation and adoption

Run `bash tools/project/run.sh` with protoc and Python protobuf installed. Tests generate Python clients and check optional presence, uint64 precision, future error values, continuation responses, rename retries, and semantically identical differently encoded create payloads. They do not prove server authorization, DynamoDB durability, or Swift/TypeScript adoption; those require consumer integration tests. `bazel build //...` checks the schema and public targets.
