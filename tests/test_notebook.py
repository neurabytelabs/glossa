"""Smoke tests for NotebookManager — subprocess mocked against real CLI shapes.

Reference shapes captured from notebooklm CLI 0.3.3:

  $ notebooklm create "T" --json
  {"notebook": {"id": "<uuid>", "title": "T", "created_at": null}}

  $ notebooklm source add ./README.md -n <id> --json
  {"source": {"id": "<uuid>", "title": "README.md", "type": "...", "url": null}}

  $ notebooklm source wait <sid> -n <id> --timeout 180 --json
  {"source_id": "<uuid>", "title": "...", "status": "ready", "status_code": 2}
  # exit 0 ready, 1 fail, 2 timeout
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from glossa.config import load_hashes, load_source_ids
from glossa.notebook import NotebookError, NotebookManager


def _completed(stdout: str = "", stderr: str = "", code: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


def _fake_run_factory(notebook_id: str, source_ids: dict[str, str]):
    """Build a subprocess.run side_effect that emulates notebooklm 0.3.3 JSON shapes.

    `source_ids` maps the file's basename to the source_id we want to return for it.
    """

    def fake_run(cmd, capture_output=True, text=True, check=False):
        # cmd is a list. cmd[0] = binary, cmd[1] = subcommand, ...
        if cmd[1] == "create":
            return _completed(
                stdout=json.dumps(
                    {
                        "notebook": {
                            "id": notebook_id,
                            "title": cmd[2],
                            "created_at": None,
                        }
                    }
                )
            )
        if cmd[1] == "source" and cmd[2] == "add":
            file_path = Path(cmd[3])
            sid = source_ids[file_path.name]
            return _completed(
                stdout=json.dumps(
                    {
                        "source": {
                            "id": sid,
                            "title": file_path.name,
                            "type": "SourceType.MARKDOWN",
                            "url": None,
                        }
                    }
                )
            )
        if cmd[1] == "source" and cmd[2] == "wait":
            sid = cmd[3]
            return _completed(
                stdout=json.dumps(
                    {
                        "source_id": sid,
                        "title": "x",
                        "status": "ready",
                        "status_code": 2,
                    }
                )
            )
        raise AssertionError(f"unexpected command: {cmd}")

    return fake_run


@patch("glossa.notebook.shutil.which", return_value="/usr/local/bin/notebooklm")
@patch("glossa.notebook.subprocess.run")
@patch("subprocess.run")
def test_init_unwraps_envelopes_and_persists_source_ids(
    mock_run_global, mock_run_module, _which, tmp_path: Path
) -> None:
    """init() must unwrap `{"notebook": {...}}` and `{"source": {...}}` envelopes,
    capture source_ids, and persist them alongside hashes."""
    nb_id = "nb-uuid-001"
    src_ids = {"a.md": "src-aaa", "b.md": "subdir-b-id"}

    (tmp_path / "a.md").write_text("# A\nfirst doc.\n")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "b.md").write_text("# B\nsecond doc.\n")

    fake = _fake_run_factory(nb_id, src_ids)
    mock_run_module.side_effect = fake
    mock_run_global.side_effect = fake

    mgr = NotebookManager(project_root=tmp_path)
    mgr.init([tmp_path / "a.md", sub], title="T")

    assert mgr.config.notebook_id == nb_id
    assert mgr.config.notebook_title == "T"
    assert mgr.config.sources == ["a.md", "subdir/b.md"]

    persisted_ids = load_source_ids(tmp_path)
    assert persisted_ids == {"a.md": "src-aaa", "subdir/b.md": "subdir-b-id"}

    persisted_hashes = load_hashes(tmp_path)
    assert set(persisted_hashes.keys()) == {"a.md", "subdir/b.md"}


@patch("glossa.notebook.shutil.which", return_value="/usr/local/bin/notebooklm")
@patch("glossa.notebook.subprocess.run")
@patch("subprocess.run")
def test_init_calls_source_wait_per_source(
    mock_run_global, mock_run_module, _which, tmp_path: Path
) -> None:
    """init() must call `notebooklm source wait` once per added source."""
    (tmp_path / "only.md").write_text("hi")

    fake = _fake_run_factory("nb-1", {"only.md": "src-only"})
    mock_run_module.side_effect = fake
    mock_run_global.side_effect = fake

    mgr = NotebookManager(project_root=tmp_path)
    mgr.init([tmp_path / "only.md"], title="T")

    wait_calls = [
        c
        for c in list(mock_run_module.call_args_list) + list(mock_run_global.call_args_list)
        if len(c.args[0]) >= 3 and c.args[0][1] == "source" and c.args[0][2] == "wait"
    ]
    assert wait_calls, "source wait was never invoked"
    cmd = wait_calls[0].args[0]
    assert "src-only" in cmd
    assert "--notebook" in cmd and "nb-1" in cmd
    assert "--timeout" in cmd


@patch("glossa.notebook.shutil.which", return_value="/usr/local/bin/notebooklm")
@patch("glossa.notebook.subprocess.run")
@patch("subprocess.run")
def test_init_raises_when_create_returns_no_id(
    mock_run_global, mock_run_module, _which, tmp_path: Path
) -> None:
    """If `create --json` envelope is missing or empty, init must raise."""
    (tmp_path / "x.md").write_text("x")

    def fake(cmd, **_):
        if cmd[1] == "create":
            return _completed(stdout=json.dumps({"notebook": {}}))
        return _completed(stdout="{}")

    mock_run_module.side_effect = fake
    mock_run_global.side_effect = fake

    mgr = NotebookManager(project_root=tmp_path)
    with pytest.raises(NotebookError, match="returned no id"):
        mgr.init([tmp_path / "x.md"])


@patch("glossa.notebook.shutil.which", return_value="/usr/local/bin/notebooklm")
@patch("glossa.notebook.subprocess.run")
@patch("subprocess.run")
def test_wait_timeout_raises_with_helpful_message(
    mock_run_global, mock_run_module, _which, tmp_path: Path
) -> None:
    """source wait exit=2 (timeout) must be surfaced as NotebookError."""
    (tmp_path / "slow.md").write_text("zzz")

    def fake(cmd, **_):
        if cmd[1] == "create":
            return _completed(stdout=json.dumps({"notebook": {"id": "nb-t"}}))
        if cmd[1] == "source" and cmd[2] == "add":
            return _completed(stdout=json.dumps({"source": {"id": "src-slow"}}))
        if cmd[1] == "source" and cmd[2] == "wait":
            return _completed(code=2, stderr="timeout")
        return _completed()

    mock_run_module.side_effect = fake
    mock_run_global.side_effect = fake

    mgr = NotebookManager(project_root=tmp_path)
    with pytest.raises(NotebookError, match="timeout waiting"):
        mgr.init([tmp_path / "slow.md"], wait_timeout=1)


@patch("glossa.notebook.shutil.which", return_value="/usr/local/bin/notebooklm")
@patch("glossa.notebook.subprocess.run")
@patch("subprocess.run")
def test_sync_unchanged_skips_reupload(
    mock_run_global, mock_run_module, _which, tmp_path: Path
) -> None:
    """Hash-stable files must report `unchanged` and not call source add."""
    f = tmp_path / "doc.md"
    f.write_text("stable")

    fake = _fake_run_factory("nb-2", {"doc.md": "src-doc"})
    mock_run_module.side_effect = fake
    mock_run_global.side_effect = fake

    mgr = NotebookManager(project_root=tmp_path)
    mgr.init([f], title="T")

    mock_run_module.reset_mock()
    mock_run_global.reset_mock()
    mock_run_module.side_effect = fake
    mock_run_global.side_effect = fake

    actions = mgr.sync()
    assert actions == {"doc.md": "unchanged"}
    add_calls = [
        c
        for c in list(mock_run_module.call_args_list) + list(mock_run_global.call_args_list)
        if len(c.args[0]) >= 3 and c.args[0][1] == "source" and c.args[0][2] == "add"
    ]
    assert add_calls == []
