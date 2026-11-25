# TODO

- [x] Add an option to move the previous ZIP to an archive folder when a newer
  version is installed.
  - Approach: register a separate `IPluginInstallerSimple` observer through
    `createPlugins()`. It never claims archive support, but uses Fluorine's
    installation-start/end callbacks to match the previous mod by Nexus ID and
    game name, snapshot its version and archive, then confirms a successful
    version increase before moving the old ZIP and optional `.meta` sidecar to
    `Downloads/Archive`. The setting is
    opt-in, matching destination files are not overwritten, and failures are
    logged.
- [x] Move the plugin from a single Python file into a project structure.
  - Approach: split data models, metadata scanning/reporting, file operations,
    logging, install lifecycle logic, and Qt UI into package modules. The package
    `__init__.py` exposes `createPlugins()`; install the whole package directory.
- [x] Add a progress bar when moving listed files.
  - Approach: pass an optional per-item progress callback through the move
    operation and update a modal `QProgressDialog` after each archive/metadata
    group. Keep the operation non-cancellable so the existing per-item rollback
    and completion reporting remain consistent.
