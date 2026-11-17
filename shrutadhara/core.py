from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class MeetingError(Exception):
    def __init__(self, message: str, code: int = 6):
        super().__init__(message)
        self.code = code


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise MeetingError(f"Unsafe directory: {path}", 4)
    path.chmod(0o700)
    return path


def atomic_json(path: Path, value: dict | list) -> None:
    private_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_text(path: Path, content: str) -> None:
    private_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("expected object")
        return value
    except (OSError, ValueError) as exc:
        raise MeetingError(f"Cannot read metadata {path}: {exc}", 4) from exc


@contextlib.contextmanager
def locked(path: Path, blocking: bool = False) -> Iterator[None]:
    private_dir(path.parent)
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as exc:
            raise MeetingError(
                "Another recording or processing operation is active", 4
            ) from exc
        yield
    finally:
        os.close(fd)


def run(args: list[str], timeout: float = 20, **kwargs) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, **kwargs
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MeetingError(f"{Path(args[0]).name} unavailable or timed out", 3) from exc
    if result.returncode:
        # Do not propagate arbitrary subprocess output: it may contain meeting content.
        raise MeetingError(f"{Path(args[0]).name} failed (exit {result.returncode})", 5)
    return result


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "team-meeting"


def notify(message: str, persistent: bool = False, tag: str | None = None) -> None:
    if shutil.which("notify-send"):
        try:
            options = [
                "--expire-time",
                "0" if persistent else "10000",
                "--app-name",
                "Shrutadhara",
            ]
            if tag:
                options += [
                    "--hint",
                    f"string:x-dunst-stack-tag:{tag}",
                    "--hint",
                    f"string:x-canonical-private-synchronous:{tag}",
                ]
            subprocess.Popen(
                ["notify-send", *options, "Shrutadhara", message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass


def runtime_dir() -> Path:
    base = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/shrutadhara-{os.getuid()}"))
    if os.environ.get("FLATPAK_ID"):
        # PID identities are meaningful only inside this sandbox. Never let a
        # native process recover or signal a sandbox worker using its PID.
        return private_dir(base / "app" / os.environ["FLATPAK_ID"] / "shrutadhara")
    legacy_base = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/meeting-{os.getuid()}"))
    legacy = legacy_base / "meeting-recorder"
    old_lock = legacy / "recording.lock"
    if old_lock.exists():
        if legacy.is_symlink() or legacy.stat().st_uid != os.getuid():
            raise MeetingError("Unsafe legacy recorder runtime directory", 4)
        fd = os.open(old_lock, os.O_RDWR | os.O_NOFOLLOW)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # Keep controlling a pre-rename worker until it finishes; never
                # start another recorder merely because the application was renamed.
                return legacy
        finally:
            os.close(fd)
    return private_dir(base / "shrutadhara")


def config_path() -> Path:
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        / "shrutadhara/config.json"
    )


def migrate_configuration() -> None:
    destination = config_path().parent
    legacy = destination.parent / "meeting"
    names = [
        name
        for name in ["config.json", "capability.json"]
        if (legacy / name).is_file() and not (destination / name).exists()
    ]
    if not names:
        return
    with locked(destination / ".migration.lock", blocking=True):
        copies = {
            name: read_json(legacy / name)
            for name in names
            if not (destination / name).exists()
        }
        for key in ["hosted_consent", "auto_process"]:
            if key in copies.get("config.json", {}) and not isinstance(
                copies["config.json"][key], bool
            ):
                raise MeetingError(f"Legacy configuration {key} must be a boolean", 4)
        for name, value in copies.items():
            atomic_json(destination / name, value)
        if copies:
            atomic_json(
                destination / "migration.json",
                {
                    "at": now(),
                    "from": "meeting",
                    "to": "shrutadhara",
                    "copied": sorted(copies),
                    "originals_retained": True,
                },
            )


def config() -> dict:
    migrate_configuration()
    p = config_path()
    result = {
        "root": str(Path.home() / "Meetings"),
        "model": "gemini-3.8-flash-high",
        "hosted_consent": False,
        "auto_process": False,
        "chunk_seconds": 300,
        "overlap_seconds": 2,
        "max_chunk_bytes": 16 * 1024 * 1024,
        "ai_timeout": 600,
        "reserve_bytes": 512 * 1024 * 1024,
    }
    if p.exists():
        result.update(read_json(p))
    for key in ["hosted_consent", "auto_process"]:
        if not isinstance(result[key], bool):
            raise MeetingError(f"Configuration {key} must be a boolean", 4)
    if os.environ.get("SHRUTA_ROOT"):
        result["root"] = os.environ["SHRUTA_ROOT"]
    elif os.environ.get("MEETING_ROOT"):
        result["root"] = os.environ["MEETING_ROOT"]
    return result
