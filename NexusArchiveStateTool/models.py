from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar"}


@dataclass(frozen=True)
class ArchiveMatch:
    state: str
    archive: Path | None
    metadata: Path

    @property
    def is_orphan_metadata(self) -> bool:
        return self.archive is None

    @property
    def display_name(self) -> str:
        if self.archive is not None:
            return self.archive.name
        return f"{self.metadata.name} (metadata only)"
