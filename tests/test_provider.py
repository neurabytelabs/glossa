"""Smoke tests for NotebookLMProvider — subprocess mocked."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from glossa.provider import NotebookLMError, NotebookLMProvider


@patch("glossa.provider.shutil.which", return_value="/usr/local/bin/notebooklm")
def test_provider_construction(_which) -> None:
    p = NotebookLMProvider(notebook_id="nb_xyz")
    assert p.notebook_id == "nb_xyz"
    assert p.name == "NotebookLM"


@patch("glossa.provider.shutil.which", return_value=None)
def test_provider_missing_binary_raises(_which) -> None:
    with pytest.raises(NotebookLMError, match="not found on PATH"):
        NotebookLMProvider(notebook_id="nb_xyz")


@patch("glossa.provider.shutil.which", return_value="/usr/local/bin/notebooklm")
@patch("glossa.provider.subprocess.run")
def test_ask_parses_json(mock_run, _which) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps(
            {
                "answer": "X is the thing.",
                "conversation_id": "conv_1",
                "references": [
                    {"source_id": "src_a", "citation_number": 1, "cited_text": "Snippet A"},
                ],
            }
        ),
        stderr="",
    )

    p = NotebookLMProvider(notebook_id="nb_xyz")
    response = p.ask("What is X?")

    assert response.answer == "X is the thing."
    assert response.conversation_id == "conv_1"
    assert len(response.references) == 1
    assert response.references[0].source_id == "src_a"
    assert response.references[0].cited_text == "Snippet A"


@patch("glossa.provider.shutil.which", return_value="/usr/local/bin/notebooklm")
@patch("glossa.provider.subprocess.run")
def test_ask_raises_on_nonzero_exit(mock_run, _which) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr="auth expired",
    )

    p = NotebookLMProvider(notebook_id="nb_xyz")
    with pytest.raises(NotebookLMError, match="auth expired"):
        p.ask("anything")


@patch("glossa.provider.shutil.which", return_value="/usr/local/bin/notebooklm")
@patch("glossa.provider.subprocess.run")
def test_ask_prepends_system_prompt(mock_run, _which) -> None:
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps({"answer": "ok", "references": []}),
        stderr="",
    )

    p = NotebookLMProvider(notebook_id="nb_xyz")
    p.ask("question?", system="be concise")

    call_args = mock_run.call_args[0][0]
    # prompt arg is index 2: ["notebooklm", "ask", "<merged>", ...]
    assert "be concise" in call_args[2]
    assert "question?" in call_args[2]
