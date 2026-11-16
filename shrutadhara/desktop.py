"""Explicit, reversible desktop setup for a checkout or installed wheel."""

import os
import shlex
import sys
import time
from pathlib import Path

from .core import private_dir


def install(home=None, data_home=None, no_desktop=False):
    home = Path(home or Path.home())
    data_home = Path(
        data_home or os.environ.get("XDG_DATA_HOME", home / ".local/share")
    )
    launcher = home / ".local/bin/shruta"
    marker = "# Managed by shrutadhara"
    if launcher.is_symlink() or (
        launcher.exists() and marker not in launcher.read_text(errors="replace")
    ):
        raise ValueError("Refusing to replace an unrelated meeting launcher")
    desktop = data_home / "applications/io.github.Praneel7015.Shrutadhara.desktop"
    if not no_desktop and (
        desktop.is_symlink()
        or (desktop.exists() and "X-Shrutadhara=true" not in desktop.read_text())
    ):
        raise ValueError("Refusing to replace an unrelated desktop entry")
    launcher.parent.mkdir(parents=True, exist_ok=True)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        f'#!/bin/sh\n{marker}\nexec {shlex.quote(sys.executable)} -m shrutadhara "$@"\n'
    )
    launcher.chmod(0o700)
    if no_desktop:
        return f"Installed {launcher}; no recording or hosted processing enabled."
    escaped = (
        str(launcher)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
        .replace("%", "%%")
    )
    desktop.write_text(
        "[Desktop Entry]\nType=Application\nName=Shrutadhara\n"
        f'Exec="{escaped}" show\nIcon=audio-input-microphone\nTerminal=false\n'
        "Categories=AudioVideo;Audio;\nStartupNotify=true\nX-Shrutadhara=true\n"
    )
    old_launcher = home / ".local/bin/meeting"
    if (
        old_launcher.is_file()
        and not old_launcher.is_symlink()
        and any(
            marker in old_launcher.read_text(errors="replace")
            for marker in [
                "# Managed by linux-meeting-recorder",
                "# Legacy alias for Shrutadhara",
            ]
        )
    ):
        old_launcher.write_text(
            f'#!/bin/sh\n# Legacy alias for Shrutadhara\nexec {shlex.quote(str(launcher))} "$@"\n'
        )
        old_launcher.chmod(0o700)
    old_desktop = data_home / "applications/local.meeting.Recorder.desktop"
    if (
        old_desktop.is_file()
        and not old_desktop.is_symlink()
        and "X-Meeting-Recorder=true" in old_desktop.read_text(errors="replace")
    ):
        backups = data_home / "shrutadhara/migration"
        private_dir(backups)
        backup = backups / "legacy-recorder.desktop.backup"
        if backup.exists():
            backup = backups / f"legacy-recorder-{time.time_ns()}.desktop.backup"
        old_desktop.replace(backup)
    return f"Installed {launcher} and {desktop}; no recording or hosted processing enabled."
