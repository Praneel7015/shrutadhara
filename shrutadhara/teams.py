"""Optional, read-only use of Teams' documented local D-Bus interface."""

from __future__ import annotations

import json
import threading

from . import recorder
from .core import MeetingError, notify

OBJECT = "/com/github/IsmaelMartinez/teams_for_linux"
INTERFACE = "com.github.IsmaelMartinez.teams_for_linux.Control"


class _CallAutomation:
    """Reconcile the latest confirmed call state with only our own recording.

    External recorder operations never hold the state lock. A changed desired
    state is retained while an operation is in flight. Failures get one attempt
    per state generation, rather than a tight retry loop.
    """

    def __init__(self, launch=None):
        self._lock = threading.Lock()
        self._desired: bool | None = None
        self._generation = 0
        self._failed_generation = None
        self._owned_session: str | None = None
        self._busy = False
        self._launch = launch or self._start_thread

    @staticmethod
    def _start_thread(action):
        threading.Thread(target=action, daemon=True).start()

    def desire(self, in_call: bool | None):
        if in_call is not None and not isinstance(in_call, bool):
            in_call = None
        with self._lock:
            if self._desired is in_call:
                return
            self._desired = in_call
            self._generation += 1
            if self._busy or in_call is None:
                return
            self._busy = True
        self._launch(self._work)

    def _work(self):
        generation = None
        try:
            while True:
                with self._lock:
                    generation = self._generation
                    desired = self._desired
                    owned = self._owned_session
                    if desired is None or generation == self._failed_generation:
                        return
                try:
                    current = recorder.active()
                    if desired:
                        if current:
                            # Never adopt a manual or another monitor's session.
                            if current["session"] != owned:
                                with self._lock:
                                    self._owned_session = None
                            return
                        path = recorder.start("Teams call", {})
                        with self._lock:
                            self._owned_session = str(path)
                    else:
                        if owned is None:
                            return
                        if current and current["session"] == owned:
                            recorder.stop(expected_session=owned)
                        with self._lock:
                            if self._owned_session == owned:
                                self._owned_session = None
                except (MeetingError, OSError, ValueError):
                    with self._lock:
                        self._failed_generation = generation
                    notify("Call automation failed — inspect shruta status")
                    # A newer transition still needs reconciliation after a
                    # failure; the failed generation itself is not retried.
        finally:
            with self._lock:
                self._busy = False
                retry = (
                    self._desired is not None
                    and self._generation != generation
                    and self._generation != self._failed_generation
                )
                if retry:
                    self._busy = True
            if retry:
                self._launch(self._work)


def watch(bus_name: str, auto_record: bool = False, validated: bool = False):
    if auto_record and not validated:
        raise MeetingError(
            "Test call transitions and devices first, then explicitly pass --validated --auto-record",
            7,
        )
    try:
        from gi.repository import Gio, GLib
    except ImportError as exc:
        raise MeetingError("Call monitoring needs python-gobject", 3) from exc
    if not Gio.dbus_is_name(bus_name):
        raise MeetingError("Invalid D-Bus service name", 2)
    proxy = Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION,
        Gio.DBusProxyFlags.DO_NOT_AUTO_START,
        None,
        bus_name,
        OBJECT,
        INTERFACE,
        None,
    )
    if not proxy.get_name_owner():
        raise MeetingError(
            "Teams D-Bus control is unavailable; enable dbusControl.enabled and restart Teams",
            3,
        )
    state = {"in_call": None, "pending_stop": 0, "attached": False}
    automation = _CallAutomation() if auto_record else None

    def snapshot():
        result = proxy.call_sync("GetState", None, Gio.DBusCallFlags.NONE, 3000, None)
        return json.loads(result.unpack()[0])

    def confirm_end():
        state["pending_stop"] = 0
        try:
            if not proxy.get_name_owner():
                if automation:
                    automation.desire(None)
            elif snapshot().get("inCall") is False:
                notify("Teams call ended")
                if auto_record:
                    automation.desire(False)
        except Exception:
            if automation:
                automation.desire(None)
            notify("Teams call state unknown; recording continues")
        return False

    def observe(in_call, initial=False):
        in_call = in_call if isinstance(in_call, bool) else None
        previous = state["in_call"]
        state["in_call"] = in_call
        if state["pending_stop"]:
            GLib.source_remove(state["pending_stop"])
            state["pending_stop"] = 0
        if in_call is None and automation:
            automation.desire(None)
        if initial:
            # Reconnection must resolve a pending owned recording when the call
            # has ended, without starting a recording mid-call on attachment.
            if in_call is False and state["attached"]:
                state["pending_stop"] = GLib.timeout_add_seconds(5, confirm_end)
            state["attached"] = True
            return
        if in_call and previous is False:
            notify(
                "Teams call detected"
                + (" — recording requested" if auto_record else " — use shruta start")
            )
            if auto_record:
                automation.desire(True)
        elif in_call is False and previous is True:
            state["pending_stop"] = GLib.timeout_add_seconds(5, confirm_end)

    def on_signal(_proxy, sender, name, parameters):
        if name == "InCallChanged":
            observe(parameters.unpack()[0])

    def owner_changed(*_):
        if state["pending_stop"]:
            GLib.source_remove(state["pending_stop"])
            state["pending_stop"] = 0
        if not proxy.get_name_owner():
            state["in_call"] = None
            if automation:
                automation.desire(None)
            notify(
                "Teams connection lost; call state unknown. Active recording continues."
            )
        else:
            try:
                observe(snapshot().get("inCall"), initial=True)
            except Exception:
                state["in_call"] = None
                if automation:
                    automation.desire(None)

    proxy.connect("g-signal", on_signal)
    proxy.connect("notify::g-name-owner", owner_changed)
    observe(snapshot().get("inCall"), initial=True)
    notify(
        "Teams call monitor active"
        + (" — automatic recording enabled" if auto_record else " — notifications only")
    )
    try:
        GLib.MainLoop().run()
    finally:
        if automation:
            automation.desire(None)
        notify(
            "Teams call monitor stopped; check shruta status for any active recording"
        )
