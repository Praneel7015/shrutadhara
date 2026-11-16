from __future__ import annotations

import json
import os
import selectors
import signal
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

from . import audio, sessions
from .core import (
    MeetingError,
    atomic_json,
    config,
    locked,
    notify,
    now,
    private_dir,
    read_json,
    runtime_dir,
)


def process_identity(pid: int) -> str | None:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def active() -> dict | None:
    p = runtime_dir() / "active.json"
    if not p.exists():
        return None
    d = read_json(p)
    if process_identity(d.get("pid", 0)) == d.get("identity") and d.get("identity"):
        metadata = read_json(Path(d["session"]) / "session.json")
        if metadata["recording"] in {"starting", "recording", "stopping"}:
            return d
    return None


def status() -> dict:
    d = active()
    if not d:
        return {"active": False}
    data = read_json(Path(d["session"]) / "session.json")
    snapshot = runtime_dir() / "status.json"
    extra = read_json(snapshot) if snapshot.exists() else {}
    if extra.get("session_id") != data["id"]:
        extra = {}
    return {
        **extra,
        "active": True,
        "session": d["session"],
        "id": data["id"],
        "title": data["title"],
        "recording": data["recording"],
        "transcription": data["transcription"],
        "notes": data["notes"],
        "elapsed_seconds": sessions.elapsed(data),
        "coverage_complete": data["coverage_complete"],
    }


def request(command: str) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        try:
            client.connect(str(runtime_dir() / "control.sock"))
            credentials = client.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
            if struct.unpack("3i", credentials)[1] != os.getuid():
                raise MeetingError("Recorder socket belongs to another user", 4)
            client.sendall((json.dumps({"command": command}) + "\n").encode())
            return json.loads(client.recv(8192))
        except (OSError, ValueError) as exc:
            raise MeetingError(
                "Recorder control unavailable; inspect status and run shruta recover",
                4,
            ) from exc


def recover(path: Path | None = None) -> dict:
    with locked(runtime_dir() / "recording.lock"):
        paths = [path] if path else sessions.list_sessions()
        recovered = []
        for p in paths:
            data = read_json(p / "session.json")
            journal = p / "audio/routing.json"
            if journal.exists():
                audio.restore_routes(journal)
            if data["recording"] not in {
                "starting",
                "recording",
                "stopping",
                "interrupted",
            }:
                continue
            if data["recording"] == "interrupted" and data.get("recovery_finalized"):
                continue
            audio.verify_archive_integrity(p)
            if data["recording"] != "interrupted":
                sessions.update(p, recording="interrupted")
            epochs = data.get("epochs", [])
            manifest, errors = audio.archive_manifest(p, epochs)
            end = max((m["end"] for m in manifest), default=0)
            sessions.update(
                p,
                ended_at=data.get("ended_at") or now(),
                duration_seconds=max(data["duration_seconds"], end),
            )
            duration = max(data["duration_seconds"], end)
            if manifest:
                try:
                    artifacts = audio.exports(p, manifest, duration)
                    sessions.update(p, artifacts=artifacts, recovery_finalized=True)
                except MeetingError:
                    sessions.error(
                        p,
                        "recovery",
                        "WAV export incomplete; originals retained for processing retry",
                    )
            sessions.error(
                p,
                "recovery",
                "Recorder interrupted; original archives retained. Review recovered audio before processing.",
            )
            recovered.append(
                {
                    "session": str(p),
                    "segments": len(manifest),
                    "invalid_segments": len(errors),
                }
            )
        return {"recovered": recovered}


def start(title: str, options: dict, foreground: bool = False) -> Path:
    with locked(runtime_dir() / "launch.lock"):
        if active():
            raise MeetingError("A recording is already active", 4)
        # A dead supervisor may have left Teams routed through a private sink.
        recover()
        devices = audio.select_devices(audio.inventory(), options)
        audio.disk_check(sessions.root(), config()["reserve_bytes"], start=True)
        path = sessions.create(title, options)
        sessions.update(path, devices=devices)
        command = [sys.executable, "-m", "shrutadhara", "_record", str(path)]
        if foreground:
            return path  # Caller runs supervisor after releasing launch lock.
        environment = [
            f"--setenv={name}={os.environ[name]}"
            for name in [
                "SHRUTA_ROOT",
                "MEETING_ROOT",  # Legacy storage override; new commands use SHRUTA_ROOT.
                "XDG_CONFIG_HOME",
                "XDG_RUNTIME_DIR",
                "PULSE_SERVER",
                "PIPEWIRE_REMOTE",
                "PATH",
            ]
            if name in os.environ
        ]
        try:
            subprocess.run(
                [
                    "systemd-run",
                    "--user",
                    "--quiet",
                    "--collect",
                    "--service-type=exec",
                    "--property=KillMode=control-group",
                    "--property=TimeoutStopSec=90",
                    f"--unit=shrutadhara-recording-{read_json(path / 'session.json')['id']}",
                    f"--working-directory={Path(__file__).resolve().parent.parent}",
                    "--setenv=PYTHONUNBUFFERED=1",
                    *environment,
                    *command,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            # Detached fallback still uses the same lock and control protocol.
            log = (path / "logs/supervisor.log").open("a")
            try:
                subprocess.Popen(
                    command,
                    cwd=Path(__file__).resolve().parent.parent,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            finally:
                log.close()
        for _ in range(150):
            data = read_json(path / "session.json")
            if data["recording"] == "recording":
                return path
            if data["recording"] in {"failed", "interrupted"}:
                raise MeetingError("Recorder startup failed; inspect session errors", 5)
            time.sleep(0.1)
        # Do not kill a possibly healthy worker or create a second one.
        raise MeetingError(
            f"Recorder readiness timed out; check shruta status. Session: {path}", 5
        )


def stop(wait: bool = True) -> dict:
    d = active()
    if not d:
        raise MeetingError("No active recording; use shruta recover after a crash", 4)
    metadata = read_json(Path(d["session"]) / "session.json")
    # The control socket closes during export/finalization. Repeated Stop should
    # attach to the existing finalization, not fail or signal a different process.
    result = (
        {"accepted": True, "session": d["session"], "recording": "stopping"}
        if metadata["recording"] == "stopping"
        else request("stop")
    )
    if wait:
        path = Path(d["session"])
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            data = read_json(path / "session.json")
            if not process_identity(d["pid"]) and data["recording"] in {
                "starting",
                "recording",
                "stopping",
            }:
                recover(path)
                data = read_json(path / "session.json")
            if data["recording"] not in {"starting", "recording", "stopping"}:
                return {"session": str(path), **data}
            time.sleep(0.3)
        raise MeetingError("Finalization is still running; inspect shruta status", 5)
    return result


class Supervisor:
    def __init__(self, path: Path):
        self.path = path
        self.data = read_json(path / "session.json")
        self.cfg = config()
        self.running = True
        self.proc: subprocess.Popen | None = None
        self.routing: audio.Routing | None = None
        self.selector = selectors.DefaultSelector()
        self.progress_at = time.monotonic()
        self.progress_buffer = b""
        self.started = 0.0
        self.epochs = self.data.get("epochs", [])
        self.gaps = self.data.get("gaps", [])
        self.health = {}
        self.log = None
        self.control = None
        self.fatal = False
        self.restart_attempts = 0
        self.missing_since: dict[str, float] = {}
        self.last_poll = time.monotonic()
        self.observed_teams = False

    def snapshot(self):
        atomic_json(
            runtime_dir() / "status.json",
            {
                "session_id": self.data["id"],
                "updated_at": now(),
                "health": self.health,
                "progress_age_seconds": round(time.monotonic() - self.progress_at, 1),
                "gaps": len(self.gaps),
                "microphone_notice": "Local microphone is captured even while muted in Teams",
            },
        )

    def spawn(self):
        directory = private_dir(
            self.path / f"audio/originals/epoch-{len(self.epochs):03d}"
        )
        offset = time.monotonic() - self.started
        self.epochs.append(
            {
                "id": len(self.epochs),
                "directory": str(directory.relative_to(self.path)),
                "offset": offset,
                "started_at": now(),
            }
        )
        sessions.update(self.path, epochs=self.epochs)
        self.proc = subprocess.Popen(
            audio.recording_command(self.routing.remote, self.routing.local, directory),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=self.log,
        )
        os.set_blocking(self.proc.stdout.fileno(), False)
        self.selector.register(self.proc.stdout, selectors.EVENT_READ, "progress")
        self.progress_at = time.monotonic()

    def halt_capture(self):
        if self.proc:
            try:
                self.selector.unregister(self.proc.stdout)
            except (KeyError, ValueError):
                pass
            if self.proc.poll() is None:
                self.proc.send_signal(signal.SIGINT)
                try:
                    self.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
                    sessions.error(
                        self.path,
                        "recording",
                        "FFmpeg forced to stop; inspect final archive",
                    )
                    self.fatal = True
            self.proc.stdout.close()
            self.proc = None

    def serve_control(self):
        conn, _ = self.control.accept()
        with conn:
            conn.settimeout(1)
            creds = struct.unpack(
                "3i",
                conn.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
                ),
            )
            if creds[1] != os.getuid():
                return
            try:
                message = json.loads(conn.recv(4096))
                if message.get("command") == "stop":
                    self.running = False
                elif message.get("command") != "status":
                    conn.sendall(b'{"error":"Unknown command"}\n')
                    return
                conn.sendall(
                    json.dumps({"accepted": True, "session": str(self.path)}).encode()
                )
            except (OSError, ValueError):
                return

    def reconcile(self):
        t = time.monotonic()
        if t - self.last_poll > 8:
            self.gaps.append(
                {
                    "start": self.last_poll - self.started,
                    "end": t - self.started,
                    "track": "both",
                    "reason": "Scheduling interruption or suspend; inspect audio",
                }
            )
        self.last_poll = t
        audio.disk_check(self.path, self.cfg["reserve_bytes"])
        inv = audio.inventory()
        names = {s["name"] for s in inv["sinks"]}
        if self.routing.remote not in names or self.routing.local not in names:
            raise MeetingError(
                "Audio server restarted or recording buses disappeared", 5
            )
        opts = self.data["options"]
        physical = {
            s["name"]: s for s in inv["sources"] if not s["name"].endswith(".monitor")
        }
        mic = opts.get("microphone") or inv["default_source"]
        captures = audio.teams_streams(
            inv["source-outputs"], self.data["devices"].get("teams_pid")
        )
        if not opts.get("microphone") and captures:
            ids = {s["source"] for s in captures}
            if len(ids) == 1:
                mic = next(
                    (s["name"] for s in inv["sources"] if s["index"] in ids), mic
                )
        output = opts.get("output") or inv["default_sink"]
        self.health = {
            "microphone_muted": physical.get(mic, {}).get("mute"),
            "microphone_present": mic in physical,
            "output_present": output in names,
            "teams_streams": len(
                audio.teams_streams(
                    inv["sink-inputs"], self.data["devices"].get("teams_pid")
                )
            ),
            "microphone": mic,
            "output": output,
        }
        for track, available in [
            ("microphone", mic in physical),
            ("output", output in names),
        ]:
            if not available:
                self.missing_since.setdefault(track, t - self.started)
            elif track in self.missing_since:
                self.gaps.append(
                    {
                        "start": self.missing_since.pop(track),
                        "end": t - self.started,
                        "track": track,
                        "reason": "Audio device unavailable",
                    }
                )
                if track == "microphone":
                    self.routing.connect_mic(mic)
                else:
                    self.routing.connect_output(output)
        if mic in physical and mic != self.routing.last_mic:
            self.routing.connect_mic(mic)
        if (
            output in names
            and not output.startswith("shruta_")
            and output != self.routing.last_output
        ):
            self.routing.connect_output(output)
        if self.health["teams_streams"]:
            self.observed_teams = True
        if self.observed_teams and not self.health["teams_streams"]:
            self.missing_since.setdefault("participants", t - self.started)
        elif "participants" in self.missing_since:
            self.gaps.append(
                {
                    "start": self.missing_since.pop("participants"),
                    "end": t - self.started,
                    "track": "participants",
                    "reason": "Teams playback stream disappeared",
                }
            )
        self.routing.route_teams(inv)
        sessions.update(self.path, gaps=self.gaps)
        self.snapshot()

    def execute(self):
        os.umask(0o077)
        with locked(runtime_dir() / "recording.lock"):
            self.started = time.monotonic()
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, lambda *_: setattr(self, "running", False))
            self.log = (self.path / "logs/recording.log").open("a")
            sockpath = runtime_dir() / "control.sock"
            try:
                sockpath.unlink(missing_ok=True)
                self.control = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.control.bind(str(sockpath))
                sockpath.chmod(0o600)
                self.control.listen(4)
                self.selector.register(self.control, selectors.EVENT_READ, "control")
                atomic_json(
                    runtime_dir() / "active.json",
                    {
                        "pid": os.getpid(),
                        "identity": process_identity(os.getpid()),
                        "session": str(self.path),
                    },
                )
                self.routing = audio.Routing(
                    self.data["id"],
                    self.data["devices"],
                    self.path / "audio/routing.json",
                )
                self.routing.setup(audio.inventory())
                self.started = time.monotonic()
                self.last_poll = self.started
                sessions.update(self.path, started_at=now())
                self.spawn()
                ready = False
                next_check = 0
                while self.running:
                    for key, _ in self.selector.select(0.3):
                        if key.data == "control":
                            self.serve_control()
                        else:
                            block = os.read(key.fileobj.fileno(), 65536)
                            if block:
                                self.progress_buffer += block
                                if b"progress=" in self.progress_buffer:
                                    self.progress_at = time.monotonic()
                                    self.progress_buffer = b""
                                    if not ready:
                                        sessions.update(
                                            self.path, recording="recording"
                                        )
                                        ready = True
                                        notify(
                                            "Recording started — local microphone and Teams audio",
                                            True,
                                            "shrutadhara-capture",
                                        )
                    if (
                        self.proc.poll() is not None
                        or time.monotonic() - self.progress_at > 15
                    ):
                        if self.restart_attempts >= 3:
                            raise MeetingError(
                                "Audio capture stopped or stalled after bounded restarts",
                                5,
                            )
                        self.restart_attempts += 1
                        begin = self.progress_at - self.started
                        self.halt_capture()
                        self.spawn()
                        self.gaps.append(
                            {
                                "start": max(0, begin),
                                "end": time.monotonic() - self.started,
                                "track": "both",
                                "reason": "Capture process stopped or stalled",
                            }
                        )
                    if time.monotonic() >= next_check:
                        try:
                            self.reconcile()
                        except MeetingError:
                            # Restart capture/routing after an audio server failure, at most three times.
                            if self.restart_attempts >= 3:
                                raise
                            self.restart_attempts += 1
                            begin = time.monotonic() - self.started
                            self.halt_capture()
                            self.routing.cleanup()
                            time.sleep(1)
                            self.routing = audio.Routing(
                                self.data["id"],
                                self.data["devices"],
                                self.path / "audio/routing.json",
                            )
                            self.routing.setup(audio.inventory())
                            self.spawn()
                            self.gaps.append(
                                {
                                    "start": begin,
                                    "end": time.monotonic() - self.started,
                                    "track": "both",
                                    "reason": "Capture routing restarted",
                                }
                            )
                        next_check = time.monotonic() + 2
            except BaseException as exc:
                self.fatal = True
                sessions.error(
                    self.path,
                    "recording",
                    str(exc)
                    if isinstance(exc, MeetingError)
                    else "Unexpected supervisor failure",
                )
            finally:
                duration = time.monotonic() - self.started
                for track, begin in self.missing_since.items():
                    self.gaps.append(
                        {
                            "start": begin,
                            "end": duration,
                            "track": track,
                            "reason": "Audio unavailable at stop",
                        }
                    )
                state = read_json(self.path / "session.json")["recording"]
                if state == "starting":
                    sessions.update(self.path, recording="failed")
                elif state == "recording":
                    sessions.update(self.path, recording="stopping")
                # Saved before shutdown/export so a crash during finalization has a bounded timeline.
                sessions.update(
                    self.path, ended_at=now(), duration_seconds=duration, gaps=self.gaps
                )
                self.halt_capture()
                if self.routing:
                    try:
                        self.routing.cleanup()
                    except (MeetingError, OSError, ValueError, KeyError):
                        sessions.error(
                            self.path,
                            "routing",
                            "Routing cleanup incomplete; run shruta recover",
                        )
                self.control.close() if self.control else None
                sockpath.unlink(missing_ok=True)
                sessions.update(
                    self.path, ended_at=now(), duration_seconds=duration, gaps=self.gaps
                )
                try:
                    manifest, errors = audio.archive_manifest(self.path, self.epochs)
                    if not manifest:
                        raise MeetingError("No valid audio archive segments", 5)
                    artifacts = audio.exports(self.path, manifest, duration)
                    sessions.update(self.path, artifacts=artifacts)
                    if errors:
                        self.fatal = True
                except MeetingError as exc:
                    self.fatal = True
                    sessions.error(self.path, "finalization", str(exc))
                state = read_json(self.path / "session.json")["recording"]
                if state == "stopping":
                    sessions.update(
                        self.path, recording="interrupted" if self.fatal else "recorded"
                    )
                self.log.close()
                self.selector.close()
                notify(
                    "Recording stopped"
                    if not self.fatal
                    else "Recording interrupted — inspect session and recovery",
                    False,
                    "shrutadhara-capture",
                )
        if self.cfg["auto_process"] and self.cfg["hosted_consent"] and not self.fatal:
            from .processing import process

            try:
                process(self.path)
            except MeetingError:
                pass
