"""Check built artifacts without installing or executing their application code."""

import argparse
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path


def check_names(names):
    for name in names:
        path = Path(name)
        if path.suffix.lower() in {".wav", ".mkv", ".mp3", ".flac", ".m4a", ".opus", ".ogg", ".webm"}:
            raise ValueError(f"Audio fixture must not be shipped: {name}")
        if (
            ".local-fixtures" in path.parts
            or ".git" in path.parts
            or set(path.parts) & {"audio", "transcript", "notes", "questions", "logs", "Meetings"}
            or path.name in {"session.json", "config.json", "capability.json", ".env"}
            or path.name.startswith(".env.")
        ):
            raise ValueError(
                f"Private development/user data must not be shipped: {name}"
            )
    for required in ["LICENSE", "NOTICE"]:
        if not any(Path(name).name == required for name in names):
            raise ValueError(f"Missing license notice: {required}")


def check(directory):
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if not wheels or not sources:
        raise ValueError("Build both wheel and source distribution first")
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            check_names(names)
            if not any(
                name.endswith(
                    "/share/applications/io.github.Praneel7015.Shrutadhara.desktop"
                )
                for name in names
            ):
                raise ValueError("Wheel lacks desktop entry")
    for source in sources:
        if source.name == "shrutadhara-aur.tar.gz":
            continue
        with tarfile.open(source) as archive:
            names = archive.getnames()
            check_names(names)
            for required in [
                "install.py",
                "install.sh",
                "npm/launcher.js",
                "npm/package.json",
                "npm/LICENSE",
            ]:
                if not any(name.endswith("/" + required) for name in names):
                    raise ValueError(f"Source distribution lacks {required}")
    for package in directory.glob("*.tgz"):
        with tarfile.open(package) as archive:
            names = archive.getnames()
            check_names(names)
            for name in [
                "package/launcher.js",
                "package/package.json",
                "package/LICENSE",
            ]:
                if name not in names:
                    raise ValueError(f"npm artifact lacks {name}")
            manifest = json.load(archive.extractfile("package/package.json"))
            if manifest.get("scripts"):
                raise ValueError(
                    "npm convenience package must have no install/lifecycle hooks"
                )
            wheel_name = f"shrutadhara-{manifest['version']}-py3-none-any.whl"
            wheel_path = "package/native/" + wheel_name
            bundled = archive.extractfile(wheel_path).read()
            checksum = json.load(archive.extractfile("package/native/manifest.json"))
            if checksum != {"filename": wheel_name, "sha256": hashlib.sha256(bundled).hexdigest()}:
                raise ValueError("Bundled wheel manifest mismatch")
            with zipfile.ZipFile(io.BytesIO(bundled)) as nested:
                check_names(nested.namelist())
            if manifest.get("private") or manifest.get("publishConfig", {}).get("tag") != "experimental":
                raise ValueError("npm release must explicitly target the experimental channel")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        check(args.directory)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Release check failed: {exc}\n")
    print(
        "Release artifacts contain desktop/source setup and license notices, with no audio/user-data fixtures."
    )


if __name__ == "__main__":
    main()
