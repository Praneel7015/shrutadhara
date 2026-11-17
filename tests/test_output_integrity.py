"""Accepted model output, literal rendering and serialized request regressions."""

from unittest.mock import Mock

import pytest

from shrutadhara import output_cache
from shrutadhara import processing as p
from shrutadhara.core import MeetingError, atomic_json, read_json


def test_unknown_legacy_cache_is_never_baselined(recorded):
    target = recorded / "transcript/chunks/example/result.json"
    atomic_json(target, {"fingerprint": "input", "result": {"text": "legacy"}})
    assert output_cache.read(recorded, target) is None
    assert not (recorded / "transcript/accepted-outputs.json").exists()


def test_valid_schema_cache_edit_is_rejected_and_revision_preserved(recorded):
    target = recorded / "transcript/chunks/example/result.json"
    value = {"fingerprint": "input", "result": {"text": "accepted"}}
    output_cache.write(recorded, target, value)
    record = read_json(recorded / "transcript/accepted-outputs.json")["files"][
        "transcript/chunks/example/result.json"
    ]
    snapshot = (
        recorded / "transcript/accepted-output-revisions" / (record["sha256"] + ".json")
    )
    original = snapshot.read_bytes()
    atomic_json(target, {"fingerprint": "input", "result": {"text": "silently edited"}})
    with pytest.raises(output_cache.OutputIntegrityError, match="changed"):
        output_cache.read(recorded, target)
    assert snapshot.read_bytes() == original


def test_explicit_correction_preserves_old_snapshot_and_appends_revision(recorded):
    target = recorded / "transcript/chunks/example/result.json"
    output_cache.write(recorded, target, {"fingerprint": "input", "result": "old"})
    old = read_json(recorded / "transcript/accepted-outputs.json")["files"][
        "transcript/chunks/example/result.json"
    ]["sha256"]
    target.write_text("{corrupt cache is deliberately superseded")
    correction = {"fingerprint": "input", "result": "corrected"}
    output_cache.write(recorded, target, correction, explicit_import=True)
    assert output_cache.read(recorded, target) == correction
    ledger = read_json(recorded / "transcript/accepted-outputs.json")
    assert ledger["revisions"][-1]["reason"] == "explicit correction import"
    assert ledger["revisions"][-1]["previous_sha256"] == old
    assert (
        recorded / "transcript/accepted-output-revisions" / (old + ".json")
    ).exists()


def test_modified_snapshot_and_unsafe_cache_paths_are_rejected(recorded, tmp_path):
    target = recorded / "notes/notes.json"
    output_cache.write(recorded, target, {"fingerprint": "input", "notes": {}})
    ledger = read_json(recorded / "transcript/accepted-outputs.json")
    snapshot = (
        recorded
        / "transcript/accepted-output-revisions"
        / (ledger["files"]["notes/notes.json"]["sha256"] + ".json")
    )
    snapshot.write_text("changed")
    with pytest.raises(output_cache.OutputIntegrityError, match="revision"):
        output_cache.read(recorded, target)
    link = recorded / "notes/escape.json"
    link.symlink_to(tmp_path / "outside.json")
    with pytest.raises(output_cache.OutputIntegrityError, match="Unsafe"):
        output_cache.write(recorded, link, {"arbitrary": "value"})


def transcript(text):
    return {
        "coverage_complete": True,
        "unprocessed": [],
        "review": [],
        "accuracy_notice": "Synthetic",
        "segments": [
            {
                "id": "seg-000000",
                "start": 0,
                "end": 1,
                "speaker": "Local",
                "uncertain": False,
                "text": text,
            }
        ],
    }


@pytest.mark.parametrize(
    "payload",
    [
        "![image](https://example.invalid/track)",
        '<img src="https://example.invalid/track">',
        "[fake evidence](#seg-000999)",
        "# heading\n| injected | cell |",
    ],
)
def test_untrusted_output_is_literal_but_json_remains_faithful(recorded, payload):
    value = transcript(payload)
    p.render_transcript(recorded, value)
    p.render_notes(
        recorded,
        value,
        {
            "summary": [{"text": payload, "evidence": ["seg-000000"]}],
            "topics": [],
            "decisions": [],
            "actions": [
                {
                    "task": payload,
                    "owner": None,
                    "deadline": None,
                    "status": "Open",
                    "evidence": ["seg-000000"],
                }
            ],
        },
    )
    assert (
        read_json(recorded / "transcript/transcript.json")["segments"][0]["text"]
        == payload
    )
    for target in [
        "transcript/full-transcript.md",
        "notes/summary.md",
        "notes/action-items.md",
    ]:
        text = (recorded / target).read_text()
        assert payload not in text
        assert "https://" not in text
        if "<img" in payload:
            assert r"\<img" in text
    assert (
        "../transcript/full-transcript.md#seg-000000"
        in (recorded / "notes/summary.md").read_text()
    )


@pytest.mark.parametrize("text", ["a" * 200_000, "अ" * 25_000])
def test_oversized_single_notes_segment_never_reaches_adapter(
    recorded, monkeypatch, text
):
    provider = Mock()
    monkeypatch.setattr(p.providers, "get_provider", lambda cfg: provider)
    with pytest.raises(MeetingError, match="segment exceeds"):
        p.generate_notes(recorded, transcript(text), {"model": "fake"}, False)
    provider.structured.assert_not_called()


def test_complete_notes_prompt_overhead_is_in_budget(recorded, monkeypatch):
    provider = Mock()
    monkeypatch.setattr(p.providers, "get_provider", lambda cfg: provider)
    monkeypatch.setattr(p, "MAX_NOTES_CONTEXT_BYTES", 1000)
    with pytest.raises(MeetingError, match="UTF-8 context budget"):
        p.generate_notes(
            recorded, transcript("Short dialogue."), {"model": "fake"}, False
        )
    provider.structured.assert_not_called()


def test_processing_rejects_tampered_accepted_output_before_any_new_call(
    recorded, monkeypatch
):
    item = {
        "id": "a",
        "track": "microphone",
        "start": 0,
        "end": 10,
        "core_start": 0,
        "core_end": 10,
        "sha256": "hash",
        "path": "transcript/chunks/a/audio.wav",
    }
    (recorded / item["path"]).parent.mkdir(parents=True, exist_ok=True)
    provider = Mock()
    provider.capable.return_value = True
    provider.identity.return_value = {"model": "fake"}
    provider.transcribe.return_value = {
        "audio_received": True,
        "fully_processed": True,
        "limitation": "",
        "segments": [
            {"start": 1, "end": 2, "text": "Accepted speech.", "uncertain": False}
        ],
    }
    monkeypatch.setattr(p.providers, "get_provider", lambda cfg: provider)
    monkeypatch.setattr(p, "config", lambda: {"hosted_consent": True, "model": "fake"})
    monkeypatch.setattr(
        p,
        "prepare",
        lambda *_: {
            "chunks": [item],
            "archive_errors": [],
            "source_fingerprint": "synthetic",
        },
    )
    monkeypatch.setattr(p, "generate_notes", lambda *a: None)
    p.process(recorded)
    cache = recorded / "transcript/chunks/a/result.json"
    transcript_before = (recorded / "transcript/transcript.json").read_bytes()
    record = read_json(cache)
    record["result"]["segments"][0]["text"] = "Unapproved change."
    atomic_json(cache, record)
    with pytest.raises(output_cache.OutputIntegrityError, match="changed"):
        p.process(recorded)
    assert provider.transcribe.call_count == 1
    assert (recorded / "transcript/transcript.json").read_bytes() == transcript_before
    assert not read_json(recorded / "session.json")["coverage_complete"]


def test_snapshot_creation_failure_preserves_prior_cache(recorded, monkeypatch):
    target = recorded / "notes/notes.json"
    value = {"fingerprint": "old", "notes": {"text": "accepted"}}
    output_cache.write(recorded, target, value)
    original = target.read_bytes()
    monkeypatch.setattr(
        output_cache,
        "atomic_text",
        lambda *_: (_ for _ in ()).throw(OSError("synthetic snapshot write failure")),
    )
    with pytest.raises(OSError, match="snapshot write"):
        output_cache.write(
            recorded, target, {"fingerprint": "new", "notes": {"text": "replacement"}}
        )
    assert target.read_bytes() == original
    assert output_cache.read(recorded, target) == value


def test_ledger_commit_failure_is_fail_closed_with_old_revision_retained(
    recorded, monkeypatch
):
    target = recorded / "notes/notes.json"
    output_cache.write(recorded, target, {"fingerprint": "old", "notes": "accepted"})
    ledger_path = recorded / "transcript/accepted-outputs.json"
    old_ledger = ledger_path.read_bytes()
    old_hash = read_json(ledger_path)["files"]["notes/notes.json"]["sha256"]
    original_atomic = output_cache.atomic_json

    def fail_ledger(path, value):
        if path == ledger_path:
            raise OSError("synthetic ledger commit failure")
        return original_atomic(path, value)

    monkeypatch.setattr(output_cache, "atomic_json", fail_ledger)
    with pytest.raises(OSError, match="ledger commit"):
        output_cache.write(
            recorded, target, {"fingerprint": "new", "notes": "replacement"}
        )
    assert ledger_path.read_bytes() == old_ledger
    with pytest.raises(output_cache.OutputIntegrityError, match="changed"):
        output_cache.read(recorded, target)
    old_snapshot = (
        recorded / "transcript/accepted-output-revisions" / (old_hash + ".json")
    )
    assert read_json(old_snapshot)["notes"] == "accepted"


def test_rejected_transcript_does_not_replace_previously_accepted_markdown(recorded):
    original = transcript("Previously accepted dialogue.")
    p.render_transcript(recorded, original)
    markdown = recorded / "transcript/full-transcript.md"
    previous = markdown.read_bytes()
    atomic_json(
        recorded / "transcript/transcript.json", transcript("Unapproved JSON edit.")
    )
    with pytest.raises(output_cache.OutputIntegrityError, match="changed"):
        p.render_transcript(recorded, transcript("Replacement must not appear."))
    assert markdown.read_bytes() == previous


def test_ledger_failure_does_not_publish_new_markdown(recorded, monkeypatch):
    p.render_transcript(recorded, transcript("Previously accepted dialogue."))
    markdown = recorded / "transcript/full-transcript.md"
    previous = markdown.read_bytes()
    original_atomic = output_cache.atomic_json

    def fail_ledger(path, value):
        if path.name == "accepted-outputs.json":
            raise OSError("synthetic ledger failure")
        return original_atomic(path, value)

    monkeypatch.setattr(output_cache, "atomic_json", fail_ledger)
    with pytest.raises(OSError, match="ledger failure"):
        p.render_transcript(recorded, transcript("Replacement must not appear."))
    assert markdown.read_bytes() == previous
    with pytest.raises(output_cache.OutputIntegrityError, match="changed"):
        output_cache.read(recorded, recorded / "transcript/transcript.json")
