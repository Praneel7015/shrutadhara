"""Linux parent-bound children without unsafe preexec_fn callbacks.

This tiny interpreter sets its own parent-death signal, verifies the parent's
start identity, records its identity when requested, then execs the target.
The signal survives ordinary exec. Optional group supervision keeps this
interpreter alive to terminate same-group descendants after parent death or
target exit. Descendants that deliberately create independent process sessions
require separate supervision; this is not a sandbox.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .core import atomic_json


def process_identity(pid: int) -> str | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except (OSError, IndexError, ValueError):
        return None


def guarded_command(
    command: list[str],
    death_signal: int = signal.SIGTERM,
    identity_file: Path | None = None,
    supervise_group: bool = False,
) -> list[str]:
    if supervise_group and death_signal == signal.SIGKILL:
        raise ValueError("Group supervision requires a catchable parent-death signal")
    parent = os.getpid()
    identity = process_identity(parent)
    if not identity:
        raise OSError("Cannot establish parent process identity")
    args = [
        sys.executable,
        "-m",
        "shrutadhara.child",
        "--parent-pid",
        str(parent),
        "--parent-identity",
        identity,
        "--signal",
        str(int(death_signal)),
    ]
    if identity_file is not None:
        args += ["--identity-file", str(identity_file)]
    if supervise_group:
        args.append("--supervise-group")
    return [*args, "--", *command]


def _supervise(command, parent_matches, stop_requested):
    """Own a process group until its leader and remaining members are stopped.

    No poll/wait/communicate call reaps the leader before group cleanup. Keeping
    that PID reserved prevents a recycled PGID from receiving our escalation.
    """
    if stop_requested() or not parent_matches():
        return 3
    try:
        proc = subprocess.Popen(command, start_new_session=True)
    except OSError:
        return 3

    def signal_group(signum):
        try:
            os.killpg(proc.pid, signum)
        except ProcessLookupError:
            pass

    def exited():
        return (
            os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            is not None
        )

    requested = None
    try:
        while True:
            requested = stop_requested()
            if requested or not parent_matches():
                signal_group(signal.SIGTERM)
                deadline = time.monotonic() + 1
                while not exited() and time.monotonic() < deadline:
                    time.sleep(0.02)
                break
            if exited():
                break
            time.sleep(0.02)
    finally:
        # Even a normally exiting leader can leave descendants behind. Always
        # clean its still-reserved group before reaping, including on errors.
        signal_group(signal.SIGKILL)
        returncode = proc.wait()
    if requested:
        return 128 + requested
    return returncode if returncode >= 0 else 128 - returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--parent-identity", required=True)
    parser.add_argument("--signal", required=True, type=int)
    parser.add_argument("--identity-file", type=Path)
    parser.add_argument("--supervise-group", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.signal not in {
        signal.SIGTERM,
        signal.SIGINT,
        signal.SIGKILL,
    }:
        return 3
    if args.supervise_group and args.signal == signal.SIGKILL:
        return 3
    stopped = None
    if args.supervise_group:
        # Install before arming PDEATHSIG, so parent death cannot bypass cleanup.
        # Caught handlers reset to defaults in the exec'd target; unlike SIG_IGN
        # they do not silently suppress provider termination.
        def stopping(signum, _frame):
            nonlocal stopped
            stopped = signum

        signal.signal(signal.SIGTERM, stopping)
        signal.signal(signal.SIGINT, stopping)
        # Inherited SIGCHLD=SIG_IGN would auto-reap the leader and defeat the
        # reserved-PID rule used by the process-group cleanup below.
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    libc = ctypes.CDLL(None, use_errno=True)
    # PR_SET_PDEATHSIG is applied here in the dedicated child interpreter, never
    # between fork and exec in a possibly multithreaded application.
    if libc.prctl(1, args.signal, 0, 0, 0) != 0:
        return 3

    def parent_matches():
        return (
            os.getppid() == args.parent_pid
            and process_identity(args.parent_pid) == args.parent_identity
        )

    if not parent_matches():
        return 3
    if args.identity_file:
        atomic_json(
            args.identity_file,
            {
                "pid": os.getpid(),
                "identity": process_identity(os.getpid()),
                "parent_pid": args.parent_pid,
                "parent_identity": args.parent_identity,
            },
        )
    if not parent_matches():
        return 3
    if args.supervise_group:
        return _supervise(command, parent_matches, lambda: stopped)
    os.execvp(command[0], command)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
