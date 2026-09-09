#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
context_tmp=$(mktemp -d)
trap 'rm -rf "$context_tmp"' EXIT
protoc -I proto --python_out="$context_tmp" proto/fastverk/product/v1/context.proto proto/fastverk/product/testing/v1/fixtures.proto
PYTHONPATH="$context_tmp${PYTHONPATH:+:$PYTHONPATH}" python3 tools/conformance/test_context.py
