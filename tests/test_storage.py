from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from personal_backlog.model import ConflictError, ValidationError
from personal_backlog import __version__
from personal_backlog.storage import (
    VERSION_NAME,
    add_project_agent_instructions,
    check_backlog,
    current_release,
    create_task,
    discover_backlog,
    get_task,
    init_backlog,
    list_tasks,
    parse_task,
    serialize_task,
    task_revision,
    update_task,
    upgrade_backlog,
)


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.backlog = init_backlog(self.root / "backlog")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_init_and_discovery_from_nested_directory(self) -> None:
        nested = self.root / "src" / "feature"
        nested.mkdir(parents=True)
        self.assertEqual(discover_backlog(start=nested), self.backlog)
        self.assertTrue((self.backlog / "README.md").is_file())
        self.assertTrue((self.backlog / "AGENTS.md").is_file())
        self.assertEqual((self.backlog / VERSION_NAME).read_text(encoding="utf-8"), f"{__version__}\n")
        agent_instructions = (self.backlog / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Extracting context from a conversation", agent_instructions)
        self.assertIn("transcript wholesale", agent_instructions)

    def test_project_agent_instructions_are_safe_and_idempotent(self) -> None:
        root_agents = self.root / "AGENTS.md"
        root_agents.write_text("# Existing instructions\n", encoding="utf-8")
        path, changed = add_project_agent_instructions(self.backlog)
        self.assertEqual(path, root_agents.resolve())
        self.assertTrue(changed)
        first = root_agents.read_text(encoding="utf-8")
        self.assertIn("# Existing instructions", first)
        self.assertIn("read `backlog/AGENTS.md`", first)

        _, changed_again = add_project_agent_instructions(self.backlog)
        self.assertFalse(changed_again)
        self.assertEqual(root_agents.read_text(encoding="utf-8"), first)

    def test_upgrade_previews_then_applies_generated_files_and_version_marker(self) -> None:
        (self.backlog / VERSION_NAME).write_text("0.2.1\n", encoding="utf-8")
        (self.backlog / "README.md").write_text("old generated readme\n", encoding="utf-8")
        root_agents = self.root / "AGENTS.md"
        root_agents.write_text("# Project notes\n", encoding="utf-8")

        preview = upgrade_backlog(self.backlog)
        self.assertFalse(preview["applied"])
        self.assertEqual(preview["from_version"], "0.2.1")
        self.assertEqual(preview["to_version"], __version__)
        self.assertEqual((self.backlog / "README.md").read_text(encoding="utf-8"), "old generated readme\n")
        self.assertEqual((self.backlog / VERSION_NAME).read_text(encoding="utf-8"), "0.2.1\n")

        applied = upgrade_backlog(self.backlog, apply=True)
        self.assertTrue(applied["applied"])
        self.assertEqual((self.backlog / VERSION_NAME).read_text(encoding="utf-8"), f"{__version__}\n")
        self.assertIn("Project backlog", root_agents.read_text(encoding="utf-8"))
        self.assertEqual(upgrade_backlog(self.backlog)["changes"], [])

    def test_create_get_and_list_tasks(self) -> None:
        later = create_task(self.backlog, title="Later", priority=4)
        first = create_task(
            self.backlog,
            title="First",
            release="next",
            priority=1,
            size="S",
            body="## Context\n\nImportant.",
        )
        self.assertEqual((later.id, first.id), ("T0001", "T0002"))
        self.assertEqual([task.id for task in list_tasks(self.backlog)], ["T0002", "T0001"])
        self.assertEqual(get_task(self.backlog, "2").body, "## Context\n\nImportant.")

    def test_current_release_uses_the_earliest_release_with_unfinished_work(self) -> None:
        create_task(self.backlog, title="Released", release="1.0.0", state="done")
        current = create_task(self.backlog, title="Current", release="1.1.0")
        next_release = create_task(self.backlog, title="Future", release="next")
        create_task(self.backlog, title="Unassigned")

        self.assertEqual(current_release(self.backlog), "1.1.0")
        update_task(self.backlog, current.id, state="done")
        self.assertEqual(current_release(self.backlog), "next")
        update_task(self.backlog, next_release.id, state="done")
        self.assertIsNone(current_release(self.backlog))

    def test_serialization_round_trip_and_bare_yaml(self) -> None:
        task = create_task(self.backlog, title='A colon: and "quotes"', release="1.0")
        reparsed = parse_task(serialize_task(task))
        self.assertEqual(reparsed.as_dict(), task.as_dict())

        path = next((self.backlog / "tasks").glob("*.md"))
        text = path.read_text(encoding="utf-8").replace('state: "todo"', "state: todo")
        self.assertEqual(parse_task(text).state, "todo")

    def test_state_transitions_manage_done_timestamp(self) -> None:
        task = create_task(self.backlog, title="Finish me")
        done = update_task(self.backlog, task.id, state="done")
        self.assertEqual(done.state, "done")
        self.assertIsNotNone(done.done)
        reopened = update_task(self.backlog, task.id, state="todo")
        self.assertIsNone(reopened.done)

    def test_tags_are_optional_and_round_trip_when_present(self) -> None:
        untagged = create_task(self.backlog, title="No category")
        tagged = create_task(self.backlog, title="Fix it", tags=["bug", "ios"])
        self.assertEqual(untagged.tags, [])
        self.assertNotIn("tags:", serialize_task(untagged))
        self.assertEqual(get_task(self.backlog, tagged.id).tags, ["bug", "ios"])
        self.assertIn('tags: ["bug", "ios"]', serialize_task(tagged))
        updated = update_task(self.backlog, tagged.id, tags=[])
        self.assertEqual(updated.tags, [])

    def test_tags_must_be_unique_non_empty_single_line_strings(self) -> None:
        with self.assertRaises(ValidationError):
            create_task(self.backlog, title="Bad tags", tags=["bug", "Bug"])
        with self.assertRaises(ValidationError):
            create_task(self.backlog, title="Bad tags", tags=[""])

    def test_revision_prevents_lost_update(self) -> None:
        task = create_task(self.backlog, title="Original")
        revision = task_revision(self.backlog, task.id)
        update_task(self.backlog, task.id, title="Changed elsewhere")
        with self.assertRaises(ConflictError):
            update_task(
                self.backlog,
                task.id,
                title="Stale browser change",
                expected_revision=revision,
            )

    def test_validation_reports_file_and_invariants(self) -> None:
        task = create_task(self.backlog, title="Broken soon")
        path = next((self.backlog / "tasks").glob(f"{task.id}-*.md"))
        path.write_text(path.read_text().replace("priority: 3", "priority: 0"))
        issues = check_backlog(self.backlog)
        self.assertEqual(len(issues), 1)
        self.assertIn("priority must be one of 1, 2, 3, 4, or 5", issues[0]["error"])
        with self.assertRaises(ValidationError):
            list_tasks(self.backlog)


if __name__ == "__main__":
    unittest.main()
