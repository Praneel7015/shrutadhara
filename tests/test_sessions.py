import pytest

from shrutadhara import sessions
from shrutadhara.core import MeetingError, atomic_json, locked, read_json


def test_creation_private_and_unique():
    a, b = sessions.create("../../Roadmap; $(echo bad)"), sessions.create("Roadmap")
    assert a != b and a.parent == sessions.root()
    assert (a / "audio/originals").is_dir()
    assert a.stat().st_mode & 0o777 == 0o700
    assert (a / "session.json").stat().st_mode & 0o777 == 0o600
    assert read_json(a / "session.json")["recording"] == "starting"


def test_state_transitions():
    p = sessions.create()
    with pytest.raises(MeetingError, match="Invalid"):
        sessions.update(p, recording="recorded")
    sessions.update(p, recording="recording")
    sessions.update(p, recording="stopping")
    sessions.update(p, recording="recorded")
    with pytest.raises(MeetingError):
        sessions.update(p, recording="recording")
    sessions.update(p, transcription="running")
    sessions.update(p, transcription="partial")
    sessions.update(p, transcription="running")
    sessions.update(p, transcription="complete")


def test_atomic_failure_preserves_metadata(tmp_path):
    p = tmp_path / "private/state.json"
    atomic_json(p, {"value": 1})
    with pytest.raises(ValueError):
        atomic_json(p, {"invalid": float("nan")})
    assert read_json(p) == {"value": 1}
    assert list(p.parent.iterdir()) == [p]


def test_lock_excludes_duplicate(tmp_path):
    with locked(tmp_path / "lock"):
        with pytest.raises(MeetingError):
            with locked(tmp_path / "lock"):
                pass


def test_resolve_id_and_unknown():
    p = sessions.create("Meeting")
    assert sessions.resolve(read_json(p / "session.json")["id"][:8]) == p
    with pytest.raises(MeetingError):
        sessions.resolve("does-not-exist")


def test_reject_symlink_directory(tmp_path):
    from shrutadhara.core import private_dir

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(MeetingError):
        private_dir(link)


def test_elapsed_uses_boot_timeline_including_suspend(monkeypatch):
    monkeypatch.setattr(sessions, "boot_identity", lambda: "same-boot")
    monkeypatch.setattr(sessions, "elapsed_time", lambda: 175.0)
    data = {"started_at": "2000-01-01T00:00:00+00:00", "recording": "recording",
            "timeline": {"clock": "boottime", "boot_id": "same-boot", "start": 100}}
    assert sessions.elapsed(data) == 75
    data["recording"] = "recorded"
    data["duration_seconds"] = 74
    assert sessions.elapsed(data) == 74


def test_elapsed_does_not_reinterpret_previous_boot_anchor(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(sessions, "boot_identity", lambda: "new-boot")
    monkeypatch.setattr(sessions, "elapsed_time", lambda: pytest.fail("wrong boot"))
    data = {"started_at": datetime.now(timezone.utc).isoformat(), "recording": "recording",
            "timeline": {"clock": "boottime", "boot_id": "old-boot", "start": 100}}
    assert 0 <= sessions.elapsed(data) < 2
