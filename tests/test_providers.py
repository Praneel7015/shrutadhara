from pathlib import Path
from unittest.mock import Mock

import pytest

from shrutadhara import agy, cli, providers
from shrutadhara.core import MeetingError


def test_selection_is_local_and_rejects_explicit_unknown(monkeypatch):
    monkeypatch.setattr(agy, "identity", Mock(side_effect=AssertionError("no probe")))
    assert isinstance(providers.get_provider({}), providers.AgyProvider)
    assert isinstance(
        providers.get_provider({"provider": "agy"}), providers.AgyProvider
    )
    for value in ("other", "", None, False):
        with pytest.raises(MeetingError) as caught:
            providers.get_provider({"provider": value})
        assert caught.value.code == 3


def test_identity_and_capability_are_exact_delegates(monkeypatch):
    cfg = {"model": "existing-model", "hosted_consent": False}
    identity = {"existing": "identity"}
    identify = Mock(return_value=identity)
    capable = Mock(return_value=False)
    monkeypatch.setattr(agy, "identity", identify)
    monkeypatch.setattr(agy, "capable", capable)
    provider = providers.get_provider(cfg)
    assert provider.identity(cfg) is identity
    assert provider.capable(cfg) is False
    identify.assert_called_once_with(cfg)
    capable.assert_called_once_with(cfg)
    assert cfg == {"model": "existing-model", "hosted_consent": False}


def test_transcribe_and_structured_forward_exact_policy(monkeypatch):
    path, workspace = Path("synthetic.wav"), Path("private-workspace")
    cfg = {"hosted_consent": False}
    invoke = Mock(return_value={"result": True})
    prompt = Mock(return_value="audio prompt")
    monkeypatch.setattr(agy, "invoke", invoke)
    monkeypatch.setattr(agy, "transcription_prompt", prompt)
    provider = providers.get_provider(cfg)
    assert provider.transcribe(path, 2.5, workspace, cfg) == {"result": True}
    prompt.assert_called_once_with(path, 2.5)
    invoke.assert_called_once_with(
        "audio prompt", agy.TRANSCRIPT_SCHEMA, workspace, cfg, audio_path=path
    )
    invoke.reset_mock()
    schema = {"type": "object"}
    provider.structured("notes prompt", schema, workspace, cfg)
    invoke.assert_called_once_with("notes prompt", schema, workspace, cfg)
    error = MeetingError("consent required", 7)
    invoke.side_effect = error
    with pytest.raises(MeetingError) as caught:
        provider.structured("notes", schema, workspace, cfg)
    assert caught.value is error


def test_cli_lists_adapter_without_checking_installation(monkeypatch, capsys):
    monkeypatch.setattr(agy, "identity", Mock(side_effect=AssertionError("no network")))
    assert cli.main(["providers", "--json"]) == 0
    import json

    assert json.loads(capsys.readouterr().out) == providers.available_providers()
