import shutil
import wave
from pathlib import Path

import pytest

from shrutadhara import audio, processing
from shrutadhara.core import MeetingError, atomic_json, config, digest, read_json


def wav(path, sample):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(sample * 16000)


@pytest.fixture
def prepared(recorded, monkeypatch):
    for name in ["participants", "microphone"]:
        wav(recorded / f"audio/{name}.wav", b"\x01\x00")
    monkeypatch.setattr(audio, "archive_manifest", lambda *_: ([], []))
    monkeypatch.setattr(
        audio,
        "validate_audio",
        lambda path: {
            "sha256": digest(path),
            "duration_seconds": 1,
            "tracks": [{"silent": False}],
        },
    )

    def convert(args, **kwargs):
        shutil.copyfile(Path(args[args.index("-i") + 1]), Path(args[-1]))

    monkeypatch.setattr(processing, "run", convert)
    manifest = processing.prepare(recorded, config())
    return recorded, manifest


@pytest.mark.parametrize("kind", ["derivative", "chunk"])
def test_modified_cache_fails_without_rebaselining_manifest(prepared, kind):
    session, manifest = prepared
    manifest_path = session / "transcript/chunks/manifest.json"
    before = manifest_path.read_bytes()
    target = session / (
        manifest["chunks"][0]["path"]
        if kind == "chunk"
        else "audio/participants-16k.wav"
    )
    wav(target, b"\x02\x00")
    with pytest.raises(MeetingError, match="Cached.*changed") as exc:
        processing.prepare(session, config())
    assert exc.value.code == 5 and manifest_path.read_bytes() == before


def test_legacy_cache_without_digest_is_rebuilt_from_parent(prepared):
    session, manifest = prepared
    target = session / manifest["chunks"][0]["path"]
    expected = digest(target)
    sidecar = target.parent / "input.json"
    metadata = read_json(sidecar)
    metadata.pop("sha256")
    atomic_json(sidecar, metadata)
    wav(target, b"\x02\x00")
    rebuilt = processing.prepare(session, config())
    assert rebuilt["chunks"][0]["sha256"] == expected
    assert read_json(sidecar)["sha256"] == expected


def test_unchanged_cache_does_not_resample_again(prepared, monkeypatch):
    session, manifest = prepared
    monkeypatch.setattr(
        processing, "run", lambda *a, **k: pytest.fail("Valid cache should be reused")
    )
    assert (
        processing.prepare(session, config())["source_fingerprint"]
        == manifest["source_fingerprint"]
    )


def test_preparation_verifies_trusted_archives_even_outside_export_manifest(prepared):
    session, _ = prepared
    original = session / "audio/originals/damaged-original.mkv"
    original.write_bytes(b"known damaged source")
    atomic_json(
        session / "audio/archive-integrity.json",
        {
            "schema_version": 1,
            "files": {str(original.relative_to(session)): digest(original)},
        },
    )
    original.write_bytes(b"changed source")
    with pytest.raises(MeetingError, match="integrity"):
        processing.prepare(session, config())
