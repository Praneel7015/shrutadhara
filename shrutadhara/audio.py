from __future__ import annotations

import csv
import json
import os
import re
import selectors
import shutil
import subprocess
import time
from pathlib import Path

from .child import guarded_command
from .core import MeetingError, atomic_json, digest, locked, private_dir, read_json, run


def pulse(*args: str):
    return run(["pactl", *args])


def inventory() -> dict:
    result = {}
    for kind in ["sinks", "sources", "sink-inputs", "source-outputs"]:
        result[kind] = json.loads(pulse("-f", "json", "list", kind).stdout)
    result["default_sink"] = pulse("get-default-sink").stdout.strip()
    result["default_source"] = pulse("get-default-source").stdout.strip()
    return result


def teams_streams(items: list[dict], pid: str | None = None) -> list[dict]:
    return [
        item
        for item in items
        if item.get("properties", {}).get("application.process.binary")
        == "teams-for-linux"
        and (not pid or item["properties"].get("application.process.id") == str(pid))
    ]


def teams_processes() -> list[int]:
    found = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            if (directory / "comm").read_text().strip() == "teams-for-linux":
                found.append(int(directory.name))
        except OSError:
            continue
    return sorted(found)


def select_devices(inv: dict, options: dict) -> dict:
    playback = teams_streams(inv["sink-inputs"], options.get("teams_pid"))
    processes = {x["properties"].get("application.process.id") for x in playback}
    if len(processes) > 1 and not options.get("teams_pid"):
        raise MeetingError("Multiple Teams instances: select --teams-pid", 4)
    mic = options.get("microphone")
    if not mic:
        captures = teams_streams(inv["source-outputs"], options.get("teams_pid"))
        indices = {x["source"] for x in captures}
        if len(indices) == 1:
            mic = next(
                (x["name"] for x in inv["sources"] if x["index"] in indices), None
            )
        mic = mic or inv["default_source"]
    output = options.get("output") or inv["default_sink"]
    source = next((s for s in inv["sources"] if s["name"] == mic), None)
    sink = next((s for s in inv["sinks"] if s["name"] == output), None)
    if not source or source.get("monitor_source") or mic.endswith(".monitor"):
        raise MeetingError("Select an available physical microphone, not a monitor", 5)
    if not sink or output.startswith(("shruta_", "meeting_")):
        raise MeetingError("Selected listening output is unavailable", 5)
    if source.get("mute") and not options.get("allow_muted_mic"):
        raise MeetingError(
            "Microphone is system-muted. Unmute it or use --allow-muted-mic", 5
        )
    return {
        "microphone": mic,
        "output": output,
        "microphone_muted": bool(source.get("mute")),
        "microphone_properties": source.get("properties", {}),
        "output_properties": sink.get("properties", {}),
        "teams_pid": options.get("teams_pid")
        or (next(iter(processes)) if processes else None),
    }


class Routing:
    """Only own modules/streams are modified; no desktop default changes."""

    def __init__(self, session_id: str, devices: dict, journal: Path):
        self.remote = "shruta_" + session_id.replace("-", "")[:12] + "_remote"
        self.local = self.remote.removesuffix("remote") + "mic"
        self.devices = devices
        self.journal = journal
        self.modules: dict[str, str] = {}
        self.moved: dict[str, dict] = {}
        self.last_mic = devices["microphone"]
        self.last_output = devices["output"]

    def save(self):
        atomic_json(
            self.journal,
            {
                "modules": self.modules,
                "moved": self.moved,
                "remote": self.remote,
                "local": self.local,
            },
        )

    def load_module(self, label: str, module: str, *args: str):
        index = pulse("load-module", module, *args).stdout.strip()
        if not index.isdecimal():
            raise MeetingError("Invalid module ID from audio server", 5)
        self.modules[label] = index
        self.save()

    def setup(self, inv: dict):
        try:
            self.load_module(
                "remote",
                "module-null-sink",
                f"sink_name={self.remote}",
                "rate=48000",
                "channels=2",
                "sink_properties=device.description=Meeting_Participants",
            )
            self.load_module(
                "local",
                "module-null-sink",
                f"sink_name={self.local}",
                "rate=48000",
                "channels=1",
                "channel_map=mono",
                "sink_properties=device.description=Meeting_Microphone",
            )
            self.connect_mic(self.last_mic)
            self.connect_output(self.last_output)
            self.route_teams(inv)
        except BaseException:
            self.cleanup()
            raise

    def unload(self, label: str):
        index = self.modules.get(label)
        if index:
            # A failure must preserve ownership and prevent a duplicate replacement.
            pulse("unload-module", index)
            self.modules.pop(label, None)
        self.save()

    def connect_mic(self, source: str):
        self.unload("mic_loop")
        self.load_module(
            "mic_loop",
            "module-loopback",
            f"source={source}",
            f"sink={self.local}",
            "source_dont_move=true",
            "sink_dont_move=true",
            "latency_msec=30",
        )
        self.last_mic = source

    def connect_output(self, sink: str):
        self.unload("output_loop")
        self.load_module(
            "output_loop",
            "module-loopback",
            f"source={self.remote}.monitor",
            f"sink={sink}",
            "source_dont_move=true",
            "sink_dont_move=true",
            "latency_msec=30",
        )
        self.last_output = sink

    def route_teams(self, inv: dict):
        remote = next(
            (s["index"] for s in inv["sinks"] if s["name"] == self.remote), None
        )
        by_index = {s["index"]: s["name"] for s in inv["sinks"]}
        for item in teams_streams(inv["sink-inputs"], self.devices.get("teams_pid")):
            if remote is not None and item["sink"] == remote:
                continue
            key = str(item["index"])
            if key not in self.moved:
                self.moved[key] = {
                    "sink": by_index.get(item["sink"], self.last_output),
                    "pid": item["properties"].get("application.process.id"),
                    "serial": item.get("properties", {}).get("object.serial"),
                }
                self.save()  # Persist undo before mutation.
            pulse("move-sink-input", key, self.remote)

    def cleanup(self):
        try:
            inv = inventory()
        except MeetingError:
            return  # Keep journal for explicit recovery.
        restore_routes(self.journal, inv, ownership={
            "modules": self.modules, "moved": self.moved,
            "remote": self.remote, "local": self.local,
        })


def restore_routes(journal: Path, inv: dict | None = None, ownership: dict | None = None):
    """Restore only streams whose identity and current session target still match."""
    if ownership is None and not journal.exists():
        return
    from .core import read_json

    # Live ownership may be newer than disk when a journal write failed.
    data = ownership if ownership is not None else read_json(journal)
    inv = inv or inventory()
    sinks = {s["index"]: s["name"] for s in inv["sinks"]}
    names = set(sinks.values())
    for item in inv["sink-inputs"]:
        previous = data.get("moved", {}).get(str(item["index"]))
        props = item.get("properties", {})
        if (
            previous
            and sinks.get(item["sink"]) == data.get("remote")
            and props.get("application.process.binary") == "teams-for-linux"
            and props.get("application.process.id") == previous.get("pid")
            and props.get("object.serial") == previous.get("serial")
        ):
            target = (
                previous["sink"] if previous["sink"] in names else inv["default_sink"]
            )
            if target.startswith(("shruta_", "meeting_")):
                continue
            pulse("move-sink-input", str(item["index"]), target)
    # Check module identity before unloading: Pulse IDs can be reused after a server restart.
    # pactl's JSON module listing on this PipeWire version omits module IDs.
    # The documented short listing includes IDs and is stable across versions.
    modules = []
    for line in pulse("list", "short", "modules").stdout.splitlines():
        fields = line.split("\t")
        if len(fields) >= 3 and fields[0].isdigit():
            modules.append(
                {"index": fields[0], "name": fields[1], "argument": fields[2]}
            )
    remaining = {}
    for label, module_id in reversed(list(data.get("modules", {}).items())):
        module = next((m for m in modules if str(m["index"]) == str(module_id)), None)
        arguments = str(module.get("argument", "")) if module else ""
        if module and any(
            name and name in arguments
            for name in [data.get("remote"), data.get("local")]
        ):
            try:
                pulse("unload-module", str(module_id))
            except MeetingError:
                remaining[label] = module_id
    atomic_json(journal, {**data, "modules": remaining, "moved": {}})


def recording_command(remote: str, local: str, epoch: Path) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "warning",
        "-n",
        "-stats_period",
        "1",
        "-progress",
        "pipe:1",
        "-copyts",
        "-start_at_zero",
        "-thread_queue_size",
        "1024",
        "-f",
        "pulse",
        "-sample_rate",
        "48000",
        "-channels",
        "2",
        "-name",
        "shrutadhara",
        "-stream_name",
        "Meeting participants capture",
        "-i",
        remote + ".monitor",
        "-thread_queue_size",
        "1024",
        "-f",
        "pulse",
        "-sample_rate",
        "48000",
        "-channels",
        "1",
        "-name",
        "shrutadhara",
        "-stream_name",
        "Meeting microphone capture",
        "-i",
        local + ".monitor",
        "-map",
        "0:a:0",
        "-map",
        "1:a:0",
        "-c:a",
        "pcm_s16le",
        "-ar:a",
        "48000",
        "-ac:a",
        "1",
        "-metadata:s:a:0",
        "title=Remote participants",
        "-metadata:s:a:1",
        "title=Local microphone",
        "-f",
        "segment",
        "-segment_time",
        "60",
        "-reset_timestamps",
        "0",
        "-segment_format",
        "matroska",
        "-segment_list",
        str(epoch / "segments.csv"),
        "-segment_list_type",
        "csv",
        str(epoch / "%06d.mkv"),
    ]


def probe(path: Path) -> dict:
    return json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            timeout=60,
        ).stdout
    )


def validate_audio(path: Path) -> dict:
    info = probe(path)
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    duration = float(info.get("format", {}).get("duration", 0))
    if not streams or duration <= 0:
        raise MeetingError("Audio has no decodable duration or tracks", 5)
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(path),
            "-map",
            "0:a",
            "-f",
            "null",
            "-",
        ],
        timeout=max(60, duration),
    )
    health = []
    for index, stream in enumerate(streams):
        result = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(path),
                "-map",
                f"0:a:{index}",
                "-af",
                "astats=metadata=0:reset=0",
                "-f",
                "null",
                "-",
            ],
            timeout=max(60, duration),
        )
        import re

        peaks = re.findall(r"Peak level dB: ([-\w.]+)", result.stderr)
        peak = next((float(v) for v in reversed(peaks) if v != "nan"), float("-inf"))
        health.append(
            {
                "track": index,
                "silent": peak < -60,
                "clipping": peak >= -0.1,
                "peak_db": peak if peak != float("-inf") else None,
                "channels": stream.get("channels"),
                "sample_rate": stream.get("sample_rate"),
            }
        )
    return {"duration_seconds": duration, "tracks": health, "sha256": digest(path)}


def archive_path(session: Path, relative: str) -> Path:
    """Resolve archive metadata paths without allowing escapes through symlinks."""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise MeetingError("Invalid archive integrity path", 5)
    path = session / relative
    if not path.resolve().is_relative_to(session.resolve()):
        raise MeetingError("Archive integrity path escapes its session", 5)
    return path


def verify_archive_integrity(session: Path) -> dict[str, str]:
    """Verify old baselines before discovering or repairing any archive bytes."""
    trusted = {}

    def include(relative, sha256):
        archive_path(session, relative)
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise MeetingError("Invalid archive integrity hash", 5)
        if relative in trusted and trusted[relative] != sha256:
            raise MeetingError("Conflicting archive integrity baselines", 5)
        trusted[relative] = sha256

    manifest_path = session / "audio/manifest.json"
    ledger_path = session / "audio/archive-integrity.json"
    try:
        for metadata in (manifest_path, ledger_path):
            archive_path(session, str(metadata.relative_to(session)))
            if metadata.is_symlink():
                raise MeetingError("Unsafe archive integrity metadata", 5)
        if manifest_path.exists():
            previous = read_json(manifest_path)
            if not isinstance(previous.get("segments"), list) or not isinstance(
                previous.get("errors"), list
            ):
                raise MeetingError("Invalid archive manifest", 5)
            for entry in previous["segments"]:
                include(entry["path"], entry["sha256"])
                if "original_path" in entry or "original_sha256" in entry:
                    include(entry["original_path"], entry["original_sha256"])
        if ledger_path.exists():
            ledger = read_json(ledger_path)
            if ledger.get("schema_version") != 1 or not isinstance(
                ledger.get("files"), dict
            ):
                raise MeetingError("Invalid archive integrity ledger", 5)
            for relative, sha256 in ledger["files"].items():
                include(relative, sha256)
        for relative, sha256 in trusted.items():
            path = archive_path(session, relative)
            if not path.is_file() or digest(path) != sha256:
                raise MeetingError(
                    "Archive integrity failure: trusted audio changed or is missing", 5
                )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise MeetingError(
            "Cannot verify archive integrity metadata or files", 5
        ) from exc
    return trusted


def archive_manifest(
    session: Path, epochs: list[dict]
) -> tuple[list[dict], list[dict]]:
    trusted = verify_archive_integrity(session)
    manifest, errors = [], []

    def remember(path: Path):
        relative = str(path.relative_to(session))
        archive_path(session, relative)
        actual = digest(path)
        if relative in trusted and trusted[relative] != actual:
            raise MeetingError(
                "Archive integrity failure: audio changed during recovery", 5
            )
        trusted[relative] = actual
        # Persist before salvage: even an interrupted/failed repair must retain
        # the first observed original baseline, independent of its decodability.
        atomic_json(
            session / "audio/archive-integrity.json",
            {"schema_version": 1, "files": trusted},
        )
        return actual

    for epoch in epochs:
        directory = archive_path(session, epoch["directory"])
        entries = {}
        csv_path = archive_path(
            session, str((directory / "segments.csv").relative_to(session))
        )
        if csv_path.exists():
            with csv_path.open(newline="") as stream:
                for row in csv.reader(stream):
                    if len(row) == 3:
                        entries[Path(row[0]).name] = (float(row[1]), float(row[2]))
        for path in sorted(directory.glob("*.mkv")):
            original_hash = remember(path)
            try:
                info = probe(path)
                tracks = [s for s in info["streams"] if s.get("codec_type") == "audio"]
                if len(tracks) != 2:
                    raise MeetingError("Archive must contain two audio tracks", 5)
                start, end = entries.get(
                    path.name,
                    (
                        float(info["format"].get("start_time", 0)),
                        float(info["format"].get("duration", 0)),
                    ),
                )
                # Matroska duration with retained timestamps is an end timestamp.
                if end <= start:
                    raise MeetingError("Archive has invalid timestamps", 5)
                run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-xerror",
                        "-i",
                        str(path),
                        "-map",
                        "0:a",
                        "-f",
                        "null",
                        "-",
                    ],
                    timeout=90,
                )
                manifest.append(
                    {
                        "path": str(path.relative_to(session)),
                        "start": epoch["offset"] + start,
                        "end": epoch["offset"] + end,
                        "media_start": start,
                        "sha256": original_hash,
                        "epoch": epoch["id"],
                    }
                )
            except (MeetingError, KeyError, ValueError):
                issue = {
                    "path": str(path.relative_to(session)),
                    "error": "Archive validation failed; original retained",
                }
                try:
                    repaired = (
                        private_dir(session / "audio/recovered")
                        / f"{epoch['id']}-{path.stem}-{original_hash[:12]}.mkv"
                    )
                    if not repaired.exists():
                        temporary = repaired.with_suffix(".partial.mkv")
                        run(
                            [
                                "ffmpeg",
                                "-v",
                                "error",
                                "-y",
                                "-copyts",
                                "-i",
                                str(path),
                                "-map",
                                "0:a",
                                "-c",
                                "copy",
                                "-f",
                                "matroska",
                                str(temporary),
                            ],
                            timeout=90,
                        )
                        temporary.replace(repaired)
                    repaired_hash = remember(repaired)
                    info = probe(repaired)
                    start = float(info["format"].get("start_time", 0))
                    end = float(info["format"].get("duration", 0))
                    if (
                        end <= start
                        or len(
                            [
                                s
                                for s in info["streams"]
                                if s.get("codec_type") == "audio"
                            ]
                        )
                        != 2
                    ):
                        raise MeetingError("Archive salvage has no valid timeline", 5)
                    run(
                        [
                            "ffmpeg",
                            "-v",
                            "error",
                            "-xerror",
                            "-i",
                            str(repaired),
                            "-map",
                            "0:a",
                            "-f",
                            "null",
                            "-",
                        ],
                        timeout=90,
                    )
                    manifest.append(
                        {
                            "path": str(repaired.relative_to(session)),
                            "start": epoch["offset"] + start,
                            "end": epoch["offset"] + end,
                            "media_start": start,
                            "sha256": repaired_hash,
                            "epoch": epoch["id"],
                            "original_path": str(path.relative_to(session)),
                            "original_sha256": original_hash,
                            "recovered": True,
                        }
                    )
                    issue["error"] = (
                        "Archive salvaged into a derivative; original retained, review required"
                    )
                except (MeetingError, OSError, KeyError, ValueError):
                    pass
                errors.append(issue)
    verify_archive_integrity(session)
    manifest.sort(key=lambda x: x["start"])
    atomic_json(
        session / "audio/manifest.json", {"segments": manifest, "errors": errors}
    )
    return manifest, errors


def artifact_lock(session: Path):
    """Lock ordering: recording/processing -> audio artifacts -> metadata."""
    return locked(session / ".audio-artifacts.lock", blocking=True)


def pcm_blocks(command: list[str], timeout: float):
    """Yield aligned PCM blocks while bounding reads and process exit together."""
    deadline = time.monotonic() + timeout
    proc = subprocess.Popen(guarded_command(command), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    selector = selectors.DefaultSelector()
    pending = b""
    try:
        os.set_blocking(proc.stdout.fileno(), False)
        selector.register(proc.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MeetingError("Audio export exceeded its deadline; originals retained", 5)
            if not selector.select(min(1, remaining)):
                continue
            try:
                block = os.read(proc.stdout.fileno(), 65536)
            except BlockingIOError:
                continue
            if not block:
                break
            block = pending + block
            size = len(block) - len(block) % 2
            pending = block[size:]
            if size:
                yield block[:size]
        if pending:
            raise MeetingError("Audio export ended with an incomplete PCM sample", 5)
        try:
            code = proc.wait(timeout=max(.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            raise MeetingError("Audio export exceeded its deadline; originals retained", 5) from exc
        if code:
            raise MeetingError("Failed to export archive; originals retained", 5)
    finally:
        selector.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        proc.stdout.close()


def exports(session: Path, manifest: list[dict], duration: float) -> dict:
    """Stream PCM to aligned WAVs; never load an entire meeting into memory."""
    import wave

    outputs = {}
    for track, name in [(0, "participants"), (1, "microphone")]:
        target = session / f"audio/{name}.wav"
        tmp = target.with_suffix(".wav.partial")
        cursor = 0
        total = round(duration * 48000)
        with wave.open(str(tmp), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            for entry in manifest:
                start = round(entry["start"] * 48000)
                if start > cursor:
                    write_silence(wav, start - cursor)
                    cursor = start
                skip = max(0, cursor - start)
                command = [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(session / entry["path"]),
                    "-map",
                    f"0:a:{track}",
                    "-af",
                    f"aresample=48000:async=1:first_pts=0,apad,atrim=end_sample={round((entry['end'] - entry['start']) * 48000)}",
                    "-ac",
                    "1",
                    "-f",
                    "s16le",
                    "-",
                ]
                for block in pcm_blocks(command, timeout=max(120, entry["end"] - entry["start"])):
                    if skip:
                        cut = min(skip * 2, len(block))
                        block = block[cut:]
                        skip -= cut // 2
                    remaining = max(0, total - cursor)
                    block = block[: remaining * 2]
                    wav.writeframesraw(block)
                    cursor += len(block) // 2
            if cursor < total:
                write_silence(wav, total - cursor)
        tmp.replace(target)
        outputs[name] = validate_audio(target)
    target = session / "audio/combined.wav"
    tmp = target.with_suffix(".partial.wav")
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(session / "audio/participants.wav"),
            "-i",
            str(session / "audio/microphone.wav"),
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95:level=false:latency=1",
            "-c:a",
            "pcm_s16le",
            str(tmp),
        ],
        timeout=max(120, duration),
    )
    tmp.replace(target)
    outputs["combined"] = validate_audio(target)
    return outputs


def write_silence(wav, samples: int):
    while samples:
        count = min(samples, 48000)
        wav.writeframesraw(b"\0" * count * 2)
        samples -= count


def disk_check(path: Path, reserve: int, start: bool = False):
    # Archives + two exports + combined + processing derivatives, for at least 2 hours.
    required = reserve + (4 * 1024**3 if start else 0)
    if shutil.disk_usage(path).free < required:
        raise MeetingError(
            "Insufficient free disk space; preserve existing audio and free space", 5
        )
