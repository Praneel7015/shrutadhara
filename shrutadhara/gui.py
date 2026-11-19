from __future__ import annotations

import subprocess
import sys
import textwrap
import threading
from pathlib import Path

from . import audio, recorder, sessions
from .core import MeetingError, atomic_json, config, config_path, now, read_json
from .sandbox import is_flatpak, keep_window_open


def ui_state(
    recording: str | None, busy: bool, has_session: bool, processing: bool
) -> dict:
    active = recording in {"starting", "recording", "stopping"}
    return {
        "record_label": "Stop recording" if active else "Start recording",
        "record_enabled": not busy and recording not in {"starting", "stopping"},
        "process_enabled": has_session and not active and not busy and not processing,
        "settings_enabled": not active and not busy,
    }


def require_gtk_version(gtk):
    if (gtk.get_major_version(), gtk.get_minor_version()) < (4, 10):
        raise MeetingError("GUI requires GTK 4.10 or newer for recording confirmations", 3)


def output_state(path: Path | None, data: dict | None) -> dict:
    return {
        "folder": data is not None,
        "notes": bool(data and data["notes"] in {"complete", "partial"}),
        "transcript": bool(path and (path / "transcript/full-transcript.md").exists()),
    }


def recent_sessions(limit: int = 12) -> list[tuple[Path, str]]:
    items = []
    for path in sessions.list_sessions():
        try:
            data = read_json(path / "session.json")
        except MeetingError:
            continue
        items.append((path, f"{path.name[:17]} · {data.get('title', 'Meeting')}"))
        if len(items) >= limit:
            break
    return items


def history_selection(items: list[tuple[Path, str]], current: Path | None):
    """Keep the selected target represented even when it falls outside history."""
    items = list(items)
    paths = [path for path, _ in items]
    if current is not None and current not in paths:
        items.insert(0, (current, f"Selected meeting · {current.name}"))
        paths.insert(0, current)
    index = paths.index(current) if current in paths else 0
    return items, index


def launch_processing(path: Path, prepare_only: bool = False):
    command = [
        sys.executable,
        "-m",
        "shrutadhara",
        "process",
        "--session",
        str(path),
    ]
    if prepare_only:
        command.append("--prepare-only")
    with (path / "logs/processing.log").open("a") as log:
        return subprocess.Popen(
            command,
            cwd=Path(__file__).resolve().parent.parent,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )


def launch() -> int:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, GLib, Gtk
    except (ImportError, ValueError) as exc:
        raise MeetingError(
            "GUI needs GTK 4 and python-gobject. The CLI works without them.", 3
        ) from exc
    require_gtk_version(Gtk)
    if not Gtk.init_check():
        raise MeetingError("No graphical display available; use the CLI", 3)
    from .cli import HOSTED, PRIVACY, artifact, doctor, open_path

    class Window(Gtk.ApplicationWindow):
        def __init__(self, app):
            super().__init__(
                application=app,
                title="Shrutadhara",
                default_width=430,
                resizable=True,
            )
            self.busy = False
            self.path = None
            self.recording = None
            self.mic_names, self.output_names = [None], [None]
            self.process_requested = False
            self.processing_pid = None
            self.history_paths = []
            self.history_items = []
            self.updating_history = False
            self.preparing_local = False
            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=12,
                margin_top=20,
                margin_bottom=20,
                margin_start=20,
                margin_end=20,
            )
            scroll = Gtk.ScrolledWindow(
                hscrollbar_policy=Gtk.PolicyType.NEVER,
                propagate_natural_height=True,
                min_content_height=320,
                max_content_height=700,
            )
            scroll.set_child(box)
            self.set_child(scroll)
            heading = Gtk.Label(label="Shrutadhara", xalign=0)
            heading.add_css_class("title-2")
            box.append(heading)
            philosophy = Gtk.Label(
                label="Hear everything. Preserve knowledge. Remember what matters.",
                xalign=0,
                wrap=True,
            )
            philosophy.add_css_class("dim-label")
            box.append(philosophy)
            self.title_entry = Gtk.Entry(placeholder_text="Meeting title (optional)")
            box.append(self.title_entry)
            self.state_label = Gtk.Label(
                label="Ready", xalign=0, wrap=True, selectable=True
            )
            box.append(self.state_label)
            self.health_label = Gtk.Label(
                label="Audio devices will be checked before recording",
                xalign=0,
                wrap=True,
            )
            self.health_label.add_css_class("dim-label")
            box.append(self.health_label)
            self.record_button = Gtk.Button(label="Start recording")
            self.record_button.add_css_class("suggested-action")
            self.record_button.connect("clicked", self.record_clicked)
            box.append(self.record_button)
            self.process_button = Gtk.Button(label="Process recording")
            self.process_button.connect("clicked", self.process_clicked)
            box.append(self.process_button)
            row = Gtk.Box(spacing=6, homogeneous=True)
            self.output_buttons = {}
            for name, label in [
                ("notes", "Open notes"),
                ("transcript", "Transcript"),
                ("folder", "Folder"),
            ]:
                button = Gtk.Button(label=label)
                button.connect("clicked", lambda _, kind=name: self.open_artifact(kind))
                self.output_buttons[name] = button
                row.append(button)
            box.append(row)
            self.settings = Gtk.Expander(label="Devices and diagnostics")
            settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            mic_label = Gtk.Label(label="_Microphone", use_underline=True, xalign=0)
            settings_box.append(mic_label)
            self.mic = Gtk.DropDown.new_from_strings(["Automatic (Teams / default)"])
            mic_label.set_mnemonic_widget(self.mic)
            settings_box.append(self.mic)
            output_label = Gtk.Label(label="_Listen through", use_underline=True, xalign=0)
            settings_box.append(output_label)
            self.output = Gtk.DropDown.new_from_strings(["Automatic (desktop default)"])
            output_label.set_mnemonic_widget(self.output)
            settings_box.append(self.output)
            self.allow_muted = Gtk.CheckButton(
                label="Allow recording with system-muted microphone"
            )
            settings_box.append(self.allow_muted)
            refresh = Gtk.Button(label="Refresh devices")
            refresh.connect(
                "clicked", lambda *_: self.background(audio.inventory, self.set_devices)
            )
            settings_box.append(refresh)
            diagnostics = Gtk.Button(label="Check dependencies (no AI upload)")
            diagnostics.connect(
                "clicked", lambda *_: self.background(doctor, self.show_doctor)
            )
            settings_box.append(diagnostics)
            self.settings.set_child(settings_box)
            box.append(self.settings)
            recordings = Gtk.Expander(label="Recordings and local tools")
            recordings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            history_label = Gtk.Label(label="_Recent meeting", use_underline=True, xalign=0)
            recordings_box.append(history_label)
            self.history = Gtk.DropDown.new_from_strings(["No recordings yet"])
            history_label.set_mnemonic_widget(self.history)
            self.history.connect("notify::selected", self.select_history)
            recordings_box.append(self.history)
            history_refresh = Gtk.Button(label="Refresh meetings")
            history_refresh.connect("clicked", lambda *_: self.background(recent_sessions, self.set_history))
            recordings_box.append(history_refresh)
            self.prepare_button = Gtk.Button(label="Prepare audio locally (no AI upload)")
            self.prepare_button.connect("clicked", self.prepare_clicked)
            recordings_box.append(self.prepare_button)
            audio_row = Gtk.Box(spacing=6, homogeneous=True)
            self.audio_buttons = {}
            for kind, label in [("microphone", "Microphone audio"), ("participants", "Participants audio")]:
                button = Gtk.Button(label=label)
                button.connect("clicked", lambda _, name=kind: self.open_artifact(name))
                audio_row.append(button)
                self.audio_buttons[kind] = button
            recordings_box.append(audio_row)
            recordings.set_child(recordings_box)
            box.append(recordings)
            self.message = Gtk.Label(xalign=0, wrap=True, selectable=True)
            box.append(self.message)
            self.location = Gtk.Label(xalign=0, wrap=True, selectable=True)
            self.location.add_css_class("dim-label")
            box.append(self.location)
            self.timer = GLib.timeout_add_seconds(1, self.tick)
            self.connect("close-request", self.close_requested)
            self.connect("destroy", lambda *_: GLib.source_remove(self.timer))
            self.set_history(recent_sessions())
            self.tick()
            self.background(audio.inventory, self.set_devices)

        def close_requested(self, *_):
            # The last window owns the Flatpak sandbox lifetime. Retain it until
            # capture finalization/local preparation has finished.
            blocked = keep_window_open(self.busy, self.recording, self.process_requested)
            if blocked:
                self.message.set_text(
                    "Stop recording and wait for local work to finish before closing this Flatpak window."
                )
            return blocked

        def background(self, function, done=None):
            if self.busy:
                return
            self.busy = True
            self.tick()

            def work():
                value, error = None, None
                try:
                    value = function()
                except Exception as exc:
                    error = (
                        str(exc)
                        if isinstance(exc, MeetingError)
                        else "Operation failed; inspect session diagnostics"
                    )
                GLib.idle_add(self.finished, done, value, error)

            threading.Thread(target=work, daemon=True).start()

        def finished(self, done, value, error):
            self.busy = False
            if error:
                self.message.set_text(error)
            elif done:
                done(value)
            self.tick()
            return False

        def set_devices(self, inv):
            microphones = [
                s for s in inv["sources"] if not s["name"].endswith(".monitor")
            ]
            sinks = [s for s in inv["sinks"] if not s["name"].startswith("shruta_")]
            self.mic_names = [None] + [s["name"] for s in microphones]
            self.output_names = [None] + [s["name"] for s in sinks]
            self.mic.set_model(
                Gtk.StringList.new(
                    ["Automatic (Teams / default)"]
                    + [s.get("description", s["name"]) for s in microphones]
                )
            )
            self.output.set_model(
                Gtk.StringList.new(
                    ["Automatic (desktop default)"]
                    + [s.get("description", s["name"]) for s in sinks]
                )
            )
            self.mic.set_selected(0)
            self.output.set_selected(0)

        def show_doctor(self, report):
            mic = report.get("audio", {}).get("microphones", [])
            text = (
                "; ".join(report["errors"])
                if report["errors"]
                else "Recording dependencies available"
            )
            text += f". {report['gui']}. agy audio: {report['audio_capability']}."
            if any(m["muted"] for m in mic):
                text += " A microphone is system-muted."
            self.message.set_text(text)

        def set_history(self, items):
            self.updating_history = True
            try:
                items, index = history_selection(items, self.path)
                self.history_items = items
                self.history_paths = [path for path, _ in items]
                self.history.set_model(Gtk.StringList.new([label for _, label in items] or ["No recordings yet"]))
                if not self.path and self.history_paths:
                    self.path = self.history_paths[0]
                self.history.set_selected(index)
            finally:
                self.updating_history = False

        def select_history(self, *_):
            if self.updating_history or self.busy or self.recording in {"starting", "recording", "stopping"} or self.process_requested:
                return
            index = self.history.get_selected()
            if index < len(self.history_paths):
                self.path = self.history_paths[index]
                self.tick()

        def prepare_clicked(self, *_):
            if not self.path:
                return
            path = self.path
            job = launch_processing(path, prepare_only=True)
            self.processing_pid = job.pid
            self.process_requested = True
            self.preparing_local = True
            self.message.set_text("Local audio preparation requested. No AI upload is performed.")
            self.tick()

        def confirm(self, title, body, accept, callback):
            dialog = Gtk.AlertDialog(
                message=title,
                detail=textwrap.fill(body, width=58),
                buttons=["Cancel", accept],
                cancel_button=0,
                default_button=0,
            )

            def answered(d, result):
                try:
                    if d.choose_finish(result) == 1:
                        callback()
                except GLib.Error:
                    pass

            dialog.choose(self, None, answered)

        def record_clicked(self, *_):
            if self.recording in {"starting", "recording", "stopping"}:
                self.background(lambda: recorder.stop(wait=False))
                return
            cfg = config()
            if not cfg.get("microphone_notice_ack"):

                def acknowledge():
                    cfg["microphone_notice_ack"] = True
                    atomic_json(config_path(), cfg)
                    self.begin_recording()

                self.confirm(
                    "Before recording", PRIVACY, "Start recording", acknowledge
                )
            else:
                self.begin_recording()

        def begin_recording(self):
            opts = {
                "microphone": self.mic_names[self.mic.get_selected()],
                "output": self.output_names[self.output.get_selected()],
                "allow_muted_mic": self.allow_muted.get_active(),
            }
            title = self.title_entry.get_text().strip() or "Team meeting"
            self.message.set_text("")
            self.background(lambda: recorder.start(title, opts), self.started)

        def started(self, path):
            self.path = path
            self.message.set_text("Recording continues if you close this window.")

        def process_clicked(self, *_):
            if not self.path:
                return
            path = self.path

            def begin():
                job = launch_processing(path)
                self.processing_pid = job.pid
                self.process_requested = True
                self.preparing_local = False
                self.message.set_text(
                    "Processing requested. Capability checks run before any meeting upload; use the CLI doctor probe if blocked."
                )
                self.tick()

            cfg = config()
            if not cfg["hosted_consent"]:

                def allow():
                    cfg.update(
                        hosted_consent=True,
                        hosted_consent_at=now(),
                        hosted_disclosure=HOSTED,
                    )
                    atomic_json(config_path(), cfg)
                    begin()

                self.confirm(
                    "Allow hosted AI processing?", HOSTED, "Allow processing", allow
                )
            else:
                begin()

        def open_artifact(self, kind):
            if not self.path:
                return
            try:
                open_path(artifact(self.path, kind))
            except MeetingError as exc:
                self.message.set_text(str(exc))

        def tick(self):
            try:
                state = recorder.status()
                if state.get("active"):
                    self.path = Path(state["session"])
                if self.path and (
                    self.path not in self.history_paths
                    or self.history.get_selected() != self.history_paths.index(self.path)
                ):
                    self.set_history(self.history_items)
                data = read_json(self.path / "session.json") if self.path else None
                self.recording = data["recording"] if data else None
                processing = bool(
                    data
                    and (
                        data["transcription"] == "running" or data["notes"] == "running"
                    )
                )
                if self.process_requested and data:
                    if self.processing_pid and recorder.process_identity(self.processing_pid) is None:
                        self.process_requested = False
                        self.message.set_text(
                            "Local preparation finished. Check the session folder and processing log."
                            if self.preparing_local
                            else (
                                data["errors"][-1]["message"]
                                if data["transcription"] in {"blocked", "failed", "partial"} and data["errors"]
                                else "Processing finished. Check the session outputs and processing log."
                            )
                        )
                flags = ui_state(
                    self.recording,
                    self.busy,
                    bool(data),
                    processing or self.process_requested,
                )
                self.record_button.set_label(flags["record_label"])
                self.record_button.set_sensitive(flags["record_enabled"])
                self.process_button.set_sensitive(flags["process_enabled"] and not is_flatpak())
                if is_flatpak():
                    self.process_button.set_tooltip_text("AI processing requires a native installation")
                self.prepare_button.set_sensitive(flags["process_enabled"])
                self.history.set_sensitive(flags["process_enabled"])
                for name, button in self.audio_buttons.items():
                    button.set_sensitive(bool(self.path and (self.path / f"audio/{name}.wav").exists()))
                self.settings.set_sensitive(flags["settings_enabled"])
                if self.recording == "recording":
                    seconds = int(state.get("elapsed_seconds", 0))
                    self.state_label.set_text(
                        f"● RECORDING  {seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
                    )
                    self.record_button.add_css_class("destructive-action")
                    self.record_button.remove_css_class("suggested-action")
                else:
                    self.state_label.set_text(
                        "Working…"
                        if self.busy
                        else (self.recording or "Ready").capitalize()
                    )
                    self.record_button.remove_css_class("destructive-action")
                    self.record_button.add_css_class("suggested-action")
                if self.recording == "stopping":
                    self.health_label.set_text(
                        "Stopping capture and finalizing local audio files. "
                        "Original archives are retained; wait for finalization before processing."
                    )
                elif state.get("active"):
                    health = state.get("health", {})
                    mic = (
                        "system-muted"
                        if health.get("microphone_muted")
                        else (
                            "connected"
                            if health.get("microphone_present") and health.get("mic_route_connected")
                            else "checking / unavailable"
                        )
                    )
                    remote = (
                        "Teams selection needed"
                        if health.get("teams_ambiguous")
                        else f"{health.get('teams_streams', 0)} Teams streams"
                    )
                    self.health_label.set_text(
                        "Recording status is stale; audio health is unknown. Check status or stop recording."
                        if state.get("health_stale") else
                        f"Microphone: {mic} · Participants: {remote} · Audio warnings: {state.get('gaps', 0)}"
                        f" · Monitor delays: {state.get('monitor_delays', 0)}"
                    )
                elif data:
                    health_text = (
                        f"Transcript: {data['transcription']} · Notes: {data['notes']}"
                    )
                    warnings = [
                        name
                        for name, item in data.get("artifacts", {}).items()
                        if name != "combined"
                        and any(t.get("silent") for t in item.get("tracks", []))
                    ]
                    if warnings:
                        health_text += " · Silent track: " + ", ".join(warnings)
                    clipped = [
                        name
                        for name, item in data.get("artifacts", {}).items()
                        if name != "combined"
                        and any(t.get("clipping") for t in item.get("tracks", []))
                    ]
                    if clipped:
                        health_text += " · Clipping: " + ", ".join(clipped)
                    self.health_label.set_text(health_text)
                if data:
                    self.location.set_text(str(self.path))
                for name, enabled in output_state(self.path, data).items():
                    self.output_buttons[name].set_sensitive(enabled)
            except MeetingError as exc:
                self.message.set_text(str(exc))
            return True

    app = Gtk.Application(
        application_id="io.github.Praneel7015.Shrutadhara",
        flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
    )

    def activate(application):
        window = application.get_active_window()
        if window is None:
            window = Window(application)
        window.present()

    from .shortcuts import accelerators

    def shortcut_action(name):
        window = app.get_active_window()
        if window is None:
            activate(app)
            window = app.get_active_window()
        if window.busy:
            return
        if name == "start" and window.recording not in {
            "starting",
            "recording",
            "stopping",
        }:
            window.record_clicked()
        elif name == "stop" and window.recording in {"starting", "recording"}:
            window.background(lambda: recorder.stop(wait=False))

    for name, accelerator in accelerators().items():
        action = Gio.SimpleAction.new(name, None)
        action.connect(
            "activate", lambda _action, _parameter, name=name: shortcut_action(name)
        )
        app.add_action(action)
        if accelerator:
            app.set_accels_for_action("app." + name, [accelerator])
    app.connect("activate", activate)
    return app.run([])
