"""Emergency alarm: loops audio/alarm.wav until stop() is called."""
import os
import sys

_WAV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alarm.wav")
_playing = False
_use = None          # "winsound" | "pygame" | None


def start():
    global _playing, _use
    if _playing:
        return
    if sys.platform.startswith("win"):
        try:
            import winsound
            winsound.PlaySound(_WAV, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            _playing, _use = True, "winsound"
            return
        except Exception as e:
            print("[alarm] winsound failed:", e)
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        snd = pygame.mixer.Sound(_WAV)
        snd.set_volume(1.0)
        snd.play(loops=-1)
        start.snd = snd
        _playing, _use = True, "pygame"
    except Exception as e:
        print("[alarm] no sound available:", e)


def stop():
    global _playing, _use
    if _use == "winsound":
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
    elif _use == "pygame":
        try:
            start.snd.stop()
        except Exception:
            pass
    _playing, _use = False, None


def is_playing():
    return _playing
