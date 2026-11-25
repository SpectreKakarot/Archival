from __future__ import annotations

import mobase

from .file_ops import archive_previous_zip, delete_matches, move_matches
from .install import NativeInstallObserver, install_selected_matches
from .models import ArchiveMatch
from .scanning import classify_metadata, scan_archives, write_archive_report
from .ui import NexusArchiveStateTool


def createPlugins() -> list[mobase.IPlugin]:
    return [NexusArchiveStateTool(), NativeInstallObserver()]
