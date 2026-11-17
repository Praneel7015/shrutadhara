"""Synthetic, offline codec smoke test, without microphone access."""

import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

from shrutadhara import audio


def main():
    with tempfile.TemporaryDirectory(prefix="shruta-flatpak-smoke-") as directory:
        root = Path(directory)
        source = root / "tone.wav"
        with wave.open(str(source), "wb") as stream:
            stream.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            stream.writeframes(b"".join(
                struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * n / 48000)))
                for n in range(48000)
            ))
        assert not audio.validate_audio(source)["tracks"][0]["silent"]
        subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(source), "-i", str(source),
            "-map", "0:a", "-map", "1:a", "-c:a", "pcm_s16le", "-f", "segment",
            "-segment_time", "0.5", "-segment_format", "matroska", str(root / "%03d.mkv"),
        ], check=True, timeout=30)
        assert len(list(root.glob("*.mkv"))) >= 2
        subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(source), "-i", str(source),
            "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0,alimiter=limit=0.95:level=false:latency=1",
            "-c:a", "pcm_s16le", str(root / "combined.wav"),
        ], check=True, timeout=30)
        assert not audio.validate_audio(root / "combined.wav")["tracks"][0]["silent"]
    print("Offline Flatpak codec smoke passed; no microphone or hosted AI used")


if __name__ == "__main__":
    main()
