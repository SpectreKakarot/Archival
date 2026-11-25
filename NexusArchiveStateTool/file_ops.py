from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from .logging_utils import LOGGER
from .models import ArchiveMatch

ProgressCallback = Callable[[int, int, str], None]


def _move_files(
    sources: list[Path], targets: list[Path], overwrite: bool
) -> str | None:
    label = sources[0].name if sources else "files"
    missing_sources = [source for source in sources if not source.is_file()]
    if missing_sources:
        return f"{label}: source file is missing"

    if any(source.resolve() == target.resolve() for source, target in zip(sources, targets)):
        return f"{label}: source and destination are the same"

    collisions = [target for target in targets if target.exists() or target.is_symlink()]
    if collisions and not overwrite:
        return (
            f"{label}: destination file already exists "
            f"({', '.join(path.name for path in collisions)})"
        )
    if any(target.is_dir() for target in collisions):
        return f"{label}: destination contains a directory with a target name"

    moved_sources: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    destination = targets[0].parent
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
                        rollback_errors.append(f"{target.name}: {rollback_error}")
                for backup, target in backups:
                    try:
                        if backup.exists():
                            shutil.move(str(backup), str(target))
                    except OSError as rollback_error:
                        rollback_errors.append(f"{target.name}: {rollback_error}")
                if rollback_errors:
                    raise OSError(
                        f"{error}; rollback failed: " + "; ".join(rollback_errors)
                    ) from error
                raise
        return None
    except OSError as error:
        return f"{label}: {error}"


def move_matches(
    matches: list[ArchiveMatch],
    destination: Path,
    overwrite: bool = False,
    progress: ProgressCallback | None = None,
) -> tuple[int, list[str]]:
    destination.mkdir(parents=True, exist_ok=True)
    moved = 0
    errors: list[str] = []
    total = len(matches)
    LOGGER.info(
        "Moving %d listed items to %s (overwrite=%s)", total, destination, overwrite
    )

    for index, match in enumerate(matches, start=1):
        sources = [match.metadata]
        if match.archive is not None:
            sources.insert(0, match.archive)
        targets = [destination / source.name for source in sources]
        error = _move_files(sources, targets, overwrite)
        if error is None:
            moved += 1
            LOGGER.info("Moved listed item: %s", match.display_name)
        else:
            errors.append(error)
            LOGGER.warning("Move skipped or failed: %s", error)

        if progress is not None:
            progress(index, total, match.display_name)

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


def archive_previous_zip(
    downloads: Path, previous_archive: Path, new_archive: Path
) -> tuple[bool, str | None]:
    archive_directory = downloads / "Archive"
    try:
        source = previous_archive.resolve(strict=True)
        downloads_root = downloads.resolve(strict=True)
        new_source = new_archive.resolve(strict=True)
    except OSError as error:
        return False, f"Could not resolve install archive paths: {error}"

    if source == new_source:
        return False, "Previous and newly installed archive are the same file"
    if source.suffix.lower() != ".zip":
        return False, f"Previous archive is not a ZIP file: {source.name}"
    if not source.is_relative_to(downloads_root):
        return False, f"Previous archive is outside the Downloads folder: {source}"
    if source.parent == archive_directory.resolve():
        return False, f"Previous archive is already in {archive_directory}"

    sources = [source]
    metadata = source.with_name(source.name + ".meta")
    if metadata.is_file():
        sources.append(metadata)

    try:
        archive_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return False, f"Could not create {archive_directory}: {error}"

    targets = [archive_directory / path.name for path in sources]
    error = _move_files(sources, targets, overwrite=False)
    if error is not None:
        return False, error
    LOGGER.info("Archived previous version ZIP: %s", source)
    return True, None
