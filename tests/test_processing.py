import wave

import pytest

from shrutadhara import agy
from shrutadhara import processing as p
from shrutadhara.core import (
    MeetingError,
    atomic_json,
    config,
    config_path,
    read_json,
)


def chunk(id="a", start=0, end=12, core_start=0, core_end=10, track="microphone"):
    return {
        "id": id,
        "start": start,
        "end": end,
        "core_start": core_start,
        "core_end": core_end,
        "track": track,
        "sha256": "hash",
    }


def result(text="Hello", start=1, end=2):
    return {
        "audio_received": True,
        "fully_processed": True,
        "limitation": "",
        "segments": [{"start": start, "end": end, "text": text, "uncertain": False}],
    }


def test_exact_chunk_windows():
    windows = p.chunk_windows(16000 * 601 + 13, 16000, 300, 2)
    assert len(windows) == 3
    assert windows[1] == {
        "core_start_sample": 4800000,
        "core_end_sample": 9600000,
        "start_sample": 4768000,
        "end_sample": 9616013,
    }
    assert windows[-1]["end_sample"] == 16000 * 601 + 13


def test_split_preserves_exact_samples(tmp_path):
    source, dest = tmp_path / "a.wav", tmp_path / "b.wav"
    samples = b"".join(i.to_bytes(2, "little") for i in range(100))
    with wave.open(str(source), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(samples)
    p.write_chunk(source, dest, 23, 71)
    with wave.open(str(dest), "rb") as inp:
        assert inp.getnframes() == 48
        assert inp.readframes(48) == samples[46:142]


def test_merge_offsets_track_order_and_missing():
    chunks = [chunk("b", 8, 22, 10, 20), chunk("a")]
    merged = p.merge(chunks, {"a": result(), "b": result("World", 5, 6)}, [])
    assert [s["start"] for s in merged["segments"]] == [1, 13]
    assert merged["coverage_complete"]
    assert not p.merge(chunks, {"a": result()}, [])["coverage_complete"]


def test_overlap_ownership_prevents_duplicate():
    a, b = chunk(), chunk("b", 8, 22, 10, 20)
    merged = p.merge(
        [a, b], {"a": result("Boundary", 9, 11), "b": result("Boundary", 1, 3)}, []
    )
    assert len(merged["segments"]) == 1
    assert merged["segments"][0]["start"] == 9


def test_repeated_phrase_not_globally_deleted():
    a, b = chunk(), chunk("b", 8, 22, 10, 20)
    merged = p.merge([a, b], {"a": result("Yes", 1, 2), "b": result("Yes", 5, 6)}, [])
    assert len(merged["segments"]) == 2


def test_ambiguous_overlap_is_reviewed():
    a, b = chunk(), chunk("b", 8, 22, 10, 20)
    merged = p.merge(
        [a, b],
        {"a": result("First reading", 8, 11), "b": result("Different reading", 2, 5)},
        [],
    )
    assert (
        len(merged["segments"]) == 2
        and merged["review"]
        and not merged["coverage_complete"]
    )


@pytest.mark.parametrize(
    "r",
    [
        result(start=5, end=4),
        result(start=0, end=20),
        result(start=float("nan")),
        {**result(), "fully_processed": False},
    ],
)
def test_reject_bad_transcripts(r):
    with pytest.raises(MeetingError):
        p.validate_transcription(r, chunk())


def test_notes_reject_invented_owner_and_invalid_evidence():
    segments = [{"id": "seg-1", "text": "Alice will ship it on Friday.", "start": 0}]
    notes = {
        "summary": [],
        "topics": [],
        "decisions": [],
        "actions": [
            {
                "task": "Ship it",
                "owner": "Bob",
                "deadline": "Friday",
                "status": "Open",
                "evidence": ["seg-1"],
            }
        ],
    }
    with pytest.raises(MeetingError, match="owner"):
        p.validate_notes(notes, segments)
    notes["actions"][0]["owner"] = "Alice"
    p.validate_notes(notes, segments)
    notes["actions"][0]["evidence"] = ["missing"]
    with pytest.raises(MeetingError, match="nonexistent"):
        p.validate_notes(notes, segments)


def test_partial_notes_blocked(recorded):
    with pytest.raises(MeetingError, match="incomplete"):
        p.generate_notes(
            recorded, {"coverage_complete": False, "segments": []}, config(), False
        )
    assert read_json(recorded / "session.json")["notes"] == "blocked"


def test_notes_render_evidence_and_safe_table(recorded):
    transcript = {
        "coverage_complete": False,
        "segments": [{"id": "seg-1", "start": 12}],
    }
    notes = {
        "summary": [{"text": "Overview", "evidence": ["seg-1"]}],
        "topics": [],
        "decisions": [],
        "actions": [
            {
                "task": "Fix | table",
                "owner": None,
                "deadline": None,
                "status": "Open",
                "evidence": ["seg-1"],
            }
        ],
    }
    p.render_notes(recorded, transcript, notes)
    assert "PARTIAL" in (recorded / "notes/summary.md").read_text()
    text = (recorded / "notes/action-items.md").read_text()
    assert "Fix \\| table" in text and "Not specified" in text and "#seg-1" in text


def test_processing_resume_does_not_call_ai_twice(recorded, monkeypatch):
    cfg = config()
    cfg["hosted_consent"] = True
    atomic_json(config_path(), cfg)
    c = {**chunk(), "path": "transcript/chunks/a/audio.wav", "fingerprint": "input"}
    (recorded / "transcript/chunks/a").mkdir()
    (recorded / c["path"]).write_bytes(b"fake")
    manifest = {"chunks": [c], "archive_errors": [], "source_fingerprint": "source"}
    monkeypatch.setattr(p, "prepare", lambda *_: manifest)
    monkeypatch.setattr(agy, "capable", lambda *_: True)
    monkeypatch.setattr(agy, "identity", lambda *_: {"version": "test"})
    calls = []
    monkeypatch.setattr(agy, "invoke", lambda *a, **kw: calls.append(a) or result())
    monkeypatch.setattr(p, "generate_notes", lambda *a, **kw: None)
    p.process(recorded)
    p.process(recorded)
    assert len(calls) == 1


def test_failed_chunk_never_claims_complete(recorded, monkeypatch):
    cfg = config()
    cfg["hosted_consent"] = True
    atomic_json(config_path(), cfg)
    c = {**chunk(), "path": "transcript/chunks/a/audio.wav"}
    (recorded / "transcript/chunks/a").mkdir()
    monkeypatch.setattr(
        p,
        "prepare",
        lambda *_: {
            "chunks": [c],
            "archive_errors": [],
            "source_fingerprint": "source",
        },
    )
    monkeypatch.setattr(agy, "capable", lambda *_: True)
    monkeypatch.setattr(agy, "identity", lambda *_: {})

    def fail(*a, **k):
        raise agy.AIError("Provider blocked")

    monkeypatch.setattr(agy, "invoke", fail)
    with pytest.raises(MeetingError):
        p.process(recorded)
    data = read_json(recorded / "session.json")
    assert not data["coverage_complete"] and data["transcription"] == "partial"
    assert "INCOMPLETE" in (recorded / "transcript/full-transcript.md").read_text()


def test_safe_artifact_paths(recorded):
    with pytest.raises(MeetingError):
        p.safe_path(recorded, "../../secret")


def test_manual_import_provenance_and_no_silent_upload(recorded, monkeypatch, tmp_path):
    c = {**chunk(), "path": "transcript/chunks/a/audio.wav"}
    (recorded / "transcript/chunks/a").mkdir()
    manifest = {"chunks": [c], "archive_errors": [], "source_fingerprint": "source"}
    monkeypatch.setattr(p, "prepare", lambda *_: manifest)
    monkeypatch.setattr(
        agy,
        "invoke",
        lambda *a, **k: pytest.fail("Import must not upload without consent"),
    )
    imported = tmp_path / "import.json"
    atomic_json(imported, {"source_fingerprint": "source", "results": {"a": result()}})
    answer = p.process(recorded, import_path=imported)
    transcript = read_json(recorded / "transcript/transcript.json")
    assert transcript["segments"][0]["provenance"]["transport"] == "manual-import"
    assert (
        answer["coverage_complete"]
        and read_json(recorded / "session.json")["notes"] == "blocked"
    )


def test_interrupted_processing_writes_truthful_partial_transcript(
    recorded, monkeypatch
):
    cfg = config()
    cfg["hosted_consent"] = True
    atomic_json(config_path(), cfg)
    c = {**chunk(), "path": "transcript/chunks/a/audio.wav"}
    (recorded / "transcript/chunks/a").mkdir()
    monkeypatch.setattr(
        p,
        "prepare",
        lambda *_: {
            "chunks": [c],
            "archive_errors": [],
            "source_fingerprint": "source",
        },
    )
    monkeypatch.setattr(agy, "capable", lambda *_: True)
    monkeypatch.setattr(agy, "identity", lambda *_: {})

    def interrupted(*a, **k):
        raise KeyboardInterrupt()

    monkeypatch.setattr(agy, "invoke", interrupted)
    with pytest.raises(KeyboardInterrupt):
        p.process(recorded)
    data = read_json(recorded / "session.json")
    transcript = read_json(recorded / "transcript/transcript.json")
    assert not data["coverage_complete"] and not transcript["coverage_complete"]
    assert transcript["unprocessed"] and data["transcription"] == "partial"


def test_boundary_readings_on_opposite_sides_of_core_are_not_lost():
    a, b = chunk(), chunk("b", 8, 20, 10, 20)
    merged = p.merge(
        [a, b],
        {
            "a": result("Boundary speech", 9.5, 11),
            "b": result("Boundary speech", 0.5, 2),
        },
        [],
    )
    assert len(merged["segments"]) == 1
    assert merged["segments"][0]["text"] == "Boundary speech"
    assert len(merged["segments"][0]["provenance"]["readings"]) == 2
    assert merged["coverage_complete"]


def test_unmatched_context_speech_survives_silent_neighbor():
    a, b = chunk(), chunk("b", 8, 20, 10, 20)
    silent = {**result(), "segments": []}
    merged = p.merge([a, b], {"a": result("Only reading", 10.5, 11.5), "b": silent}, [])
    assert merged["segments"][0]["text"] == "Only reading"
    assert merged["review"] and not merged["coverage_complete"]


def test_unequal_boundary_segmentation_retains_every_reading_for_review():
    a, b = chunk(), chunk("b", 8, 20, 10, 20)
    split = {
        **result(),
        "segments": [
            {"start": 1, "end": 2, "text": "We", "uncertain": False},
            {"start": 2, "end": 3, "text": "agree", "uncertain": False},
        ],
    }
    merged = p.merge([a, b], {"a": result("We agree", 9, 11), "b": split}, [])
    assert {s["text"] for s in merged["segments"]} == {"We agree", "We", "agree"}
    assert not merged["coverage_complete"]


def test_technical_punctuation_disagreement_is_not_erased():
    a, b = chunk(), chunk("b", 8, 20, 10, 20)
    merged = p.merge(
        [a, b], {"a": result("Use a+b", 9, 11), "b": result("Use a-b", 1, 3)}, []
    )
    assert len(merged["segments"]) == 2 and not merged["coverage_complete"]


def test_corrected_import_replaces_cached_text_and_resumes_omitted_chunks(
    recorded, monkeypatch, tmp_path
):
    a = {**chunk("a"), "path": "transcript/chunks/a/audio.wav"}
    b = {**chunk("b", 10, 20, 10, 20), "path": "transcript/chunks/b/audio.wav"}
    for c in [a, b]:
        (recorded / c["path"]).parent.mkdir()
    monkeypatch.setattr(
        p,
        "prepare",
        lambda *_: {
            "chunks": [a, b],
            "archive_errors": [],
            "source_fingerprint": "source",
        },
    )
    imported = tmp_path / "corrected.json"
    atomic_json(
        imported,
        {
            "source_fingerprint": "source",
            "results": {"a": result("Old text"), "b": result("Keep this")},
        },
    )
    p.process(recorded, import_path=imported)
    atomic_json(
        imported,
        {"source_fingerprint": "source", "results": {"a": result("Corrected text")}},
    )
    answer = p.process(recorded, import_path=imported)
    text = (recorded / "transcript/full-transcript.md").read_text()
    assert "Corrected text" in text and "Keep this" in text and "Old text" not in text
    assert answer["coverage_complete"]


def test_invalid_correction_does_not_fall_back_to_old_text(
    recorded, monkeypatch, tmp_path
):
    a = {**chunk(), "path": "transcript/chunks/a/audio.wav"}
    (recorded / a["path"]).parent.mkdir()
    monkeypatch.setattr(
        p,
        "prepare",
        lambda *_: {
            "chunks": [a],
            "archive_errors": [],
            "source_fingerprint": "source",
        },
    )
    imported = tmp_path / "corrected.json"
    atomic_json(
        imported, {"source_fingerprint": "source", "results": {"a": result("Old text")}}
    )
    p.process(recorded, import_path=imported)
    atomic_json(
        imported,
        {"source_fingerprint": "source", "results": {"a": result("Bad time", 4, 2)}},
    )
    answer = p.process(recorded, import_path=imported)
    assert not answer["coverage_complete"]
    assert "Old text" not in (recorded / "transcript/full-transcript.md").read_text()


def test_explicit_correction_does_not_read_corrupt_obsolete_cache(
    recorded, monkeypatch, tmp_path
):
    a = {**chunk(), "path": "transcript/chunks/a/audio.wav"}
    folder = (recorded / a["path"]).parent
    folder.mkdir()
    (folder / "result.json").write_text("{broken")
    monkeypatch.setattr(
        p,
        "prepare",
        lambda *_: {
            "chunks": [a],
            "archive_errors": [],
            "source_fingerprint": "source",
        },
    )
    imported = tmp_path / "corrected.json"
    atomic_json(
        imported,
        {"source_fingerprint": "source", "results": {"a": result("Corrected text")}},
    )
    assert p.process(recorded, import_path=imported)["coverage_complete"]
    assert "Corrected text" in (recorded / "transcript/full-transcript.md").read_text()


def test_native_audio_refusal_stops_later_submissions(recorded, monkeypatch):
    from unittest.mock import Mock

    from shrutadhara import providers

    chunks = []
    for i in range(3):
        item = chunk(f'microphone-{i:05d}', i * 10, (i + 1) * 10, i * 10, (i + 1) * 10)
        item['path'] = f'transcript/chunks/{item["id"]}/audio.wav'
        folder = (recorded / item['path']).parent
        folder.mkdir(parents=True, exist_ok=True)
        chunks.append(item)
    manifest = {'chunks': chunks, 'source_fingerprint': 'synthetic', 'archive_errors': []}
    adapter = Mock()
    adapter.capable.return_value = True
    adapter.identity.return_value = {'model': 'fake'}
    adapter.transcribe.return_value = {'audio_received': False, 'fully_processed': False, 'limitation': 'Native audio is unsupported', 'segments': []}
    monkeypatch.setattr(p, 'prepare', lambda *_: manifest)
    monkeypatch.setattr(p, 'config', lambda: {**config(), 'hosted_consent': True})
    monkeypatch.setattr(p.providers, 'get_provider', lambda _: adapter)
    with pytest.raises(providers.CapabilityRefusal, match='later submissions stopped'):
        p.process(recorded)
    assert adapter.transcribe.call_count == 1
    metadata = read_json(recorded / 'session.json')
    assert metadata['transcription'] == 'blocked'
    assert not metadata['coverage_complete']
    transcript = read_json(recorded / 'transcript/transcript.json')
    assert not transcript['coverage_complete'] and transcript['unprocessed']
