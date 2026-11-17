"""Call automation stays responsive to transitions during slow recorder work."""

import json
import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from shrutadhara import teams
from shrutadhara.core import MeetingError


@pytest.fixture
def harness(monkeypatch):
    state = {"active": None, "started": [], "stopped": [], "notifications": []}
    threads = []

    def launch(action):
        thread = threading.Thread(target=action, daemon=True)
        threads.append(thread)
        thread.start()

    def start(*_):
        path = f"/synthetic/session-{len(state['started']) + 1}"
        state["started"].append(path)
        state["active"] = {"session": path}
        return Path(path)

    def stop(expected_session=None):
        if expected_session != state["active"]["session"]:
            raise MeetingError("Synthetic session ownership mismatch")
        state["stopped"].append(state["active"]["session"])
        state["active"] = None

    monkeypatch.setattr(teams.recorder, "active", lambda: state["active"])
    monkeypatch.setattr(teams.recorder, "start", start)
    monkeypatch.setattr(teams.recorder, "stop", stop)
    monkeypatch.setattr(teams, "notify", state["notifications"].append)

    def join():
        # Completion can launch one successor if a transition races with exit.
        for thread in threads:
            thread.join(timeout=2)
            assert not thread.is_alive()

    automation = teams._CallAutomation(launch)
    yield SimpleNamespace(
        state=state, automation=automation, join=join, start=start, stop=stop
    )
    join()


def test_call_end_during_blocked_start_eventually_stops(harness, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def blocked_start(*args):
        entered.set()
        assert release.wait(2)
        return harness.start(*args)

    monkeypatch.setattr(teams.recorder, "start", blocked_start)
    harness.automation.desire(True)
    assert entered.wait(2)
    harness.automation.desire(False)
    release.set()
    harness.join()
    assert harness.state["started"] == ["/synthetic/session-1"]
    assert harness.state["stopped"] == ["/synthetic/session-1"]
    assert harness.state["active"] is None


def test_new_call_during_blocked_stop_eventually_starts(harness, monkeypatch):
    harness.automation.desire(True)
    harness.join()
    entered, release = threading.Event(), threading.Event()

    def blocked_stop(**kwargs):
        entered.set()
        assert release.wait(2)
        harness.stop(**kwargs)

    monkeypatch.setattr(teams.recorder, "stop", blocked_stop)
    harness.automation.desire(False)
    assert entered.wait(2)
    harness.automation.desire(True)
    release.set()
    harness.join()
    assert harness.state["started"] == ["/synthetic/session-1", "/synthetic/session-2"]
    assert harness.state["stopped"] == ["/synthetic/session-1"]
    assert harness.state["active"] == {"session": "/synthetic/session-2"}


def test_unknown_state_preserves_owned_recording_until_confirmed_end(harness):
    harness.automation.desire(True)
    harness.join()
    harness.automation.desire(None)
    harness.join()
    assert harness.state["stopped"] == []
    assert harness.state["active"]
    harness.automation.desire(False)
    harness.join()
    assert harness.state["stopped"] == ["/synthetic/session-1"]


def test_bus_loss_during_start_keeps_result_for_later_reconciliation(
    harness, monkeypatch
):
    entered, release = threading.Event(), threading.Event()

    def blocked_start(*args):
        entered.set()
        assert release.wait(2)
        return harness.start(*args)

    monkeypatch.setattr(teams.recorder, "start", blocked_start)
    harness.automation.desire(True)
    assert entered.wait(2)
    harness.automation.desire(None)
    release.set()
    harness.join()
    assert harness.state["active"] and harness.state["stopped"] == []
    harness.automation.desire(False)
    harness.join()
    assert harness.state["active"] is None


def test_manual_recording_is_never_adopted_or_stopped(harness):
    harness.state["active"] = {"session": "/synthetic/manual"}
    harness.automation.desire(True)
    harness.join()
    harness.automation.desire(False)
    harness.join()
    assert harness.state["started"] == [] and harness.state["stopped"] == []
    assert harness.state["active"] == {"session": "/synthetic/manual"}


def test_replaced_recording_is_not_stopped(harness):
    harness.automation.desire(True)
    harness.join()
    harness.state["active"] = {"session": "/synthetic/manual"}
    harness.automation.desire(False)
    harness.join()
    assert harness.state["stopped"] == []
    assert harness.state["active"] == {"session": "/synthetic/manual"}


def test_failure_is_bounded_until_another_transition(harness, monkeypatch):
    calls = []

    def failed_start(*_):
        calls.append(True)
        raise MeetingError("Synthetic startup failure")

    monkeypatch.setattr(teams.recorder, "start", failed_start)
    harness.automation.desire(True)
    harness.join()
    harness.automation.desire(True)
    harness.join()
    assert len(calls) == 1
    assert len(harness.state["notifications"]) == 1
    harness.automation.desire(False)
    harness.join()
    harness.automation.desire(True)
    harness.join()
    assert len(calls) == 2


def test_queued_new_state_survives_failed_old_operation(harness, monkeypatch):
    harness.automation.desire(True)
    harness.join()
    entered, release = threading.Event(), threading.Event()

    def failed_stop(**_kwargs):
        entered.set()
        assert release.wait(2)
        raise MeetingError("Synthetic stop failure")

    monkeypatch.setattr(teams.recorder, "stop", failed_stop)
    harness.automation.desire(False)
    assert entered.wait(2)
    harness.automation.desire(True)
    release.set()
    harness.join()
    assert harness.state["active"] == {"session": "/synthetic/session-1"}
    assert harness.state["started"] == ["/synthetic/session-1"]
    assert len(harness.state["notifications"]) == 1


def install_fake_bus(monkeypatch, scenario):
    """Run watch's actual event wiring against a controlled GLib/D-Bus surface."""
    timers, handlers, calls = {}, {}, []
    state = {"owner": "fake-owner", "inCall": False}
    sequence = iter(range(1, 100))

    class Proxy:
        def get_name_owner(self):
            return state["owner"]

        def call_sync(self, *_):
            return SimpleNamespace(
                unpack=lambda: [json.dumps({"inCall": state["inCall"]})]
            )

        def connect(self, signal, callback):
            handlers[signal] = callback

    proxy = Proxy()

    def timeout(_seconds, callback):
        index = next(sequence)
        timers[index] = callback
        return index

    class Automation:
        def desire(self, value):
            calls.append(value)

    def emit(value):
        state["inCall"] = value
        handlers["g-signal"](
            proxy, "fake", "InCallChanged", SimpleNamespace(unpack=lambda: [value])
        )

    def owner(value):
        state["owner"] = value
        handlers["notify::g-name-owner"]()

    def fire():
        callbacks = list(timers.values())
        timers.clear()
        for callback in callbacks:
            callback()

    gi, repository = ModuleType("gi"), ModuleType("gi.repository")
    repository.Gio = SimpleNamespace(
        dbus_is_name=lambda value: True,
        DBusProxy=SimpleNamespace(new_for_bus_sync=lambda *_: proxy),
        BusType=SimpleNamespace(SESSION=1),
        DBusProxyFlags=SimpleNamespace(DO_NOT_AUTO_START=1),
        DBusCallFlags=SimpleNamespace(NONE=0),
    )
    repository.GLib = SimpleNamespace(
        timeout_add_seconds=timeout,
        source_remove=lambda index: timers.pop(index, None),
        MainLoop=lambda: SimpleNamespace(
            run=lambda: scenario(emit, owner, fire, state, calls)
        ),
    )
    gi.repository = repository
    monkeypatch.setitem(sys.modules, "gi", gi)
    monkeypatch.setitem(sys.modules, "gi.repository", repository)
    monkeypatch.setattr(teams, "_CallAutomation", Automation)
    monkeypatch.setattr(teams, "notify", lambda *_: None)
    teams.watch("synthetic.Teams", auto_record=True, validated=True)
    return calls


def test_bus_reconnect_confirms_end_without_midcall_start(monkeypatch):
    def scenario(emit, owner, fire, state, calls):
        fire()  # Initial false observation is safe and cannot start anything.
        emit(True)
        assert calls[-1] is True
        owner(None)
        assert calls[-1] is None
        state["inCall"] = True
        owner("new-owner")
        assert calls[-1] is None  # Reattachment does not start mid-call.
        owner(None)
        state["inCall"] = False
        owner("another-owner")
        fire()
        assert calls[-1] is False

    calls = install_fake_bus(monkeypatch, scenario)
    assert calls[-1] is None  # Monitor shutdown cancels pending actions.


def test_unknown_signal_does_not_request_start(monkeypatch):
    def scenario(emit, _owner, fire, _state, calls):
        fire()
        emit("not-a-boolean")
        assert calls[-1] is None
        assert True not in calls

    install_fake_bus(monkeypatch, scenario)


def test_stop_passes_owned_identity_if_recording_changes_after_lookup(
    harness, monkeypatch
):
    harness.automation.desire(True)
    harness.join()
    owned = dict(harness.state["active"])

    def replaced_after_lookup():
        harness.state["active"] = {"session": "/synthetic/replacement-manual"}
        return owned

    monkeypatch.setattr(teams.recorder, "active", replaced_after_lookup)
    harness.automation.desire(False)
    harness.join()
    assert harness.state["active"] == {"session": "/synthetic/replacement-manual"}
    assert harness.state["stopped"] == []
    assert len(harness.state["notifications"]) == 1


def test_transition_during_worker_exit_is_reconciled(harness, monkeypatch):
    harness.automation.desire(True)
    harness.join()
    harness.automation.desire(None)
    looked_up = threading.Event()

    def change_after_lookup():
        if not looked_up.is_set():
            looked_up.set()
            harness.automation.desire(False)
        return harness.state["active"]

    monkeypatch.setattr(teams.recorder, "active", change_after_lookup)
    harness.automation.desire(True)
    harness.join()
    assert harness.state["stopped"] == ["/synthetic/session-1"]
    assert harness.state["active"] is None
