# TODO

1. Add an option to move a ZIP file to an archive folder when a new version is
   installed.
   - Approach: use the plugin's install lifecycle hook to identify the archive
     that was successfully installed, then compare its Nexus metadata with the
     previously installed version. When the install is confirmed as a newer
     version, move the ZIP and its matching `.meta` sidecar into an `Archive`
     subfolder under Downloads. Make the behavior opt-in, avoid overwriting
     existing files, and log any move failures.
2. Move the plugin from a single Python file into a project structure.
   - Approach: create a small package with separate modules for the plugin
     interface/UI, archive scanning and metadata classification, file move/delete
     operations, and logging. Keep a thin plugin entry point that exposes
     `createPlugin()`, then update packaging and tests to import the package.
