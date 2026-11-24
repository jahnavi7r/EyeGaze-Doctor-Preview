import hashlib
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent.parent / "audio"


def audio_path(code: str, text: str) -> Path:
    """Where the pre-generated clip for this sentence is stored."""
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
    return AUDIO_DIR / code / f"{digest}.mp3"