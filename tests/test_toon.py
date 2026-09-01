from __future__ import annotations

import unittest

from personal_backlog.toon import dumps


class ToonTests(unittest.TestCase):
    def test_flat_object_uses_toon_primitives_and_quoting(self) -> None:
        value = {
            "id": "T0001",
            "title": "A title, with punctuation",
            "priority": 1,
            "size": None,
            "done": False,
            "body": "Line one\nLine two",
        }
        self.assertEqual(
            dumps(value),
            '\n'.join(
                (
                    "id: T0001",
                    'title: "A title, with punctuation"',
                    "priority: 1",
                    "size: null",
                    "done: false",
                    'body: "Line one\\nLine two"',
                )
            ),
        )

    def test_uniform_task_list_uses_tabular_form(self) -> None:
        value = [
            {"id": "T0001", "title": "First", "priority": 1},
            {"id": "T0002", "title": "Second, quoted", "priority": 2},
        ]
        self.assertEqual(
            dumps(value),
            '[2]{id,title,priority}:\n  T0001,First,1\n  T0002,"Second, quoted",2',
        )

    def test_object_can_contain_empty_and_tabular_arrays(self) -> None:
        self.assertEqual(dumps({"ok": True, "issues": []}), "ok: true\nissues: []")
        self.assertEqual(
            dumps({"ok": False, "issues": [{"file": "bad.md", "error": "bad: value"}]}),
            'ok: false\nissues[1]{file,error}:\n  bad.md,"bad: value"',
        )

    def test_task_list_with_nested_tags_uses_object_items(self) -> None:
        self.assertEqual(
            dumps([{"id": "T0001", "tags": ["bug", "ios"]}]),
            "[1]:\n  -\n    id: T0001\n    tags[2]: bug,ios",
        )

    def test_numbers_are_canonicalized(self) -> None:
        self.assertEqual(dumps({"whole": 1.0, "small": 0.000001}), "whole: 1\nsmall: 0.000001")

    def test_control_characters_use_the_spec_escape_set(self) -> None:
        self.assertEqual(dumps({"value": "a\bb\fc"}), 'value: "a\\u0008b\\u000cc"')


if __name__ == "__main__":
    unittest.main()
