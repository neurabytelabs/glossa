"""NotebookLM provider — thin subprocess wrapper around the `notebooklm` CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any


class NotebookLMError(RuntimeError):
    """Raised when the notebooklm CLI returns a non-zero status."""


@dataclass
class Reference:
    """A single citation in a NotebookLM answer."""

    source_id: str
    citation_number: int
    cited_text: str


@dataclass
class GlossaResponse:
    """The result of a Glossa ask call."""

    answer: str
    references: list[Reference] = field(default_factory=list)
    conversation_id: str = ""
    elapsed_sec: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class NotebookLMProvider:
    """Subprocess wrapper around `notebooklm ask --json`.

    Stateless: each call starts a fresh conversation unless conversation_id is provided.
    """

    def __init__(self, notebook_id: str, binary: str = "notebooklm") -> None:
        if not shutil.which(binary):
            raise NotebookLMError(
                f"`{binary}` CLI not found on PATH. Install with `pip install notebooklm-py` "
                f"and authenticate with `{binary} login`."
            )
        self.notebook_id = notebook_id
        self.binary = binary

    @property
    def name(self) -> str:
        return "NotebookLM"

    def ask(
        self,
        prompt: str,
        system: str | None = None,
        sources: list[str] | None = None,
    ) -> GlossaResponse:
        """Send a single question to the notebook and return the answer.

        Args:
            prompt: The user question.
            system: Optional system-style preamble; prepended to the prompt
                because NotebookLM has no native system slot.
            sources: Optional list of source IDs to scope the question to.
        """
        merged_prompt = f"{system}\n\n{prompt}" if system else prompt

        cmd = [self.binary, "ask", merged_prompt, "--notebook", self.notebook_id, "--json"]
        for sid in sources or []:
            cmd.extend(["-s", sid])

        t0 = time.monotonic()
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        elapsed = time.monotonic() - t0

        if result.returncode != 0:
            raise NotebookLMError(
                f"notebooklm ask failed (exit={result.returncode}): {result.stderr.strip()}"
            )

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise NotebookLMError(f"Invalid JSON from notebooklm CLI: {e}") from e

        refs = [
            Reference(
                source_id=r.get("source_id", ""),
                citation_number=r.get("citation_number", 0),
                cited_text=r.get("cited_text", ""),
            )
            for r in data.get("references", [])
        ]

        return GlossaResponse(
            answer=data.get("answer", ""),
            references=refs,
            conversation_id=data.get("conversation_id", ""),
            elapsed_sec=round(elapsed, 2),
            raw=data,
        )

    def auth_check(self) -> bool:
        """Return True if `notebooklm` reports a valid authenticated session."""
        result = subprocess.run(
            [self.binary, "auth", "check", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return False
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False
        checks = data.get("checks", {})
        return all(checks.get(k) for k in ("storage_exists", "json_valid", "cookies_present"))
