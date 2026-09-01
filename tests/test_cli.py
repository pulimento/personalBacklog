from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personal_backlog.assistant import TaskProposal
from personal_backlog import __version__
from personal_backlog.cli import build_parser, main


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.backlog = self.root / "backlog"
        self.run_cli("init", str(self.backlog))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def command(self, *arguments: str) -> tuple[int, str, str]:
        return self.run_cli("--backlog", str(self.backlog), *arguments)

    def test_json_workflow(self) -> None:
        code, output, _ = self.command(
            "add", "Ship it", "--release", "next", "--size", "M", "--json"
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["id"], "T0001")

        code, _, _ = self.command("update", "1", "--state", "done")
        self.assertEqual(code, 0)
        _, output, _ = self.command("show", "T0001", "--json")
        self.assertIsNotNone(json.loads(output)["done"])

    def test_mutating_commands_emit_json_and_toon(self) -> None:
        code, output, error = self.command("add", "Structured", "--json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["title"], "Structured")

        code, output, error = self.command("update", "1", "--priority", "2", "--toon")
        self.assertEqual((code, error), (0, ""))
        self.assertIn("id: T0001", output)
        self.assertIn("priority: 2", output)

    def test_add_assistant_proposes_before_an_explicit_apply(self) -> None:
        class FakeProvider:
            name = "fake"

            def propose(self, context):
                return TaskProposal("Suggested task", None, 1, "S", "## Context\n\nSuggested.")

        with patch("personal_backlog.cli.get_provider", return_value=FakeProvider()):
            code, output, error = self.command("add-assistant", "Make it important", "--json")
            self.assertEqual((code, error), (0, ""))
            proposal = json.loads(output)
            self.assertFalse(proposal["applied"])
            self.assertEqual(proposal["task"]["title"], "Suggested task")
            _, output, _ = self.command("list", "--json")
            self.assertEqual(json.loads(output), [])

            code, output, error = self.command(
                "add-assistant", "Make it important", "--apply", "--json"
            )
            self.assertEqual((code, error), (0, ""))
            applied = json.loads(output)
            self.assertTrue(applied["applied"])
            self.assertEqual(applied["task"]["id"], "T0001")

    def test_templates_support_structured_fields_and_custom_configuration(self) -> None:
        code, _, error = self.command(
            "add", "Templated", "--template", "standard", "--context", "Why now",
            "--outcome", "Ship it", "--criteria", "Works", "--criteria", "Is documented",
        )
        self.assertEqual((code, error), (0, ""))
        _, output, _ = self.command("show", "1", "--json")
        body = json.loads(output)["body"]
        self.assertIn("## Context\n\nWhy now", body)
        self.assertIn("## Desired outcome\n\nShip it", body)
        self.assertIn("- Works\n- Is documented", body)

        (self.backlog / "backlog.toml").write_text(
            "schema = 1\n\n[templates]\nreview = '''## Review\n\nCheck carefully.\n'''\n",
            encoding="utf-8",
        )
        code, _, error = self.command("add", "Custom", "--template", "review")
        self.assertEqual((code, error), (0, ""))
        _, output, _ = self.command("show", "2", "--json")
        self.assertEqual(json.loads(output)["body"], "## Review\n\nCheck carefully.")

    def test_add_batch_validates_every_task_before_writing(self) -> None:
        source = self.root / "tasks.json"
        source.write_text(
            json.dumps([
                {"title": "First", "priority": 2, "body": "## Context"},
                {"title": "Second", "size": "S", "state": "done"},
            ]),
            encoding="utf-8",
        )
        code, output, error = self.command("add-batch", "--file", str(source), "--json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual([task["id"] for task in json.loads(output)], ["T0001", "T0002"])

        source.write_text(json.dumps([{"title": "Would create"}, {"title": ""}]), encoding="utf-8")
        code, _, error = self.command("add-batch", "--file", str(source))
        self.assertEqual(code, 2)
        self.assertIn("batch task 2", error)
        _, output, _ = self.command("list", "--json")
        self.assertEqual([task["id"] for task in json.loads(output)], ["T0001", "T0002"])

    def test_toon_output(self) -> None:
        self.command("add", "First", "--release", "next", "--tag", "bug", "--tag", "ios")
        self.command("add", "Second, quoted")
        code, output, error = self.command("list", "--toon")
        self.assertEqual((code, error), (0, ""))
        self.assertIn("[2]{id,title,release,priority,size,state,created,done,tags}:", output)
        self.assertIn('T0002,"Second, quoted",null,3,null,todo', output)
        self.assertIn("bug · ios", output)

        _, output, _ = self.command("show", "1", "--toon")
        self.assertIn("id: T0001", output)
        self.assertIn("release: next", output)
        self.assertIn("tags: bug · ios", output)

    def test_nullable_filters_and_updates_do_not_depend_on_sys_argv(self) -> None:
        self.command("add", "Unassigned")
        self.command("add", "Next", "--release", "next")
        _, output, _ = self.command("list", "--release", "none", "--json")
        self.assertEqual([task["title"] for task in json.loads(output)], ["Unassigned"])
        self.command("update", "2", "--release", "none", "--size", "S")
        _, output, _ = self.command("show", "2", "--json")
        self.assertIsNone(json.loads(output)["release"])

    def test_repeatable_optional_tags_can_be_updated_and_cleared(self) -> None:
        code, output, error = self.command("add", "Tagged", "--tag", "bug", "--tag", "ios", "--json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["tags"], ["bug", "ios"])
        code, output, error = self.command("update", "1", "--clear-tags", "--json")
        self.assertEqual((code, error), (0, ""))
        self.assertNotIn("tags", json.loads(output))

    def test_list_filters_by_every_requested_tag_case_insensitively(self) -> None:
        self.command("add", "Bug", "--tag", "bug", "--tag", "web")
        self.command("add", "Web only", "--tag", "web")
        self.command("add", "Other", "--tag", "ios")
        code, output, error = self.command("list", "--tag", "BUG", "--tag", "web", "--json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual([task["title"] for task in json.loads(output)], ["Bug"])

    def test_update_requires_a_change(self) -> None:
        self.command("add", "No-op")
        code, _, error = self.command("update", "1")
        self.assertEqual(code, 2)
        self.assertIn("nothing to update", error)

    def test_priority_is_limited_to_the_five_convention_buckets(self) -> None:
        with self.assertRaises(SystemExit) as error:
            self.command("add", "Not a priority", "--priority", "6")
        self.assertEqual(error.exception.code, 2)

    def test_init_can_add_project_agent_pointer(self) -> None:
        project = self.root / "another-project"
        code, output, error = self.run_cli(
            "init", str(project / "backlog"), "--add-agent-instructions"
        )
        self.assertEqual((code, error), (0, ""))
        self.assertIn("Added backlog instructions", output)
        instructions = (project / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("personal-backlog:start", instructions)
        self.assertIn("use the `backlog` CLI", instructions)

    def test_upgrade_previews_by_default_and_requires_apply(self) -> None:
        (self.backlog / ".version").write_text("0.2.1\n", encoding="utf-8")
        (self.backlog / "README.md").write_text("old\n", encoding="utf-8")
        code, output, error = self.command("upgrade")
        self.assertEqual((code, error), (0, ""))
        self.assertIn(f"0.2.1 → {__version__}", output)
        self.assertIn("Run `backlog upgrade --apply`", output)
        self.assertEqual((self.backlog / "README.md").read_text(encoding="utf-8"), "old\n")

        code, output, error = self.command("upgrade", "--apply", "--json")
        self.assertEqual((code, error), (0, ""))
        result = json.loads(output)
        self.assertTrue(result["applied"])
        self.assertEqual((self.backlog / ".version").read_text(encoding="utf-8"), f"{__version__}\n")

    def test_upgrade_interactively_applies_only_after_yes(self) -> None:
        (self.backlog / ".version").write_text("0.2.1\n", encoding="utf-8")
        (self.backlog / "README.md").write_text("old\n", encoding="utf-8")
        with patch("personal_backlog.cli.sys.stdin.isatty", return_value=True), patch(
            "builtins.input", return_value="y"
        ) as prompt:
            code, output, error = self.command("upgrade")
        self.assertEqual((code, error), (0, ""))
        prompt.assert_called_once_with("Apply now? [y/N] ")
        self.assertIn("Applied changes.", output)
        self.assertEqual((self.backlog / ".version").read_text(encoding="utf-8"), f"{__version__}\n")

    def test_web_command_defaults_to_its_own_port(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["web", "--no-browser"])
        self.assertEqual(args.command, "web")
        self.assertEqual(args.port, 8765)
        self.assertFalse(args.read_only)
        self.assertTrue(args.no_browser)
        help_text = parser.format_help()
        self.assertIn("web                 open the local web app (board and editor)", help_text)
        self.assertIn("serve               open the local web app (alias for web)", help_text)

    def test_web_command_accepts_a_custom_port(self) -> None:
        args = build_parser().parse_args(["web", "--port", "9999", "--read-only"])
        self.assertEqual(args.port, 9999)
        self.assertTrue(args.read_only)


if __name__ == "__main__":
    unittest.main()
