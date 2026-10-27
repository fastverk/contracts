# Work execution conformance oracle

Run `bash tools/work/run.sh`. See [the contract](../../docs/work-execution.md).
The shell runner generates Python from the actual shared proto in a temporary
directory; tests leave no database or generated bindings in the source tree.
SQLite provides transactional fixture persistence only. It creates no fleet run,
charges no resource, and verifies no real credential or artifact signature.
