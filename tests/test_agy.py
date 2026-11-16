import json

import pytest

from shrutadhara import agy
from shrutadhara.core import MeetingError, config

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def envelope(response=None, status="SUCCESS"):
    return (
        json.dumps(
            {
                "event": "result",
                "result": {
                    "status": status,
                    "structured_output": {"ok": True},
                    "response": response if response is not None else '{"ok":true}',
                },
            }
        )
        + "\n"
    )


def test_parse_structured_result():
    assert agy.parse_response(envelope(), SCHEMA, False) == {"ok": True}


@pytest.mark.parametrize(
    "raw",
    [
        envelope('Provider error\n{"ok":true}'),
        envelope(status="ERROR"),
        "not json\n",
        envelope() + envelope(),
        "",
    ],
)
def test_reject_contamination_even_with_success(raw):
    with pytest.raises(agy.AIError):
        agy.parse_response(raw, SCHEMA, False)


def test_unexpected_tool_rejected():
    event = json.dumps(
        {
            "event": "step_update",
            "step_update": {"step_type": "tool", "tool_name": "run_command"},
        }
    )
    with pytest.raises(agy.AIError):
        agy.parse_response(event + "\n" + envelope(), SCHEMA, True)


def test_consent_gate_prevents_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr(
        agy.subprocess,
        "Popen",
        lambda *a, **kw: pytest.fail("Must not spawn without consent"),
    )
    with pytest.raises(MeetingError) as error:
        agy.invoke("prompt", SCHEMA, tmp_path, config())
    assert error.value.code == 7


def test_transient_retry_bounded_and_prompt_on_stdin(tmp_path, monkeypatch):
    calls = []

    class Process:
        pid = 999999

        def __init__(self, args, **kwargs):
            calls.append((args, kwargs))
            self.out = kwargs["stdout"]
            self.err = kwargs["stderr"]
            self.returncode = 1 if len(calls) < 3 else 0

        def communicate(self, payload, timeout):
            assert "secret meeting text" in payload
            if self.returncode:
                self.err.write("503 Unavailable")
            else:
                self.out.write(envelope())
            self.err.flush()
            self.out.flush()

    monkeypatch.setattr(agy.subprocess, "Popen", Process)
    monkeypatch.setattr(agy.time, "sleep", lambda _: None)
    assert agy.invoke(
        "secret meeting text", SCHEMA, tmp_path, {**config(), "hosted_consent": True}
    ) == {"ok": True}
    assert len(calls) == 3
    assert all("secret meeting text" not in str(args) for args, _ in calls)
    assert all(k["env"]["AGY_CLI_DISABLE_AUTO_UPDATE"] == "true" for _, k in calls)


def test_provider_block_not_retried(tmp_path, monkeypatch):
    calls = []

    class Process:
        returncode = 0

        def __init__(self, *args, **kw):
            self.out = kw["stdout"]
            calls.append(1)

        def communicate(self, *args, **kw):
            self.out.write(envelope('Blocked by Gemini filters\n{"ok":true}'))
            self.out.flush()

    monkeypatch.setattr(agy.subprocess, "Popen", Process)
    with pytest.raises(agy.AIError):
        agy.invoke("prompt", SCHEMA, tmp_path, {**config(), "hosted_consent": True})
    assert len(calls) == 1


def test_capability_invalidated_by_version(monkeypatch, tmp_path):
    from shrutadhara.core import atomic_json

    path = tmp_path / "capability.json"
    atomic_json(path, {"identity": {"version": "1"}, "passed": True})
    monkeypatch.setattr(agy, "capability_path", lambda: path)
    monkeypatch.setattr(agy, "identity", lambda *_: {"version": "2"})
    assert not agy.capable()


def test_accuracy_failure_revokes_previously_passed_probe(monkeypatch, tmp_path):
    from shrutadhara.core import atomic_json, read_json

    path = tmp_path / "capability.json"
    atomic_json(path, {"identity": {"version": "same"}, "passed": True})
    monkeypatch.setattr(agy, "capability_path", lambda: path)
    monkeypatch.setattr(agy, "identity", lambda *_: {"version": "same"})
    agy.invalidate_capability("Known speech was recognized incorrectly")
    assert not agy.capable() and read_json(path)["invalidated_at"]


def test_timeout_kills_process_group_and_stops_after_three_attempts(
    tmp_path, monkeypatch
):
    import subprocess

    calls, signals = [], []

    class Process:
        pid = 999999
        returncode = 0

        def __init__(self, *a, **k):
            calls.append(1)

        def communicate(self, *a, **k):
            raise subprocess.TimeoutExpired("agy", 1)

        def wait(self, *a, **k):
            return 0

    monkeypatch.setattr(agy.subprocess, "Popen", Process)
    monkeypatch.setattr(agy.os, "killpg", lambda *a: signals.append(a))
    monkeypatch.setattr(agy.time, "sleep", lambda *_: None)
    with pytest.raises(agy.AIError, match="deadline"):
        agy.invoke("prompt", SCHEMA, tmp_path, {**config(), "hosted_consent": True})
    assert len(calls) == len(signals) == 3
