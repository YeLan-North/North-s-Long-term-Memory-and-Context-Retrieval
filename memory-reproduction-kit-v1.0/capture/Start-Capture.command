#!/bin/zsh
set -eu
capture_root="$(cd "$(dirname "$0")" && pwd)"
cd "$capture_root"
print 'Project Chat Capture：保持此终端打开；停止请按 Ctrl+C。'
exec python3 "$capture_root/bin/chatgpt-sync" serve
