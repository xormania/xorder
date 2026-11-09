"""The Chrome ZIP payload keeps ordinary Unix permissions during extraction."""
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("chrome_payload_extract", ROOT / "images/components/chrome-for-testing-157/extract.py")
EXTRACTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRACTOR)


def member(name, mode):
    info = zipfile.ZipInfo(name)
    info.create_system = 3
    info.external_attr = mode << 16
    return info


class ChromeArchiveModeTests(unittest.TestCase):
    def test_wrapper_shared_libraries_data_and_directories_keep_ordinary_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "chrome.zip"
            expected = {"chrome-linux64/resources/": (stat.S_IFDIR | 0o2750, 0o750),
                        "chrome-linux64/chrome-wrapper": (stat.S_IFREG | 0o4755, 0o755),
                        "chrome-linux64/libEGL.so": (stat.S_IFREG | 0o755, 0o755),
                        "chrome-linux64/resources/data": (stat.S_IFREG | 0o640, 0o640)}
            with zipfile.ZipFile(archive_path, "w") as archive:
                for name, (mode, _ordinary) in expected.items():
                    archive.writestr(member(name, mode), b"" if name.endswith("/") else b"qualified payload")
            destination = root / "payload"
            EXTRACTOR.extract(archive_path, destination)
            for name, (_mode, ordinary) in expected.items():
                with self.subTest(name=name):
                    self.assertEqual(stat.S_IMODE((destination / name).stat().st_mode), ordinary)

    def test_unsafe_member_paths_and_symlinks_are_rejected_before_extraction(self):
        for name, mode in (("../escape", stat.S_IFREG | 0o755),
                           ("/chrome-linux64/escape", stat.S_IFREG | 0o755),
                           ("chrome-linux64/../escape", stat.S_IFREG | 0o755),
                           ("chrome-linux64/link", stat.S_IFLNK | 0o777)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive_path = root / "chrome.zip"
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr(member("chrome-linux64/chrome-wrapper", stat.S_IFREG | 0o755), b"wrapper")
                    archive.writestr(member(name, mode), b"unexpected payload")
                destination = root / "payload"
                with self.assertRaisesRegex(ValueError, "Unsafe|Unsupported"):
                    EXTRACTOR.extract(archive_path, destination)
                self.assertFalse(destination.exists())
                self.assertFalse((root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
