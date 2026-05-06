from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WatchState:
    """Estado mínimo para no reprocesar archivos en modo watch."""

    files: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "WatchState":
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        files = raw.get("files", {})
        return cls(files=files if isinstance(files, dict) else {})

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"files": self.files}, ensure_ascii=False, indent=2), encoding="utf-8")

