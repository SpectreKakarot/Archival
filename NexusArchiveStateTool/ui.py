from __future__ import annotations

from pathlib import Path

import mobase
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .file_ops import delete_matches, move_matches
from .install import install_selected_matches
from .logging_utils import LOGGER, configure_logging
from .models import ArchiveMatch
from .scanning import scan_archives, write_archive_report


class ModNameSelectionDialog(QDialog):
    def __init__(
        self,
        selected_matches: list[tuple[int, ArchiveMatch]],
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose Suggested Mod Names")
        self.resize(700, 420)
        self._selected_matches = selected_matches

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Set a suggested mod name for each archive. Fluorine Manager "
                "uses these as its native install name suggestions."
            )
        )

        self._table = QTableWidget(len(selected_matches), 2)
        self._table.setHorizontalHeaderLabels(["Archive", "Suggested mod name"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self._table.horizontalHeader().setStretchLastSection(True)
        for table_row, (_match_row, match) in enumerate(selected_matches):
            archive = match.archive
            assert archive is not None
            archive_item = QTableWidgetItem(archive.name)
            archive_item.setFlags(archive_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(table_row, 0, archive_item)
            self._table.setItem(table_row, 1, QTableWidgetItem(archive.stem))
        self._table.resizeColumnsToContents()
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        buttons.addStretch()
        install_button = QPushButton("Start Installations")
        install_button.clicked.connect(self.accept)
        buttons.addWidget(install_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def name_suggestions(self) -> dict[int, str]:
        suggestions: dict[int, str] = {}
        for table_row, (match_row, _match) in enumerate(self._selected_matches):
            item = self._table.item(table_row, 1)
            suggestions[match_row] = item.text().strip() if item is not None else ""
        return suggestions


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
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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
            "Overwrite existing destination files (replaces matching archives and metadata)"
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

        install_button = QPushButton("Install Selected")
        install_button.clicked.connect(self._install_selected)
        button_layout.addWidget(install_button)

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

    def _install_selected(self) -> None:
        selected_rows = sorted(
            index.row() for index in self._table.selectionModel().selectedRows()
        )
        if not selected_rows:
            QMessageBox.information(
                self, "No Archives Selected", "Select one or more archive rows to install."
            )
            return

        installable_matches = [
            (row, self._matches[row])
            for row in selected_rows
            if 0 <= row < len(self._matches)
            and self._matches[row].archive is not None
        ]
        if not installable_matches:
            QMessageBox.information(
                self,
                "No Installable Archives",
                "The selected rows contain metadata-only entries and no archives.",
            )
            return

        name_dialog = ModNameSelectionDialog(installable_matches, self)
        if name_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name_suggestions = name_dialog.name_suggestions()
        answer = QMessageBox.question(
            self,
            "Confirm Native Installations",
            f"Start {len(installable_matches)} archive installation(s) with the "
            "suggested names you entered? Fluorine Manager will run its normal "
            "native installer flow for each archive.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        installed, issues = install_selected_matches(
            self._matches, selected_rows, self._organizer, name_suggestions
        )
        if issues:
            QMessageBox.warning(
                self,
                "Bulk Install Completed with Issues",
                f"Installed {installed} of {len(installable_matches)} archive(s).\n\n"
                + "\n".join(issues),
            )
        else:
            QMessageBox.information(
                self, "Bulk Install Complete", f"Installed {installed} archive(s)."
            )

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

        destination = Path(destination_text)
        if not destination.is_absolute():
            destination = self._downloads / destination

        answer = QMessageBox.question(
            self,
            "Move Listed Archives",
            f"Move {len(self._matches)} listed items (including metadata-only "
            f"entries) to:\n{destination}\n\n"
            f"Overwrite existing destination files: "
            f"{'Yes' if self._overwrite_existing.isChecked() else 'No'}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        progress = QProgressDialog(
            "Preparing to move listed files...", "", 0, len(self._matches), self
        )
        progress.setWindowTitle("Moving Listed Files")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        progress.show()

        def update_progress(current: int, total: int, name: str) -> None:
            progress.setLabelText(f"Moving {current} of {total}: {name}")
            progress.setValue(current)
            QApplication.processEvents()

        try:
            moved, errors = move_matches(
                self._matches,
                destination,
                overwrite=self._overwrite_existing.isChecked(),
                progress=update_progress,
            )
        except OSError as error:
            QMessageBox.critical(
                self, "Move Failed", f"Could not move files to {destination}:\n{error}"
            )
            return
        finally:
            progress.close()

        if errors:
            QMessageBox.warning(
                self,
                "Move Completed with Errors",
                f"Moved {moved} of {len(self._matches)} items.\n\n"
                + "\n".join(errors),
            )
        else:
            QMessageBox.information(
                self, "Move Complete", f"Moved {moved} listed items."
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
            "This deletes matching archive and metadata pairs, or metadata-only "
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
                self, "Delete Complete", f"Deleted {deleted} listed items."
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
        return "Inspect and manage Nexus/Vortex ZIP, 7z, and RAR archives by metadata state."

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
