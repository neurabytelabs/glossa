"""Notebook lifecycle — create, add sources, hash-based incremental sync."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from glossa.config import (
    GlossaConfig,
    load_hashes,
    load_source_ids,
    save_hashes,
    save_source_ids,
)


SOURCE_EXTENSIONS = {".md", ".txt", ".pdf", ".docx", ".rtf", ".html"}
DEFAULT_INDEX_TIMEOUT = 300


class NotebookError(RuntimeError):
    """Raised on notebooklm CLI failures during lifecycle ops."""


@dataclass
class SourceRecord:
    """A single tracked source: path, hash, NotebookLM source_id."""

    path: str
    sha256: str
    source_id: str = ""


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _expand_paths(paths: list[Path]) -> Iterator[Path]:
    """Walk dirs, keep files; only emit files with supported extensions."""
    for p in paths:
        if p.is_file():
            if p.suffix.lower() in SOURCE_EXTENSIONS:
                yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in SOURCE_EXTENSIONS:
                    yield f


def _run(cmd: list[str]) -> dict:
    """Run a notebooklm CLI command expecting JSON output."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise NotebookError(f"{' '.join(cmd[:3])}... failed: {result.stderr.strip()}")
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise NotebookError(f"non-JSON output from {cmd[0]}: {e}") from e


class NotebookManager:
    """Owns the lifecycle of a single Glossa notebook."""

    def __init__(self, project_root: Path, binary: str = "notebooklm") -> None:
        if not shutil.which(binary):
            raise NotebookError(
                f"`{binary}` CLI not found. Install with `pip install notebooklm-py`."
            )
        self.project_root = project_root
        self.binary = binary
        self.config = GlossaConfig.load(project_root)

    def init(
        self,
        source_paths: list[Path],
        title: str = "Glossa Knowledge Base",
        wait_timeout: int = DEFAULT_INDEX_TIMEOUT,
    ) -> None:
        """Create a notebook, upload sources, wait for indexing, persist state."""
        if self.config.is_initialized():
            raise NotebookError(
                f"Notebook already initialized: {self.config.notebook_id}. "
                f"Use `glossa notebook sync` to refresh sources."
            )

        created = _run([self.binary, "create", title, "--json"])
        notebook_id = created.get("notebook", {}).get("id", "")
        if not notebook_id:
            raise NotebookError(f"Notebook create returned no id: {created}")

        files = list(_expand_paths(source_paths))
        if not files:
            raise NotebookError("No supported source files found in given paths.")

        hashes: dict[str, str] = {}
        source_ids: dict[str, str] = {}
        for f in files:
            rel = (
                str(f.relative_to(self.project_root))
                if f.is_relative_to(self.project_root)
                else str(f)
            )
            added = _run(
                [self.binary, "source", "add", str(f), "--notebook", notebook_id, "--json"]
            )
            sid = added.get("source", {}).get("id", "")
            if not sid:
                raise NotebookError(f"source add returned no id for {rel}: {added}")
            hashes[rel] = _hash_file(f)
            source_ids[rel] = sid

        for rel, sid in source_ids.items():
            self._wait_for_source(notebook_id, sid, wait_timeout, rel)

        self.config.notebook_id = notebook_id
        self.config.notebook_title = title
        self.config.sources = sorted(hashes.keys())
        self.config.save(self.project_root)
        save_hashes(self.project_root, hashes)
        save_source_ids(self.project_root, source_ids)

    def sync(self, wait_timeout: int = DEFAULT_INDEX_TIMEOUT) -> dict[str, str]:
        """Hash-based incremental sync. Returns a dict of {path: action}."""
        if not self.config.is_initialized():
            raise NotebookError("No notebook initialized. Run `glossa notebook init` first.")

        old_hashes = load_hashes(self.project_root)
        source_ids = load_source_ids(self.project_root)
        actions: dict[str, str] = {}
        new_hashes: dict[str, str] = {}
        reuploaded: list[tuple[str, str]] = []

        for rel in self.config.sources:
            f = self.project_root / rel
            if not f.exists():
                actions[rel] = "removed (file gone)"
                continue
            current = _hash_file(f)
            new_hashes[rel] = current
            if old_hashes.get(rel) == current:
                actions[rel] = "unchanged"
                continue
            # Re-add. v0.1 limitation: previous version is not deleted server-side.
            added = _run(
                [
                    self.binary,
                    "source",
                    "add",
                    str(f),
                    "--notebook",
                    self.config.notebook_id,
                    "--json",
                ]
            )
            sid = added.get("source", {}).get("id", "")
            if not sid:
                raise NotebookError(f"source add returned no id for {rel}: {added}")
            source_ids[rel] = sid
            reuploaded.append((rel, sid))
            actions[rel] = "re-uploaded"

        for rel, sid in reuploaded:
            self._wait_for_source(self.config.notebook_id, sid, wait_timeout, rel)

        save_hashes(self.project_root, new_hashes)
        save_source_ids(self.project_root, source_ids)
        return actions

    def status(self) -> dict:
        """Snapshot of current notebook state."""
        return {
            "initialized": self.config.is_initialized(),
            "notebook_id": self.config.notebook_id,
            "title": self.config.notebook_title,
            "source_count": len(self.config.sources),
            "sources": self.config.sources,
        }

    def _wait_for_source(self, notebook_id: str, source_id: str, timeout: int, rel: str) -> None:
        """Block until a source finishes indexing, or raise on failure/timeout."""
        result = subprocess.run(
            [
                self.binary,
                "source",
                "wait",
                source_id,
                "--notebook",
                notebook_id,
                "--timeout",
                str(timeout),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return
        if result.returncode == 2:
            raise NotebookError(
                f"timeout waiting for `{rel}` to index "
                f"({timeout}s). Re-run `glossa notebook sync` once ready."
            )
        raise NotebookError(
            f"source wait failed for `{rel}` (exit={result.returncode}): {result.stderr.strip()}"
        )
