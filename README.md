# Nexus Archive State Tool

A Python plugin package for Fluorine Manager: an `IPluginTool` that classifies
Nexus/Vortex download archives from adjacent `.meta` files, plus an opt-in install
observer for archiving the previous ZIP after a newer version installs.

## Features

- Scans ZIP, 7z, and RAR archives in the active instance's Downloads folder.
- Lists `downloaded` and `uninstalled` metadata states, including orphaned
  uninstalled sidecars with no matching archive.
- Supports multi-select installation through Fluorine Manager's native installer;
  each selected archive follows its normal installation flow. Before installation,
  you can provide suggested mod names for all selected archives.
- Writes `zip_states.txt` and activity logs to the Downloads folder.
- Moves listed archive/metadata pairs or metadata-only sidecars to a chosen folder.
- Optionally overwrites destination conflicts; overwrite is disabled by default.
- Can permanently delete listed files after confirmation.
- Can optionally move the previous ZIP and sidecar to `Downloads/Archive` after
  installing a newer version of the same Nexus mod.
- Shows per-item progress while moving listed files.

## Installation

Copy the entire `NexusArchiveStateTool` package directory into Fluorine Manager's
`plugins` directory, for example:

```text
~/.local/share/fluorine/bin/plugins/NexusArchiveStateTool/
```

Restart Fluorine Manager and open the tool from its Tools menu. The optional update
archive behavior is configured in Fluorine Manager's plugin settings for
**NexusArchiveInstallObserver** and is disabled by default.

## Development

The plugin requires Fluorine Manager's `mobase` Python module and PyQt6. Run its
unit tests in an environment where those imports are available:

```bash
python -m unittest -v test_nexus_archive_state_tool.py
```

See [TODO.md](TODO.md) for planned work.
