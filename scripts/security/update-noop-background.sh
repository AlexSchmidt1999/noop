#!/bin/zsh
set -u

cd "$(dirname "$0")/../.." || exit 1
if python3 scripts/security/install-analyzed-ios.py >> build/noop-background.log 2>&1; then
  exit 0
fi

/usr/bin/osascript -e 'display notification "Automatic install failed. See build/noop-background.log in the NOOP checkout." with title "NOOP Update"' >/dev/null 2>&1 || true
exit 1
