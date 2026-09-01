"""Local listener diagnostics for the web commands."""

from __future__ import annotations

import subprocess


def port_conflict_details(port: int) -> str:
    """Return best-effort process details for local TCP listeners on *port*."""
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpctu"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return f"\nPort {port} is already in use, but process details are unavailable."

    processes: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in result.stdout.splitlines():
        if not line:
            continue
        field, value = line[0], line[1:]
        if field == "p":
            current = {"pid": value}
            processes.append(current)
        elif current is not None and field in {"c", "u"}:
            current[{"c": "command", "u": "user"}[field]] = value

    if not processes:
        return f"\nPort {port} is already in use, but process details are unavailable."

    lines = [f"\nPort {port} is already in use by:"]
    for process in processes:
        pid = process.get("pid", "unknown")
        command = process.get("command", "unknown")
        user = process.get("user", "unknown")
        lines.append(f"- PID {pid}; command {command}; user {user}")
    return "\n".join(lines)
