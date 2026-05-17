"""Best-effort scheduler process status helpers."""

from __future__ import annotations

import json
import os
import subprocess


def get_scheduler_processes() -> list[dict[str, str]]:
    """Return processes that look like the ETFEngine scheduler."""
    try:
        if os.name == "nt":
            pattern = "src.scheduler.runner|src\\\\scheduler\\\\runner"
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    f"Where-Object {{ $_.CommandLine -match '{pattern}' }} | "
                    "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
                ),
            ]
            raw = subprocess.check_output(cmd, text=True, timeout=5)
            if not raw.strip():
                return []
            parsed = json.loads(raw)
            items = parsed if isinstance(parsed, list) else [parsed]
            return [
                {
                    "pid": str(item.get("ProcessId", "")),
                    "command": str(item.get("CommandLine", "")),
                }
                for item in items
            ]

        raw = subprocess.check_output(["ps", "-eo", "pid,command"], text=True, timeout=5)
        rows = []
        for line in raw.splitlines():
            if "src.scheduler.runner" in line or "src/scheduler/runner" in line:
                pid, _, command = line.strip().partition(" ")
                rows.append({"pid": pid, "command": command.strip()})
        return rows
    except Exception:
        return []


def is_scheduler_running() -> bool:
    """Whether a scheduler process appears to be running."""
    return bool(get_scheduler_processes())
