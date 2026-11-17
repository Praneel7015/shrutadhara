from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from . import __version__, agy, audio, recorder, sessions
from .core import (
    MeetingError,
    atomic_json,
    config,
    config_path,
    now,
    private_dir,
    read_json,
    run,
    runtime_dir,
)

PRIVACY = (
    "Recording captures the local microphone even while muted in Teams. "
    "Closing the window does not stop capture. Provide participant notice and obtain required permission; "
    "this does not trigger Teams' recording announcement."
)
HOSTED = (
    "Hosted processing sends staged audio and transcript data through agy to Google's service using your account. "
    "It may consume quota and retain conversation history. Only enable this for meetings you are permitted to upload."
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="shruta",
        description="Shrutadhara (श्रुतधर) — a local-first AI meeting assistant.",
        epilog="Hear everything. Preserve knowledge. Remember what matters.",
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")
    providers = sub.add_parser(
        "providers", help="List supported adapters without network access"
    )
    providers.add_argument("--json", action="store_true")
    doctor = sub.add_parser(
        "doctor",
        help="Check tools, audio devices, GUI, and AI capability; offline for AI by default",
    )
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument(
        "--probe-ai",
        action="store_true",
        help="Consent to a hosted known-speech capability test (may consume quota)",
    )
    doctor.add_argument(
        "--sample",
        type=Path,
        help="Approved 1–30 second known-speech audio required for --probe-ai",
    )
    doctor.add_argument(
        "--expected", help="Exact spoken text for a custom capability sample"
    )
    doctor.add_argument(
        "--test-recording",
        action="store_true",
        help="Explicitly record 3 seconds of Teams and microphone audio to a test session",
    )
    start = sub.add_parser(
        "start",
        help="Start a supervised recording; local microphone capture is independent of Teams mute",
    )
    start.add_argument("--title", default="Team meeting")
    start.add_argument(
        "--microphone",
        help="Pulse source name; default follows Teams capture/default source",
    )
    start.add_argument(
        "--output", help="Listening sink name; default follows the desktop default"
    )
    start.add_argument(
        "--teams-pid", help="Select Teams instance using its audio-stream PID"
    )
    start.add_argument(
        "--allow-muted-mic",
        action="store_true",
        help="Accept a system-muted microphone without unmuting it",
    )
    start.add_argument(
        "--foreground", action="store_true", help="Run supervisor in this terminal"
    )
    status = sub.add_parser(
        "status", help="Show recording health, location, duration and processing state"
    )
    status.add_argument("--json", action="store_true")
    status.add_argument("--session")
    stop = sub.add_parser(
        "stop", help="Gracefully stop and validate the active recording"
    )
    stop.add_argument(
        "--no-wait", action="store_true", help="Return while finalization continues"
    )
    process = sub.add_parser(
        "process", help="Validate, transcribe/resume, and generate notes"
    )
    process.add_argument("--session")
    process.add_argument(
        "--prepare-only",
        action="store_true",
        help="Create chunks and prompts locally without any AI call",
    )
    process.add_argument(
        "--allow-partial",
        action="store_true",
        help="Explicitly allow prominently labeled partial notes",
    )
    process.add_argument(
        "--import",
        dest="import_path",
        type=Path,
        help="Import JSON chunk results matching the prepared manifest",
    )
    ask = sub.add_parser(
        "ask", help="Ask an evidence-linked question about an accepted transcript"
    )
    ask.add_argument("question", nargs="?")
    ask.add_argument("--session")
    ask.add_argument("--allow-partial", action="store_true")
    for name in ["notes", "summary", "actions", "decisions", "transcript", "open"]:
        command = sub.add_parser(
            name,
            help={
                "notes": "Display detailed notes",
                "summary": "Display summary",
                "actions": "Display action items",
                "decisions": "Display decisions",
                "transcript": "Display full transcript",
                "open": "Open the session folder or an artifact",
            }[name],
        )
        command.add_argument("--session")
        if name != "open":
            command.add_argument(
                "--open",
                action="store_true",
                help="Open in the desktop default application",
            )
        if name == "notes":
            command.add_argument(
                "--kind",
                choices=["summary", "detailed-notes", "action-items", "decisions"],
                default="detailed-notes",
            )
        if name == "open":
            command.add_argument(
                "--artifact",
                choices=["folder", "notes", "transcript", "audio", "microphone", "participants"],
                default="folder",
            )
    listing = sub.add_parser(
        "list", help="List sessions and their durations and processing states"
    )
    listing.add_argument("--json", action="store_true")
    sub.add_parser("gui", help="Open the compact native GTK 4 window")
    sub.add_parser("show", help="Show or focus the recorder window")
    shortcuts = sub.add_parser("shortcuts", help="Show manual desktop shortcut setup")
    shortcuts.add_argument(
        "--start", dest="start_accel", help="Local GTK accelerator; empty disables"
    )
    shortcuts.add_argument(
        "--stop", dest="stop_accel", help="Local GTK accelerator; empty disables"
    )
    sub.add_parser(
        "install-desktop", help="Explicitly install user launcher and desktop entry"
    )
    recover = sub.add_parser(
        "recover", help="Restore routes and inspect archives left by a crashed recorder"
    )
    recover.add_argument("--session")
    configure = sub.add_parser(
        "configure",
        help="Review/configure hosted processing and explicit automation options",
    )
    group = configure.add_mutually_exclusive_group()
    group.add_argument("--allow-hosted", action="store_true", help=HOSTED)
    group.add_argument("--deny-hosted", action="store_true")
    configure.add_argument(
        "--model",
        help="Explicit agy model slug; changing it invalidates the capability test",
    )
    group = configure.add_mutually_exclusive_group()
    group.add_argument(
        "--auto-process",
        action="store_true",
        help="Automatically process after stop (requires hosted consent)",
    )
    group.add_argument("--no-auto-process", action="store_true")
    configure.add_argument(
        "--chunk-seconds", type=int, help="Core length, 30–300 seconds"
    )
    watch = sub.add_parser(
        "watch",
        help="Opt-in D-Bus call notifications; automatic capture requires --auto-record",
    )
    watch.add_argument(
        "--auto-record",
        action="store_true",
        help="Explicitly record calls detected during this invocation",
    )
    watch.add_argument(
        "--validated",
        action="store_true",
        help="Acknowledge call start/end and device behavior were manually tested",
    )
    watch.add_argument(
        "--bus-name", default="com.github.IsmaelMartinez.teams_for_linux"
    )
    internal = sub.add_parser("_record")
    internal.add_argument("path", type=Path)
    return p


def configure(args) -> dict:
    data = config()
    if args.allow_hosted:
        data.update(
            hosted_consent=True, hosted_consent_at=now(), hosted_disclosure=HOSTED
        )
    if args.deny_hosted:
        data.update(hosted_consent=False, auto_process=False)
    if args.model:
        data["model"] = args.model
    if args.chunk_seconds is not None:
        if not 30 <= args.chunk_seconds <= 300:
            raise MeetingError("Chunk seconds must be between 30 and 300", 2)
        data["chunk_seconds"] = args.chunk_seconds
    if args.auto_process:
        if not data["hosted_consent"]:
            raise MeetingError(
                "Automatic processing requires explicit hosted consent", 7
            )
        data["auto_process"] = True
    if args.no_auto_process:
        data["auto_process"] = False
    if any(
        [
            args.allow_hosted,
            args.deny_hosted,
            args.model,
            args.auto_process,
            args.no_auto_process,
            args.chunk_seconds is not None,
        ]
    ):
        atomic_json(config_path(), data)
    return data


def doctor(
    probe_ai: bool = False,
    sample: Path | None = None,
    expected: str | None = None,
    test_recording: bool = False,
) -> dict:
    from .sandbox import is_flatpak, require_native_ai

    if probe_ai:
        require_native_ai()
    if probe_ai and (sample is None or not expected or not expected.strip()):
        raise MeetingError(
            "AI probes require an approved --sample and its --expected spoken text", 2
        )
    checks = {
        name: shutil.which(name)
        for name in [
            "pactl",
            "ffmpeg",
            "ffprobe",
            "agy",
            "systemd-run",
            "notify-send",
            "xdg-open",
            "busctl",
        ]
    }
    report = {
        "dependencies": checks,
        "hosted_processing_enabled": config()["hosted_consent"],
        "privacy": PRIVACY,
        "hosted_disclosure": HOSTED,
        "audio_capability": "unverified",
        "recording_test": "not run (requires --test-recording)",
        "limitations": [
            "agy audio size/duration limits remain unverified; application chunks at five minutes and 16 MiB",
            "Native file-reader processing requires a clean capability probe; @path and ACP are not audio transports",
            "Teams call state is observed, not server-confirmed; microphone capture is independent of Teams mute",
        ],
    }
    errors = []
    if any(not checks[k] for k in ["pactl", "ffmpeg", "ffprobe"]):
        errors.append("Missing recording dependencies")
    try:
        inv = audio.inventory()
        report["audio"] = {
            "default_source": inv["default_source"],
            "default_sink": inv["default_sink"],
            "microphones": [
                {
                    "name": s["name"],
                    "description": s.get("description"),
                    "muted": s.get("mute"),
                }
                for s in inv["sources"]
                if not s["name"].endswith(".monitor")
            ],
            "sinks": [
                {"name": s["name"], "description": s.get("description")}
                for s in inv["sinks"]
            ],
            "teams_playback_streams": len(audio.teams_streams(inv["sink-inputs"])),
            "teams_processes": audio.teams_processes(),
        }
        report["pulse_capture"] = (
            "pulse" in run(["ffmpeg", "-hide_banner", "-devices"]).stdout
        )
        # ffmpeg prints the device table on stderr on some builds.
        if not report["pulse_capture"]:
            report["pulse_capture"] = (
                "pulse" in run(["ffmpeg", "-hide_banner", "-devices"]).stderr
            )
        if not report["pulse_capture"]:
            errors.append("FFmpeg has no PulseAudio capture device")
    except MeetingError as exc:
        errors.append(str(exc))
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        from .gui import require_gtk_version

        require_gtk_version(Gtk)
        report["gui"] = f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}"
    except MeetingError as exc:
        report["gui"] = str(exc)
    except (ImportError, ValueError):
        report["gui"] = (
            "Unavailable: install GTK 4 and python-gobject (CLI still works)"
        )
    if checks["agy"]:
        try:
            report["agy"] = agy.identity()
            report["audio_capability"] = (
                "verified" if agy.capable() else "unverified / blocked"
            )
            report["authentication"] = "not contacted; verified by explicit AI probe"
        except MeetingError as exc:
            report["agy_error"] = str(exc)
    if is_flatpak():
        report["hosted_processing_enabled"] = False
        report["audio_capability"] = "unavailable in recording-only Flatpak; use a native installation for AI"
    if probe_ai:
        workspace = private_dir(
            runtime_dir() / "ai-probes" / str(__import__("time").time_ns())
        )
        result = agy.probe_capability(sample, expected, workspace, config())
        report["audio_probe"] = result
        report["authentication"] = (
            "verified by explicit AI probe" if result["passed"] else "probe failed"
        )
        report["audio_capability"] = (
            "verified" if result["passed"] else "failed / blocked"
        )
        if not result["passed"]:
            errors.append("Known-speech test failed")
    if test_recording:
        import time

        path = recorder.start("Explicit 3-second recording test", {})
        time.sleep(3)
        result = recorder.stop()
        report["recording_test"] = {
            "session": str(path),
            "state": result["recording"],
            "artifacts": result["artifacts"],
        }
        if result["recording"] != "recorded":
            errors.append("Recording test was interrupted")
    report["errors"] = errors
    return report


def selected(identifier: str | None) -> Path:
    if identifier:
        return sessions.resolve(identifier)
    current = recorder.active()
    return Path(current["session"]) if current else sessions.resolve()


def artifact(path: Path, kind: str) -> Path:
    data = read_json(path / "session.json")
    key = {"notes": "notes", "transcript": "transcription"}.get(kind)
    if key and data[key] not in {"complete", "partial"}:
        raise MeetingError(
            "Requested AI artifact is not current; finish processing first", 4
        )
    target = (
        path
        / {
            "notes": "notes/detailed-notes.md",
            "transcript": "transcript/full-transcript.md",
            "audio": "audio/combined.wav",
            "microphone": "audio/microphone.wav",
            "participants": "audio/participants.wav",
            "folder": "",
        }[kind]
    )
    if not target.exists():
        raise MeetingError("Requested artifact has not been generated", 4)
    return target


def open_path(path: Path):
    if not path.exists():
        raise MeetingError("Requested output is not available", 4)
    try:
        subprocess.Popen(
            ["xdg-open", str(path.resolve())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise MeetingError("xdg-open is unavailable", 3) from exc


def dispatch(args):
    from .sandbox import validate_command

    validate_command(args)
    command = args.command
    if command == "providers":
        from .providers import available_providers

        values = available_providers()
        if args.json:
            print(json.dumps(values, indent=2))
        else:
            for value in values:
                print(f"{value['id']} (default): {value['description']}")
        return 0
    if command == "doctor":
        value = doctor(args.probe_ai, args.sample, args.expected, args.test_recording)
        if args.json:
            print(json.dumps(value, indent=2, ensure_ascii=False))
        else:
            print(
                "Recording tools: "
                + ("ready" if not value["errors"] else "; ".join(value["errors"]))
            )
            print("GUI: " + value["gui"])
            print("agy audio: " + value["audio_capability"])
            print(
                "Hosted meeting processing: "
                + ("enabled" if value["hosted_processing_enabled"] else "disabled")
            )
            for item in value.get("audio", {}).get("microphones", []):
                print(
                    f"Microphone: {item['name']}"
                    + (" (system-muted)" if item["muted"] else "")
                )
            for item in value.get("audio", {}).get("sinks", []):
                print(f"Output: {item['name']}")
        return 3 if value["errors"] else 0
    if command == "start":
        active = recorder.active()
        if active:
            print(active["session"])
            return 0
        print(PRIVACY, file=sys.stderr)
        options = {
            k: getattr(args, k)
            for k in ["microphone", "output", "teams_pid", "allow_muted_mic"]
        }
        path = recorder.start(args.title, options, args.foreground)
        if args.foreground:
            recorder.Supervisor(path).execute()
        print(path)
    elif command == "_record":
        recorder.Supervisor(args.path.resolve()).execute()
    elif command == "status":
        value = (
            read_json(selected(args.session) / "session.json")
            if args.session
            else recorder.status()
        )
        if not args.session and not value["active"]:
            paths = sessions.list_sessions()
            if paths:
                value["latest"] = {
                    "session": str(paths[0]),
                    **read_json(paths[0] / "session.json"),
                }
        if args.json:
            print(json.dumps(value, indent=2, ensure_ascii=False))
        else:
            latest = value.get("latest", value)
            print("Active recording" if value.get("active") else "No active recording")
            if latest.get("id"):
                duration = latest.get(
                    "elapsed_seconds", latest.get("duration_seconds", 0)
                )
                print(
                    f"{latest['title']} · {duration / 60:.1f} minutes · {latest['recording']}"
                )
                print(latest.get("session", ""))
                print(
                    f"Transcript: {latest['transcription']} · Notes: {latest['notes']}"
                )
                if latest.get("health"):
                    if latest.get("health_stale"):
                        print("Audio health unknown: recorder status is stale")
                    else:
                        print("Audio: " + json.dumps(latest["health"]))
    elif command == "stop":
        if not recorder.active():
            print("No active recording")
            return 0
        result = recorder.stop(not args.no_wait)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("recording") in {"failed", "interrupted"}:
            return 5
    elif command == "process":
        from .processing import process

        def interrupted(*_):
            raise KeyboardInterrupt()

        previous = signal.signal(signal.SIGTERM, interrupted)
        try:
            result = process(
                selected(args.session),
                args.prepare_only,
                args.allow_partial,
                args.import_path,
            )
        finally:
            signal.signal(signal.SIGTERM, previous)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("coverage_complete") is False:
            return 6
    elif command == "ask":
        from .questions import ask

        question = args.question
        if question is None:
            question = input("Question: ") if sys.stdin.isatty() else sys.stdin.read()
        print(ask(selected(args.session), question, args.allow_partial), end="")
    elif command in {"notes", "summary", "actions", "decisions", "transcript", "open"}:
        path = selected(args.session)
        note_kinds = {
            "summary": "summary",
            "actions": "action-items",
            "decisions": "decisions",
        }
        if command in note_kinds:
            args.kind = note_kinds[command]
            command = "notes"
        if command == "open":
            open_path(artifact(path, args.artifact))
        else:
            target = path / (
                f"notes/{args.kind}.md"
                if command == "notes"
                else "transcript/full-transcript.md"
            )
            if not target.exists():
                raise MeetingError("Requested output has not been generated", 4)
            data = read_json(path / "session.json")
            if command == "notes" and data["notes"] not in {"complete", "partial"}:
                raise MeetingError("Notes are not current; finish processing first", 4)
            if command == "transcript" and data["transcription"] not in {
                "complete",
                "partial",
            }:
                raise MeetingError(
                    "Transcript is not current; finish processing first", 4
                )
            if args.open:
                open_path(target)
            else:
                print(target.read_text())
    elif command == "list":
        values = []
        for path in sessions.list_sessions():
            data = read_json(path / "session.json")
            values.append(
                {
                    "directory": str(path),
                    **{
                        k: data[k]
                        for k in [
                            "id",
                            "title",
                            "created_at",
                            "duration_seconds",
                            "recording",
                            "transcription",
                            "notes",
                        ]
                    },
                }
            )
        if args.json:
            print(json.dumps(values, indent=2, ensure_ascii=False))
        else:
            for d in values:
                print(
                    f"{d['id'][:8]}  {d['created_at'][:16]}  {d['duration_seconds'] / 60:.1f}m  {d['recording']}/{d['transcription']}/{d['notes']}  {d['title']}"
                )
    elif command == "configure":
        print(HOSTED, file=sys.stderr)
        print(json.dumps(configure(args), indent=2))
    elif command == "recover":
        print(
            json.dumps(
                recorder.recover(
                    sessions.resolve(args.session) if args.session else None
                ),
                indent=2,
            )
        )
    elif command == "install-desktop":
        from .desktop import install

        print(install())
    elif command == "shortcuts":
        from .shortcuts import save_accelerators, setup_text

        save_accelerators(args.start_accel, args.stop_accel)
        print(setup_text())
    elif command in {"gui", "show"}:
        from .gui import launch

        return launch()
    elif command == "watch":
        from .teams import watch

        watch(args.bus_name, args.auto_record, args.validated)
    return 0


def main(argv: list[str] | None = None) -> int:
    os.umask(0o077)
    try:
        return dispatch(parser().parse_args(argv))
    except MeetingError as exc:
        print(f"shruta: {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print(
            "shruta: interrupted; recordings and accepted results retained",
            file=sys.stderr,
        )
        return 130
    except (OSError, ValueError) as exc:
        print(
            f"shruta: {type(exc).__name__}; check paths, configuration, and private session diagnostics",
            file=sys.stderr,
        )
        return 4
