"""Generates real (if robotic) narration audio for every stop in seed_data.py,
using espeak-ng for text-to-speech and ffmpeg to encode to mp3. This replaces
silent/missing audio with something that actually plays end-to-end, so the
whole pipeline (download, GPS trigger, playback, audio_started/finished
events) can be tested for real instead of just exercising the happy path
around a 404.

Swap for professionally recorded narration before this goes anywhere near
production — this is a development convenience, not a content strategy.

Run with:  python -m app.generate_audio
Requires espeak-ng and ffmpeg on PATH (both are apt-installable).
"""

import shutil
import subprocess
import sys
from pathlib import Path

from app.config import settings
from app.seed_data import TOURS


def generate_stop_audio(text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path = output_path.with_suffix(".wav")

    subprocess.run(
        ["espeak-ng", "-v", "en-us+f3", "-s", "165", "-w", str(wav_path), text],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-codec:a", "libmp3lame", "-qscale:a", "4", str(output_path)],
        check=True,
        capture_output=True,
    )
    wav_path.unlink(missing_ok=True)


def main() -> None:
    for tool in ("espeak-ng", "ffmpeg"):
        if shutil.which(tool) is None:
            print(f"Missing dependency: {tool}. Install it (e.g. `apt-get install {tool}`) and retry.")
            sys.exit(1)

    audio_root = Path(settings.AUDIO_DIR)
    count = 0
    for tour in TOURS:
        for stop in tour["stops"]:
            output_path = audio_root / stop["audio_filename"]
            generate_stop_audio(stop["narrative_text"], output_path)
            print(f"Generated {output_path}")
            count += 1

    print(f"\nDone — generated {count} narration files under {audio_root.resolve()}")


if __name__ == "__main__":
    main()
