#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
work_tmp=$(mktemp -d)
trap 'rm -rf "$work_tmp"' EXIT
protoc -I proto --python_out="$work_tmp" proto/fastverk/work/v1/execution.proto
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$work_tmp:tools/work${PYTHONPATH:+:$PYTHONPATH}" python3 -m unittest discover -s tools/work -p 'test_*.py' -v
