#!/bin/zsh
set -u

cd "$(dirname "$0")/../.." || exit 1
status=0
python3 scripts/security/auto_update.py --local >> build/noop-background.log 2>&1 || status=1
if [[ -f build/noop-approved-ios/approval.json ]]; then
  python3 scripts/security/install-analyzed-ios.py >> build/noop-background.log 2>&1 || status=1
fi

if (( status == 0 )); then exit 0; fi

/usr/bin/osascript -e 'display notification "Automatic update failed. See build/noop-background.log in the NOOP checkout." with title "NOOP Update"' >/dev/null 2>&1 || true
exit 1
