from unittest.mock import Mock

import pytest

from shrutadhara import cli, output_cache, questions
from shrutadhara.core import MeetingError, atomic_json


@pytest.fixture
def accepted(tmp_path, monkeypatch):
    session = tmp_path / "session"
    atomic_json(
        session / "session.json", {"transcription": "complete", "notes": "complete"}
    )
    output_cache.write(
        session,
        session / "transcript/transcript.json",
        {
            "source_fingerprint": "source",
            "coverage_complete": True,
            "segments": [
                {"id": "seg-000001", "text": "Ship Friday.", "start": 0, "end": 2}
            ],
        },
    )
    atomic_json(
        session / "transcript/chunks/manifest.json", {"source_fingerprint": "source"}
    )
    monkeypatch.setattr(questions, "config", lambda: {"hosted_consent": True})
    provider = Mock()
    provider.structured.return_value = {
        "answered": True,
        "claims": [{"text": "Ship Friday.", "evidence": ["seg-000001"]}],
    }
    monkeypatch.setattr(questions, "get_provider", lambda cfg: provider)
    return session, provider


def test_answer_only_uploads_full_transcript_and_retains_private_evidence(accepted):
    session, provider = accepted
    markdown = questions.ask(session, "When?")
    assert "evidence.md#seg-000001" in markdown
    prompt, schema, workspace, cfg = provider.structured.call_args.args
    assert "Ship Friday." in prompt and "When?" in prompt
    assert (workspace / "request.json").exists()
    assert (workspace / "answer.md").stat().st_mode & 0o777 == 0o600
    assert (workspace / "prompt.txt").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("case", ["consent", "partial", "stale", "huge", "missing"])
def test_preflight_blocks_without_hosted_call(accepted, monkeypatch, case):
    session, provider = accepted
    if case == "consent":
        monkeypatch.setattr(questions, "config", lambda: {"hosted_consent": False})
    elif case == "partial":
        atomic_json(session / "session.json", {"transcription": "partial"})
    elif case == "stale":
        atomic_json(
            session / "transcript/chunks/manifest.json",
            {"source_fingerprint": "changed"},
        )
    elif case == "huge":
        monkeypatch.setattr(questions, "MAX_CONTEXT_BYTES", 10)
    else:
        (session / "transcript/transcript.json").unlink()
    with pytest.raises(MeetingError):
        questions.ask(session, "When?")
    provider.structured.assert_not_called()


def test_partial_is_prominent_and_unknown_evidence_rejected(accepted):
    session, provider = accepted
    atomic_json(session / "session.json", {"transcription": "partial"})
    assert "PARTIAL TRANSCRIPT" in questions.ask(session, "When?", True)
    provider.structured.return_value["claims"][0]["evidence"] = ["seg-999999"]
    with pytest.raises(MeetingError, match="unknown"):
        questions.ask(session, "When?", True)


def test_changed_transcript_rejects_result(accepted):
    session, provider = accepted
    result = provider.structured.return_value

    def changed(*args):
        atomic_json(session / "transcript/transcript.json", {"changed": True})
        return result

    provider.structured.side_effect = changed
    with pytest.raises(MeetingError, match="changed"):
        questions.ask(session, "When?")


def test_schema_and_abstention(accepted):
    session, provider = accepted
    provider.structured.return_value = {"answered": False, "claims": []}
    assert "does not establish" in questions.ask(session, "Who?")
    provider.structured.return_value = {"answered": True, "claims": []}
    with pytest.raises(MeetingError, match="inconsistent"):
        questions.ask(session, "Who?")
    provider.structured.return_value = {"arbitrary": "bad"}
    with pytest.raises(MeetingError, match="schema"):
        questions.ask(session, "Who?")


def test_cli_note_aliases_and_default(accepted, monkeypatch, capsys):
    session, _ = accepted
    monkeypatch.setattr(cli, "selected", lambda identifier: session)
    for command, name in [
        ("notes", "detailed-notes"),
        ("summary", "summary"),
        ("actions", "action-items"),
        ("decisions", "decisions"),
    ]:
        target = session / f"notes/{name}.md"
        target.parent.mkdir(exist_ok=True)
        target.write_text(name)
        assert cli.main([command]) == 0
        assert capsys.readouterr().out.strip() == name
    assert cli.parser().prog == "shruta"


def test_cli_ask_stdin(accepted, monkeypatch, capsys):
    import io

    session, _ = accepted
    monkeypatch.setattr(cli, "selected", lambda _: session)
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("When?"))
    assert cli.main(["ask"]) == 0
    assert "Ship Friday" in capsys.readouterr().out


def test_historical_answer_links_to_its_original_evidence_after_correction(accepted):
    from shrutadhara.core import read_json

    session, provider = accepted
    answer = questions.ask(session, "When?")
    workspace = provider.structured.call_args.args[2]
    evidence = workspace / "evidence.md"
    original = evidence.read_bytes()
    snapshot = read_json(workspace / "evidence.json")
    assert snapshot["segments"][0]["text"] == "Ship Friday."
    assert "evidence.md#seg-000001" in answer
    assert "../../transcript/" not in answer
    atomic_json(
        session / "transcript/transcript.json",
        {"segments": [{"id": "seg-000001", "text": "Do not ship Friday."}]},
    )
    assert evidence.read_bytes() == original
    assert "Do not ship" not in evidence.read_text()
    assert read_json(workspace / "request.json")["evidence_sha256"]


def test_valid_transcript_edit_is_rejected_before_question_submission(accepted):
    from shrutadhara.core import read_json

    session, provider = accepted
    path = session / "transcript/transcript.json"
    value = read_json(path)
    value["segments"][0]["text"] = "Changed without an explicit import."
    atomic_json(path, value)
    with pytest.raises(output_cache.OutputIntegrityError, match="changed"):
        questions.ask(session, "When?")
    provider.structured.assert_not_called()


def test_legacy_unbaselined_transcript_requires_explicit_reprocess(accepted):
    session, provider = accepted
    (session / "transcript/accepted-outputs.json").unlink()
    with pytest.raises(MeetingError, match="reprocess or explicitly import"):
        questions.ask(session, "When?")
    provider.structured.assert_not_called()
    assert not (session / "questions").exists()
