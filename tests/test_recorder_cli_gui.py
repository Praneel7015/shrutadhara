import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from shrutadhara import audio, cli, gui, recorder, sessions
from shrutadhara.core import MeetingError, atomic_json, read_json, runtime_dir


def test_supervisor_lifecycle_without_external_capture(inv, monkeypatch):
    path = sessions.create("Lifecycle", {})
    sessions.update(path, devices=audio.select_devices(inv, {}))
    supervisor = recorder.Supervisor(path)
    monkeypatch.setattr(audio, "inventory", lambda: inv)

    class Routing:
        def __init__(self, *a):
            pass

        def setup(self, *a):
            pass

        def cleanup(self):
            pass

    monkeypatch.setattr(audio, "Routing", Routing)

    def spawn():
        r, w = os.pipe()
        os.write(w, b"progress=continue\n")
        os.close(w)
        out = os.fdopen(r, "rb", buffering=0)
        supervisor.proc = SimpleNamespace(stdout=out, poll=lambda: None)
        supervisor.selector.register(
            out, __import__("selectors").EVENT_READ, "progress"
        )

    monkeypatch.setattr(supervisor, "spawn", spawn)

    def reconcile():
        assert read_json(path / "session.json")["recording"] == "recording"
        supervisor.running = False

    monkeypatch.setattr(supervisor, "reconcile", reconcile)
    monkeypatch.setattr(
        supervisor,
        "halt_capture",
        lambda: supervisor.proc.stdout.close() if supervisor.proc else None,
    )
    monkeypatch.setattr(
        audio, "archive_manifest", lambda *a: ([{"start": 0, "end": 1}], [])
    )
    monkeypatch.setattr(
        audio, "exports", lambda *a: {"participants": {"sha256": "test"}}
    )
    supervisor.execute()
    data = read_json(path / "session.json")
    assert data["recording"] == "recorded" and data["ended_at"] and data["artifacts"]
    assert not recorder.active()


def test_duplicate_start_prevented(monkeypatch):
    monkeypatch.setattr(recorder, "active", lambda: {"session": "existing"})
    with pytest.raises(MeetingError) as err:
        recorder.start("Duplicate", {})
    assert err.value.code == 4


def test_recover_preserves_interrupted_session(monkeypatch):
    path = sessions.create("Crash")
    sessions.update(path, recording="recording")
    monkeypatch.setattr(audio, "archive_manifest", lambda *a: ([{"end": 125}], []))
    monkeypatch.setattr(
        audio, "exports", lambda *a: {"participants": {"sha256": "recovered"}}
    )
    report = recorder.recover(path)
    assert report["recovered"][0]["segments"] == 1
    data = read_json(path / "session.json")
    assert data["recording"] == "interrupted" and data["duration_seconds"] == 125
    assert data["recovery_finalized"]


def test_status_ignores_pid_reuse(monkeypatch):
    atomic_json(
        runtime_dir() / "active.json",
        {"pid": 123, "identity": "before", "session": "/missing"},
    )
    monkeypatch.setattr(recorder, "process_identity", lambda _: "after")
    assert recorder.status() == {"active": False}


def test_stop_requires_live_control(monkeypatch):
    monkeypatch.setattr(recorder, "active", lambda: None)
    with pytest.raises(MeetingError) as err:
        recorder.stop()
    assert err.value.code == 4


def test_repeated_stop_during_finalization_needs_no_control_socket(monkeypatch):
    path = sessions.create("Finalizing synthetic session")
    sessions.update(path, recording="recording")
    sessions.update(path, recording="stopping")
    monkeypatch.setattr(recorder, "active", lambda: {"session": str(path)})
    monkeypatch.setattr(
        recorder,
        "request",
        lambda *_: pytest.fail("Socket already closed during finalization"),
    )
    assert recorder.stop(wait=False)["recording"] == "stopping"


def test_cli_help_and_invalid_args(capsys):
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])
    assert result.value.code == 0
    assert "gui" in capsys.readouterr().out
    with pytest.raises(SystemExit) as result:
        cli.main(["process", "--unknown"])
    assert result.value.code == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"sample": Path("approved.wav")},
        {"expected": "Known words"},
    ],
)
def test_ai_probe_requires_approved_input_before_any_tool_call(monkeypatch, kwargs):
    monkeypatch.setattr(
        cli.shutil, "which", lambda *_: pytest.fail("Must validate probe inputs first")
    )
    with pytest.raises(MeetingError) as exc:
        cli.doctor(probe_ai=True, **kwargs)
    assert exc.value.code == 2


def test_cli_failure_exit_and_config_consent(capsys):
    assert cli.main(["stop"]) == 0  # Idempotent shortcut-friendly stop.
    assert cli.main(["configure", "--auto-process"]) == 7
    assert cli.main(["configure", "--allow-hosted", "--auto-process"]) == 0
    assert cli.main(["configure", "--deny-hosted"]) == 0
    from shrutadhara.core import config

    assert not config()["auto_process"] and not config()["hosted_consent"]


@pytest.mark.parametrize(
    "recording,busy,processing,can_record,can_process",
    [
        (None, False, False, True, True),
        ("recording", False, False, True, False),
        ("stopping", False, False, False, False),
        ("recorded", True, False, False, False),
        ("recorded", False, True, True, False),
    ],
)
def test_gui_state(recording, busy, processing, can_record, can_process):
    flags = gui.ui_state(recording, busy, True, processing)
    assert flags["record_enabled"] == can_record
    assert flags["process_enabled"] == can_process


def test_gui_processing_is_detached(recorded, monkeypatch):
    calls = []
    monkeypatch.setattr(
        gui.subprocess, "Popen", lambda *args, **kw: calls.append((args, kw))
    )
    gui.launch_processing(recorded)
    assert calls[0][1]["start_new_session"]
    assert "--session" in calls[0][0][0]
