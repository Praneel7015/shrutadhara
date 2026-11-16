import json
import os
from pathlib import Path

import pytest

from shrutadhara import core
from shrutadhara.desktop import install


def legacy_config():
    directory = core.config_path().parent.parent / "meeting"
    directory.mkdir(parents=True)
    return directory


def test_legacy_settings_and_failed_capability_are_copied_without_changing_originals():
    legacy = legacy_config()
    settings = {
        "root": "/private/original-meetings",
        "hosted_consent": False,
        "auto_process": False,
        "model": "existing-agy-model",
        "microphone_notice_ack": True,
    }
    (legacy / "config.json").write_text(json.dumps(settings))
    capability = {
        "identity": {"version": "existing"},
        "passed": False,
        "reason": "Known accuracy failure",
    }
    (legacy / "capability.json").write_text(json.dumps(capability))
    original = (legacy / "config.json").read_bytes()
    assert core.config()["model"] == "existing-agy-model"
    assert core.read_json(core.config_path()) == settings
    assert core.read_json(core.config_path().parent / "capability.json") == capability
    assert (legacy / "config.json").read_bytes() == original
    assert core.config_path().stat().st_mode & 0o777 == 0o600


def test_current_settings_take_precedence_over_legacy_settings():
    legacy = legacy_config()
    (legacy / "config.json").write_text('{"hosted_consent":true,"model":"old"}')
    core.atomic_json(core.config_path(), {"hosted_consent": False, "model": "new"})
    assert core.config()["hosted_consent"] is False
    assert core.config()["model"] == "new"


def test_legacy_explicit_consent_is_preserved_not_invented():
    legacy = legacy_config()
    (legacy / "config.json").write_text('{"hosted_consent":true,"auto_process":false}')
    assert core.config()["hosted_consent"] is True
    assert core.config()["auto_process"] is False


@pytest.mark.parametrize("location", ["legacy", "current"])
def test_nonboolean_consent_never_enables_uploads(location):
    directory = (
        legacy_config()
        if location == "legacy"
        else core.private_dir(core.config_path().parent)
    )
    (directory / "config.json").write_text('{"hosted_consent":"false"}')
    with pytest.raises(core.MeetingError, match="must be a boolean"):
        core.config()


def test_storage_override_compatibility(monkeypatch):
    monkeypatch.delenv("SHRUTA_ROOT")
    monkeypatch.setenv("MEETING_ROOT", "/old/storage")
    assert core.config()["root"] == "/old/storage"
    monkeypatch.setenv("SHRUTA_ROOT", "/new/storage")
    assert core.config()["root"] == "/new/storage"


def test_active_legacy_runtime_remains_controllable(monkeypatch):
    legacy = Path(os.environ["XDG_RUNTIME_DIR"]) / "meeting-recorder"
    with core.locked(legacy / "recording.lock"):
        assert core.runtime_dir() == legacy
    assert core.runtime_dir().name == "shrutadhara"


def test_managed_legacy_launcher_is_forwarded_and_desktop_is_backed_up(tmp_path):
    old_launcher = tmp_path / ".local/bin/meeting"
    old_launcher.parent.mkdir(parents=True)
    old_launcher.write_text(
        "#!/bin/sh\n# Managed by linux-meeting-recorder\nold command\n"
    )
    data = tmp_path / "data"
    old_desktop = data / "applications/local.meeting.Recorder.desktop"
    old_desktop.parent.mkdir(parents=True)
    old_body = "[Desktop Entry]\nName=Meeting recorder\nX-Meeting-Recorder=true\n"
    old_desktop.write_text(old_body)
    install(tmp_path, data)
    assert (tmp_path / ".local/bin/shruta").exists()
    assert str(tmp_path / ".local/bin/shruta") in old_launcher.read_text()
    assert not old_desktop.exists()
    assert (
        data / "shrutadhara/migration/legacy-recorder.desktop.backup"
    ).read_text() == old_body


def test_unrelated_old_launcher_is_not_modified(tmp_path):
    old = tmp_path / ".local/bin/meeting"
    old.parent.mkdir(parents=True)
    old.write_text("unrelated application")
    install(tmp_path, tmp_path / "data")
    assert old.read_text() == "unrelated application"


def test_repeated_installation_keeps_legacy_alias_on_current_launcher(
    tmp_path, monkeypatch
):
    import shrutadhara.desktop as desktop

    old = tmp_path / ".local/bin/meeting"
    old.parent.mkdir(parents=True)
    old.write_text("#!/bin/sh\n# Managed by linux-meeting-recorder\nold command\n")
    monkeypatch.setattr(desktop.sys, "executable", "/old-venv/bin/python")
    install(tmp_path, tmp_path / "data")
    monkeypatch.setattr(desktop.sys, "executable", "/new-venv/bin/python")
    install(tmp_path, tmp_path / "data")
    assert str(tmp_path / ".local/bin/shruta") in old.read_text()
    assert "/old-venv" not in old.read_text()
    assert "/new-venv/bin/python" in (tmp_path / ".local/bin/shruta").read_text()
