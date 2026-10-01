#!/usr/bin/env python3
"""Install a green GitHub build with local Personal Team signing.

Run this as the logged-in Mac user. The signing key never leaves the login keychain.
"""

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import subprocess
import tarfile
import tempfile


REPO = "AlexSchmidt1999/noop"
WORKFLOW = "noop-security.yml"
ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "build/noop-last-installed-run.json"
APPROVED = ROOT / "build/noop-approved-ios"
REINSTALL_AFTER = dt.timedelta(days=5)
PARTS = [
    ("Watch/NOOPWatch.app/PlugIns/NOOPWatchComplications.appex", "NOOPWatchComplications", ".noop.watch.complications"),
    ("Watch/NOOPWatch.app", "NOOPWatch", ".noop.watch"),
    ("PlugIns/NOOPWidgets.appex", "NOOPiOSWidgets", ".noop.widgets"),
    (".", "NOOPiOS", ".noop"),
]
REQUIRED_JOBS = {"source-policy", "secrets", "ios-static", "build-unsigned", "codeql-swift", "security-gate", "mobsf-binary"}
PROFILE_DIRS = [
    Path.home() / "Library/Developer/Xcode/UserData/Provisioning Profiles",
    Path.home() / "Library/MobileDevice/Provisioning Profiles",
]


def command(*args, cwd=None, quiet=False):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(map(str, args[:3]))} failed: {result.stderr[-1200:]}")
    if not quiet and result.stderr.strip():
        print(result.stderr.strip())
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derived_data():
    persistent = ROOT / "build/noop-local-dd"
    persistent.mkdir(parents=True, exist_ok=True)
    link = Path("/private/tmp/noop-sign-dd")
    if link.is_symlink():
        if link.resolve() != persistent.resolve():
            raise RuntimeError("Unexpected Xcode cache symlink")
    elif link.exists():
        raise RuntimeError("Unexpected Xcode cache directory")
    else:
        link.symlink_to(persistent, target_is_directory=True)
    return str(link)


def api(path):
    return json.loads(command("gh", "api", path, quiet=True))


def config():
    settings = {}
    for line in (ROOT / "Config/BundleIdSecrets.xcconfig").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("//"):
            key, value = line.split("=", 1)
            settings[key.strip()] = value.strip()
    prefix, team = settings["BUNDLE_ID_PREFIX"], settings["DEVELOPMENT_TEAM"]
    if not re.fullmatch(r"[A-Za-z0-9]+(\.[A-Za-z0-9-]+)+", prefix) or not re.fullmatch(r"[A-Z0-9]{10}", team):
        raise RuntimeError("Invalid local bundle prefix or team ID")
    return prefix, team


def verify_run(run, branch):
    if run["status"] != "completed" or run["conclusion"] != "success":
        raise RuntimeError("GitHub run is not green")
    if run["repository"]["full_name"] != REPO or run["head_branch"] != branch:
        raise RuntimeError("Unexpected repository or branch")
    if run["path"].split("@")[0] != f".github/workflows/{WORKFLOW}":
        raise RuntimeError("Unexpected workflow")
    if run["event"] not in {"push", "workflow_dispatch"}:
        raise RuntimeError("Unexpected workflow event")
    jobs = json.loads(command("gh", "run", "view", str(run["id"]), "--repo", REPO, "--json", "jobs", quiet=True))["jobs"]
    passed = {job["name"] for job in jobs if job["conclusion"] == "success"}
    if not REQUIRED_JOBS <= passed:
        raise RuntimeError(f"Mandatory security jobs missing: {sorted(REQUIRED_JOBS - passed)}")


def extract_verified(artifact, destination, run, prefix, baseline_sha=None):
    handoff = json.loads((artifact / "handoff.json").read_text())
    binary = json.loads((artifact / "binary.json").read_text())
    baseline = json.loads((artifact / "source-baseline.json").read_text())
    if handoff["repository"] != run["repository"]["full_name"] or handoff["commit"] != run["head_sha"] or handoff["bundle_id_prefix"] != prefix:
        raise RuntimeError("Artifact identity mismatch")
    for name, key in [("unsigned-app.tar.gz", "archive_sha256"), ("binary.json", "binary_report_sha256"), ("source-baseline.json", "source_baseline_sha256")]:
        if sha(artifact / name) != handoff[key]:
            raise RuntimeError(f"Artifact hash mismatch: {name}")
    expected_baseline = baseline_sha or sha(ROOT / "scripts/security/baselines/source.json")
    if sha(artifact / "source-baseline.json") != expected_baseline:
        raise RuntimeError("Local reviewed capability baseline differs from GitHub")
    if binary["status"] != "PASS" or binary["failures"]:
        raise RuntimeError("Binary security report is not clean")
    expected = {".", "PlugIns/NOOPWidgets.appex", "Watch/NOOPWatch.app", "Watch/NOOPWatch.app/PlugIns/NOOPWatchComplications.appex"}
    if set(binary["bundles"]) != expected:
        raise RuntimeError("Unexpected app bundle set")
    with tarfile.open(artifact / "unsigned-app.tar.gz", "r:gz") as archive:
        seen = set()
        for member in archive:
            path = PurePosixPath(member.name)
            if path.parts[0] != "NOOP.app" or ".." in path.parts or path.is_absolute() or not (member.isfile() or member.isdir()) or member.name in seen:
                raise RuntimeError("Unsafe or duplicate archive member")
            seen.add(member.name)
        archive.extractall(destination, filter="data")
    app = destination / "NOOP.app"
    for rel, details in binary["bundles"].items():
        executable = PurePosixPath(details["executable"])
        if len(executable.parts) != 1 or executable.name in {".", ".."}:
            raise RuntimeError("Unsafe executable name in binary report")
        bundle = app if rel == "." else app / rel
        if sha(bundle / executable.name) != details["executable_sha256"]:
            raise RuntimeError(f"Executable differs from analyzed binary: {rel}")
    return app, baseline


def approve_run(run_id, branch, prefix):
    """Pin one completed green run locally; future renewals need no GitHub build."""
    from mobsf_binary_gate import check as check_mobsf

    run = api(f"repos/{REPO}/actions/runs/{run_id}")
    verify_run(run, branch)
    APPROVED.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="noop-approval-", dir=APPROVED.parent) as temp:
        scratch = Path(temp)
        artifact = scratch / "artifact"
        report_dir = scratch / "mobsf"
        artifact.mkdir()
        report_dir.mkdir()
        command("gh", "run", "download", str(run_id), "--repo", REPO, "--name", "analyzed-unsigned-ios", "--dir", str(artifact), quiet=True)
        command("gh", "run", "download", str(run_id), "--repo", REPO, "--name", "mobsf-binary-report", "--dir", str(report_dir), quiet=True)
        handoff = json.loads((artifact / "handoff.json").read_text())
        gate = json.loads((report_dir / "gate.json").read_text())
        if gate != {"status": "PASS", "failures": []}:
            raise RuntimeError("MobSF binary findings gate did not pass")
        findings = check_mobsf(json.loads((report_dir / "report.json").read_text()), f"{prefix}.noop")
        if findings:
            raise RuntimeError(f"MobSF report failed local review: {findings}")
        extract_verified(artifact, scratch, run, prefix, handoff["source_baseline_sha256"])
        approval = {
            "repository": REPO,
            "run_id": run_id,
            "commit": run["head_sha"],
            "branch": branch,
            "prefix": prefix,
            "handoff_sha256": sha(artifact / "handoff.json"),
            "gate_sha256": sha(report_dir / "gate.json"),
            "source_baseline_sha256": handoff["source_baseline_sha256"],
            "approved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        (artifact / "gate.json").write_bytes((report_dir / "gate.json").read_bytes())
        (artifact / "approval.json").write_text(json.dumps(approval, indent=2) + "\n")
        previous = APPROVED.with_name(APPROVED.name + "-previous")
        if previous.exists():
            shutil.rmtree(previous)
        if APPROVED.exists():
            APPROVED.rename(previous)
        try:
            artifact.rename(APPROVED)
        except Exception:
            if previous.exists():
                previous.rename(APPROVED)
            raise
        if previous.exists():
            shutil.rmtree(previous)
    print(f"Approved GitHub run {run_id} as the reusable local iOS build")


def approved_build(prefix):
    if not APPROVED.is_dir():
        raise RuntimeError("No approved iOS build; use --approve-run after a full green security run")
    approval = json.loads((APPROVED / "approval.json").read_text())
    if approval["repository"] != REPO or approval["prefix"] != prefix:
        raise RuntimeError("Approved build identity mismatch")
    if sha(APPROVED / "handoff.json") != approval["handoff_sha256"] or sha(APPROVED / "gate.json") != approval["gate_sha256"]:
        raise RuntimeError("Approved build metadata changed")
    if json.loads((APPROVED / "gate.json").read_text()) != {"status": "PASS", "failures": []}:
        raise RuntimeError("Approved MobSF gate is not clean")
    return approval


def profile_records(team, prefix):
    records = []
    expected = {f"{team}.{prefix}{suffix}" for _, _, suffix in PARTS}
    for root in PROFILE_DIRS:
        if not root.exists():
            continue
        for path in root.glob("*.mobileprovision"):
            try:
                data = plistlib.loads(subprocess.check_output(["security", "cms", "-D", "-i", str(path)], stderr=subprocess.DEVNULL))
            except (subprocess.CalledProcessError, ValueError):
                continue
            app_id = data.get("Entitlements", {}).get("application-identifier")
            if app_id in expected:
                records.append((app_id, path, data))
    return records


def profiles(team, prefix):
    result = {}
    for app_id, path, data in profile_records(team, prefix):
        if app_id not in result or data["ExpirationDate"] > result[app_id][1]["ExpirationDate"]:
            result[app_id] = (path, data)
    return result


def safe_provisioning_project(destination, team, prefix):
    """Generate a fixed, dependency-free project; never build downloaded app source."""
    app_source = 'import SwiftUI\n@main struct ProfileApp: App { var body: some Scene { WindowGroup { Text("Profiles") } } }\n'
    widget_source = '''import WidgetKit
import SwiftUI
@main struct ProfileWidget: Widget {
    let kind = "ProfileWidget"
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { _ in Text("Profiles") }
    }
}
struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> Entry { Entry(date: .now) }
    func getSnapshot(in context: Context, completion: @escaping (Entry) -> Void) { completion(Entry(date: .now)) }
    func getTimeline(in context: Context, completion: @escaping (Timeline<Entry>) -> Void) {
        completion(Timeline(entries: [Entry(date: .now)], policy: .never))
    }
}
struct Entry: TimelineEntry { let date: Date }
'''
    for name, source in (("iOSApp", app_source), ("WatchApp", app_source),
                         ("iOSWidget", widget_source), ("WatchWidget", widget_source)):
        (destination / f"{name}.swift").write_text(source)
    group = f"group.{prefix}.noop.staging"
    for name, health in (("iOSApp", True), ("WatchApp", True), ("iOSWidget", False), ("WatchWidget", False)):
        entitlements = {"com.apple.security.application-groups": [group]}
        if health:
            entitlements["com.apple.developer.healthkit"] = True
            entitlements["com.apple.developer.healthkit.access"] = []
        if name == "iOSApp":
            entitlements["com.apple.developer.healthkit.background-delivery"] = True
        (destination / f"{name}.entitlements").write_bytes(plistlib.dumps(entitlements))
    spec = f'''name: NOOPProfiles
settings:
  base:
    DEVELOPMENT_TEAM: {team}
    CODE_SIGN_STYLE: Automatic
    SWIFT_VERSION: "5.0"
targets:
  iOSApp:
    type: application
    platform: iOS
    deploymentTarget: "17.0"
    sources: [iOSApp.swift]
    info:
      path: iOSApp-Info.plist
      properties:
        NSHealthShareUsageDescription: "Profile renewal"
        NSHealthUpdateUsageDescription: "Profile renewal"
    entitlements:
      path: iOSApp.entitlements
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: {prefix}.noop
    dependencies:
      - target: iOSWidget
      - target: WatchApp
  iOSWidget:
    type: app-extension
    platform: iOS
    deploymentTarget: "17.0"
    sources: [iOSWidget.swift]
    info:
      path: iOSWidget-Info.plist
      properties:
        NSExtension:
          NSExtensionPointIdentifier: com.apple.widgetkit-extension
    entitlements:
      path: iOSWidget.entitlements
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: {prefix}.noop.widgets
  WatchApp:
    type: application
    platform: watchOS
    deploymentTarget: "10.0"
    sources: [WatchApp.swift]
    info:
      path: WatchApp-Info.plist
      properties:
        WKApplication: true
        WKCompanionAppBundleIdentifier: {prefix}.noop
        NSHealthShareUsageDescription: "Profile renewal"
        NSHealthUpdateUsageDescription: "Profile renewal"
    entitlements:
      path: WatchApp.entitlements
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: {prefix}.noop.watch
    dependencies:
      - target: WatchWidget
  WatchWidget:
    type: app-extension
    platform: watchOS
    deploymentTarget: "10.0"
    sources: [WatchWidget.swift]
    info:
      path: WatchWidget-Info.plist
      properties:
        NSExtension:
          NSExtensionPointIdentifier: com.apple.widgetkit-extension
    entitlements:
      path: WatchWidget.entitlements
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: {prefix}.noop.watch.complications
'''
    (destination / "project.yml").write_text(spec)
    command("xcodegen", "generate", "--spec", str(destination / "project.yml"), "--project", str(destination), quiet=True)
    return destination / "NOOPProfiles.xcodeproj"


def refresh_profiles_if_needed(team, prefix):
    current = profiles(team, prefix)
    expected = {f"{team}.{prefix}{suffix}" for _, _, suffix in PARTS}
    cutoff = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)
    if current.keys() == expected and all(data["ExpirationDate"].replace(tzinfo=dt.timezone.utc) > cutoff for _, data in current.values()):
        return current
    print("Renewing Personal Team profiles with an incremental local build")
    with tempfile.TemporaryDirectory(prefix="noop-profiles-") as backup_dir:
        moved = []
        for _, path, _ in profile_records(team, prefix):
            backup = Path(backup_dir) / path.name
            path.rename(backup)
            moved.append((backup, path))
        try:
            with tempfile.TemporaryDirectory(prefix="noop-provision-project-") as project_dir:
                project = safe_provisioning_project(Path(project_dir), team, prefix)
                command("xcodebuild", "-quiet", "-project", str(project), "-scheme", "iOSApp", "-configuration", "Release",
                        "-destination", "generic/platform=iOS", "-derivedDataPath", derived_data(),
                        "-allowProvisioningUpdates", "build", cwd=project_dir, quiet=True)
            renewed = profiles(team, prefix)
            if renewed.keys() != expected or any(data["ExpirationDate"].replace(tzinfo=dt.timezone.utc) <= cutoff for _, data in renewed.values()):
                raise RuntimeError("Xcode did not renew all four profiles")
            return renewed
        except Exception:
            for backup, path in moved:
                if not path.exists():
                    backup.rename(path)
            raise


def sign(app, baseline, selected, prefix, team, device, scratch):
    valid = command("security", "find-identity", "-v", "-p", "codesigning", quiet=True)
    identities = set(re.findall(r"\b([0-9A-F]{40})\b", valid))
    for index, (rel, target, suffix) in enumerate(PARTS):
        bundle = app if rel == "." else app / rel
        info = plistlib.loads((bundle / "Info.plist").read_bytes())
        app_id = f"{team}.{prefix}{suffix}"
        if info["CFBundleIdentifier"] != f"{prefix}{suffix}":
            raise RuntimeError(f"Bundle ID mismatch: {target}")
        profile_path, profile = selected[app_id]
        allowed = profile["Entitlements"]
        if profile["TeamIdentifier"] != [team] or allowed["application-identifier"] != app_id or allowed.get("get-task-allow") is not True:
            raise RuntimeError(f"Wrong development profile: {target}")
        if device not in profile.get("ProvisionedDevices", []):
            raise RuntimeError(f"Device is not in profile: {target}")
        if profile["ExpirationDate"].replace(tzinfo=dt.timezone.utc) <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2):
            raise RuntimeError(f"Profile expires too soon: {target}")
        certs = {hashlib.sha1(cert).hexdigest().upper() for cert in profile["DeveloperCertificates"]}
        candidates = identities & certs
        if len(candidates) != 1:
            raise RuntimeError(f"No unique valid local signing identity: {target}")
        requested = baseline["capabilities"][target]["entitlements"]["values"]
        requested = json.loads(json.dumps(requested).replace("$(BUNDLE_ID_PREFIX)", prefix).replace("$(APP_GROUP_ID)", f"group.{prefix}.noop.staging"))
        for key, value in requested.items():
            profile_value = allowed.get(key)
            authorized = set(value) <= set(profile_value or []) if isinstance(value, list) else profile_value == value
            if not authorized:
                raise RuntimeError(f"Profile does not authorize {target}: {key}")
        entitlements = {**requested, "application-identifier": app_id, "com.apple.developer.team-identifier": team, "get-task-allow": True}
        (bundle / "embedded.mobileprovision").write_bytes(profile_path.read_bytes())
        ent_path = scratch / f"{index}.plist"
        ent_path.write_bytes(plistlib.dumps(entitlements))
        command("codesign", "--force", "--sign", next(iter(candidates)), "--entitlements", str(ent_path), str(bundle), quiet=True)
        print(f"Signed {target}")
    command("codesign", "--verify", "--deep", "--strict", str(app), quiet=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--approve-run", type=int, help="Pin a fully scanned GitHub run; does not contact the iPhone")
    parser.add_argument("--device", help="Device ID; defaults to build/noop-device-id")
    parser.add_argument("--force", action="store_true", help="Re-sign and reinstall the approved app even before the five-day interval")
    args = parser.parse_args()
    prefix, team = config()
    if args.approve_run:
        approve_run(args.approve_run, args.branch, prefix)
        return
    approval = approved_build(prefix)
    if STATE.exists() and not args.force:
        state = json.loads(STATE.read_text())
        installed = dt.datetime.fromisoformat(state["installed_at"])
        if state.get("run_id") == approval["run_id"] and dt.datetime.now(dt.timezone.utc) - installed < REINSTALL_AFTER:
            print("Approved build is not due for renewal")
            return
    device = args.device or (ROOT / "build/noop-device-id").read_text().strip()
    if not re.fullmatch(r"[A-Fa-f0-9-]{20,50}", device):
        raise RuntimeError("Invalid or missing local device ID")
    with tempfile.TemporaryDirectory(prefix="noop-install-") as temp:
        scratch = Path(temp)
        app, baseline = extract_verified(APPROVED, scratch, {"head_sha": approval["commit"], "repository": {"full_name": approval["repository"]}}, prefix, approval["source_baseline_sha256"])
        selected = refresh_profiles_if_needed(team, prefix)
        sign(app, baseline, selected, prefix, team, device, scratch)
        command("xcrun", "devicectl", "device", "install", "app", "--device", device, str(app), quiet=True)
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"run_id": approval["run_id"], "commit": approval["commit"], "installed_at": dt.datetime.now(dt.timezone.utc).isoformat()}) + "\n")
        print(f"Re-signed and installed approved GitHub run {approval['run_id']} on the paired iPhone")


if __name__ == "__main__":
    main()
