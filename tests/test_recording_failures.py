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
