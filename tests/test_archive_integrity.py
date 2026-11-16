from types import SimpleNamespace

import pytest

from shrutadhara import audio, recorder, sessions
from shrutadhara.core import MeetingError, atomic_json, digest, read_json


@pytest.fixture
def archive(tmp_path, monkeypatch):
    session = sessions.create("Synthetic integrity fixture")
    folder = session / "audio/originals/epoch-000"
    folder.mkdir()
    original = folder / "000000.mkv"
    original.write_bytes(b"valid synthetic archive")
    epochs = [{"id": 0, "offset": 0, "directory": "audio/originals/epoch-000"}]
    monkeypatch.setattr(
        audio,
        "probe",
        lambda _: {
            "streams": [{"codec_type": "audio"}] * 2,
            "format": {"start_time": "0", "duration": "1"},
        },
    )
    monkeypatch.setattr(audio, "run", lambda *a, **kw: SimpleNamespace())
    sessions.update(session, recording="interrupted", epochs=epochs)
    return session, original, epochs


@pytest.mark.parametrize("mutation", ["changed", "missing"])
def test_recovery_rejects_trusted_original_before_mutation(
    archive, monkeypatch, mutation
):
    session, original, epochs = archive
    audio.archive_manifest(session, epochs)
    manifest = (session / "audio/manifest.json").read_bytes()
    metadata = (session / "session.json").read_bytes()
    if mutation == "changed":
        original.write_bytes(b"different but still decodable archive")
    else:
        original.unlink()
    monkeypatch.setattr(audio, "exports", lambda *_: pytest.fail("must not export"))
    with pytest.raises(MeetingError, match="integrity"):
        recorder.recover(session)
    assert (session / "audio/manifest.json").read_bytes() == manifest
    assert (session / "session.json").read_bytes() == metadata


def test_new_archive_preserves_previous_baseline(archive):
    session, original, epochs = archive
    audio.archive_manifest(session, epochs)
    old_hash = digest(original)
    (original.parent / "000001.mkv").write_bytes(b"new segment")
    manifest, errors = audio.archive_manifest(session, epochs)
    assert not errors and len(manifest) == 2
    assert manifest[0]["sha256"] == old_hash


@pytest.mark.parametrize("mutation", ["changed", "missing"])
def test_recovered_derivative_is_trusted_too(archive, mutation):
    session, original, epochs = archive
    recovered = session / "audio/recovered/salvage.mkv"
    recovered.parent.mkdir()
    recovered.write_bytes(b"recovered")
    atomic_json(
        session / "audio/manifest.json",
        {
            "segments": [
                {
                    "path": str(recovered.relative_to(session)),
                    "sha256": digest(recovered),
                    "original_path": str(original.relative_to(session)),
                    "original_sha256": digest(original),
                }
            ],
            "errors": [],
        },
    )
    before = (session / "audio/manifest.json").read_bytes()
    if mutation == "changed":
        recovered.write_bytes(b"changed")
    else:
        recovered.unlink()
    with pytest.raises(MeetingError, match="integrity"):
        audio.archive_manifest(session, epochs)
    assert (session / "audio/manifest.json").read_bytes() == before


def test_interrupted_salvage_keeps_original_baseline(archive, monkeypatch):
    session, original, epochs = archive
    monkeypatch.setattr(
        audio, "probe", lambda _: (_ for _ in ()).throw(MeetingError("bad archive"))
    )
    monkeypatch.setattr(
        audio, "run", lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    with pytest.raises(KeyboardInterrupt):
        audio.archive_manifest(session, epochs)
    ledger = read_json(session / "audio/archive-integrity.json")
    assert ledger["files"][str(original.relative_to(session))] == digest(original)
    original.write_bytes(b"changed after interrupted salvage")
    with pytest.raises(MeetingError, match="integrity"):
        audio.archive_manifest(session, epochs)


@pytest.mark.parametrize(
    "content", ["{bad json", "{}", '{"segments":[{}],"errors":[]}']
)
def test_corrupt_manifest_not_overwritten(archive, content):
    session, _, epochs = archive
    path = session / "audio/manifest.json"
    path.write_text(content)
    with pytest.raises(MeetingError):
        audio.archive_manifest(session, epochs)
    assert path.read_text() == content


def test_archive_path_escape_rejected(archive, tmp_path):
    session, original, epochs = archive
    outside = tmp_path / "outside"
    outside.mkdir()
    original.parent.joinpath("escape.mkv").symlink_to(outside / "secret.mkv")
    with pytest.raises(MeetingError, match="escapes"):
        audio.archive_manifest(session, epochs)
    with pytest.raises(MeetingError, match="escapes"):
        audio.archive_manifest(
            session, [{"directory": "../../outside", "id": 0, "offset": 0}]
        )
