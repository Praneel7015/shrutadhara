from types import SimpleNamespace

import pytest

from shrutadhara import audio
from shrutadhara.core import MeetingError, atomic_json, read_json


def test_device_selection_and_mute(inv):
    assert audio.select_devices(inv, {})["microphone"] == "mic"
    inv["sources"][0]["mute"] = True
    with pytest.raises(MeetingError, match="muted"):
        audio.select_devices(inv, {})
    assert audio.select_devices(inv, {"allow_muted_mic": True})["microphone_muted"]
    with pytest.raises(MeetingError):
        audio.select_devices(inv, {"microphone": "speakers.monitor"})


def test_multiple_instances_require_selection(inv):
    inv["sink-inputs"].append(
        {
            "index": 12,
            "sink": 1,
            "properties": {
                "application.process.binary": "teams-for-linux",
                "application.process.id": "222",
            },
        }
    )
    with pytest.raises(MeetingError, match="Multiple"):
        audio.select_devices(inv, {})
    assert audio.select_devices(inv, {"teams_pid": "111"})["teams_pid"] == "111"


def test_safe_ffmpeg_command_preserves_tracks(tmp_path):
    cmd = audio.recording_command("remote; echo injected", "local", tmp_path)
    assert cmd.count("-i") == 2
    assert cmd[cmd.index("-i") + 1] == "remote; echo injected.monitor"
    assert "0:a:0" in cmd and "1:a:0" in cmd
    assert "pcm_s16le" in cmd and "matroska" in cmd
    assert cmd[cmd.index("-segment_time") + 1] == "60"
    assert "-copyts" in cmd


def test_routing_moves_only_teams_and_journals_first(inv, tmp_path, monkeypatch):
    calls = []
    r = audio.Routing(
        "12345678", audio.select_devices(inv, {}), tmp_path / "routing.json"
    )

    def pulse(*args):
        calls.append(args)
        if args[0] == "load-module":
            return SimpleNamespace(stdout=str(len(calls)))
        if args[0] == "move-sink-input":
            assert read_json(r.journal)["moved"]["9"]["sink"] == "speakers"
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(audio, "pulse", pulse)
    r.setup(inv)
    moved = [c for c in calls if c[0] == "move-sink-input"]
    assert moved == [("move-sink-input", "9", r.remote)]
    assert not any(c[0] == "set-default-sink" for c in calls)


def test_restore_does_not_unload_reused_ids(inv, tmp_path, monkeypatch):
    journal = tmp_path / "routing.json"
    atomic_json(
        journal,
        {
            "remote": "shruta_remote",
            "local": "shruta_mic",
            "modules": {"remote": "123"},
            "moved": {},
        },
    )
    calls = []

    def pulse(*args):
        calls.append(args)
        return SimpleNamespace(
            stdout="123\tmodule-null-sink\tsink_name=unrelated\tn/a\n"
        )

    monkeypatch.setattr(audio, "pulse", pulse)
    audio.restore_routes(journal, inv)
    assert not any(c[0] == "unload-module" for c in calls)


def test_restore_with_pipewire_short_module_listing(inv, tmp_path, monkeypatch):
    journal = tmp_path / "routing.json"
    inv["sinks"].append({"index": 20, "name": "shruta_remote"})
    inv["sink-inputs"][0]["sink"] = 20
    atomic_json(
        journal,
        {
            "remote": "shruta_remote",
            "local": "shruta_mic",
            "modules": {"remote": "123"},
            "moved": {"9": {"sink": "speakers", "pid": "111", "serial": "777"}},
        },
    )
    calls = []

    def pulse(*args):
        calls.append(args)
        return SimpleNamespace(
            stdout="123\tmodule-null-sink\tsink_name=shruta_remote\tn/a\n"
        )

    monkeypatch.setattr(audio, "pulse", pulse)
    audio.restore_routes(journal, inv)
    assert ("move-sink-input", "9", "speakers") in calls
    assert ("unload-module", "123") in calls
    assert read_json(journal)["modules"] == {}


def test_validate_silent_audio(monkeypatch, tmp_path):
    p = tmp_path / "audio.wav"
    p.write_bytes(b"audio")
    monkeypatch.setattr(
        audio,
        "probe",
        lambda _: {
            "streams": [{"codec_type": "audio", "channels": 1}],
            "format": {"duration": "3"},
        },
    )
    monkeypatch.setattr(
        audio,
        "run",
        lambda *a, **k: SimpleNamespace(stderr="Peak level dB: -inf\n", stdout=""),
    )
    assert audio.validate_audio(p)["tracks"][0]["silent"]


def test_archive_order_uses_offsets(tmp_path, monkeypatch):
    folder = tmp_path / "audio/originals/epoch-000"
    folder.mkdir(parents=True)
    (folder / "000001.mkv").write_bytes(b"2")
    (folder / "000000.mkv").write_bytes(b"1")
    (folder / "segments.csv").write_text("000000.mkv,0,60\n000001.mkv,60,80\n")
    monkeypatch.setattr(
        audio,
        "probe",
        lambda _: {"streams": [{"codec_type": "audio"}] * 2, "format": {}},
    )
    monkeypatch.setattr(audio, "run", lambda *a, **kw: None)
    result, errors = audio.archive_manifest(
        tmp_path, [{"directory": "audio/originals/epoch-000", "offset": 2.5, "id": 0}]
    )
    assert not errors
    assert [(s["start"], s["end"]) for s in result] == [(2.5, 62.5), (62.5, 82.5)]
