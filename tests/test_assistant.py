from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from personal_backlog.assistant import (
    AppleIntelligenceProvider,
    AssistantError,
    TaskProposal,
    context_for,
)
from personal_backlog.storage import create_task, init_backlog


class AssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.backlog = init_backlog(Path(self.temporary.name) / "backlog")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_context_uses_current_release_and_existing_titles(self) -> None:
        create_task(self.backlog, title="Finished", release="0.8.0", state="done")
        create_task(self.backlog, title="Current", release="0.9.0")
        context = context_for(self.backlog, "Add another task")
        self.assertEqual(context.current_release, "0.9.0")
        self.assertEqual(context.releases, ("0.8.0", "0.9.0"))
        self.assertEqual(context.existing_titles, ("Current", "Finished"))

    def test_proposal_rejects_unknown_release(self) -> None:
        proposal = TaskProposal("A task", "9.9.9", 3, "S", "## Context")
        with self.assertRaises(AssistantError):
            proposal.validate(context_for(self.backlog, "Anything"))

    def test_apple_provider_converts_structured_response(self) -> None:
        provider = AppleIntelligenceProvider()
        response = {
            "title": "Generated task",
            "release": "none",
            "priority": 1,
            "size": "M",
            "body": "## Context\n\nGenerated.",
        }
        with patch.object(provider, "_helper_path", return_value=Path("/tmp/apple-helper")), patch(
            "personal_backlog.assistant.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(response), ""),
        ):
            proposal = provider.propose(context_for(self.backlog, "Top priority task"))
        self.assertEqual(proposal.as_dict()["release"], None)
        self.assertEqual(proposal.priority, 1)
