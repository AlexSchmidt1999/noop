#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 scripts/security/policy.py check --report "${1:-build/security/source-policy.json}"
