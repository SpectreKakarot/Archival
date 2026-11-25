from __future__ import annotations

from pathlib import Path

import mobase

from .file_ops import archive_previous_zip
from .logging_utils import LOGGER, configure_logging
from .models import ArchiveMatch


def _read_archive_identity(archive: Path) -> tuple[int, str] | None:
    metadata = archive.with_name(archive.name + ".meta")
    try:
        flags: dict[str, str] = {}
        for line in metadata.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            key, separator, value = line.partition("=")
            if separator:
                flags[key.strip()] = value.strip()
        mod_id = int(flags.get("modID", ""))
    except (OSError, ValueError):
        return None

    game_name = flags.get("gameName", "")
    return (mod_id, game_name) if mod_id > 0 and game_name else None


def _find_previous_mod(
    organizer: mobase.IOrganizer,
    archive: Path,
    current_mod: mobase.IModInterface | None,
) -> mobase.IModInterface | None:
    identity = _read_archive_identity(archive)
    if identity is None:
        LOGGER.info("Cannot identify Nexus mod for update archive %s", archive)
        return None
    mod_id, game_name = identity

    candidates: list[mobase.IModInterface] = []
    mod_list = organizer.modList()
    for mod_name in mod_list.allMods():
        mod = mod_list.getMod(mod_name)
        if (
            mod is not None
            and mod.nexusId() == mod_id
            and mod.gameName().casefold() == game_name.casefold()
        ):
            candidates.append(mod)

    if current_mod is not None and current_mod.name() not in {
        mod.name() for mod in candidates
    }:
        if (
            current_mod.nexusId() == mod_id
            and current_mod.gameName().casefold() == game_name.casefold()
        ):
            candidates.append(current_mod)

    if len(candidates) != 1:
        LOGGER.info(
            "Expected one previous mod for Nexus ID %d/game %s; found %d",
            mod_id,
            game_name,
            len(candidates),
        )
        return None
    return candidates[0]


def install_selected_matches(
    matches: list[ArchiveMatch],
    selected_rows: list[int],
    organizer: mobase.IOrganizer,
    name_suggestions: dict[int, str] | None = None,
) -> tuple[int, list[str]]:
    installed = 0
    issues: list[str] = []
    rows = sorted(set(selected_rows))
    name_suggestions = name_suggestions or {}
    LOGGER.info("Starting native bulk install for %d selected rows", len(rows))

    for row in rows:
        if row < 0 or row >= len(matches):
            issues.append(f"Selection row {row + 1} is no longer available")
            LOGGER.warning("Skipping invalid selected row: %d", row)
            continue

        match = matches[row]
        if match.archive is None:
            issues.append(f"{match.display_name}: metadata only; no archive to install")
            LOGGER.info("Skipping metadata-only install selection: %s", match.display_name)
            continue

        name_suggestion = name_suggestions.get(row, "").strip()
        try:
            result = organizer.installMod(str(match.archive), name_suggestion)
        except (OSError, RuntimeError, ValueError) as error:
            issue = f"{match.archive.name}: installer error: {error}"
            issues.append(issue)
            LOGGER.exception("Native install failed for %s", match.archive)
            continue

        if result is None:
            issue = f"{match.archive.name}: installation failed or was canceled"
            issues.append(issue)
            LOGGER.warning("Native install returned no installed mod for %s", match.archive)
            continue

        installed += 1
        LOGGER.info(
            "Native install completed for %s with suggested name %r",
            match.archive,
            name_suggestion,
        )

    LOGGER.info(
        "Native bulk install complete: %d installed, %d issues",
        installed,
        len(issues),
    )
    return installed, issues


class NativeInstallObserver(mobase.IPluginInstallerSimple):
    def __init__(self) -> None:
        super().__init__()
        self._organizer: mobase.IOrganizer | None = None
        self._downloads = Path()
        self._previous_archive: Path | None = None
        self._previous_version = ""
        self._new_archive: Path | None = None

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        self._downloads = Path(organizer.downloadsPath())
        configure_logging(self._downloads)
        LOGGER.info("Native install observer initialized")
        return True

    def name(self) -> str:
        return "NexusArchiveInstallObserver"

    def localizedName(self) -> str:
        return self.name()

    def author(self) -> str:
        return "Fluorine Manager"

    def description(self) -> str:
        return (
            "Optionally archives the previous ZIP after a newer version installs "
            "successfully."
        )

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0)

    def requirements(self) -> list[mobase.PluginRequirement]:
        return []

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "archive_previous_zip",
                "Move the previous ZIP and metadata to Downloads/Archive after a newer version installs",
                False,
            )
        ]

    def priority(self) -> int:
        return 0

    def isManualInstaller(self) -> bool:
        return False

    def isArchiveSupported(self, tree: mobase.IFileTree) -> bool:
        return False

    def install(
        self,
        name: mobase.GuessedString,
        tree: mobase.IFileTree,
        version: str,
        nexus_id: int,
    ) -> mobase.InstallResult:
        return mobase.InstallResult.NOT_ATTEMPTED

    def onInstallationStart(
        self,
        archive: str,
        reinstallation: bool,
        current_mod: mobase.IModInterface | None,
    ) -> None:
        self._new_archive = Path(archive)
        self._previous_archive = None
        self._previous_version = ""
        if self._organizer is None:
            return

        try:
            previous_mod = _find_previous_mod(
                self._organizer, self._new_archive, current_mod
            )
            if previous_mod is None:
                return
            previous_version = previous_mod.version()
            if not previous_version.isValid():
                LOGGER.info("Skipping archive-on-update: previous version is invalid")
                return
            previous_archive = previous_mod.installationFile()
        except (AttributeError, RuntimeError, ValueError) as error:
            LOGGER.warning("Could not inspect previous mod version/archive: %s", error)
            return

        if not previous_archive:
            LOGGER.info("Skipping archive-on-update: previous install has no archive path")
            return

        self._previous_archive = Path(previous_archive)
        self._previous_version = previous_version.canonicalString()
        LOGGER.info(
            "Install started: archive=%s previous=%s version=%s reinstallation=%s",
            archive,
            self._previous_archive,
            self._previous_version,
            reinstallation,
        )

    def onInstallationEnd(
        self,
        result: mobase.InstallResult,
        new_mod: mobase.IModInterface | None,
    ) -> None:
        previous_archive = self._previous_archive
        previous_version_text = self._previous_version
        new_archive = self._new_archive
        self._previous_archive = None
        self._previous_version = ""
        self._new_archive = None

        if self._organizer is None or previous_archive is None or new_archive is None:
            return
        if result != mobase.InstallResult.SUCCESS or new_mod is None:
            LOGGER.info("Not archiving previous ZIP: install did not succeed")
            return
        if not self._organizer.pluginSetting(self.name(), "archive_previous_zip"):
            return

        try:
            previous_version = mobase.VersionInfo(previous_version_text)
            installed_version = new_mod.version()
        except (AttributeError, RuntimeError, ValueError) as error:
            LOGGER.warning("Could not compare installed mod versions: %s", error)
            return

        if not previous_version.isValid() or not installed_version.isValid():
            LOGGER.info("Not archiving previous ZIP: one of the versions is invalid")
            return
        if installed_version <= previous_version:
            LOGGER.info(
                "Not archiving previous ZIP: installed version %s is not newer than %s",
                installed_version.canonicalString(),
                previous_version.canonicalString(),
            )
            return

        archived, error = archive_previous_zip(
            self._downloads, previous_archive, new_archive
        )
        if archived:
            LOGGER.info(
                "Archived prior version %s -> Downloads/Archive",
                previous_archive,
            )
        elif error is not None:
            LOGGER.warning("Could not archive prior version: %s", error)
