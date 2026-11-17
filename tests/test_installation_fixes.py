"""Regression tests for native launch compatibility and first-use GUI controls."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from shrutadhara import gui
from shrutadhara.core import MeetingError

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not shutil.which('node'), reason='Node unavailable')
@pytest.mark.parametrize('matching', [False, True])
def test_npm_checks_native_version_before_forwarding_start(tmp_path, monkeypatch, matching):
    expected = json.loads((ROOT / 'npm/package.json').read_text())['version']
    native = expected if matching else '0.0.0-old'
    runtime = tmp_path / 'data/shrutadhara/npm-runtime'
    binary = runtime / 'bin/python'
    binary.parent.mkdir(parents=True)
    marker = tmp_path / 'forwarded'
    binary.write_text(
        f'#!{sys.executable}\nimport sys\nfrom pathlib import Path\n'
        f'if sys.argv[1] == "-c": print({native!r})\n'
        f'else: Path({str(marker)!r}).write_text(" ".join(sys.argv[1:]))\n'
    )
    binary.chmod(0o700)
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    monkeypatch.delenv('SHRUTA_NATIVE_EXECUTABLE', raising=False)
    result = subprocess.run(['node', str(ROOT / 'npm/launcher.js'), 'start'], capture_output=True, text=True, timeout=15)
    assert result.returncode == (0 if matching else 3)
    assert marker.exists() is matching
    if not matching:
        assert expected in result.stderr and native in result.stderr
        assert 'setup-native' in result.stderr


@pytest.mark.skipif(not shutil.which('node'), reason='Node unavailable')
def test_npm_override_mismatch_never_forwards_recording(tmp_path, monkeypatch):
    marker = tmp_path / 'recorded'
    command = tmp_path / 'native'
    command.write_text(f'#!{sys.executable}\nimport sys\nfrom pathlib import Path\nif sys.argv[1] == "--version": print("old")\nelse: Path({str(marker)!r}).touch()\n')
    command.chmod(0o700)
    monkeypatch.setenv('SHRUTA_NATIVE_EXECUTABLE', str(command))
    result = subprocess.run(['node', str(ROOT / 'npm/launcher.js'), 'start'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 3
    assert 'does not match' in result.stderr
    assert not marker.exists()


def test_unsupported_gtk_rejected_before_window_or_display(monkeypatch):
    gtk = SimpleNamespace(get_major_version=lambda: 4, get_minor_version=lambda: 8, init_check=lambda: pytest.fail('Must reject before display initialization'))
    monkeypatch.setitem(sys.modules, 'gi', SimpleNamespace(require_version=lambda *_: None))
    monkeypatch.setitem(sys.modules, 'gi.repository', SimpleNamespace(Gtk=gtk, Gio=None, GLib=None))
    with pytest.raises(MeetingError, match='4.10') as error:
        gui.launch()
    assert error.value.code == 3
    gui.require_gtk_version(SimpleNamespace(get_major_version=lambda: 4, get_minor_version=lambda: 10))


def test_output_controls_recover_after_first_session(recorded):
    assert not gui.output_state(None, None)['folder']
    state = gui.output_state(recorded, {'notes': 'pending'})
    assert state == {'folder': True, 'notes': False, 'transcript': False}
    (recorded / 'transcript/full-transcript.md').write_text('Synthetic')
    state = gui.output_state(recorded, {'notes': 'complete'})
    assert all(state.values())
