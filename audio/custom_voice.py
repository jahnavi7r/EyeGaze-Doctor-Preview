"""Render locally entered text to a WAV in the selected language."""
import ctypes as ct
import io
import os
import wave
from espeakng_loader import get_data_path, load_library


def render_wave(sentence, language):
    lib = load_library()
    if lib is None:
        raise RuntimeError("The offline voice library could not be loaded.")
    rate = lib.espeak_Initialize(2, 0, os.fsencode(get_data_path()), 0)
    if rate <= 0:
        raise RuntimeError("The offline voice data could not be opened.")
    chunks = []
    callback_type = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_int, ct.c_void_p)

    @callback_type
    def collect(samples, count, events):
        if samples and count:
            chunks.append(ct.string_at(samples, count * 2))
        return 0

    try:
        lib.espeak_SetSynthCallback(collect)
        if lib.espeak_SetVoiceByName(language.encode("ascii")):
            raise RuntimeError("The selected language voice is unavailable.")
        data = sentence.encode("utf-8")
        if lib.espeak_Synth(data, len(data) + 1, 0, 1, 0, 1, None, None) or not chunks:
            raise RuntimeError("The voice could not read this sentence.")
    finally:
        lib.espeak_Terminate()
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, rate, 0, "NONE", ""))
        audio.writeframes(b"".join(chunks))
    return output.getvalue()
