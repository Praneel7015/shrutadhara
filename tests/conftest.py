import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    # Synthetic subprocesses must import the same checkout even when their
    # private working directory differs and no editable install exists (Arch
    # makepkg check / minimum-dependency jobs). Installed-wheel smoke checks
    # run separately outside pytest with this test-only environment removed.
    source = str(Path(__file__).resolve().parents[1])
    previous = os.environ.get("PYTHONPATH")
    monkeypatch.setenv("PYTHONPATH", source + (os.pathsep + previous if previous else ""))
    monkeypatch.setenv("SHRUTA_ROOT", str(tmp_path / "Meetings"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr("shrutadhara.core.notify", lambda *_: None)
    monkeypatch.setattr("shrutadhara.recorder.notify", lambda *_: None)
    monkeypatch.setattr("shrutadhara.processing.notify", lambda *_: None)


@pytest.fixture
def inv():
    return {
        "sinks": [
            {"index": 1, "name": "speakers", "properties": {}},
            {"index": 2, "name": "headphones", "properties": {}},
        ],
        "sources": [
            {"index": 3, "name": "mic", "mute": False, "properties": {}},
            {"index": 4, "name": "speakers.monitor", "monitor_source": "speakers"},
        ],
        "sink-inputs": [
            {
                "index": 9,
                "sink": 1,
                "properties": {
                    "application.process.binary": "teams-for-linux",
                    "application.process.id": "111",
                    "object.serial": "777",
                },
            },
            {
                "index": 10,
                "sink": 1,
                "properties": {"application.process.binary": "waterfox"},
            },
        ],
        "source-outputs": [
            {
                "index": 11,
                "source": 3,
                "properties": {
                    "application.process.binary": "teams-for-linux",
                    "application.process.id": "111",
                },
            }
        ],
        "default_source": "mic",
        "default_sink": "speakers",
    }


@pytest.fixture
def recorded():
    from shrutadhara import sessions

    p = sessions.create("Design review")
    sessions.update(p, recording="recording")
    sessions.update(p, recording="stopping")
    sessions.update(p, recording="recorded", duration_seconds=10)
    return p
