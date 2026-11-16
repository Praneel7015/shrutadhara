"""Offline metadata generation tests: python -m unittest discover -s packaging/arch."""

import hashlib
import importlib.util
import io
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "arch_prepare", Path(__file__).with_name("prepare.py")
)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class MetadataTests(unittest.TestCase):
    def archive(self, root, extra=None):
        source = root / "shrutadhara-0.1.0.tar.gz"
        required = [
            "pyproject.toml",
            "LICENSE",
            "NOTICE",
            "desktop/io.github.Praneel7015.Shrutadhara.desktop",
            "desktop/shrutadhara-call-monitor.service",
            "tests/conftest.py",
        ]
        with tarfile.open(source, "w:gz") as archive:
            for name in required:
                info = tarfile.TarInfo("shrutadhara-0.1.0/" + name)
                info.size = 1
                archive.addfile(info, io.BytesIO(b"x"))
            if extra:
                archive.addfile(extra)
        return source

    def test_exact_digest_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.archive(root)
            with (
                patch.object(prepare.shutil, "which", return_value="/usr/bin/makepkg"),
                patch.object(
                    prepare.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(
                        [], 0, "pkgbase = shrutadhara\n"
                    ),
                ),
            ):
                prepare.prepare(source, root / "out")
            recipe = (root / "out/PKGBUILD").read_text()
            self.assertIn(hashlib.sha256(source.read_bytes()).hexdigest(), recipe)
            self.assertNotIn("SKIP", recipe.split("sha256sums=")[1])
            self.assertEqual(
                (root / "out/.SRCINFO").read_text(), "pkgbase = shrutadhara\n"
            )

    def test_rejects_traversal_and_symlinks(self):
        for name, kind in [
            ("shrutadhara-0.1.0/../../escape", tarfile.REGTYPE),
            ("shrutadhara-0.1.0/link", tarfile.SYMTYPE),
        ]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                info = tarfile.TarInfo(name)
                info.type = kind
                info.linkname = "/etc/passwd"
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    prepare.prepare(self.archive(root, info), root / "out")


if __name__ == "__main__":
    unittest.main()
