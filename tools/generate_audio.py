import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edge_tts
from nlp.languages import LANGUAGES
from nlp.audio_cache import audio_path

VOICES = {
    "te": "te-IN-ShrutiNeural",
    "hi": "hi-IN-SwaraNeural",
    "en": "en-IN-NeerjaNeural",
}
RATE = "-15%"  # slightly slower, easier to follow


def all_sentences(lang):
    out = []
    for entry in lang["menu"]:
        if entry["type"] == "sentence":
            out.append(entry["sentence"])
        for item in entry.get("items", []):
            out.append(item["sentence"])
    out.append(lang["ui"]["recal_message"])
    return out


async def main():
    for code, lang in LANGUAGES.items():
        for text in all_sentences(lang):
            path = audio_path(code, text)
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            await edge_tts.Communicate(text, VOICES[code], rate=RATE).save(str(path))
            print(f"[{code}] {text}")
    print("Done.")


asyncio.run(main())