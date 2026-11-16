#!/usr/bin/env python3
"""Generate reviewed AUR metadata against exact local release bytes, without downloads."""

import argparse
import hashlib
import re
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


def prepare(source: Path, output: Path) -> None:
    source = source.resolve(strict=True)
    match = re.fullmatch(
        r"shrutadhara-(\d+\.\d+\.\d+(?:[a-z][a-z0-9]*)?)\.tar\.gz", source.name
    )
    if not match:
        raise ValueError("Expected shrutadhara-VERSION.tar.gz release asset")
    version = match[1]
    with tarfile.open(source, "r:gz") as archive:
        entries = archive.getmembers()
        if any(
            PurePosixPath(entry.name).is_absolute()
            or ".." in PurePosixPath(entry.name).parts
            or not (entry.isfile() or entry.isdir())
            for entry in entries
        ):
            raise ValueError("Release archive has unsafe paths or non-regular members")
        members = [entry.name for entry in entries]
        root = f"shrutadhara-{version}"
        if any(name != root and not name.startswith(root + "/") for name in members):
            raise ValueError(
                "Release archive must contain exactly the versioned source root"
            )
        required = [
            "pyproject.toml",
            "LICENSE",
            "NOTICE",
            "desktop/io.github.Praneel7015.Shrutadhara.desktop",
            "desktop/shrutadhara-call-monitor.service",
            "tests/conftest.py",
        ]
        if any(root + "/" + name not in members for name in required):
            raise ValueError(
                "Release archive lacks required source/license/desktop/test files"
            )
    makepkg = shutil.which("makepkg")
    if not makepkg:
        raise ValueError(
            "makepkg is required to generate authoritative .SRCINFO on Arch"
        )
    output.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    template = Path(__file__).with_name("PKGBUILD.in").read_text()
    (output / "PKGBUILD").write_text(
        template.replace("@VERSION@", version).replace("@SHA256@", digest)
    )
    target = output / source.name
    if source != target.resolve():
        shutil.copyfile(source, target)
    info = subprocess.run(
        [makepkg, "--printsrcinfo"],
        cwd=output,
        check=True,
        capture_output=True,
        text=True,
    )
    (output / ".SRCINFO").write_text(info.stdout)
    print(f"Prepared {output.resolve()} against SHA256 {digest}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.source, args.output)
    except (
        ValueError,
        OSError,
        tarfile.TarError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(1, f"Arch metadata generation failed: {exc}\n")


if __name__ == "__main__":
    main()
