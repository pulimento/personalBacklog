from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
from importlib.resources import as_file, files
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Protocol

from personal_backlog.model import BacklogError, Task, ValidationError
from personal_backlog.storage import current_release, list_tasks, now_iso, release_sort_key


class AssistantError(BacklogError):
    """A local AI provider could not produce a safe task proposal."""


@dataclass(frozen=True, slots=True)
class AssistantContext:
    request: str
    current_release: str | None
    releases: tuple[str, ...]
    existing_titles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TaskProposal:
    title: str
    release: str | None
    priority: int
    size: str | None
    body: str

    def validate(self, context: AssistantContext) -> None:
        if self.release is not None and self.release not in context.releases:
            raise AssistantError(
                f"provider proposed unknown release {self.release!r}; choose one of: "
                f"{', '.join(context.releases) or 'none'}"
            )
        task = Task(
            id="T0000",
            title=self.title.strip(),
            release=self.release,
            priority=self.priority,
            size=self.size,
            state="todo",
            created=now_iso(),
            done=None,
            body=self.body.strip("\n"),
        )
        try:
            task.validate()
        except ValidationError as exc:
            raise AssistantError(f"provider returned an invalid task: {exc}") from exc

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title.strip(),
            "release": self.release,
            "priority": self.priority,
            "size": self.size,
            "state": "todo",
            "body": self.body.strip("\n"),
        }


class AssistantProvider(Protocol):
    name: str

    def propose(self, context: AssistantContext) -> TaskProposal:
        """Produce one proposal without writing to the backlog."""


def context_for(backlog_dir: Path, request: str) -> AssistantContext:
    tasks = list_tasks(backlog_dir)
    releases = tuple(sorted({task.release for task in tasks if task.release}, key=release_sort_key))
    return AssistantContext(
        request=request,
        current_release=current_release(backlog_dir),
        releases=releases,
        existing_titles=tuple(task.title for task in tasks),
    )


class AppleIntelligenceProvider:
    """Foundation Models bridge for the on-device Apple Intelligence model."""

    name = "apple-intelligence"

    def _helper_path(self) -> Path:
        source = files("personal_backlog.assistant_assets").joinpath("apple_intelligence.swift")
        with ExitStack() as stack:
            source_path = stack.enter_context(as_file(source))
            digest = hashlib.sha256(source_path.read_bytes()).hexdigest()[:16]
            helper = Path(tempfile.gettempdir()) / f"personal-backlog-apple-intelligence-{digest}"
            if helper.is_file() and os.access(helper, os.X_OK):
                return helper
            temporary = helper.with_name(f".{helper.name}-{os.getpid()}")
            result = subprocess.run(
                ["xcrun", "swiftc", "-parse-as-library", str(source_path), "-o", str(temporary)],
                capture_output=True,
                check=False,
                text=True,
            )
            if result.returncode:
                temporary.unlink(missing_ok=True)
                message = result.stderr.strip() or result.stdout.strip() or "unknown compiler error"
                raise AssistantError(f"could not prepare Apple Intelligence provider: {message}")
            os.replace(temporary, helper)
            helper.chmod(0o700)
            return helper

    def propose(self, context: AssistantContext) -> TaskProposal:
        payload = {
            "request": context.request,
            "currentRelease": context.current_release,
            "releases": list(context.releases),
            "existingTitles": list(context.existing_titles),
        }
        try:
            result = subprocess.run(
                [str(self._helper_path())],
                input=json.dumps(payload),
                capture_output=True,
                check=False,
                text=True,
                timeout=90,
            )
        except OSError as exc:
            raise AssistantError(f"could not run Apple Intelligence provider: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AssistantError("Apple Intelligence provider timed out") from exc
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or "unknown provider error"
            raise AssistantError(message.removeprefix("Apple Intelligence provider error: ").strip())
        try:
            generated = json.loads(result.stdout)
            release = generated["release"].strip()
            proposal = TaskProposal(
                title=generated["title"],
                release=None if release.casefold() in {"none", "null", "-"} else release,
                priority=generated["priority"],
                size=generated["size"],
                body=generated["body"],
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AssistantError("Apple Intelligence provider returned an invalid structured response") from exc
        proposal.validate(context)
        return proposal


def get_provider(name: str) -> AssistantProvider:
    providers: dict[str, AssistantProvider] = {AppleIntelligenceProvider.name: AppleIntelligenceProvider()}
    try:
        return providers[name]
    except KeyError as exc:
        raise AssistantError(
            f"unknown assistant provider {name!r}; available providers: {', '.join(sorted(providers))}"
        ) from exc
