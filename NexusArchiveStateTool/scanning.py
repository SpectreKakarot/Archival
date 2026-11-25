from __future__ import annotations

from pathlib import Path

from .logging_utils import LOGGER, configure_logging
from .models import ARCHIVE_SUFFIXES, ArchiveMatch


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


def scan_archives(downloads: Path) -> list[ArchiveMatch]:
    configure_logging(downloads)
    LOGGER.info("Scanning downloads folder: %s", downloads)
    matches: list[ArchiveMatch] = []
    for metadata in sorted(downloads.glob("*.meta"), key=lambda path: path.name.lower()):
        archive = metadata.with_name(metadata.name[: -len(".meta")])
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
        "".join(f"{match.state}\t{match.display_name}\n" for match in matches),
        encoding="utf-8",
    )
    LOGGER.info("Wrote archive report: %s (%d entries)", report, len(matches))
    return report
