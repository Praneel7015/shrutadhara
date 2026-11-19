"""Failure-path tests use owned synthetic processes, never audio devices."""

import errno
import io
import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from shrutadhara import audio, recorder, sessions
from shrutadhara.child import process_identity
from shrutadhara.core import MeetingError, atomic_json, read_json


@pytest.mark.skipif(sys.platform != "linux", reason="Linux parent-death contract")
def test_guarded_child_dies_with_parent_before_more_output(tmp_path):
    identity_file = tmp_path / "capture.json"
    target = tmp_path / "ticks"
    child_code = (
        "import time;from pathlib import Path; p=Path(__import__('sys').argv[1]);"
        "\nwhile True:\n with p.open('a') as f: f.write('tick\\n'); f.flush()\n time.sleep(.03)"
    )
    parent_code = (
        "import sys,time,subprocess;from pathlib import Path;"
        "from shrutadhara.child import guarded_command;"
        "subprocess.Popen(guarded_command([sys.executable,'-c',sys.argv[3],sys.argv[2]],"
        "identity_file=Path(sys.argv[1])),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
        "time.sleep(30)"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", parent_code, str(identity_file), str(target), child_code],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    identity = None
    try:
        deadline = time.monotonic() + 5
        while not target.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert target.exists(), "guarded command did not start"
        identity = read_json(identity_file)
        assert process_identity(identity["pid"]) == identity["identity"]
        parent.kill()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 5
        while process_identity(identity["pid"]) == identity["identity"] and time.monotonic() < deadline:
            time.sleep(.02)
        assert process_identity(identity["pid"]) != identity["identity"]
        before = target.stat().st_size
        time.sleep(.1)
        assert target.stat().st_size == before
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        if identity and process_identity(identity["pid"]) == identity["identity"]:
            os.kill(identity["pid"], signal.SIGKILL)


def test_guard_refuses_a_changed_parent_identity_before_exec(tmp_path):
    target = tmp_path / "must-not-exist"
    result = subprocess.run([
        sys.executable, "-m", "shrutadhara.child", "--parent-pid", str(os.getpid()),
        "--parent-identity", "not-this-process", "--signal", str(signal.SIGTERM), "--",
        sys.executable, "-c", f"from pathlib import Path;Path({str(target)!r}).touch()",
    ], capture_output=True, timeout=5)
    assert result.returncode == 3
    assert not target.exists()


def test_recovery_refuses_live_owned_capture_before_touching_archives(monkeypatch):
    path = sessions.create("Owned synthetic writer")
    atomic_json(path / "audio/capture-process.json", {"pid": 12345, "identity": "live"})
    monkeypatch.setattr(recorder, "process_identity", lambda pid: "live")
    monkeypatch.setattr(audio, "verify_archive_integrity", lambda *_: pytest.fail("writer still alive"))
    with pytest.raises(MeetingError, match="still alive"):
        recorder.recover(path)


@pytest.mark.parametrize("failed_operation", ["read", "update"])
def test_metadata_failure_cannot_bypass_capture_route_socket_cleanup(monkeypatch, failed_operation):
    path = sessions.create("Synthetic storage failure")
    supervisor = recorder.Supervisor(path)
    supervisor.started = time.monotonic()
    supervisor.log = io.StringIO()
    calls = []
    supervisor.control = SimpleNamespace(close=lambda: calls.append("socket"))
    supervisor.routing = SimpleNamespace(cleanup=lambda: calls.append("routes"))
    supervisor.proc = SimpleNamespace()
    monkeypatch.setattr(supervisor, "halt_capture", lambda: calls.append("capture"))
    def fail(*args, **kwargs):
        raise OSError(errno.ENOSPC, "synthetic full filesystem")
    if failed_operation == "read":
        monkeypatch.setattr(recorder, "read_json", fail)
    else:
        monkeypatch.setattr(sessions, "update", fail)
    monkeypatch.setattr(sessions, "error", fail)
    monkeypatch.setattr(audio, "archive_manifest", lambda *_: pytest.fail("metadata failed; defer export"))
    supervisor.finalize(path / "synthetic-control.sock")
    assert calls == ["capture", "routes", "socket"]
    assert supervisor.fatal and supervisor.log.closed
    assert supervisor.selector.get_map() is None


def test_failed_capture_shutdown_still_attempts_routes_and_socket(monkeypatch):
    path = sessions.create("Capture teardown failure")
    supervisor = recorder.Supervisor(path)
    supervisor.started = time.monotonic()
    supervisor.log = io.StringIO()
    calls = []
    supervisor.routing = SimpleNamespace(cleanup=lambda: calls.append("routes"))
    supervisor.control = SimpleNamespace(close=lambda: calls.append("socket"))
    monkeypatch.setattr(supervisor, "halt_capture", lambda: (_ for _ in ()).throw(OSError("synthetic")))
    monkeypatch.setattr(audio, "archive_manifest", lambda *_: ([], []))
    supervisor.finalize(path / "synthetic.sock")
    assert calls == ["routes", "socket"] and supervisor.fatal


def test_unload_failure_retains_journal_and_prevents_replacement(tmp_path, monkeypatch):
    route = audio.Routing("synthetic", {"microphone": "mic", "output": "out"}, tmp_path / "routing.json")
    route.modules["mic_loop"] = "123"
    route.save()
    def fail(*args):
        if args[0] == "load-module":
            pytest.fail("must not add a duplicate after failed unload")
        raise MeetingError("synthetic unload failure")
    monkeypatch.setattr(audio, "pulse", fail)
    with pytest.raises(MeetingError):
        route.connect_mic("replacement")
    assert route.modules == {"mic_loop": "123"}
    assert read_json(route.journal)["modules"] == {"mic_loop": "123"}


def test_cleanup_uses_live_ownership_when_journal_write_failed(inv, tmp_path, monkeypatch):
    route = audio.Routing("synthetic", {"microphone": "mic", "output": "speakers"}, tmp_path / "absent.json")
    route.modules["remote"] = "123"
    calls = []
    def pulse(*args):
        calls.append(args)
        return SimpleNamespace(stdout=f"123\tmodule-null-sink\tsink_name={route.remote}\tn/a\n")
    monkeypatch.setattr(audio, "inventory", lambda: inv)
    monkeypatch.setattr(audio, "pulse", pulse)
    monkeypatch.setattr(audio, "atomic_json", lambda *_: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
    with pytest.raises(OSError):
        route.cleanup()
    assert ("unload-module", "123") in calls


def test_stop_expected_session_refuses_replacement_before_control(monkeypatch):
    path = sessions.create("Replacement session")
    monkeypatch.setattr(recorder, "active", lambda: {"session": str(path)})
    monkeypatch.setattr(recorder, "request", lambda *_a, **_kw: pytest.fail("must not send stop"))
    with pytest.raises(MeetingError, match="expected owned session"):
        recorder.stop(wait=False, expected_session=path.parent / "different")


def test_control_stop_checks_expected_session_at_dispatch(tmp_path):
    import socket
    import threading

    path = sessions.create("Control ownership")
    supervisor = recorder.Supervisor(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock = tmp_path / "control.sock"
    server.bind(str(sock))
    server.listen()
    supervisor.control = server
    worker = threading.Thread(target=supervisor.serve_control)
    worker.start()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(sock))
            client.sendall(__import__('json').dumps({"command": "stop", "expected_session": str(path.parent / "old-session")}).encode())
            response = __import__('json').loads(client.recv(8192))
        worker.join(timeout=5)
        assert "error" in response
        assert supervisor.running
    finally:
        server.close()
        supervisor.selector.close()


def synthetic_routed_supervisor(inv, monkeypatch):
    path = sessions.create("Synthetic routed session")
    devices = audio.select_devices(inv, {})
    sessions.update(path, devices=devices)
    supervisor = recorder.Supervisor(path)
    supervisor.started = 100
    supervisor.last_poll = 105
    supervisor.last_monotonic = 105
    route = audio.Routing("synthetic-route", supervisor.data["devices"], path / "audio/routing.json")
    route.modules = {"mic_loop": "42", "output_loop": "43"}
    route.observe_devices(inv)
    supervisor.routing = route
    inv["sinks"].extend([{"index": 20, "name": route.remote}, {"index": 21, "name": route.local}])
    inv["sink-inputs"] = []
    modules = [
        {"index": "42", "name": "module-loopback", "argument": f"source=mic sink={route.local}"},
        {"index": "43", "name": "module-loopback", "argument": f"source={route.remote}.monitor sink=speakers"},
    ]
    monkeypatch.setattr(audio, "inventory", lambda: inv)
    monkeypatch.setattr(audio, "module_inventory", lambda: modules)
    monkeypatch.setattr(audio, "disk_check", lambda *_: None)
    monkeypatch.setattr(route, "route_teams", lambda *_: None)
    monkeypatch.setattr(recorder, "elapsed_time", lambda: 110)
    monkeypatch.setattr(recorder.time, "monotonic", lambda: 110)
    return supervisor, route, modules


def test_reconcile_detects_suspend_when_monotonic_does_not_advance(inv, monkeypatch):
    supervisor, _, _ = synthetic_routed_supervisor(inv, monkeypatch)
    monkeypatch.setattr(recorder, "elapsed_time", lambda: 170)
    monkeypatch.setattr(recorder.time, "monotonic", lambda: 110)
    supervisor.reconcile()
    gap = next(g for g in supervisor.gaps if "suspend" in g["reason"])
    assert (gap["start"], gap["end"]) == (5, 70)
    assert supervisor.health["mic_route_connected"]
    supervisor.selector.close()


def test_slow_monitor_does_not_claim_audio_loss(inv, monkeypatch):
    supervisor, _, _ = synthetic_routed_supervisor(inv, monkeypatch)
    monkeypatch.setattr(recorder, "elapsed_time", lambda: 120)
    monkeypatch.setattr(recorder.time, "monotonic", lambda: 120)
    supervisor.reconcile()
    assert supervisor.gaps == []
    assert supervisor.monitor_events == [{
        "start": 5, "end": 20, "kind": "poll_delayed",
        "reason": "Recording monitor delayed; audio continuity unverified",
    }]
    metadata = read_json(supervisor.path / "session.json")
    assert metadata["gaps"] == []
    assert metadata["monitor_events"] == supervisor.monitor_events
    supervisor.selector.close()


@pytest.mark.parametrize("change", ["loopback", "device-incarnation"])
def test_reconcile_repairs_lost_route_or_recreated_device(inv, monkeypatch, change):
    supervisor, route, modules = synthetic_routed_supervisor(inv, monkeypatch)
    if change == "loopback":
        modules[:] = [m for m in modules if m["index"] != "42"]
    else:
        inv["sources"][0]["index"] = 999
    calls = []
    monkeypatch.setattr(route, "connect_mic", lambda name: calls.append(name))
    supervisor.reconcile()
    assert calls == ["mic"]
    assert supervisor.health["mic_route_connected"]
    assert any("route reconnected" in gap["reason"] for gap in supervisor.gaps)
    supervisor.selector.close()


def test_status_recalculates_age_of_a_frozen_snapshot(monkeypatch):
    from shrutadhara.core import runtime_dir

    path = sessions.create("Frozen worker")
    sessions.update(path, recording="recording")
    monkeypatch.setattr(recorder, "active", lambda: {"session": str(path)})
    monkeypatch.setattr(recorder, "boot_identity", lambda: "same")
    monkeypatch.setattr(recorder, "elapsed_time", lambda: 120)
    atomic_json(runtime_dir() / "status.json", {"session_id": read_json(path / "session.json")["id"], "updated_elapsed": 100, "boot_id": "same", "health": {"microphone_present": True}, "progress_age_seconds": 1})
    state = recorder.status()
    assert state["health_stale"] and state["snapshot_age_seconds"] == 20
    assert state["progress_age_seconds"] == 21


def test_late_teams_binding_persists_only_changed_policy(inv, monkeypatch):
    supervisor, route, _ = synthetic_routed_supervisor(inv, monkeypatch)
    supervisor.data["devices"]["teams_pid"] = None
    supervisor.persist_devices()
    seen = []
    update = sessions.update
    def track(path, **fields):
        seen.append(set(fields))
        return update(path, **fields)
    monkeypatch.setattr(sessions, "update", track)
    inv["sink-inputs"] = [{"index": 9, "sink": 1, "properties": {"application.process.binary": "teams-for-linux", "application.process.id": "333"}}]
    supervisor.reconcile()
    assert read_json(supervisor.path / "session.json")["devices"]["teams_pid"] == "333"
    assert sum("devices" in fields for fields in seen) == 1
    supervisor.reconcile()
    assert sum("devices" in fields for fields in seen) == 1
    supervisor.selector.close()


def test_ambiguous_participant_interval_closes_only_after_identified_playback(inv, monkeypatch):
    supervisor, _, _ = synthetic_routed_supervisor(inv, monkeypatch)
    supervisor.data["devices"]["teams_pid"] = None
    clock = [110]
    monkeypatch.setattr(recorder, "elapsed_time", lambda: clock[0])
    monkeypatch.setattr(recorder.time, "monotonic", lambda: clock[0])
    def stream(pid):
        return {"index": 9, "sink": 1, "properties": {"application.process.binary": "teams-for-linux", "application.process.id": pid}}
    inv["sink-inputs"] = [stream(None), stream("333")]
    supervisor.reconcile()
    assert read_json(supervisor.path / "session.json")["devices"]["teams_ambiguous"]
    assert supervisor.missing_since["participants"] == 10
    clock[0] = 115
    inv["sink-inputs"] = [stream(None)]
    supervisor.reconcile()
    assert supervisor.missing_since["participants"] == 10
    assert not [gap for gap in supervisor.gaps if gap["track"] == "participants"]
    clock[0] = 120
    inv["sink-inputs"] = []
    supervisor.reconcile()
    assert supervisor.missing_since["participants"] == 10
    clock[0] = 125
    inv["sink-inputs"] = [stream("333")]
    supervisor.reconcile()
    assert "participants" not in supervisor.missing_since
    gaps = [gap for gap in supervisor.gaps if gap["track"] == "participants"]
    assert len(gaps) == 1 and gaps[0]["start"] == 10 and gaps[0]["end"] == 25
    persisted = read_json(supervisor.path / "session.json")["devices"]
    assert persisted["teams_pid"] == "333" and not persisted["teams_ambiguous"]
    supervisor.selector.close()
