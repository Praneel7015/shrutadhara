"""Hosted cancellation uses local fake processes; these tests never contact AI."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from shrutadhara import agy
from shrutadhara.child import process_identity


@pytest.mark.parametrize('failure', ['SIGTERM', 'SIGINT'])
def test_hosted_parent_cancellation_stops_fake_provider(tmp_path, failure):
    binary = tmp_path / 'bin'
    binary.mkdir()
    pidfile = tmp_path / 'provider.pid'
    grandchild_pidfile = tmp_path / 'grandchild.pid'
    fake = binary / 'agy'
    fake.write_text(
        f'#!{sys.executable}\n'
        'import os,time,subprocess,sys\nfrom pathlib import Path\n'
        'code = \"import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(os.environ[\\\"SHRUTA_FAKE_GRANDCHILD_PID\\\"]).write_text(str(os.getpid()));time.sleep(30)\"\n'
        'subprocess.Popen([sys.executable, \"-c\", code])\n'
        'while not Path(os.environ["SHRUTA_FAKE_GRANDCHILD_PID"]).exists():time.sleep(.01)\n'
        'Path(os.environ["SHRUTA_FAKE_PID"]).write_text(str(os.getpid()))\n'
        'time.sleep(30)\n'
    )
    fake.chmod(0o700)
    workspace = tmp_path / 'work'
    script = (
        'from pathlib import Path;from shrutadhara.agy import invoke;import sys;'
        'invoke("synthetic", {"type":"object"}, Path(sys.argv[1]), '
        '{"hosted_consent":True,"model":"local-fake","ai_timeout":30})'
    )
    env = {**os.environ, 'PATH': str(binary) + ':' + os.environ['PATH'], 'SHRUTA_FAKE_PID': str(pidfile), 'SHRUTA_FAKE_GRANDCHILD_PID': str(grandchild_pidfile)}
    parent = subprocess.Popen([sys.executable, '-c', script, str(workspace)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    child = None
    try:
        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            if parent.poll() is not None:
                pytest.fail('Hosted parent exited before the fake provider started')
            time.sleep(.02)
        assert pidfile.exists()
        child = int(pidfile.read_text())
        parent.send_signal(getattr(signal, failure))
        parent.wait(timeout=8)
        assert process_identity(child) is None
        assert process_identity(int(grandchild_pidfile.read_text())) is None
        attempts = list(workspace.glob('attempt-*/attempt.json'))
        assert len(attempts) == 1
        assert json.loads(attempts[0].read_text())['state'] == 'cancelled'
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()
        if child and Path(f'/proc/{child}').exists():
            os.killpg(child, signal.SIGKILL)


def test_cancellation_scope_restores_previous_handler():
    previous = signal.getsignal(signal.SIGTERM)
    with agy.cancellation():
        assert signal.getsignal(signal.SIGTERM) != previous
    assert signal.getsignal(signal.SIGTERM) == previous
