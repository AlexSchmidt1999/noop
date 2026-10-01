#!/usr/bin/env python3
"""Prepare and scan upstream releases; promote only after owner approval."""

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPO = "AlexSchmidt1999/noop"
WORKFLOW = "noop-security.yml"
BRANCH = "codex/auto-upstream-release"
UPSTREAM = "https://github.com/ryanbr/noop.git"
WORKTREE = ROOT / "build/noop-auto-candidate"
PENDING_CURRENT = ROOT / "build/noop-pending-current-approval.json"
VERSION_LINE = re.compile(r'(?m)^(\s*(?:MARKETING_VERSION|CURRENT_PROJECT_VERSION):\s*)"[^"]+"(\s*)$')


def command(*args, cwd=ROOT, check=True):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(args[:3])} failed: {result.stderr[-1000:]}")
    return result


def git(*args, cwd=ROOT):
    return command("git", *args, cwd=cwd).stdout.strip()


def version_only_project_change(before, after):
    return VERSION_LINE.sub(r'\1"VERSION"\2', before.strip()) == VERSION_LINE.sub(r'\1"VERSION"\2', after.strip())


def policy_allows_auto(failures, before, after):
    return not failures or (failures == ["scripts: changed: project.yml"] and version_only_project_change(before, after))


def release_tag():
    tag = command("gh", "release", "view", "--repo", "ryanbr/noop", "--json", "tagName", "--jq", ".tagName").stdout.strip()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise RuntimeError(f"Unexpected upstream release tag: {tag}")
    return tag


def workflow_run(branch, sha):
    url = f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=100"
    runs = json.loads(command("gh", "api", url).stdout)["workflow_runs"]
    return matching_run(runs, branch, sha)


def matching_run(runs, branch, sha):
    matches = [run for run in runs if run["head_sha"] == sha and run["head_branch"] == branch
               and run["event"] == "workflow_dispatch"]
    return max(matches, key=lambda run: run["id"], default=None)


def dispatch(branch):
    command("gh", "workflow", "run", WORKFLOW, "--repo", REPO, "--ref", branch)
    print(f"Dispatched {WORKFLOW} for {branch}")


def candidate_sha():
    line = git("ls-remote", "--heads", "origin", f"refs/heads/{BRANCH}")
    return line.split()[0] if line else None


def prepare_candidate(tag):
    git("fetch", "--no-tags", UPSTREAM, f"refs/tags/{tag}")
    upstream_sha = git("rev-parse", "FETCH_HEAD^{commit}")
    if WORKTREE.exists():
        raise RuntimeError(f"Stale candidate worktree: {WORKTREE}")
    git("worktree", "add", "--detach", str(WORKTREE), "origin/main")
    try:
        command("git", "-c", "user.name=NOOP Auto Update", "-c", "user.email=auto-update@users.noreply.github.com",
                "merge", "--no-edit", "--no-ff", upstream_sha, cwd=WORKTREE)
        changed = git("diff", "--name-only", "origin/main", "HEAD", "--", ".github/workflows", "scripts/security", cwd=WORKTREE)
        if changed:
            raise RuntimeError(f"Upstream changed security automation: {changed}")
        project = (WORKTREE / "project.yml").read_text()
        version = re.search(r'(?m)^\s*MARKETING_VERSION:\s*"([^"]+)"\s*$', project)
        if not version or tag != f"v{version.group(1)}":
            raise RuntimeError("Release tag and iOS app version disagree")
        (WORKTREE / "Config/UpstreamRelease.txt").write_text(tag + "\n")
        report = WORKTREE / "build/noop-auto-policy.json"
        command("python3", "scripts/security/policy.py", "check", "--report", str(report), cwd=WORKTREE, check=False)
        failures = json.loads(report.read_text())["failures"]
        before = git("show", "origin/main:project.yml", cwd=WORKTREE)
        if not policy_allows_auto(failures, before, project):
            raise RuntimeError("Source policy needs human review: " + "; ".join(failures[:12]))
        if failures:
            command("python3", "scripts/security/policy.py", "snapshot", cwd=WORKTREE)
            command("python3", "scripts/security/policy.py", "check", cwd=WORKTREE)
        git("add", "Config/UpstreamRelease.txt", "scripts/security/baselines/source.json", cwd=WORKTREE)
        if git("diff", "--cached", "--name-only", cwd=WORKTREE):
            command("git", "-c", "user.name=NOOP Auto Update", "-c", "user.email=auto-update@users.noreply.github.com",
                    "commit", "-m", f"ci: record upstream release {tag}", cwd=WORKTREE)
        sha = git("rev-parse", "HEAD", cwd=WORKTREE)
        git("push", "origin", f"{sha}:refs/heads/{BRANCH}", cwd=WORKTREE)
        print(f"Prepared upstream {tag} at {sha}")
    finally:
        git("worktree", "remove", "--force", str(WORKTREE))
    dispatch(BRANCH)


def verify_candidate_run(sha, run):
    if (run.get("head_sha") != sha or run.get("head_branch") != BRANCH
            or run.get("event") != "workflow_dispatch"
            or run.get("repository", {}).get("full_name") != REPO
            or run.get("path", "").split("@")[0] != f".github/workflows/{WORKFLOW}"):
        raise RuntimeError("Run does not match the exact scanned candidate")
    if run["status"] != "completed":
        raise RuntimeError(f"Security run {run['id']} is still running")
    if run["conclusion"] != "success":
        raise RuntimeError(f"Security run {run['id']} did not pass: {run['conclusion']}")


def promote_candidate(sha, run):
    verify_candidate_run(sha, run)
    jobs = json.loads(command("gh", "run", "view", str(run["id"]), "--repo", REPO, "--json", "jobs").stdout)["jobs"]
    passed = {job["name"] for job in jobs if job["conclusion"] == "success"}
    required = {"source-policy", "secrets", "ios-static", "build-unsigned", "codeql-swift", "security-gate", "mobsf-binary"}
    if not required <= passed:
        raise RuntimeError(f"Security jobs missing: {sorted(required - passed)}")
    git("push", "origin", f"{sha}:refs/heads/main")
    git("push", "origin", f":refs/heads/{BRANCH}")
    print(f"Promoted scanned release from run {run['id']}")


def inspect_pending_candidate(sha):
    run = workflow_run(BRANCH, sha)
    if run is None:
        dispatch(BRANCH)
    else:
        print(f"Candidate {sha} has security run {run['id']} ({run['status']}/{run.get('conclusion')}); awaiting owner approval")


def prepare_if_new_release(tag, approved_tag):
    if tag != approved_tag:
        prepare_candidate(tag)
    else:
        print(f"No new upstream release ({tag})")


def cache_approved_current():
    """Cache one already installed, owner-approved main commit after its scan passes."""
    if not PENDING_CURRENT.exists():
        return
    pin = json.loads(PENDING_CURRENT.read_text())
    run_id, sha = pin.get("run_id"), pin.get("commit")
    if type(run_id) is not int or run_id <= 0 or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("Invalid pinned current approval")
    run = json.loads(command("gh", "api", f"repos/{REPO}/actions/runs/{run_id}").stdout)
    if (run.get("head_sha") != sha or run.get("head_branch") != "main"
            or run.get("event") != "workflow_dispatch"
            or run.get("repository", {}).get("full_name") != REPO
            or run.get("path", "").split("@")[0] != f".github/workflows/{WORKFLOW}"):
        raise RuntimeError("Pinned approval does not match the scanned main commit")
    if run["status"] != "completed":
        print(f"Waiting for security run {run_id} of the already installed version")
        return
    if run["conclusion"] != "success":
        raise RuntimeError(f"Security run {run_id} did not pass: {run['conclusion']}")
    command("python3", "scripts/security/install-analyzed-ios.py", "--approve-run", str(run_id), "--branch", "main")
    PENDING_CURRENT.unlink()
    print(f"Cached the already approved iOS commit {sha} for five-day renewal")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only status check")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--runner", action="store_true", help="Prepare and scan releases on a GitHub runner")
    mode.add_argument("--promote-run", type=int, metavar="RUN_ID", help="Promote an explicitly approved green candidate")
    mode.add_argument("--cache-approved-current", action="store_true", help="Cache an explicitly pinned, already installed main commit after its scan passes")
    args = parser.parse_args()
    if args.check:
        tag = release_tag()
        print(f"Upstream {tag}; fork {git('show', 'origin/main:Config/UpstreamRelease.txt')}; candidate {candidate_sha() or 'none'}")
        return
    if args.cache_approved_current:
        cache_approved_current()
        return
    if not (args.runner or args.promote_run):
        parser.error("Specify --runner, --promote-run, or --cache-approved-current")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("The checkout must be clean before automatic updates")
    git("fetch", "origin", "main")
    if args.runner:
        git("checkout", "-B", "main", "origin/main")
    elif git("branch", "--show-current") != "main":
        raise RuntimeError("The local checkout must be on main")
    git("merge", "--ff-only", "origin/main")
    pending = candidate_sha()
    if args.promote_run:
        if not pending:
            raise RuntimeError("No candidate branch to approve")
        run = json.loads(command("gh", "api", f"repos/{REPO}/actions/runs/{args.promote_run}").stdout)
        promote_candidate(pending, run)
        return
    if pending:
        inspect_pending_candidate(pending)
        return
    tag = release_tag()
    approved_tag = (ROOT / "Config/UpstreamRelease.txt").read_text().strip()
    prepare_if_new_release(tag, approved_tag)


if __name__ == "__main__":
    main()
