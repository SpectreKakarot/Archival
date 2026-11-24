import tempfile
import unittest
from pathlib import Path

import NexusArchiveStateTool as plugin


class NexusArchiveStateToolTests(unittest.TestCase):
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
                    ("downloaded", "downloaded.zip", False),
                    ("uninstalled", "orphan.zip.meta (metadata only)", True),
                    ("uninstalled", "uninstalled.rar", False),
                ],
            )

            report = plugin.write_archive_report(root, matches)
            self.assertEqual(
                report.read_text(encoding="utf-8"),
                "downloaded\tdownloaded.zip\n"
                "uninstalled\torphan.zip.meta (metadata only)\n"
                "uninstalled\tuninstalled.rar\n",
            )

            destination = root / "To Sort"
            moved, errors = plugin.move_matches(matches, destination)
            self.assertEqual(moved, 3)
            self.assertEqual(errors, [])
            self.assertTrue((destination / "downloaded.zip").is_file())
            self.assertTrue((destination / "downloaded.zip.meta").is_file())
            self.assertTrue((destination / "orphan.zip.meta").is_file())
            self.assertTrue((destination / "uninstalled.rar").is_file())
            self.assertTrue(
                (destination / "uninstalled.rar.meta").is_file()
            )
            self.assertFalse(downloaded.exists())
            self.assertFalse(orphan_metadata.exists())
            self.assertTrue(existing_7z.is_file())
            self.assertTrue(existing_7z.with_name(existing_7z.name + ".meta").is_file())
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


if __name__ == "__main__":
    unittest.main()
