"""Smoke tests for GlossaConfig persistence."""

from pathlib import Path

from glossa.config import (
    GlossaConfig,
    load_hashes,
    load_source_ids,
    save_hashes,
    save_source_ids,
)


def test_config_round_trip(tmp_path: Path) -> None:
    cfg = GlossaConfig(notebook_id="abc123", notebook_title="Test", sources=["a.md", "b.md"])
    cfg.save(tmp_path)

    loaded = GlossaConfig.load(tmp_path)
    assert loaded.notebook_id == "abc123"
    assert loaded.notebook_title == "Test"
    assert loaded.sources == ["a.md", "b.md"]
    assert loaded.is_initialized()


def test_config_load_missing_returns_empty(tmp_path: Path) -> None:
    cfg = GlossaConfig.load(tmp_path)
    assert not cfg.is_initialized()
    assert cfg.notebook_id == ""
    assert cfg.sources == []


def test_hashes_round_trip(tmp_path: Path) -> None:
    save_hashes(tmp_path, {"foo.md": "deadbeef", "bar.md": "cafebabe"})
    loaded = load_hashes(tmp_path)
    assert loaded == {"foo.md": "deadbeef", "bar.md": "cafebabe"}


def test_hashes_missing_returns_empty(tmp_path: Path) -> None:
    assert load_hashes(tmp_path) == {}


def test_source_ids_round_trip(tmp_path: Path) -> None:
    save_source_ids(tmp_path, {"foo.md": "src-uuid-1", "bar.md": "src-uuid-2"})
    loaded = load_source_ids(tmp_path)
    assert loaded == {"foo.md": "src-uuid-1", "bar.md": "src-uuid-2"}


def test_source_ids_missing_returns_empty(tmp_path: Path) -> None:
    assert load_source_ids(tmp_path) == {}
