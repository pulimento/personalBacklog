from __future__ import annotations

from subprocess import CompletedProcess
import unittest
from unittest.mock import patch

from personal_backlog.ports import port_conflict_details


class PortDiagnosticsTests(unittest.TestCase):
    @patch("personal_backlog.ports.subprocess.run")
    def test_reports_pid_command_and_user_for_listening_processes(self, run) -> None:
        run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="p4242\ncpersonal-backlog\nupulimento\np9876\ncnode\nuother\n",
        )

        details = port_conflict_details(8766)

        self.assertIn("Port 8766 is already in use by:", details)
        self.assertIn("PID 4242; command personal-backlog; user pulimento", details)
        self.assertIn("PID 9876; command node; user other", details)

    @patch("personal_backlog.ports.subprocess.run", side_effect=OSError("lsof unavailable"))
    def test_reports_when_process_details_are_unavailable(self, run) -> None:
        self.assertIn("process details are unavailable", port_conflict_details(8766))


if __name__ == "__main__":
    unittest.main()
