import os
import subprocess
import sys
import threading

from nlp.languages import LANGUAGES
from nlp.audio_cache import AUDIO_DIR, audio_path

try:  # only exists on Windows (installed together with pyttsx3)
    import pythoncom
except ImportError:
    pythoncom = None


class SpeechEngine:
    """Speaks sentences in the selected language.

    Sentences are no longer built here - they come ready-made (in SOV
    order) from nlp/languages.py. This class plays a pre-generated audio
    clip if one exists, otherwise uses an installed text-to-speech voice.
    """

    RATE = 125

    def __init__(self):
        self.lang_code = "hi"
        # code -> voice id, or None if no matching voice is installed.
        # A code that is absent has not been checked yet.
        self._voice_ids = {}

    # ------------------------------------------------------------ language
    def set_language(self, code: str):
        self.lang_code = code
        if code not in self._voice_ids:
            threading.Thread(target=self._probe, args=(code,), daemon=True).start()

    def voice_missing(self, code: str = None) -> bool:
        """True only if we checked, no installed voice exists, and there
        are no pre-generated clips for this language."""
        code = code or self.lang_code
        if self._has_clips(code):
            return False
        return code in self._voice_ids and self._voice_ids[code] is None

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _com_init():
        if pythoncom is None:
            return False
        pythoncom.CoInitialize()
        return True

    @staticmethod
    def _com_uninit(started: bool):
        if started and pythoncom is not None:
            pythoncom.CoUninitialize()

    @staticmethod
    def _match_voice(engine, code: str):
        keywords = LANGUAGES[code]["voice_keywords"]
        for voice in engine.getProperty("voices"):
            haystack = f"{voice.name} {voice.id} {getattr(voice, 'languages', '')}".lower()
            if any(k in haystack for k in keywords):
                return voice.id
        return None

    @staticmethod
    def _has_clips(code: str) -> bool:
        folder = AUDIO_DIR / code
        return folder.is_dir() and any(folder.glob("*.mp3"))

    @staticmethod
    def _play_clip(path) -> bool:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
            return True
        except Exception as e:
            print(f"[Audio clip failed]: {e}")
            return False
    @staticmethod
    def stop():
        """Silences a clip that is currently playing."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
    def _probe(self, code: str):
        """Looks for an installed voice for `code` (runs in a thread)."""
        com = False
        try:
            com = self._com_init()
            import pyttsx3
            engine = pyttsx3.init()
            self._voice_ids[code] = self._match_voice(engine, code)
            if self._voice_ids[code] is None:
                print(f"[TTS] No installed voice found for '{code}'")
        except Exception as e:
            print(f"[TTS probe failed]: {e}")
        finally:
            self._com_uninit(com)

    # --------------------------------------------------------------- speak
    def speak(self, text: str, code: str = None):
        code = code or self.lang_code

        def _speak():
            # 1) pre-generated audio clip (works offline, best quality)
            clip = audio_path(code, text)
            if clip.exists() and self._play_clip(clip):
                return

            # 2) installed text-to-speech voice
            com = False
            try:
                com = self._com_init()
                import pyttsx3
                engine = pyttsx3.init()
                voice_id = self._voice_ids.get(code) or self._match_voice(engine, code)
                if voice_id:
                    engine.setProperty("voice", voice_id)
                engine.setProperty("rate", self.RATE)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
                return
            except Exception as e:
                print(f"[TTS Fallback Triggered]: {e}")
            finally:
                self._com_uninit(com)

            # 3) Windows SAPI fallback
            if sys.platform == "win32":
                self._speak_with_powershell(text, LANGUAGES[code]["locale"])

        threading.Thread(target=_speak, daemon=True).start()

    @staticmethod
    def _speak_with_powershell(text: str, locale: str):
        """Windows SAPI fallback. The text goes through an environment
        variable so Telugu / Hindi characters and quotes cannot break
        the command."""
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "try { $s.SelectVoiceByHints("
            "[System.Speech.Synthesis.VoiceGender]::NotSet, "
            "[System.Speech.Synthesis.VoiceAge]::NotSet, 0, "
            "[System.Globalization.CultureInfo]::GetCultureInfo($env:AAC_LOCALE)) } catch {}; "
            "$s.Rate = -2; $s.Speak($env:AAC_TEXT)"
        )
        env = dict(os.environ, AAC_TEXT=text, AAC_LOCALE=locale)
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                env=env, capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as err:
            print(f"[TTS SAPI Failed]: {err}")