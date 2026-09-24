# Reviewed iOS updates with a Personal Team

A GitHub runner checks the latest stable upstream release every six hours. When a new
release appears, it merges its tag into one candidate branch in this public fork and
dispatches `NOOP security gate`. The candidate stays on that branch even if every
scan passes. **Only the owner's explicit approval promotes a new version to `main`
and installs it on the iPhone.** A green scan is necessary, but it is not consent to
update. A failed scan, merge conflict, changed security workflow, changed dependency,
or new source capability leaves the current version in place for review. Static scans
reduce risk but cannot prove that new code is harmless.

The logged-in Mac runs a six-hour LaunchAgent that only renews the **last approved,
locally cached app**. It verifies the pinned artifact and executable hashes, signs
with the Personal Team key in the local login keychain, and re-installs after five
days so the short-lived provisioning profiles do not expire. If needed, Xcode renews
the four profiles with a generated, dependency-free stub project. Renewal never
builds upstream Swift source, fetches a newer app, or changes the approved commit.
The private signing key never enters GitHub.

## One-time setup

1. Keep one local checkout of `AlexSchmidt1999/noop` on the Mac. Sign in to GitHub CLI
   and Xcode with the Personal Team. The runner prepares release candidates; only a
   manual approval command pushes them to `main`.
2. Pair the iPhone with Xcode, enable Developer Mode, and allow the Mac to reach it
   over Wi-Fi. Confirm `security find-identity -v -p codesigning` shows a valid Apple
   Development identity.
3. Create the gitignored `Config/BundleIdSecrets.xcconfig` with `BUNDLE_ID_PREFIX`
   and `DEVELOPMENT_TEAM`. Set the fork's `IOS_BUNDLE_ID_PREFIX` Actions variable to
   the same prefix. Write the device ID to the gitignored `build/noop-device-id`.
   The installer creates its own small provisioning project when profiles need renewal.
4. Run `python3 scripts/security/enable-background-install.py` while logged in. Its
   user LaunchAgent checks the cached approved build every six hours. The log is
   `build/noop-background.log`; failures also trigger a macOS notification. Dispatch
   `Update upstream NOOP release` on `main` once to prepare the first candidate.

## Approving a new version

Review the candidate diff, source-policy report, and the completed security run
before approving. Record its run ID as `RUN_ID`. The candidate must still point to
that run's exact commit. After the owner explicitly accepts the new version, run:

```bash
python3 scripts/security/auto_update.py --promote-run RUN_ID
git pull --ff-only origin main
python3 scripts/security/install-analyzed-ios.py --approve-run RUN_ID --branch codex/auto-upstream-release
python3 scripts/security/install-analyzed-ios.py --force
```

The promotion command rejects an incomplete or failed run, the wrong repository,
branch, workflow, event, or commit, and any missing mandatory security job. The
installer independently verifies the run and analyzed artifact before caching it.
The approval command itself does not install anything; the final command signs and
installs over the existing app. Keep the same bundle ID to preserve its data.

The Mac must be on and logged in, with GitHub access and a reachable iPhone. An Apple
account prompt or a disconnected device may delay installation; after approval, the
agent retries. Personal Team profiles expire after seven days, so keep the five-day
renewal running. To renew the already approved build immediately, run
`python3 scripts/security/install-analyzed-ios.py --force`.

A candidate that has not been approved stays in the fork but never reaches `main`
or the iPhone. An upstream merge preserves the fork's commits if it applies cleanly;
a conflict leaves the candidate unpromoted for manual resolution. Review iPhone
performance again before accepting a release that changes Today or its rendering.
