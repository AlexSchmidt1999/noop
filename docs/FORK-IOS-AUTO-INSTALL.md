# Automatic iOS updates with a Personal Team

A GitHub runner checks the latest stable upstream release every six hours. When a new
release appears, it merges its tag into one candidate branch in this public fork and
dispatches `NOOP security gate`. A later runner promotes the candidate only after
the whole workflow succeeds, including
Gitleaks, mobsfscan, CodeQL, binary policy, and the full MobSF IPA gate. A failed scan,
merge conflict, changed security workflow, changed dependency, or new source capability
leaves the currently approved app installed and requires review. Static scans reduce
risk but cannot prove that new code is harmless.

The Mac checks the fork's main commit every six hours, downloads its exact analyzed
artifact, verifies its commit, report, hashes, and bundle set, signs it with the
Personal Team key in the local login keychain, then installs it on the paired iPhone.
The private key never enters GitHub. The installer re-signs the approved build after
five days; it asks Xcode to renew short-lived provisioning profiles when necessary
using a generated, dependency-free local project with fixed stub source. It never
builds upstream Swift source on the Mac. No GitHub rebuild is needed
for a five-day renewal.

## One-time setup

1. Keep one local checkout of `AlexSchmidt1999/noop` on the Mac. Sign in to GitHub CLI
   and Xcode with the Personal Team. The runner pushes release candidates and main.
2. Pair the iPhone with Xcode, enable Developer Mode, and allow the Mac to reach it
   over Wi-Fi. Confirm `security find-identity -v -p codesigning` shows a valid Apple
   Development identity.
3. Create the gitignored `Config/BundleIdSecrets.xcconfig` with `BUNDLE_ID_PREFIX`
   and `DEVELOPMENT_TEAM`. Set the fork's `IOS_BUNDLE_ID_PREFIX` Actions variable to
   the same prefix. Write the device ID to the gitignored `build/noop-device-id`.
   The installer creates its own small provisioning project when profiles need renewal.
4. Run `python3 scripts/security/enable-background-install.py` while logged in. Its
   user LaunchAgent checks every six hours. The log is `build/noop-background.log`;
   failures also trigger a macOS notification. Dispatch `Update upstream NOOP release`
   on main once to start the first security run. Once the run is fully green, a later
   local check approves and installs it automatically.

The Mac must be on and logged in, with GitHub access and a reachable iPhone. An Apple
account prompt or a disconnected device may delay installation; the agent retries.
Personal Team provisioning profiles expire after seven days, so the five-day renewal
needs to keep running. For an immediate reinstall of the cached build, run
`python3 scripts/security/install-analyzed-ios.py --force`.

The candidate branch is deleted after a successful runner promotion. A blocked
candidate stays in the fork for review. The local agent never signs a red or
incomplete GitHub run.
