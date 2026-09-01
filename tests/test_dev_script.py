from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from personal_backlog import __version__


class DevelopmentScriptTests(unittest.TestCase):
    def test_development_launcher_runs_the_checkout_module(self) -> None:
        root = Path(__file__).resolve().parents[1]
        launcher = root / "scripts" / "backlog-dev"
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            result = subprocess.run(
                [launcher, "--version"],
                cwd=workdir,
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual((result.returncode, result.stderr), (0, ""))
            self.assertEqual(result.stdout.strip(), f"backlog {__version__}")

            backlog = workdir / "backlog"
            initialized = subprocess.run(
                [launcher, "init", str(backlog)],
                cwd=workdir,
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual((initialized.returncode, initialized.stderr), (0, ""))
            listed = subprocess.run(
                [launcher, "--backlog", str(backlog), "list", "--json"],
                cwd=workdir,
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual((listed.returncode, listed.stderr, listed.stdout.strip()), (0, "", "[]"))


if __name__ == "__main__":
    unittest.main()
