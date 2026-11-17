"""Linux parent-bound exec without unsafe preexec_fn callbacks.

This tiny interpreter sets its own parent-death signal, verifies the parent's
start identity, records its identity when requested, then execs the target.
The signal survives ordinary exec. Descendants that create independent process
sessions require their own supervision; this is not a sandbox.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import signal
import sys
from pathlib import Path

from .core import atomic_json


def process_identity(pid: int) -> str | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except (OSError, IndexError, ValueError):
        return None


def guarded_command(
    command: list[str], death_signal: int = signal.SIGTERM,
    identity_file: Path | None = None,
) -> list[str]:
    parent = os.getpid()
    identity = process_identity(parent)
    if not identity:
        raise OSError("Cannot establish parent process identity")
    args = [sys.executable, "-m", "shrutadhara.child", "--parent-pid", str(parent),
            "--parent-identity", identity, "--signal", str(int(death_signal))]
    if identity_file is not None:
        args += ["--identity-file", str(identity_file)]
    return [*args, "--", *command]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--parent-identity", required=True)
    parser.add_argument("--signal", required=True, type=int)
    parser.add_argument("--identity-file", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.signal not in {signal.SIGTERM, signal.SIGINT, signal.SIGKILL}:
        return 3
    libc = ctypes.CDLL(None, use_errno=True)
    # PR_SET_PDEATHSIG is applied here in the dedicated child interpreter, never
    # between fork and exec in a possibly multithreaded application.
    if libc.prctl(1, args.signal, 0, 0, 0) != 0:
        return 3

    def parent_matches():
        return os.getppid() == args.parent_pid and process_identity(args.parent_pid) == args.parent_identity

    if not parent_matches():
        return 3
    if args.identity_file:
        atomic_json(args.identity_file, {
            "pid": os.getpid(), "identity": process_identity(os.getpid()),
            "parent_pid": args.parent_pid, "parent_identity": args.parent_identity,
        })
    if not parent_matches():
        return 3
    os.execvp(command[0], command)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
