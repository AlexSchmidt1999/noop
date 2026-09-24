# NOOP iOS security pipeline

This public fork treats each upstream update as untrusted. A passing workflow reduces risk and makes changes visible; **it does not prove that NOOP is non-malicious**. Health and Bluetooth code can transmit data without a new permission, and static analysis cannot prove intent or observe every runtime path.

## Trust boundary

`noop-security.yml` runs on PRs and is dispatched by the scheduled upstream updater when checking a new stable iOS build. It does not run on main pushes or on a schedule, so seven-day Personal Team renewal consumes no GitHub build minutes. No Apple secrets enter source, scanner, or build jobs. The aggregate `security-gate` succeeds only when all five mandatory source/build jobs succeed. An independent Release device build produces the unsigned artifact. The unsigned device build is handed to an optional `trusted-signing` job as an immutable GitHub artifact from the **same workflow run**. That job runs only on a manual dispatch of protected `main` and only when `ENABLE_SIGNING=true`. Set required reviewers on its GitHub Environment. It does not check out the repository; it verifies the run's repository, commit, artifact SHA-256, baseline SHA-256, binary report, and bundle set before reading signing secrets. It then provisions/signs the exact extracted `.app`; the signature and embedded profiles are the only intended changes. A changed workflow on protected main could still subvert this design, so branch protection, code-owner review, and Environment review are essential.

For a free Personal Team, the separate [local Wi-Fi installer](FORK-IOS-AUTO-INSTALL.md) keeps the development key in the Mac login keychain. A complete green runner-dispatched run, including the full MobSF binary findings gate, is verified and cached locally. Each renewal verifies that pinned artifact and its executable hashes, renews short-lived profiles with a fixed local stub project in Xcode, then re-signs and installs over the paired device connection. Upstream app source is never compiled on the Mac during renewal. It does not need a new GitHub run until a new app version is approved. This route does not use the paid `trusted-signing` job.

The previous `fork-testing-build.yml` and `fork-release.yml` release entry points are gated off on this fork. They used to publish an iOS IPA without this security gate. The upstream scheduled branch-pruning job is also gated off because it has ref-deletion permission. Keep these disabled unless redesigned for this fork. Do not sign or install older release assets as trusted outputs.

## Required gates

| Gate | Policy | Artifact |
|---|---|---|
| Source policy | Any entitlement, sensitive Info.plist, target/bundle ID, build script/workflow, SwiftPM manifest/lockfile, or new runtime/build endpoint must match the reviewed baseline. Newly executable files fail. Removed endpoints are reported. | `source-policy` JSON |
| Gitleaks | Scans committed Git history. A finding fails; scanner failure also fails. The artifact contains fingerprints and locations only. | sanitized JSON |
| CodeQL Swift | Builds the iOS simulator target separately for extraction; serious findings fail. | SARIF and gate JSON |
| Dependency Review | Checks pull request dependency changes for high-severity advisories. | workflow check |
| mobsfscan | iOS/Swift SAST, pinned 1.0.0, error-severity findings fail. | SARIF and gate JSON |
| Unsigned device build | XcodeGen, `NOOPiOS` Release for generic iOS device, locked SwiftPM, no signing credentials. The actual `NOOP Staging.app` product is renamed to `NOOP.app` after compilation for the IPA handoff; the bundle contents are unchanged. Build failure fails. | unsigned `.app` tar |
| Binary policy | Requires app, iOS widget, watch app, complication; rejects extra signable bundles, `.framework`, `.dylib`, and unrecognized Mach-O executables. Checks generated sensitive Info.plists against source baseline, rejects URL hosts absent from the reviewed runtime inventory, and verifies all four bundles are unsigned with no effective entitlements. Records linked libraries, SHA-256 and URL host strings. | binary JSON, handoff JSON |
| MobSF IPA | On dispatched runs, scans the exact unsigned IPA in a pinned MobSF v4.5.2 container. Fails for any new high/critical finding, potential secret, tracker, or domain MobSF does not mark clean. The sole reviewed high finding is `NSAllowsLocalNetworking`, required by the user's local-network endpoint; the gate confirms that precise Info.plist setting. | full report and gate JSON |

CodeQL Swift runs in a separate unsigned simulator build and blocks serious findings. Dependency Review runs for pull requests. Dependency manifest changes also require an explicit source-policy baseline update.

Full MobSF IPA analysis runs on runner-dispatched candidate builds after `security-gate`; it is skipped for ordinary PRs because of container size and run time. The local Personal Team installer requires this job to pass at approval time, then reuses the pinned artifact for subsequent renewals. The MobSF job has no Apple secrets. The optional paid `trusted-signing` job still requires its separate Environment review.

In the reviewed 11.8.0 IPA, MobSF found no trackers, secrets, or flagged domains. Its one high finding is the intentional local-network ATS allowance; the four lower-level binary warnings concern C APIs, `malloc`, `@rpath`, and unstripped symbols. The earlier scan of this build in the public fork also reported four CodeQL `UserDefaults` warnings for heart-rate and profile values. These are existing storage choices, not malware detections. Apple advises against storing sensitive information in `UserDefaults`; review or migrate them in a separate app-code change before claiming stronger local privacy guarantees.

No step uses `pull_request_target`. The new workflow declares empty global token permissions, read-only permissions for source jobs, and no CodeQL publishing permission. Actions are pinned to immutable commits. Fork PRs get no signing secrets. No cache is shared with signing. GitHub's artifact service makes same-run uploads immutable; the signing job additionally verifies its downloaded bytes. The manifest records commit, repo, Xcode, Swift, macOS, runner image, SwiftPM resolution hash and artifact hashes. Rebuilding later is not claimed to be bit-for-bit reproducible.

`mobsfscan` and Gitleaks are pattern detectors, not a proof against malicious behavior. The source baseline is deliberately stricter: it makes a new health permission, app group, network host, build script, workflow, or dependency an explicit review event. The binary strings inventory is supplementary and may miss constructed/encrypted destinations or contain harmless package strings.

## Baseline review and upstream updates

The tracked baseline is [`scripts/security/baselines/source.json`](../scripts/security/baselines/source.json). It combines the XcodeGen target definitions with each source entitlement/Info.plist and tracks script/workflow, `.xcconfig`, and SwiftPM file hashes. Runtime and build hosts are separate. The source report shows the path and line of new endpoints. `project.yml` is tracked as a whole in the script policy because a change there may add a build phase, package, entitlement, or signing setting. The scheduled updater may refresh the baseline only when `project.yml` changes solely in its version numbers; all other baseline changes require review.

When automatic promotion stops for review:

1. Bring upstream into a PR against this public fork. Read the `source-policy` artifact and `git diff --name-status upstream/main...HEAD`; check security-sensitive Swift changes under BLE, Health, networking, keychain, and data export paths.
2. Inspect each change to entitlements, Info.plists, endpoint hosts, `Package.swift`/`Package.resolved`, scripts, workflow YAML, new executable files, and new frameworks. Check the binary manifest after the build. A changed script report lists risk-pattern line numbers without exposing line contents; open the diff to inspect them.
3. If an added entitlement or endpoint is justified, update the baseline **in a separate, clearly named review commit**: `python3 scripts/security/policy.py snapshot`. Review the resulting JSON diff and record rationale in the PR. Do the same for any changed build script or dependency. Never run snapshot blindly to make a red job green.
4. Require the owner's review of baseline/workflow changes via CODEOWNERS and a protected-main ruleset. When CI is green, review the aggregate `security-gate` before merging. Do not waive a red check merely because upstream has shipped it.

A newly introduced host may be expected (for example, a user-configurable AI provider), but the review must establish what data is sent and whether the feature is opt-in. An unchanged host does not rule out extra health data sent to it. A changed Swift file under `Strand/BLE`, `Strand/Health`, `StrandiOS`, or `Packages/WhoopStore` deserves manual review even if the baseline passes.

For Gitleaks false positives, add only the reviewed fingerprint to `.gitleaksignore` and explain the reason in the PR. Never suppress a real credential; rotate it and remove it from history where practical. The report artifact omits secret values. mobsfscan supports `// mobsf-ignore: rule_id` for a reviewed line-specific false positive; use sparingly and explain in the PR. Neither suppression file is auto-generated.

The initial fork review found ten `generic-api-key` matches in upstream history. Each referenced a local UserDefaults/SharedPreferences key name or a test key identifier, rather than a credential. Their exact commit fingerprints are documented in `.gitleaksignore`; new occurrences of the same text at other commits/lines still fail.

The first `.xcconfig` inventory introduced two more `generic-api-key` matches on SHA-256 hashes in `source.json`. Those exact fingerprints are also documented in `.gitleaksignore`. A changed config hash creates a new finding and requires fresh review.

## Signing setup

The regular CI and unsigned artifact need no Apple account. To enable the optional **distribution** signing job:

1. Create the `trusted-signing` Environment with required reviewer(s), prevent self-review if available, and restrict deployments to `main`.
2. Protect `main`: require PR review, code-owner review, up-to-date `security-gate`, and block direct pushes. Restrict who can edit workflow and baseline files. Set the repository's default `GITHUB_TOKEN` permission to read-only.
3. Set repository variable `IOS_BUNDLE_ID_PREFIX` to your own reverse-domain prefix, for example `com.example`. The build uses this to generate the ignored `Config/BundleIdSecrets.xcconfig`; it must match all Apple provisioning profiles. Set `ENABLE_SIGNING=true` only after the Environment is protected.
4. Set **Environment secrets**: `SIGNING_P12_BASE64`, `SIGNING_P12_PASSWORD`, `SIGNING_IDENTITY`, `PROFILE_NOOP_IOS_BASE64`, `PROFILE_NOOP_WIDGET_BASE64`, `PROFILE_NOOP_WATCH_BASE64`, and `PROFILE_NOOP_COMPLICATION_BASE64`. Each profile must match its app ID and capabilities. The job generates its own temporary keychain password, uses a temporary keychain, and deletes local signing material after signing.
5. Dispatch `NOOP security gate` on `main`, approve the Environment only after reviewing the report, then download `noop-signed-ios` from that same run. Verify its `.sha256` file. Test on a device before trusting behavior.

The signing job rejects development profiles (`get-task-allow=true`); this is a deliberate safety restriction. It requires the paid Apple Developer distribution/provisioning setup, including HealthKit and the shared App Group for all four components. The Personal Team route uses the paired Mac and Xcode device service instead. TestFlight is intentionally absent: a valid App Store Connect account, registered app IDs, export compliance, and App Store provisioning have not been supplied. Do not put App Store Connect credentials into untrusted jobs.

## Local use and validation

```bash
./scripts/security/run-all.sh
python3 scripts/security/binary.py path/to/NOOP.app --report build/security/binary.json
python3 scripts/security/policy.py check --report build/security/source-policy.json --base-ref upstream/main
```

The first command requires Python 3 and Ruby's bundled YAML parser; no GitHub environment variables. Binary inspection requires macOS tools `file`, `otool`, `codesign`, and `strings`. Gitleaks and mobsfscan can be run locally using the same CLI commands in the workflow; the GitHub runner performs the expensive Swift build. Run `python3 -m py_compile scripts/security/*.py`, `bash -n scripts/security/run-all.sh`, and `actionlint .github/workflows/noop-security.yml` for quick local validation. GitHub Actions must still validate the actual macOS build, artifact handoff, profile compatibility and signing; local syntax checks cannot establish those.

Expected false positives include hardcoded documentation URLs in Swift source, security-related script command text, and mobile SAST rules that lack app-specific context. The host inventory keeps build endpoints separate from runtime endpoints; package-manager metadata is not counted as an app runtime destination. It will not detect a domain assembled at runtime, reached by IP generated at runtime, or hidden in encrypted data. The binary inventory records host strings only and does not prove network use or absence.
