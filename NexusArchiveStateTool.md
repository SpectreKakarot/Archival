# Nexus Archive State Tool

Python `IPluginTool` plugin for Fluorine Manager.

Place `NexusArchiveStateTool.py` in Fluorine Manager's `plugins` directory to load it.
The plugin scans the active instance's `downloadsPath()` for ZIP, 7z, and RAR archives,
writes `zip_states.txt` there, and provides an optional move destination for matched
archives and `.meta` pairs. It also
lists uninstalled `.meta` sidecars whose corresponding payload file is missing; those
orphan sidecars can be moved by themselves. Moves skip destination conflicts by
default; enable **Overwrite existing destination files** to replace conflicting files.
The **Delete Listed Files** action permanently deletes listed archive/metadata pairs or
metadata-only orphan sidecars after a confirmation prompt.

Activity is logged to `nexus_archive_state.log` in the downloads folder.
