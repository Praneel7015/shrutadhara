import json
from pathlib import Path

import pytest

from shrutadhara import agy, cli, sandbox
from shrutadhara.core import MeetingError, runtime_dir


@pytest.mark.parametrize("argv", [
    ["start"], ["process"], ["ask", "What happened?"], ["doctor", "--probe-ai"],
    ["watch"], ["install-desktop"],
])
def test_flatpak_rejects_unsupported_commands(argv, monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "io.github.Praneel7015.Shrutadhara")
    args = cli.parser().parse_args(argv)
    with pytest.raises(MeetingError) as error:
        sandbox.validate_command(args)
    assert error.value.code == 3


@pytest.mark.parametrize("argv", [["start", "--foreground"], ["process", "--prepare-only"], ["show"], ["doctor"]])
def test_flatpak_local_commands_allowed(argv, monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "io.github.Praneel7015.Shrutadhara")
    sandbox.validate_command(cli.parser().parse_args(argv))


def test_flatpak_ai_guard_precedes_subprocess_or_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("FLATPAK_ID", "io.github.Praneel7015.Shrutadhara")
    monkeypatch.setattr(agy, "_invoke", lambda *a: pytest.fail("AI must not run"))
    with pytest.raises(MeetingError, match="native installation"):
        agy.invoke("private", {}, tmp_path / "absent", {})
    assert not (tmp_path / "absent").exists()


def test_flatpak_runtime_does_not_share_native_pid_metadata(monkeypatch):
    native = runtime_dir()
    monkeypatch.setenv("FLATPAK_ID", "io.github.Praneel7015.Shrutadhara")
    assert runtime_dir() != native


@pytest.mark.parametrize("busy,recording,processing", [(True, None, False), (False, "starting", False), (False, "recording", False), (False, "stopping", False), (False, "recorded", True)])
def test_flatpak_retains_window_until_work_finished(busy, recording, processing, monkeypatch):
    monkeypatch.setenv("FLATPAK_ID", "io.github.Praneel7015.Shrutadhara")
    assert sandbox.keep_window_open(busy, recording, processing)
    assert not sandbox.keep_window_open(False, "recorded", False)
    monkeypatch.delenv("FLATPAK_ID")
    assert not sandbox.keep_window_open(busy, recording, processing)


def test_manifest_has_no_host_escape_or_network_access():
    path = Path(__file__).parents[1] / "packaging/flatpak/io.github.Praneel7015.Shrutadhara.json"
    manifest = json.loads(path.read_text())
    assert manifest["finish-args"] == [
        "--socket=wayland", "--socket=fallback-x11", "--share=ipc",
        "--socket=pulseaudio", "--filesystem=~/Meetings/Flatpak:create",
    ]
    for module in manifest["modules"]:
        for source in module["sources"]:
            if "url" in source:
                assert len(source["sha256"]) == 64
            assert source["type"] != "dir"
