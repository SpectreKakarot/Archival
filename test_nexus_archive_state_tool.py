import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import NexusArchiveStateTool as plugin


class NexusArchiveStateToolTests(unittest.TestCase):
    def test_package_factory_registers_tool_and_install_observer(self) -> None:
        plugins = plugin.createPlugins()
        self.assertEqual(len(plugins), 2)
        self.assertIsInstance(plugins[0], plugin.NexusArchiveStateTool)
        self.assertIsInstance(plugins[1], plugin.NativeInstallObserver)
        self.assertFalse(plugins[1].settings()[0].default_value)

    def test_localized_name_does_not_require_qt_tr(self) -> None:
        tool = object.__new__(plugin.NexusArchiveStateTool)
        self.assertEqual(
            tool.localizedName(),
            "Nexus Archive State Tool",
        )

    def test_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)

            downloaded = root / "downloaded.zip.meta"
            downloaded.write_text(
                "installed=false\nuninstalled=false\n", encoding="utf-8"
            )
            uninstalled = root / "uninstalled.zip.meta"
            uninstalled.write_text(
                "installed=true\nuninstalled=true\n", encoding="utf-8"
            )
            unknown = root / "unknown.zip.meta"
            unknown.write_text("installed=true\nuninstalled=false\n", encoding="utf-8")

            self.assertEqual(plugin.classify_metadata(downloaded), "downloaded")
            self.assertEqual(plugin.classify_metadata(uninstalled), "uninstalled")
            self.assertIsNone(plugin.classify_metadata(unknown))

    def test_scan_write_and_move_archives_and_orphan_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            downloaded = root / "downloaded.zip"
            downloaded.write_bytes(b"zip")
            downloaded.with_name(downloaded.name + ".meta").write_text(
                "installed=false\nuninstalled=false\n", encoding="utf-8"
            )

            unclassified = root / "unclassified.zip"
            unclassified.write_bytes(b"zip")
            unclassified.with_name(unclassified.name + ".meta").write_text(
                "installed=true\nuninstalled=false\n", encoding="utf-8"
            )

            orphan_metadata = root / "orphan.zip.meta"
            orphan_metadata.write_text(
                "installed=true\nuninstalled=true\n", encoding="utf-8"
            )

            existing_7z = root / "archive.7z"
            existing_7z.write_bytes(b"archive")
            existing_7z.with_name(existing_7z.name + ".meta").write_text(
                "installed=true\nuninstalled=true\n", encoding="utf-8"
            )
            uninstalled_rar = root / "uninstalled.rar"
            uninstalled_rar.write_bytes(b"archive")
            uninstalled_rar.with_name(uninstalled_rar.name + ".meta").write_text(
                "installed=true\nuninstalled=true\n", encoding="utf-8"
            )

            matches = plugin.scan_archives(root)
            self.assertEqual(
                [
                    (match.state, match.display_name, match.is_orphan_metadata)
                    for match in matches
                ],
                [
                    ("uninstalled", "archive.7z", False),
                    ("downloaded", "downloaded.zip", False),
                    ("uninstalled", "orphan.zip.meta (metadata only)", True),
                    ("uninstalled", "uninstalled.rar", False),
                ],
            )

            report = plugin.write_archive_report(root, matches)
            self.assertEqual(
                report.read_text(encoding="utf-8"),
                "uninstalled\tarchive.7z\n"
                "downloaded\tdownloaded.zip\n"
                "uninstalled\torphan.zip.meta (metadata only)\n"
                "uninstalled\tuninstalled.rar\n",
            )

            destination = root / "To Sort"
            progress: list[tuple[int, int, str]] = []
            moved, errors = plugin.move_matches(
                matches,
                destination,
                progress=lambda current, total, name: progress.append(
                    (current, total, name)
                ),
            )
            self.assertEqual(moved, 4)
            self.assertEqual(errors, [])
            self.assertEqual(
                [current for current, _total, _name in progress],
                [1, 2, 3, 4],
            )
            self.assertTrue(all(total == 4 for _current, total, _name in progress))
            self.assertTrue((destination / "downloaded.zip").is_file())
            self.assertTrue((destination / "downloaded.zip.meta").is_file())
            self.assertTrue((destination / "orphan.zip.meta").is_file())
            self.assertTrue((destination / "archive.7z").is_file())
            self.assertTrue((destination / "archive.7z.meta").is_file())
            self.assertTrue((destination / "uninstalled.rar").is_file())
            self.assertTrue(
                (destination / "uninstalled.rar.meta").is_file()
            )
            self.assertFalse(downloaded.exists())
            self.assertFalse(orphan_metadata.exists())
            self.assertFalse(existing_7z.exists())
            self.assertFalse(existing_7z.with_name(existing_7z.name + ".meta").exists())
            self.assertTrue((root / "nexus_archive_state.log").is_file())

    def test_move_overwrites_existing_archive_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            archive = root / "mod.zip"
            metadata = root / "mod.zip.meta"
            archive.write_bytes(b"new archive")
            metadata.write_text(
                "installed=false\nuninstalled=false\n", encoding="utf-8"
            )
            match = plugin.ArchiveMatch("downloaded", archive, metadata)

            destination = root / "To Sort"
            destination.mkdir()
            (destination / archive.name).write_bytes(b"old archive")
            (destination / metadata.name).write_text("old metadata", encoding="utf-8")

            moved, errors = plugin.move_matches([match], destination, overwrite=True)

            self.assertEqual((moved, errors), (1, []))
            self.assertEqual((destination / archive.name).read_bytes(), b"new archive")
            self.assertEqual(
                (destination / metadata.name).read_text(encoding="utf-8"),
                "installed=false\nuninstalled=false\n",
            )
            self.assertFalse(archive.exists())
            self.assertFalse(metadata.exists())

    def test_delete_removes_archive_pair_and_orphan_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            archive = root / "mod.zip"
            metadata = root / "mod.zip.meta"
            archive.write_bytes(b"zip")
            metadata.write_text("installed=true\nuninstalled=true\n", encoding="utf-8")
            orphan = root / "orphan.zip.meta"
            orphan.write_text("installed=true\nuninstalled=true\n", encoding="utf-8")

            matches = [
                plugin.ArchiveMatch("uninstalled", archive, metadata),
                plugin.ArchiveMatch("uninstalled", None, orphan),
            ]

            deleted, errors = plugin.delete_matches(matches)

            self.assertEqual((deleted, errors), (2, []))
            self.assertFalse(archive.exists())
            self.assertFalse(metadata.exists())
            self.assertFalse(orphan.exists())

    def test_bulk_install_uses_native_installer_for_selected_archives(self) -> None:
        archive_a = Path("/downloads/a.zip")
        archive_b = Path("/downloads/b.7z")
        metadata_a = Path("/downloads/a.zip.meta")
        metadata_b = Path("/downloads/b.7z.meta")
        orphan_metadata = Path("/downloads/orphan.zip.meta")
        matches = [
            plugin.ArchiveMatch("downloaded", archive_a, metadata_a),
            plugin.ArchiveMatch("uninstalled", None, orphan_metadata),
            plugin.ArchiveMatch("uninstalled", archive_b, metadata_b),
        ]
        organizer = Mock()
        organizer.installMod.side_effect = [object(), None]
        name_suggestions = {0: "Chosen A", 2: "Chosen B"}

        installed, issues = plugin.install_selected_matches(
            matches, [2, 1, 0, 0], organizer, name_suggestions
        )

        self.assertEqual(installed, 1)
        self.assertEqual(
            issues,
            [
                "orphan.zip.meta (metadata only): metadata only; no archive to install",
                "b.7z: installation failed or was canceled",
            ],
        )
        self.assertEqual(
            [call.args for call in organizer.installMod.call_args_list],
            [(str(archive_a), "Chosen A"), (str(archive_b), "Chosen B")],
        )

    def test_archive_previous_zip_moves_archive_and_sidecar_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            old_archive = root / "old.zip"
            old_meta = root / "old.zip.meta"
            new_archive = root / "new.zip"
            old_archive.write_bytes(b"old")
            old_meta.write_text("version=1.0\n", encoding="utf-8")
            new_archive.write_bytes(b"new")

            archived, error = plugin.archive_previous_zip(
                root, old_archive, new_archive
            )

            destination = root / "Archive"
            self.assertTrue(archived)
            self.assertIsNone(error)
            self.assertEqual((destination / old_archive.name).read_bytes(), b"old")
            self.assertEqual(
                (destination / old_meta.name).read_text(encoding="utf-8"),
                "version=1.0\n",
            )
            self.assertFalse(old_archive.exists())
            self.assertFalse(old_meta.exists())

    def test_install_observer_archives_old_zip_after_newer_native_install(self) -> None:
        class FakeVersion:
            def __init__(self, value: str) -> None:
                self.value = value

            def isValid(self) -> bool:
                return bool(self.value)

            def canonicalString(self) -> str:
                return self.value

            def __le__(self, other: FakeVersion) -> bool:
                return tuple(map(int, self.value.split("."))) <= tuple(
                    map(int, other.value.split("."))
                )

            def __gt__(self, other: FakeVersion) -> bool:
                return tuple(map(int, self.value.split("."))) > tuple(
                    map(int, other.value.split("."))
                )

        class FakeMod:
            def __init__(self, name: str, version: str, archive: Path) -> None:
                self._name = name
                self._version = version
                self._archive = archive

            def name(self) -> str:
                return self._name

            def version(self) -> FakeVersion:
                return FakeVersion(self._version)

            def installationFile(self) -> str:
                return str(self._archive)

            def nexusId(self) -> int:
                return 42

            def gameName(self) -> str:
                return "Cyberpunk2077"

        class FakeModList:
            def __init__(self, mod: FakeMod) -> None:
                self._mod = mod

            def allMods(self) -> list[str]:
                return [self._mod.name()]

            def getMod(self, name: str) -> FakeMod | None:
                return self._mod if name == self._mod.name() else None

        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            old_archive = root / "old-version.zip"
            old_archive.write_bytes(b"old version")
            old_archive.with_name(old_archive.name + ".meta").write_text(
                "version=1.0\n", encoding="utf-8"
            )
            new_archive = root / "new-version.zip"
            new_archive.write_bytes(b"new version")
            new_archive.with_name(new_archive.name + ".meta").write_text(
                "modID=42\ngameName=cyberpunk2077\n", encoding="utf-8"
            )

            old_mod = FakeMod("Existing Mod", "1.0", old_archive)
            new_mod = FakeMod("Existing Mod", "2.0", new_archive)
            organizer = Mock()
            organizer.downloadsPath.return_value = str(root)
            organizer.pluginSetting.return_value = True
            organizer.modList.return_value = FakeModList(old_mod)

            observer = plugin.NativeInstallObserver()
            observer.init(organizer)
            observer.onInstallationStart(str(new_archive), False, None)
            observer.onInstallationEnd(
                plugin.mobase.InstallResult.SUCCESS,
                new_mod,
            )

            archive_directory = root / "Archive"
            self.assertTrue((archive_directory / old_archive.name).is_file())
            self.assertTrue(
                (archive_directory / (old_archive.name + ".meta")).is_file()
            )
            self.assertTrue(new_archive.is_file())


if __name__ == "__main__":
    unittest.main()
