# Nexus Archive State Tool

Python `IPluginTool` plugin for Fluorine Manager, packaged as a Python plugin directory.

Place the whole `NexusArchiveStateTool` directory in Fluorine Manager's `plugins`
directory to load it. The package exports `createPlugins()` for its tool and native
install observer. The tool scans the active instance's `downloadsPath()` for ZIP, 7z, and RAR archives,
writes `zip_states.txt` there, and provides an optional move destination for matched
archives and `.meta` pairs. It also
lists uninstalled `.meta` sidecars whose corresponding payload file is missing; those
orphan sidecars can be moved by themselves. Moves skip destination conflicts by
default; enable **Overwrite existing destination files** to replace conflicting files.
The **Delete Listed Files** action permanently deletes listed archive/metadata pairs or
metadata-only orphan sidecars after a confirmation prompt.

Select one or more archive rows and choose **Install Selected** to pass them to
Fluorine Manager through `IOrganizer.installMod()`. A dialog lets you provide suggested
mod names before starting; each archive then uses the application's native installer
flow. Metadata-only entries are skipped.

When **NexusArchiveInstallObserver** is enabled and its
**archive_previous_zip** setting is turned on in plugin settings, a successful update
with a strictly newer version moves the previous ZIP and its matching `.meta` sidecar
to `Downloads/Archive`. Existing files are never overwritten.

Moving listed items displays a progress dialog with per-item progress.

Activity is logged to `nexus_archive_state.log` in the downloads folder.
