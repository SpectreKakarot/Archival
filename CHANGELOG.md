# Changelog

Notable changes to the Nexus Archive State Tool are documented here.

## Unreleased

- Organize the Fluorine Manager plugin as a `NexusArchiveStateTool` Python
  package with separate modules for the UI, scanning, file operations, logging,
  and install lifecycle handling.
- Scan ZIP, 7z, and RAR downloads, classify archive metadata states, and include
  orphaned uninstalled metadata sidecars.
- Support multi-select installation through Fluorine Manager's native installer,
  with suggested mod names before installation.
- Add optional archiving of the previous ZIP and metadata sidecar after a newer
  version of the same mod installs successfully. This setting is disabled by
  default.
- Add per-item progress when moving listed files.
- Document package installation and add unit tests for plugin behavior.
