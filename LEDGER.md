# Ledger

Provenance for every proto package in this contract vehicle, every pending
import, and every explicit exclude.

This git repo **is** one Bazel module:

| This repo | `module(name)` | `module(version)` |
| --- | --- | --- |
| [fastverk/contracts](https://github.com/fastverk/contracts) | `fastverk_contracts` | `0.0.1` |

It is **not** a takeover of the published implementation modules. Source
`MODULE.bazel` names and versions below are recorded so they are not silently
renamed here.

Status:

- `imported` — proto tree present; SHA is the source default-branch HEAD
  copied from.
- `pending` — listed for a follow-up; not in this tree.
- `excluded` — must not appear here.

## Includes (public proto packages)

Copied from each source repo's default branch (`main`) HEAD. Only `proto/`
(and enough Bazel to `bazel build` the public API). No Rust services, Helm,
Dockerfile, operator, or deploy trees.

| Package | Status | Source repo | Source SHA | Source `module(name)` | Source `module(version)` | Registry (`registry.tbzl.dev`) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `forge.v1` | imported | [fastverk/forge](https://github.com/fastverk/forge) | `98591f75f411701cea00bcd0cf54f803cc2a140d` | `forge` | `0.0.6` | `forge` 0.0.1–0.0.6 | `proto/forge/v1/{forge,provision,discovery,events}.proto`. Tags `v0.0.1`–`v0.0.6`. |
| `tracker.v1` | imported | [fastverk/tracker](https://github.com/fastverk/tracker) | `3927db97f7904e5362271187177175b82a39a005` | `tracker` | `0.0.4` | `tracker` 0.0.1–0.0.4 | `proto/tracker/v1/tracker.proto`. Tags `v0.0.1`–`v0.0.4`. |
| `fastverk.finder.v1` | imported | [fastverk/service-finder](https://github.com/fastverk/service-finder) | `abc764147a63ef0c48b84ad102010980ed8d5415` | `service_finder` | `0.0.1` | *not published* | `proto/fastverk/finder/v1/finder.proto`. Source tags are `service-finder-client-v0.0.1`–`v0.0.3` (Rust client crate), not the Bazel module. |
| `wave.v1` | imported | [fastverk/wave](https://github.com/fastverk/wave) | `c689d650fe33e34507c42d3dcb65c56954454a07` | `wave` | `0.1.0` | `wave` 0.0.1 only | `proto/wave/v1/wave.proto`. Source tags include `v0.0.1`, `v0.1.0`, `v0.2.0`; MODULE.bazel on HEAD is `0.1.0`. Registry has not caught up. |
| `agent.v1` | imported | [fastverk/agents](https://github.com/fastverk/agents) (private) | `9312188d1b35f5f109fa5340c2845db577552e63` | `fastverk_agents` | `0.1.0` | *not published* | `proto/agent/v1/{annotation,events,lineage,messages}.proto`. Byte-copied from private source via box `gh`; BUILD is new (contracts conventions — `@protobuf` `proto_library`, no `rust_prost_library`). |

### Source module names — do not silently rename

Verified against each source repo's `MODULE.bazel` on the SHA above:

| Source repo | Published / declared module | What this repo publishes |
| --- | --- | --- |
| `fastverk/forge` | `forge` 0.0.6 | proto only, under `fastverk_contracts` |
| `fastverk/tracker` | `tracker` 0.0.4 | proto only, under `fastverk_contracts` |
| `fastverk/service-finder` | `service_finder` 0.0.1 (declared; not on the registry) | proto only, under `fastverk_contracts` |
| `fastverk/wave` | `wave` 0.1.0 (registry still at 0.0.1) | proto only, under `fastverk_contracts` |
| `fastverk/agents` | `fastverk_agents` 0.1.0 (private; not on the registry) | proto only, under `fastverk_contracts` |

Publishing proto-only modules that reuse `forge` / `tracker` / `service_finder`
/ `wave` / `fastverk_agents` would collide with those identities (`@forge//:forge`
is a Rust library + OCI image today; `@fastverk_agents` owns the operator +
services). This vehicle uses `fastverk_contracts` instead.

## Follow-up PRs on implementation repos

This PR only fills `fastverk/contracts`. Do **not** drive-by rewrite
forge / tracker / wave / service-finder / agents here.

When those repos are ready, each should `bazel_dep(name = "fastverk_contracts", ...)`
and data-dep / `proto_library`-dep the labels above, then stop exporting their
own copy of the proto. Until then they remain the modules that publish the
proto.

- [ ] [fastverk/forge](https://github.com/fastverk/forge) — `bazel_dep` this; keep `module(name = "forge")` (gateway + adapters)
- [ ] [fastverk/tracker](https://github.com/fastverk/tracker) — `bazel_dep` this; keep `module(name = "tracker")` (gateway + Linear adapter)
- [ ] [fastverk/service-finder](https://github.com/fastverk/service-finder) — `bazel_dep` this; keep `module(name = "service_finder")` (daemon + client)
- [ ] [fastverk/wave](https://github.com/fastverk/wave) — `bazel_dep` this; keep `module(name = "wave")` (CLI + operator)
- [ ] [fastverk/agents](https://github.com/fastverk/agents) — `bazel_dep` this; keep `module(name = "fastverk_agents")` (operator + agent-coord + agent-runner)
- [ ] Publish `fastverk_contracts` to `registry.tbzl.dev` / `registry.fastverk.com` via tomato-bazel/bazel-registry `rels`

## Pending

| Package | Status | Source | Notes |
| --- | --- | --- | --- |
| *(none)* | — | — | `agent.v1` imported in this PR. |

## Excludes

Do not import these into this vehicle.

| Name | Status | Why excluded |
| --- | --- | --- |
| botnoc leftover protos | excluded | leftover / non-platform contract; not a published public API |
| plugin-* HTTP facades | excluded | HTTP facades over the gRPC contracts, not the contracts |
| mycelium / polyglot engines | excluded | engines, not public gRPC contracts |
| spec corpus | excluded | [fastverk/spec](https://github.com/fastverk/spec) is a separate corpus |
| forge Rust / OCI / Helm / Dockerfile | excluded | implementation; stays in `fastverk/forge` |
| tracker Linear adapter / gateway / OCI | excluded | implementation; stays in `fastverk/tracker` |
| service-finder daemon / Rust client / Helm | excluded | implementation; stays in `fastverk/service-finder` |
| wave CLI / wave-core / operator / Helm | excluded | implementation; stays in `fastverk/wave` |
| agents `dispatch.v1` / `fanout.v1` | excluded | sibling packages in private `fastverk/agents` (`proto/dispatch/v1`, `proto/fanout/v1`); not the `agent.v1` public contract |
| agents operator / Rust services / agent-runner / OCI | excluded | implementation; stays in `fastverk/agents` |

## AIP lint

`rules_aip` (`module(name = "rules_aip", version = "0.3.0")`) is published on
`registry.tbzl.dev` and is **pending** import into
[tomato-bazel/rules](https://github.com/tomato-bazel/rules) (see that repo's
LEDGER). It does not already fit these protos (not AIP-shaped). Not wired in
this PR.

## Import method

Byte-copy of `proto/` from each source default-branch HEAD (not `git subtree`
of the whole implementation repo). BUILD files here are new: source repos
only `exports_files` the `.proto`s and compile them from `build.rs` (agents
also declares `rust_prost_library`; this vehicle stays proto-only).
