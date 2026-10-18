#!/bin/zsh
set -eu
kit_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$kit_root"
exec "$kit_root/.venv/bin/openviking-server" --config "$kit_root/runtime/ov.conf"
