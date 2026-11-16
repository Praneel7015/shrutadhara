import wave

import pytest

from shrutadhara import agy, processing
from shrutadhara.core import MeetingError, config, digest


def test_limit_detection_is_specific():
    assert agy.is_limit("Audio too large")
    assert not agy.is_limit("quota exceeded")
    assert not agy.is_limit("blocked by provider")


def test_bisection_preserves_overlap_and_resume(tmp_path):
    source = tmp_path / "transcript/chunks/microphone-00000/audio.wav"
    source.parent.mkdir(parents=True)
    with wave.open(str(source), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x01\x00" * 16000 * 120)
    chunk = {
        "id": "microphone-00000",
        "track": "microphone",
        "path": str(source.relative_to(tmp_path)),
        "start": 0,
        "end": 120,
        "core_start": 0,
        "core_end": 120,
        "sha256": digest(source),
    }
    children = processing.bisect_chunk(tmp_path, chunk, config())
    assert [
        (c["start"], c["end"], c["core_start"], c["core_end"]) for c in children
    ] == [(0, 62, 0, 60), (58, 120, 60, 120)]
    assert processing.split_leaves(tmp_path, chunk) == children
    leaves = processing.bisect_chunk(tmp_path, children[0], config())
    assert len(processing.split_leaves(tmp_path, chunk)) == 3
    with pytest.raises(MeetingError, match="minimum"):
        processing.bisect_chunk(tmp_path, leaves[0], config())
