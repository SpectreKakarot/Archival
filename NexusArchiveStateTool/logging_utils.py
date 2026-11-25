from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger("NexusArchiveStateTool")
LOGGER.setLevel(logging.INFO)


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
