"""Accepted AI output baselines, independent of disposable cache fingerprints.

Callers hold the session processing lock. An unbaselined legacy cache is never
trusted; it is recomputed or replaced by an explicit import. Each newly accepted
output has an immutable byte snapshot, and corrections append revision metadata.
This detects accidental/local edits, not an actor who controls every baseline.
"""

from pathlib import Path

from .core import (
    MeetingError,
    atomic_json,
    atomic_text,
    digest,
    now,
    private_dir,
    read_json,
)


class OutputIntegrityError(MeetingError):
    pass


def _relative(session: Path, path: Path) -> str:
    if path.is_symlink() or not path.resolve().is_relative_to(session.resolve()):
        raise OutputIntegrityError("Unsafe accepted-output cache path", 6)
    return str(path.relative_to(session))


def _ledger(session: Path) -> dict:
    path = session / "transcript/accepted-outputs.json"
    _relative(session, path)
    if not path.exists():
        return {"schema_version": 1, "files": {}, "revisions": []}
    ledger = read_json(path)
    if (
        ledger.get("schema_version") != 1
        or not isinstance(ledger.get("files"), dict)
        or not isinstance(ledger.get("revisions"), list)
    ):
        raise OutputIntegrityError("Invalid accepted-output integrity ledger", 6)
    return ledger


def read(session: Path, path: Path) -> dict | None:
    """Return verified bytes parsed as JSON, or None for a missing/legacy cache."""
    relative = _relative(session, path)
    record = _ledger(session)["files"].get(relative)
    if not path.exists():
        return None
    if record is None:
        return None  # Do not establish a baseline from pre-existing unknown bytes.
    if not isinstance(record, dict) or digest(path) != record.get("sha256"):
        raise OutputIntegrityError(
            "Accepted AI output changed; use an explicit correction import or restore its saved revision",
            6,
        )
    snapshot = (
        session / "transcript/accepted-output-revisions" / (record["sha256"] + ".json")
    )
    _relative(session, snapshot)
    if not snapshot.exists() or digest(snapshot) != record["sha256"]:
        raise OutputIntegrityError(
            "Accepted AI output revision is missing or changed", 6
        )
    return read_json(path)


def write(
    session: Path, path: Path, value: dict, *, explicit_import: bool = False
) -> None:
    relative = _relative(session, path)
    ledger = _ledger(session)
    previous = ledger["files"].get(relative)
    if previous is not None and not explicit_import:
        # Re-check after a potentially long model request before replacing bytes.
        read(session, path)
    replaced_hash = digest(path) if path.exists() else None
    atomic_json(path, value)
    accepted_hash = digest(path)
    snapshots = private_dir(session / "transcript/accepted-output-revisions")
    snapshot = snapshots / (accepted_hash + ".json")
    _relative(session, snapshot)
    if snapshot.exists():
        if digest(snapshot) != accepted_hash:
            raise OutputIntegrityError("Accepted AI output revision changed", 6)
    else:
        atomic_text(snapshot, path.read_text())
    record = {"sha256": accepted_hash, "fingerprint": value.get("fingerprint")}
    if previous != record:
        ledger["revisions"].append(
            {
                "at": now(),
                "path": relative,
                "sha256": accepted_hash,
                "previous_sha256": previous.get("sha256")
                if isinstance(previous, dict)
                else None,
                "replaced_sha256": replaced_hash,
                "reason": "explicit correction import"
                if explicit_import
                else "validated model output",
            }
        )
    ledger["files"][relative] = record
    atomic_json(session / "transcript/accepted-outputs.json", ledger)
