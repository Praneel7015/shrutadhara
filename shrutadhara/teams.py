"""Optional, read-only use of Teams' documented local D-Bus interface."""

from __future__ import annotations

import json
import threading

from . import recorder
from .core import MeetingError, notify

OBJECT = "/com/github/IsmaelMartinez/teams_for_linux"
INTERFACE = "com.github.IsmaelMartinez.teams_for_linux.Control"


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
    state = {"in_call": None, "owned_session": None, "pending_stop": 0, "busy": False}

    def snapshot():
        result = proxy.call_sync("GetState", None, Gio.DBusCallFlags.NONE, 3000, None)
        return json.loads(result.unpack()[0])

    def worker(action):
        if state["busy"]:
            return
        state["busy"] = True

        def execute():
            try:
                action()
            except MeetingError:
                notify("Call automation failed — inspect shruta status")
            finally:
                state["busy"] = False

        threading.Thread(target=execute, daemon=True).start()

    def start_call():
        if recorder.active():
            return
        state["owned_session"] = str(recorder.start("Teams call", {}))

    def stop_call():
        current = recorder.active()
        if current and current["session"] == state["owned_session"]:
            recorder.stop()
        state["owned_session"] = None

    def confirm_end():
        state["pending_stop"] = 0
        try:
            if proxy.get_name_owner() and snapshot().get("inCall") is False:
                notify("Teams call ended")
                if auto_record:
                    worker(stop_call)
        except Exception:
            notify("Teams call state unknown; recording continues")
        return False

    def observe(in_call, initial=False):
        previous = state["in_call"]
        state["in_call"] = in_call
        if state["pending_stop"]:
            GLib.source_remove(state["pending_stop"])
            state["pending_stop"] = 0
        if initial:
            return
        if in_call and previous is False:
            notify(
                "Teams call detected"
                + (" — recording requested" if auto_record else " — use shruta start")
            )
            if auto_record:
                worker(start_call)
        elif in_call is False and previous is True:
            state["pending_stop"] = GLib.timeout_add_seconds(5, confirm_end)

    def on_signal(_proxy, sender, name, parameters):
        if name == "InCallChanged":
            observe(bool(parameters.unpack()[0]))

    def owner_changed(*_):
        if state["pending_stop"]:
            GLib.source_remove(state["pending_stop"])
            state["pending_stop"] = 0
        if not proxy.get_name_owner():
            state["in_call"] = None
            notify(
                "Teams connection lost; call state unknown. Active recording continues."
            )
        else:
            try:
                observe(snapshot().get("inCall"), initial=True)
            except Exception:
                state["in_call"] = None

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
        notify(
            "Teams call monitor stopped; check shruta status for any active recording"
        )
