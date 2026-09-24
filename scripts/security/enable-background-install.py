#!/usr/bin/env python3
"""Install the logged-in user's six-hour NOOP update LaunchAgent."""

from pathlib import Path
import os
import plistlib
import subprocess


root = Path(__file__).resolve().parents[2]
label = "com.alexschmidt1999.noop.personal-update"
destination = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_bytes(plistlib.dumps({
    "Label": label,
    "ProgramArguments": ["/bin/zsh", str(root / "scripts/security/update-noop-background.sh")],
    "RunAtLoad": True,
    "StartInterval": 21600,
    "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
    "WorkingDirectory": str(root),
    "StandardOutPath": str(root / "build/noop-launchd.log"),
    "StandardErrorPath": str(root / "build/noop-launchd.log"),
}))
domain = f"gui/{os.getuid()}"
subprocess.run(["launchctl", "bootout", domain, str(destination)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["launchctl", "bootstrap", domain, str(destination)], check=True)
print(f"Installed {label}: checks every six hours while this Mac user is logged in")
