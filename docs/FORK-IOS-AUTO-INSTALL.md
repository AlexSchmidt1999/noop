# Personal Team iOS updates in this fork

Build and scan a candidate iOS version once with the manual GitHub Actions workflow.
After reviewing the complete green run, pin its unsigned artifact in the Mac's ignored
`build/noop-approved-ios/` directory. A logged-in Mac reuses this exact artifact every
five days, renews local Personal Team profiles when necessary, signs it again, and
installs it on a paired iPhone with Xcode's device service. The Apple signing key
stays in the Mac's login keychain. No scheduled GitHub rebuild is needed for renewal. Only a run from this public fork can be approved for installation.

## One-time setup

1. Pair the iPhone with Xcode, enable Developer Mode, and confirm that the phone is
   reachable over Wi-Fi. Sign in to Xcode with the Personal Team and create an Apple
   Development certificate. Confirm `security find-identity -v -p codesigning` shows
   one valid identity. If the certificate is present but not valid, check the
   [current WWDR G3 intermediate](https://developer.apple.com/help/account/certificates/wwdr-intermediate-certificates).
2. Create the gitignored `Config/BundleIdSecrets.xcconfig` with `BUNDLE_ID_PREFIX`
   and `DEVELOPMENT_TEAM`. Set the fork's `IOS_BUNDLE_ID_PREFIX` GitHub Actions
   variable to the same prefix. These identifiers are public; the certificate and
   private key must not be placed in the repository or GitHub Actions secrets.
3. Write the paired iPhone's device ID to the gitignored `build/noop-device-id`.
   Run `xcodegen generate` and one signed `NOOPiOS` build with
   `-allowProvisioningUpdates` to create profiles for the four bundles. Confirm the
   app launches on the device and trust the developer identity if iOS asks.
4. Manually dispatch `NOOP security gate` for the candidate branch. After all six
   required jobs, including the full MobSF binary findings gate, pass, approve that
   run with `python3 scripts/security/install-analyzed-ios.py --approve-run RUN_ID
   --branch BRANCH`. Approval downloads and validates the artifact but does not
   contact the iPhone. Keep the resulting `build/noop-approved-ios/` directory; it
   is the durable local copy after GitHub's artifact retention expires.
5. Run `python3 scripts/security/enable-background-install.py` while logged in to
   the Mac. Its user LaunchAgent checks every six hours. The log is
   `build/noop-background.log`; on failure it attempts a macOS notification.

This optional installer needs a persistent local checkout. The Mac must be on, logged in, and able to reach the paired iPhone. GitHub Actions
compiles and scans only when selecting a new stable version. Profile renewal uses an
incremental local Xcode build against the existing checkout; it does not rebuild or
replace the approved GitHub app artifact. The first local build can be substantial.
Personal Team profiles expire after seven days, so the agent re-signs and installs
the same approved app every five days when all services are available. Apple account
prompts or device connectivity failures can still require attention. The agent
retries on its next run.

To install the cached stable build immediately, run
`python3 scripts/security/install-analyzed-ios.py` while the iPhone is reachable.
For a manual renewal test before the five-day interval, add `--force`.
Automatic checks use only the explicitly approved run, even if the source branch
later changes. Approving a newer version requires another full green manual run.
The gate permits only the reviewed local-network ATS finding; see
[the security review](SECURITY_PIPELINE.md) for the remaining lower-severity
CodeQL and MobSF findings.

This is Xcode device installation over the paired local connection. A Personal Team
does not provide an ad hoc distribution profile for a download link or web-based
OTA installation. See [Apple's Personal Team limits](https://developer.apple.com/help/account/basics/about-your-developer-account).

## New upstream releases

A small Ubuntu GitHub Action checks the latest upstream release each Monday. It creates one issue assigned to the repository owner for a version newer than `Config/UpstreamRelease.txt`; it does not build the app. Review the source diff and run the full security workflow only for a chosen candidate. After approving the new scanned artifact locally, update that version file. The existing approved app remains installed while a new candidate is under review.
