import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shrutadhara import cli
from shrutadhara.desktop import install
from shrutadhara.shortcuts import accelerators, setup_text


def test_repeated_start_and_stop_do_not_capture(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.recorder, "active", lambda: {"session": "/synthetic/session"}
    )
    monkeypatch.setattr(
        cli.recorder, "start", lambda *_: pytest.fail("must not restart")
    )
    assert cli.main(["start"]) == 0
    assert "/synthetic/session" in capsys.readouterr().out
    monkeypatch.setattr(cli.recorder, "active", lambda: None)
    monkeypatch.setattr(cli.recorder, "stop", lambda *_: pytest.fail("must not stop"))
    assert cli.main(["stop"]) == 0


def test_shortcut_help_is_offline_and_mentions_desktops():
    text = setup_text()
    assert all(name in text for name in ["Hyprland", "Sway", "KDE", "GNOME"])
    assert "deferred" in text
    assert accelerators()["start"] != accelerators()["stop"]
    assert cli.parser().parse_args(["show"]).command == "show"


def test_desktop_setup_uses_current_python_and_refuses_unrelated(tmp_path):
    install(tmp_path, tmp_path / "data")
    launcher = tmp_path / ".local/bin/shruta"
    assert "-m shrutadhara" in launcher.read_text()
    assert (
        "show"
        in (
            tmp_path / "data/applications/io.github.Praneel7015.Shrutadhara.desktop"
        ).read_text()
    )
    launcher.write_text("unrelated")
    with pytest.raises(ValueError, match="unrelated"):
        install(tmp_path, tmp_path / "data")


@pytest.mark.skipif(not shutil.which("node"), reason="Node unavailable")
def test_npm_launcher_no_runtime_and_recursion(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    launcher = root / "npm/launcher.js"
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.delenv("SHRUTA_NATIVE_EXECUTABLE", raising=False)
    result = subprocess.run(
        ["node", str(launcher), "--version"], capture_output=True, text=True
    )
    assert result.returncode == 3
    assert "setup-native" in result.stderr
    monkeypatch.setenv("SHRUTA_NATIVE_EXECUTABLE", str(launcher))
    result = subprocess.run(["node", str(launcher)], capture_output=True, text=True)
    assert result.returncode == 3
    assert "recursive" in result.stderr
    manifest = json.loads((root / "npm/package.json").read_text())
    assert manifest["private"] is True
    assert "scripts" not in manifest


@pytest.mark.skipif(not shutil.which("node"), reason="Node unavailable")
def test_npm_setup_rejects_an_unrelated_wheel_without_installing(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    wheel = tmp_path / "unrelated-1.0-py3-none-any.whl"
    wheel.write_bytes(b"not a real wheel")
    result = subprocess.run(
        ["node", str(root / "npm/launcher.js"), "setup-native", str(wheel)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3 and "matching reviewed" in result.stderr
    assert not (tmp_path / "data/shrutadhara/npm-runtime").exists()


def test_equivalent_accelerators_cannot_share_start_stop():
    pytest.importorskip("gi")
    from shrutadhara.core import MeetingError, config_path
    from shrutadhara.shortcuts import save_accelerators

    with pytest.raises(MeetingError, match="must differ"):
        save_accelerators("<Control><Shift>r", "<Shift><Control>r")
    assert not config_path().exists()
