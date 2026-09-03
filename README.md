# contracts

Public gRPC contract surface for the fastverk platform. Same idea as
[`tomato-bazel/rbe-api`](https://github.com/tomato-bazel/rbe-api): **one
definition the implementations import; implementations stay in their own
repos.**

This git repo **is** one Bazel module (`fastverk_contracts`). It is the
smallest vehicle that lets a consumer write

```python
bazel_dep(name = "fastverk_contracts", version = "0.0.1")
```

and depend on `@fastverk_contracts//:forge_proto` (or the package-local
`//proto/...` labels) **without** pulling forge-gateway OCI images, Linear
adapters, the service-finder daemon, or the wave CLI/operator.

It does **not** publish modules named `forge`, `tracker`, `service_finder`, or
`wave`. Those names are already on the implementation repos (and, for three of
them, on `registry.tbzl.dev`). This extract does not silently take them over.
See [LEDGER.md](LEDGER.md).

## Packages

| Proto package | Services | Implementation stays in |
| --- | --- | --- |
| `forge.v1` | `ForgeService`, `ForgeProvisionService`, `ForgeDiscovery`, `EventSink`, `ForgeWrite` | [fastverk/forge](https://github.com/fastverk/forge) |
| `tracker.v1` | `TrackerService` | [fastverk/tracker](https://github.com/fastverk/tracker) |
| `fastverk.finder.v1` | `Finder` (`Resolve` / `Watch`) | [fastverk/service-finder](https://github.com/fastverk/service-finder) |
| `wave.v1` | store / interchange schema (no gRPC service) | [fastverk/wave](https://github.com/fastverk/wave) |

`.proto` files are copied from each source repo's default-branch HEAD. They
are not rewritten here.

## Consume

`.bazelrc` (same registry chain as the rest of the fleet):

```
common --registry=https://registry.tbzl.dev/
common --registry=https://bcr.bazel.build/
```

`MODULE.bazel`, once this module is on the registry:

```python
bazel_dep(name = "fastverk_contracts", version = "0.0.1")
```

Until then, pin a git commit:

```python
bazel_dep(name = "fastverk_contracts", version = "0.0.1")
git_override(
    module_name = "fastverk_contracts",
    remote = "https://github.com/fastverk/contracts.git",
    commit = "<this repo SHA>",
)
```

Public `proto_library` labels:

| Label | Package |
| --- | --- |
| `@fastverk_contracts//:forge_proto` | `forge.v1` (`ForgeService`) |
| `@fastverk_contracts//:forge_provision_proto` | `forge.v1` (`ForgeProvisionService`) |
| `@fastverk_contracts//:forge_discovery_proto` | `forge.v1` (`ForgeDiscovery`) |
| `@fastverk_contracts//:forge_events_proto` | `forge.v1` (`EventSink`, `ForgeWrite`) |
| `@fastverk_contracts//:tracker_proto` | `tracker.v1` |
| `@fastverk_contracts//:finder_proto` | `fastverk.finder.v1` |
| `@fastverk_contracts//:wave_proto` | `wave.v1` |

The `.proto` files are also `exports_files` / `filegroup` targets, so a
`cargo_build_script` can data-dep them the way the implementation repos do
today (`//proto/forge/v1:forge.proto`, or `//proto:all_protos`).

`bazel build //...` compiles every public `proto_library`. There are no
language stubs, binaries, images, or Helm charts in this repo.

## AIP lint

[`tomato-bazel/rules_aip`](https://github.com/tomato-bazel/rules_aip) is
published (`rules_aip` 0.3.0 on `registry.tbzl.dev`) and is **pending** import
into [`tomato-bazel/rules`](https://github.com/tomato-bazel/rules). It does
**not** already fit these contracts: they are not AIP-shaped (no
`google.api` annotations; RPCs such as `ReadFile`, `PipelineStatus`,
`Resolve`). Wiring `aip_proto_lint` would mean rewriting the imported protos
or a disable-list that hides the linter. Deferred until the APIs are
AIP-shaped or a follow-up explicitly opts in.

A [buf.yaml](buf.yaml) covers the same tree for `buf build` / `buf lint`.
Bazel is the supported API.

## What this repo is not

- Not the `forge` / `tracker` / `service_finder` / `wave` implementation
  modules. Do not `bazel_dep(name = "forge")` against this git URL.
- Not forge-gateway, Linear adapters, the finder daemon, or the wave
  CLI/operator.
- Not `agent.v1` (private `fastverk/agents` — see LEDGER).
- Not botnoc leftover protos, plugin-\* HTTP facades, mycelium/polyglot
  engines, or the spec corpus.

## License

Apache-2.0 (this repository). Source proto files were copied from the
implementation repos; provenance is in [LEDGER.md](LEDGER.md).
