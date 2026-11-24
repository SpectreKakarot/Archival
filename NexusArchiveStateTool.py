from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import mobase
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

LOGGER = logging.getLogger("NexusArchiveStateTool")
LOGGER.setLevel(logging.INFO)
ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar"}


def configure_logging(downloads: Path) -> logging.Logger:
    if not downloads.is_dir():
        return LOGGER

    log_path = downloads / "nexus_archive_state.log"
    for handler in LOGGER.handlers:
        if (
            isinstance(handler, logging.FileHandler)
            and Path(handler.baseFilename) == log_path
        ):
            return LOGGER

    try:
        for handler in list(LOGGER.handlers):
            if isinstance(handler, logging.FileHandler):
                LOGGER.removeHandler(handler)
                handler.close()
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        LOGGER.addHandler(handler)
    except OSError as error:
        LOGGER.warning("Could not open log file %s: %s", log_path, error)
    return LOGGER


def classify_metadata(metadata_path: Path) -> str | None:
    flags: dict[str, str] = {}
    for raw_line in metadata_path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        key, separator, value = raw_line.partition("=")
        if separator:
            flags[key.strip()] = value.strip()

    if flags.get("uninstalled") == "true":
        return "uninstalled"
    if flags.get("installed") == "false" and flags.get("uninstalled") == "false":
        return "downloaded"
    return None


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


def scan_archives(downloads: Path) -> list[ArchiveMatch]:
    configure_logging(downloads)
    LOGGER.info("Scanning downloads folder: %s", downloads)
    matches: list[ArchiveMatch] = []
    for metadata in sorted(downloads.glob("*.meta"), key=lambda path: path.name.lower()):
        archive = metadata.with_name(metadata.name[:-len(".meta")])
        if archive.suffix.lower() not in ARCHIVE_SUFFIXES:
            continue
        try:
            state = classify_metadata(metadata)
        except OSError as error:
            LOGGER.warning("Could not read metadata %s: %s", metadata, error)
            continue
        if state is not None and archive.is_file():
            matches.append(ArchiveMatch(state, archive, metadata))
        elif state == "uninstalled":
            matches.append(ArchiveMatch(state, None, metadata))
            LOGGER.info("Found orphan metadata sidecar: %s", metadata.name)

    matches.sort(key=lambda match: match.display_name.lower())
    LOGGER.info(
        "Scan complete: %d downloaded, %d uninstalled, %d orphan metadata",
        sum(match.state == "downloaded" for match in matches),
        sum(match.state == "uninstalled" for match in matches),
        sum(match.is_orphan_metadata for match in matches),
    )
    return matches


def write_archive_report(downloads: Path, matches: list[ArchiveMatch]) -> Path:
    report = downloads / "zip_states.txt"
    report.write_text(
        "".join(
            f"{match.state}\t{match.display_name}\n" for match in matches
        ),
        encoding="utf-8",
    )
    LOGGER.info("Wrote archive report: %s (%d entries)", report, len(matches))
    return report


def move_matches(
    matches: list[ArchiveMatch], destination: Path, overwrite: bool = False
) -> tuple[int, list[str]]:
    destination.mkdir(parents=True, exist_ok=True)
    moved = 0
    errors: list[str] = []
    LOGGER.info(
        "Moving %d listed items to %s (overwrite=%s)",
        len(matches),
        destination,
        overwrite,
    )

    for match in matches:
        sources = [match.metadata]
        if match.archive is not None:
            sources.insert(0, match.archive)
        targets = [destination / source.name for source in sources]
        label = match.display_name

        missing_sources = [source for source in sources if not source.is_file()]
        if missing_sources:
            message = f"{label}: source file is missing"
            errors.append(message)
            LOGGER.warning("Move skipped: %s", message)
            continue

        if any(source.resolve() == target.resolve() for source, target in zip(sources, targets)):
            message = f"{label}: source and destination are the same"
            errors.append(message)
            LOGGER.warning("Move skipped: %s", message)
            continue

        collisions = [
            target
            for target in targets
            if target.exists() or target.is_symlink()
        ]
        if collisions and not overwrite:
            message = (
                f"{label}: destination file already exists "
                f"({', '.join(path.name for path in collisions)})"
            )
            errors.append(message)
            LOGGER.warning("Move skipped: %s", message)
            continue
        if any(target.is_dir() for target in collisions):
            message = f"{label}: destination contains a directory with a target name"
            errors.append(message)
            LOGGER.warning("Move skipped: %s", message)
            continue

        moved_sources: list[tuple[Path, Path]] = []
        backups: list[tuple[Path, Path]] = []
        try:
            with tempfile.TemporaryDirectory(
                prefix=".archive-state-backup-", dir=destination
            ) as backup_directory:
                backup_root = Path(backup_directory)
                try:
                    for index, target in enumerate(collisions):
                        backup = backup_root / str(index)
                        shutil.move(str(target), str(backup))
                        backups.append((backup, target))

                    for source, target in zip(sources, targets):
                        shutil.move(str(source), str(target))
                        moved_sources.append((source, target))
                except OSError as error:
                    rollback_errors: list[str] = []
                    for source, target in reversed(moved_sources):
                        try:
                            if target.exists():
                                shutil.move(str(target), str(source))
                        except OSError as rollback_error:
                            rollback_errors.append(
                                f"{target.name}: {rollback_error}"
                            )
                    for backup, target in backups:
                        try:
                            if backup.exists():
                                shutil.move(str(backup), str(target))
                        except OSError as rollback_error:
                            rollback_errors.append(
                                f"{target.name}: {rollback_error}"
                            )
                    if rollback_errors:
                        raise OSError(
                            f"{error}; rollback failed: "
                            + "; ".join(rollback_errors)
                        ) from error
                    raise
            moved += 1
            LOGGER.info("Moved listed item: %s", label)
        except OSError as error:
            message = f"{label}: {error}"
            errors.append(message)
            LOGGER.error("Move failed: %s", message)

    LOGGER.info("Move complete: %d moved, %d errors", moved, len(errors))
    return moved, errors


def delete_matches(matches: list[ArchiveMatch]) -> tuple[int, list[str]]:
    deleted = 0
    errors: list[str] = []
    LOGGER.info("Deleting %d listed items", len(matches))

    for match in matches:
        sources = [match.metadata]
        if match.archive is not None:
            sources.insert(0, match.archive)
        removed: list[Path] = []
        try:
            for source in sources:
                source.unlink()
                removed.append(source)
            deleted += 1
            LOGGER.info("Deleted listed item: %s", match.display_name)
        except OSError as error:
            message = f"{match.display_name}: {error}"
            errors.append(message)
            LOGGER.error(
                "Delete failed: %s; %d file(s) already deleted",
                message,
                len(removed),
            )

    LOGGER.info("Delete complete: %d items deleted, %d errors", deleted, len(errors))
    return deleted, errors


class ArchiveStateDialog(QDialog):
    def __init__(self, organizer: mobase.IOrganizer, parent: QWidget | None) -> None:
        super().__init__(parent)
        self._organizer = organizer
        self._downloads = Path(organizer.downloadsPath())
        self._matches: list[ArchiveMatch] = []

        self.setWindowTitle("Nexus Archive States")
        self.resize(760, 480)

        layout = QVBoxLayout(self)
        self._location_label = QLabel()
        layout.addWidget(self._location_label)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["State", "Archive / Metadata"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        destination_layout = QVBoxLayout()
        destination_row = QHBoxLayout()
        destination_row.addWidget(QLabel("Move destination:"))
        self._destination = QLineEdit("To Sort")
        destination_row.addWidget(self._destination)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_destination)
        destination_row.addWidget(browse_button)
        destination_layout.addLayout(destination_row)
        self._overwrite_existing = QCheckBox(
            "Overwrite existing destination files (replaces matching ZIPs and metadata)"
        )
        destination_layout.addWidget(self._overwrite_existing)
        layout.addLayout(destination_layout)

        button_layout = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self._refresh)
        button_layout.addWidget(refresh_button)

        move_button = QPushButton("Move Listed Files")
        move_button.clicked.connect(self._move)
        button_layout.addWidget(move_button)

        delete_button = QPushButton("Delete Listed Files")
        delete_button.clicked.connect(self._delete)
        button_layout.addWidget(delete_button)

        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        self._refresh()

    def _browse_destination(self) -> None:
        destination = QFileDialog.getExistingDirectory(
            self, "Choose Move Destination", str(self._downloads)
        )
        if destination:
            self._destination.setText(destination)

    def _refresh(self) -> None:
        if not self._downloads.is_dir():
            self._location_label.setText(
                f"Downloads folder not found: {self._downloads}"
            )
            self._matches = []
        else:
            self._matches = scan_archives(self._downloads)
            downloaded = sum(match.state == "downloaded" for match in self._matches)
            uninstalled = sum(match.state == "uninstalled" for match in self._matches)
            orphan_metadata = sum(
                match.is_orphan_metadata for match in self._matches
            )
            self._location_label.setText(
                f"{self._downloads}  -  "
                f"{downloaded} downloaded, {uninstalled} uninstalled "
                f"({orphan_metadata} metadata-only)"
            )
            write_archive_report(self._downloads, self._matches)

        self._table.setRowCount(len(self._matches))
        for row, match in enumerate(self._matches):
            state_item = QTableWidgetItem(match.state)
            state_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 0, state_item)
            self._table.setItem(row, 1, QTableWidgetItem(match.display_name))
        self._table.resizeColumnsToContents()

    def _move(self) -> None:
        if not self._matches:
            QMessageBox.information(
                self, "No Matching Archives", "There are no listed archives to move."
            )
            return

        destination_text = self._destination.text().strip()
        if not destination_text:
            QMessageBox.warning(
                self, "Invalid Destination", "Enter or choose a destination folder."
            )
            return

        destination_path = Path(destination_text)
        if not destination_path.is_absolute():
            destination_path = self._downloads / destination_path

        answer = QMessageBox.question(
            self,
            "Move Listed Archives",
            f"Move {len(self._matches)} listed items (including metadata-only "
            f"entries) to:\n"
            f"{destination_path}\n\n"
            f"Overwrite existing destination files: "
            f"{'Yes' if self._overwrite_existing.isChecked() else 'No'}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        moved, errors = move_matches(
            self._matches,
            destination_path,
            overwrite=self._overwrite_existing.isChecked(),
        )
        if errors:
            QMessageBox.warning(
                self,
                "Move Completed with Errors",
                f"Moved {moved} of {len(self._matches)} items.\n\n"
                + "\n".join(errors),
            )
        else:
            QMessageBox.information(
                self,
                "Move Complete",
                f"Moved {moved} listed items.",
            )
        self._refresh()

    def _delete(self) -> None:
        if not self._matches:
            QMessageBox.information(
                self, "No Matching Files", "There are no listed files to delete."
            )
            return

        answer = QMessageBox.warning(
            self,
            "Permanently Delete Listed Files",
            f"Permanently delete {len(self._matches)} listed item(s) from "
            f"the downloads folder?\n\n"
            "This deletes matching ZIP and metadata pairs, or metadata-only "
            "sidecars when the archive is missing. This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        deleted, errors = delete_matches(self._matches)
        if errors:
            QMessageBox.warning(
                self,
                "Delete Completed with Errors",
                f"Deleted {deleted} of {len(self._matches)} listed items.\n\n"
                + "\n".join(errors),
            )
        else:
            QMessageBox.information(
                self,
                "Delete Complete",
                f"Deleted {deleted} listed items.",
            )
        self._refresh()


class NexusArchiveStateTool(mobase.IPluginTool):
    def __init__(self) -> None:
        super().__init__()
        self._organizer: mobase.IOrganizer | None = None
        self._parent: QWidget | None = None
        self._dialog: ArchiveStateDialog | None = None

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        configure_logging(Path(organizer.downloadsPath()))
        LOGGER.info("Plugin initialized")
        return True

    def name(self) -> str:
        return "NexusArchiveStateTool"

    def localizedName(self) -> str:
        return self.displayName()

    def author(self) -> str:
        return "Fluorine Manager"

    def description(self) -> str:
        return (
            "Lists Nexus/Vortex ZIP, 7z, and RAR downloads by metadata state "
            "and optionally moves or deletes the matching files."
        )

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0)

    def requirements(self) -> list[mobase.PluginRequirement]:
        return []

    def settings(self) -> list[mobase.PluginSetting]:
        return []

    def displayName(self) -> str:
        return "Nexus Archive State Tool"

    def tooltip(self) -> str:
        return "Inspect and move Nexus/Vortex ZIP, 7z, and RAR archives by metadata state."

    def icon(self) -> QIcon:
        return QIcon.fromTheme("folder-download")

    def setParentWidget(self, parent: QWidget) -> None:
        self._parent = parent

    def display(self) -> None:
        if self._organizer is None:
            return
        LOGGER.info("Opening Nexus Archive State Tool")
        self._dialog = ArchiveStateDialog(self._organizer, self._parent)
        self._dialog.exec()


def createPlugin() -> mobase.IPlugin:
    return NexusArchiveStateTool()
