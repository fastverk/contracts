#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
project_tmp=$(mktemp -d)
trap 'rm -rf "$project_tmp"' EXIT
protoc -I proto --python_out="$project_tmp" proto/fastverk/product/v1/project.proto
PYTHONPATH="$project_tmp${PYTHONPATH:+:$PYTHONPATH}" python3 tools/project/test_project.py
