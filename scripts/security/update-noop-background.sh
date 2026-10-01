#!/bin/zsh
set -u

cd "$(dirname "$0")/../.." || exit 1
failed=0
# New versions are reviewed and approved manually. This agent only renews the
# already approved build before its Personal Team provisioning expires.
python3 scripts/security/auto_update.py --cache-approved-current >> build/noop-background.log 2>&1 || failed=1
if [[ -f build/noop-approved-ios/approval.json ]]; then
  python3 scripts/security/install-analyzed-ios.py >> build/noop-background.log 2>&1 || failed=1
fi

if (( failed == 0 )); then exit 0; fi

/usr/bin/osascript -e 'display notification "Automatic update failed. See build/noop-background.log in the NOOP checkout." with title "NOOP Update"' >/dev/null 2>&1 || true
exit 1
