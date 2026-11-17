"""Synthetic media integration; never opens microphone, Pulse or hosted AI."""

import array
import math
import shutil
import subprocess
import sys
import time
import wave

import pytest

from shrutadhara import audio
from shrutadhara.child import process_identity
from shrutadhara.core import MeetingError


def test_export_deadline_bounds_a_child_holding_stdout_open(tmp_path):
    pid = tmp_path / "child.pid"
    code = ("import os,time,sys;from pathlib import Path;"
            "Path(sys.argv[1]).write_text(str(os.getpid()));"
            "os.write(1,b'\\x01\\x00');time.sleep(30)")
    started = time.monotonic()
    with pytest.raises(MeetingError, match="deadline"):
        list(audio.pcm_blocks([sys.executable, "-c", code, str(pid)], .5))
    assert time.monotonic() - started < 3
    assert pid.exists()
    assert process_identity(int(pid.read_text())) is None


def test_export_stream_aligns_partial_sample_reads():
    code = "import os,time;os.write(1,b'\\x01');time.sleep(.03);os.write(1,b'\\x00\\x02\\x00')"
    assert b"".join(audio.pcm_blocks([sys.executable, "-c", code], 3)) == b"\x01\x00\x02\x00"


def test_export_stream_rejects_a_partial_final_sample():
    with pytest.raises(MeetingError, match="incomplete PCM"):
        list(audio.pcm_blocks([sys.executable, "-c", "import os;os.write(1,b'x')"], 3))


def test_artifact_lock_serializes_independent_processes(tmp_path):
    waiting, entered = tmp_path / "waiting", tmp_path / "entered"
    code = ("from pathlib import Path;import sys;from shrutadhara.audio import artifact_lock;"
            "Path(sys.argv[2]).touch();"
            "\nwith artifact_lock(Path(sys.argv[1])): Path(sys.argv[3]).touch()")
    child = None
    try:
        with audio.artifact_lock(tmp_path):
            child = subprocess.Popen([sys.executable, "-c", code, str(tmp_path), str(waiting), str(entered)])
            deadline = time.monotonic() + 5
            while not waiting.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            assert waiting.exists()
            time.sleep(.1)
            assert not entered.exists()
        assert child.wait(timeout=5) == 0
        assert entered.exists()
    finally:
        if child and child.poll() is None:
            child.kill()
            child.wait(timeout=5)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg unavailable")
def test_real_segmented_tones_export_preserves_every_interval(tmp_path):
    folder = tmp_path / "audio/originals/epoch-000"
    folder.mkdir(parents=True)
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=3",
        "-map", "0:a", "-map", "1:a", "-c:a", "pcm_s16le", "-f", "segment", "-segment_time", "1",
        "-reset_timestamps", "0", "-segment_format", "matroska", "-segment_list", str(folder / "segments.csv"),
        "-segment_list_type", "csv", str(folder / "%06d.mkv"),
    ], check=True, timeout=15)
    manifest, errors = audio.archive_manifest(tmp_path, [{"id": 0, "offset": 0, "directory": str(folder.relative_to(tmp_path))}])
    assert len(manifest) == 3 and not errors
    output = audio.exports(tmp_path, manifest, 3)
    for name in ["participants", "microphone"]:
        assert output[name]["duration_seconds"] == 3
        with wave.open(str(tmp_path / f"audio/{name}.wav"), "rb") as stream:
            for _ in range(3):
                samples = array.array("h", stream.readframes(48000))
                rms = math.sqrt(sum(value * value for value in samples) / len(samples))
                assert 2500 < rms < 3200
