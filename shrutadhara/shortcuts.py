"""Manual desktop bindings and explicitly configured window-local accelerators."""

from .core import MeetingError, atomic_json, config, config_path

DEFAULTS = {"start": "<Control><Shift>r", "stop": "<Control><Shift>s"}


def accelerators():
    return {**DEFAULTS, **config().get("shortcuts", {})}


def save_accelerators(start=None, stop=None):
    if start is None and stop is None:
        return
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
    except (ImportError, ValueError) as exc:
        raise MeetingError("GTK is required to validate local accelerators", 3) from exc
    values = accelerators()
    for name, value in (("start", start), ("stop", stop)):
        if value is not None:
            if value:
                valid, key, modifiers = Gtk.accelerator_parse(value)
                if not valid or not Gtk.accelerator_valid(key, modifiers):
                    raise MeetingError("Invalid GTK accelerator", 2)
            values[name] = value
    parsed = {}
    for name, value in values.items():
        if value:
            valid, key, modifiers = Gtk.accelerator_parse(value)
            if not valid or not Gtk.accelerator_valid(key, modifiers):
                raise MeetingError("Invalid GTK accelerator", 2)
            values[name] = Gtk.accelerator_name(key, modifiers)
            parsed[name] = (key, int(modifiers))
    if "start" in parsed and parsed["start"] == parsed.get("stop"):
        raise MeetingError("Start and stop shortcuts must differ", 2)
    cfg = config()
    cfg["shortcuts"] = values
    atomic_json(config_path(), cfg)


def setup_text():
    return """Recording controls: shruta show | shruta start | shruta stop
Start and stop are idempotent. Choose unused desktop bindings yourself.
Hyprland:
  bind = SUPER SHIFT, R, exec, shruta show
  bind = SUPER SHIFT, S, exec, shruta stop
Sway:
  bindsym $mod+Shift+r exec shruta show
  bindsym $mod+Shift+s exec shruta stop
KDE: System Settings > Keyboard > Shortcuts; add each command as a custom shortcut.
GNOME: Settings > Keyboard > Custom Shortcuts; add each command above.
Use the absolute installed command path if your compositor PATH differs.
Window-local GTK shortcuts (restart the GUI after changing):
  shruta shortcuts --start '<Control><Shift>r' --stop '<Control><Shift>s'
Use an empty value to disable a local shortcut. These work only in the app window.
GlobalShortcuts portal integration is deferred; compositor commands work independently.
Keep the recording window visible; closing it leaves capture running.
"""
