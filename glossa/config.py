"""Glossa runtime config — persisted in .glossa/config.json under the project root."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


CONFIG_DIR = ".glossa"
CONFIG_FILE = "config.json"
HASHES_FILE = "source_hashes.json"


@dataclass
class GlossaConfig:
    """Per-project Glossa config."""

    notebook_id: str = ""
    notebook_title: str = ""
    sources: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, project_root: Path) -> GlossaConfig:
        path = project_root / CONFIG_DIR / CONFIG_FILE
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(**data)

    def save(self, project_root: Path) -> None:
        cfg_dir = project_root / CONFIG_DIR
        cfg_dir.mkdir(exist_ok=True)
        (cfg_dir / CONFIG_FILE).write_text(json.dumps(asdict(self), indent=2))

    def is_initialized(self) -> bool:
        return bool(self.notebook_id)


def hashes_path(project_root: Path) -> Path:
    return project_root / CONFIG_DIR / HASHES_FILE


def load_hashes(project_root: Path) -> dict[str, str]:
    p = hashes_path(project_root)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save_hashes(project_root: Path, hashes: dict[str, str]) -> None:
    p = hashes_path(project_root)
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(hashes, indent=2, sort_keys=True))
