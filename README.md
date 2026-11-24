# Nexus Archive State Tool

A Python `IPluginTool` for Fluorine Manager that classifies Nexus/Vortex download
archives from their adjacent `.meta` files.

## Features

- Scans ZIP, 7z, and RAR archives in the active instance's Downloads folder.
- Lists `downloaded` and `uninstalled` metadata states, including orphaned
  uninstalled sidecars with no matching archive.
- Writes `zip_states.txt` and activity logs to the Downloads folder.
- Moves listed archive/metadata pairs or metadata-only sidecars to a chosen folder.
- Optionally overwrites destination conflicts; overwrite is disabled by default.
- Can permanently delete listed files after confirmation.

## Installation

Copy `NexusArchiveStateTool.py` into Fluorine Manager's `plugins` directory, for
example:

```text
~/.local/share/fluorine/bin/plugins/NexusArchiveStateTool.py
```

Restart Fluorine Manager and open the tool from its Tools menu.

## Development

The plugin requires Fluorine Manager's `mobase` Python module and PyQt6. Run its
unit tests in an environment where those imports are available:

```bash
python -m unittest -v test_nexus_archive_state_tool.py
```

See [TODO.md](TODO.md) for planned work.
