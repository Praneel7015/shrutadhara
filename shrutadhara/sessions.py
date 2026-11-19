from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from .clock import boot_identity, elapsed_time
from .core import (
    MeetingError,
    atomic_json,
    config,
    locked,
    now,
    private_dir,
    read_json,
    slug,
)

TRANSITIONS = {
    "recording": {
        "starting": {"recording", "failed", "interrupted"},
        "recording": {"stopping", "interrupted", "failed"},
        "stopping": {"recorded", "interrupted", "failed"},
        "interrupted": {"recorded", "failed"},
        "recorded": set(),
        "failed": set(),
    },
    "transcription": {
        "pending": {"running", "blocked"},
        "running": {"partial", "complete", "blocked", "failed"},
        "partial": {"running", "blocked"},
        "complete": {"running", "blocked"},
        "blocked": {"running"},
        "failed": {"running", "blocked"},
    },
    "notes": {
        "pending": {"running", "blocked"},
        "running": {"partial", "complete", "failed", "blocked"},
        "partial": {"running", "blocked"},
        "complete": {"running", "blocked"},
        "blocked": {"running"},
        "failed": {"running", "blocked"},
    },
}


def root() -> Path:
    return private_dir(Path(config()["root"]).expanduser().absolute())


def create(title: str = "Team meeting", options: dict | None = None) -> Path:
    identifier = str(uuid.uuid4())
    name = (
        datetime.now().strftime("%Y-%m-%d_%H%M%S")
        + "_"
        + slug(title)
        + "_"
        + identifier[:8]
    )
    path = root() / name
    for sub in ["audio/originals", "transcript/chunks", "notes", "logs"]:
        private_dir(path / sub)
    atomic_json(
        path / "session.json",
        {
            "schema_version": 1,
            "id": identifier,
            "title": title,
            "created_at": now(),
            "started_at": None,
            "ended_at": None,
            "duration_seconds": 0,
            "recording": "starting",
            "transcription": "pending",
            "notes": "pending",
            "options": options or {},
            "devices": {},
            "epochs": [],
            "gaps": [],
            "monitor_events": [],
            "errors": [],
            "artifacts": {},
            "coverage_complete": False,
        },
    )
    return path


def update(path: Path, **fields) -> dict:
    with locked(path / ".metadata.lock", blocking=True):
        data = read_json(path / "session.json")
        for key, value in fields.items():
            if key in TRANSITIONS and value != data[key]:
                if value not in TRANSITIONS[key].get(data[key], set()):
                    raise MeetingError(
                        f"Invalid {key} transition: {data[key]} → {value}", 4
                    )
        data.update(fields)
        atomic_json(path / "session.json", data)
        return data


def error(path: Path, category: str, message: str) -> None:
    with locked(path / ".metadata.lock", blocking=True):
        data = read_json(path / "session.json")
        data["errors"].append({"at": now(), "category": category, "message": message})
        atomic_json(path / "session.json", data)


def list_sessions() -> list[Path]:
    return sorted((p.parent for p in root().glob("*/session.json")), reverse=True)


def resolve(identifier: str | None = None) -> Path:
    paths = list_sessions()
    if identifier:
        candidate = Path(identifier).expanduser()
        if candidate.is_dir() and (candidate / "session.json").is_file():
            return candidate.resolve()
        matches = [
            p
            for p in paths
            if p.name == identifier
            or read_json(p / "session.json")["id"].startswith(identifier)
        ]
        if len(matches) != 1:
            raise MeetingError("Session not found or identifier is ambiguous", 4)
        return matches[0]
    if not paths:
        raise MeetingError("No meeting sessions yet", 4)
    return paths[0]


def elapsed(data: dict) -> float:
    if data.get("started_at") and data["recording"] in {
        "starting",
        "recording",
        "stopping",
    }:
        timeline = data.get("timeline", {})
        if (timeline.get("clock") == "boottime" and
                timeline.get("boot_id") == boot_identity() and
                isinstance(timeline.get("start"), (int, float))):
            return max(0, elapsed_time() - timeline["start"])
        # Legacy sessions have no boot anchor; retain their original wall-time
        # interpretation rather than silently rewriting historical timing.
        return max(
            0,
            (
                datetime.now(timezone.utc) - datetime.fromisoformat(data["started_at"])
            ).total_seconds(),
        )
    return data.get("duration_seconds", 0)
