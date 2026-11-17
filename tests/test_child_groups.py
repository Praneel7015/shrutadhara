"""Parent-bound groups use fake local providers, never accounts or audio."""

import json
import os
import signal
import subprocess
import sys
import time

import pytest

from shrutadhara.child import guarded_command, process_identity

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Linux parent-death API"
)


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    assert predicate(), "synthetic child did not reach its expected state"


@pytest.fixture
def provider_group(tmp_path):
    target = tmp_path / "provider.py"
    target.write_text(
        "import json,os,signal,subprocess,sys,time\nfrom pathlib import Path\n"
        "root=Path(sys.argv[1])\n"
        "(root/'signal-disposition.json').write_text(json.dumps({'term_ignored':signal.getsignal(signal.SIGTERM)==signal.SIG_IGN,'int_ignored':signal.getsignal(signal.SIGINT)==signal.SIG_IGN}))\n"
        "code='import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path('+repr(str(root/'grandchild.pid'))+').write_text(str(os.getpid()));time.sleep(30)'\n"
        "subprocess.Popen([sys.executable,'-c',code])\n"
        "while not (root/'grandchild.pid').exists():time.sleep(.01)\n"
        "if sys.argv[2]=='ignore':signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
        "(root/'provider.pid').write_text(str(os.getpid()))\n"
        "if sys.argv[2]=='exit':raise SystemExit(37)\n"
        "time.sleep(30)\n"
    )
    shim = tmp_path / "delayed-spawn.py"
    shim.write_text(
        "import sys,time\nfrom pathlib import Path\nfrom shrutadhara import child\n"
        f"root=Path({str(tmp_path)!r})\nreal=child.subprocess.Popen\n"
        "def delayed(*args,**kwargs):\n"
        " proc=real(*args,**kwargs)\n"
        " (root/'spawn-paused').touch()\n"
        " while not (root/'release-spawn').exists():time.sleep(.01)\n"
        " return proc\n"
        "child.subprocess.Popen=delayed\nraise SystemExit(child.main())\n"
    )
    parents, identities = [], {}

    def launch(mode="wait", delay=False, ignored_signals=False):
        script = (
            "import json,os,signal,subprocess,sys,time\nfrom pathlib import Path\n"
            "from shrutadhara.child import guarded_command\n"
            "root=Path(sys.argv[1])\n"
            "(root/'signal-disposition.json').write_text(json.dumps({'term_ignored':signal.getsignal(signal.SIGTERM)==signal.SIG_IGN,'int_ignored':signal.getsignal(signal.SIGINT)==signal.SIG_IGN}))\n"
            + (
                "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
                "signal.signal(signal.SIGINT,signal.SIG_IGN)\n"
                "signal.signal(signal.SIGCHLD,signal.SIG_IGN)\n"
                if ignored_signals
                else ""
            )
            + "command=guarded_command([sys.executable,str(root/'provider.py'),str(root),sys.argv[2]],supervise_group=True)\n"
            + (
                "command=[sys.executable,str(root/'delayed-spawn.py'),*command[3:]]\n"
                if delay
                else ""
            )
            + "proc=subprocess.Popen(command,start_new_session=True)\n"
            "(root/'watchdog.pid').write_text(str(proc.pid))\n"
            "status=proc.wait()\n(root/'status.json').write_text(json.dumps(status))\n"
        )
        parent = subprocess.Popen(
            [sys.executable, "-c", script, str(tmp_path), mode],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={
                **os.environ,
                "HOME": str(tmp_path / "home"),
                "XDG_CONFIG_HOME": str(tmp_path / "config"),
            },
        )
        parents.append(parent)
        wait_for(lambda: (tmp_path / "provider.pid").exists())
        for name in ["provider", "grandchild", "watchdog"]:
            pid = int((tmp_path / f"{name}.pid").read_text())
            identities[name] = (pid, process_identity(pid))
        return parent

    yield tmp_path, launch, identities
    (tmp_path / "release-spawn").touch()
    for parent in parents:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
    # Signal only known, still-matching synthetic children if an assertion fails.
    for name in ["watchdog", "provider", "grandchild"]:
        if name in identities:
            pid, identity = identities[name]
            if identity and process_identity(pid) == identity:
                os.kill(pid, signal.SIGKILL)


@pytest.mark.parametrize("ignore_provider", [False, True])
def test_parent_sigkill_stops_provider_and_term_ignoring_grandchild(
    provider_group, ignore_provider
):
    _root, launch, identities = provider_group
    parent = launch(mode="ignore" if ignore_provider else "wait")
    parent.kill()
    parent.wait(timeout=5)
    wait_for(
        lambda: all(process_identity(pid) is None for pid, _ in identities.values())
    )


def test_normal_target_exit_cleans_stray_group_and_preserves_status(provider_group):
    root, launch, identities = provider_group
    parent = launch(mode="exit")
    parent.wait(timeout=5)
    assert json.loads((root / "status.json").read_text()) == 37
    wait_for(
        lambda: all(process_identity(pid) is None for pid, _ in identities.values())
    )


def test_parent_death_during_spawn_still_cleans_new_group(provider_group):
    root, launch, identities = provider_group
    parent = launch(delay=True)
    assert (root / "spawn-paused").exists()
    parent.kill()
    parent.wait(timeout=5)
    (root / "release-spawn").touch()
    wait_for(
        lambda: all(process_identity(pid) is None for pid, _ in identities.values())
    )


def test_group_target_does_not_inherit_ignored_termination_signals(provider_group):
    root, launch, identities = provider_group
    parent = launch(ignored_signals=True)
    assert json.loads((root / "signal-disposition.json").read_text()) == {
        "term_ignored": False,
        "int_ignored": False,
    }
    watchdog, _ = identities["watchdog"]
    os.kill(watchdog, signal.SIGTERM)
    parent.wait(timeout=5)
    wait_for(
        lambda: all(process_identity(pid) is None for pid, _ in identities.values())
    )
    # SIGCHLD was deliberately ignored by the outer test parent. The guard must
    # still reserve/reap its own target correctly and clean its descendants.
    assert json.loads((root / "status.json").read_text()) == 0


def test_group_rejects_uncatchable_death_signal():
    with pytest.raises(ValueError, match="catchable"):
        guarded_command(
            [sys.executable, "-c", "pass"], signal.SIGKILL, supervise_group=True
        )
