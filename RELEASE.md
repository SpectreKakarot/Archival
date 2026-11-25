# Release Guide

There are no published releases yet. This guide describes how to prepare a
release of the Nexus Archive State Tool.

## Before release

- Choose a version and update the plugin version returned by both plugin classes
  in `NexusArchiveStateTool/`.
- Move the corresponding changes from the `Unreleased` section of
  [CHANGELOG.md](CHANGELOG.md) into a versioned section with the release date.
- Run the unit tests in an environment that provides Fluorine Manager's `mobase`
  module and PyQt6:

  ```bash
  python -m unittest -v test_nexus_archive_state_tool.py
  ```

- Check the final changes for whitespace errors:

  ```bash
  git diff --check
  ```

- Optionally validate the GitHub Actions workflow with Ruby in Docker. This
  requires Docker access but does not install Ruby on the host:

  ```bash
  bash scripts/check_release_workflow.sh
  ```

  The script writes its output to the ignored `release-workflow-check.log` in
  the repository root.

## Package

Distribute the complete `NexusArchiveStateTool/` directory, preserving its
Python files and directory name. Do not package only `__init__.py`; Fluorine
Manager loads the package through its `createPlugins()` entry point. Include
`README.md` or the plugin documentation if publishing a source bundle.

Users install the package directory under Fluorine Manager's `plugins`
directory, restart the application, and open **Nexus Archive State Tool** from
the Tools menu. The previous-version ZIP archiving observer is opt-in and must
be enabled in plugin settings.

## Publish

After review and validation, commit the release changes and create a version
tag. Create and publish a GitHub Release for that tag; the workflow in
`.github/workflows/release.yml` will package the entire plugin directory as
`NexusArchiveStateTool.zip` and attach it to the release. The ZIP preserves the
`NexusArchiveStateTool/` directory at its root.

Do not describe the release as verified unless the tests and installation have
been checked in the target Fluorine Manager environment.
