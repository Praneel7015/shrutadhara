"""Limits of the initial recording-only Flatpak distribution."""

import os

from .core import MeetingError


def is_flatpak() -> bool:
    return bool(os.environ.get("FLATPAK_ID"))


def require_native_ai() -> None:
    if is_flatpak():
        raise MeetingError(
            "This Flatpak supports recording and local preparation only. "
            "Use a native installation for agy transcription and notes.", 3
        )


def validate_command(args) -> None:
    if not is_flatpak():
        return
    if args.command == "start" and not args.foreground:
        raise MeetingError(
            "Use the Flatpak recording window (shruta show) or start --foreground; "
            "a detached recorder cannot outlive its sandbox.", 3
        )
    if (
        (args.command == "process" and not args.prepare_only)
        or args.command == "ask"
        or (args.command == "doctor" and args.probe_ai)
    ):
        require_native_ai()
    if args.command in {"watch", "install-desktop", "shortcuts"}:
        raise MeetingError("This command requires a native installation", 3)


def keep_window_open(busy: bool, recording: str | None, processing: bool) -> bool:
    return is_flatpak() and (
        busy or processing or recording in {"starting", "recording", "stopping"}
    )
