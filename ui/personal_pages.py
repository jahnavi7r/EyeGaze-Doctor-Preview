import io
import sqlite3
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QLabel
from audio.custom_voice import render_wave
from ui.personalization import WORDS
from ui.theme import CARD_PALETTE, BACK_COLOR, NEXT_COLOR, CARD_TEXT


class PersonalPages:
    @property
    def words(self):
        return WORDS[self.lang["code"] if self.lang else "en"]

    def refresh_tools(self):
        self.speed_button.setText(f"{self.words[0]}  ·  {self.dwell_ms / 1000:.1f} s")
        self.personal_button.setText(self.words[1])
        self.personal_button.setEnabled(bool(self.lang))

    def utility_page(self, title):
        self._stop_auto_return()
        self.clear_active_cards()
        self.stacked_widget.setCurrentWidget(self.sub_menu_page)
        self._clear_grid(self.sub_grid)
        self.header_title.setText(title)

    def utility_card(self, text, pos, color, action, icon=None):
        return self._make_card(text, color, self.sub_grid, *divmod(pos, 3),
                               lambda *_: action(), font_px=38, icon=icon)

    def change_speed(self, ms):
        self.preferences.set_dwell(ms)
        self.dwell_ms = ms
        for card in [self.output_back_btn, *self.cards]:
            if card is not self.stop_card:
                card.dwell_time_ms = ms
        self.refresh_tools()

    def open_settings(self, parent=None):
        from ui.caregiver import CaregiverDialog
        self._set_active_card(None)
        self._stop_auto_return()
        splash = self.stage == "splash"
        if splash:
            self.splash_page._anim.pause()
        CaregiverDialog(self, parent or self).exec()
        if splash:
            self.splash_page._anim.resume()
        if self.stage == "running" and not self.emergency and not self.calibrating:
            if self.stacked_widget.currentWidget() is self.sub_menu_page and self.active_category is not None:
                self.render_sub_menu(self.active_category, self.sub_page)
            else:
                self.lock_page_briefly()
                if self.stacked_widget.currentWidget() is self.output_page and self.auto_return_timer is None:
                    from PyQt6.QtCore import QTimer
                    self.auto_return_timer = QTimer(self)
                    self.auto_return_timer.setSingleShot(True)
                    self.auto_return_timer.timeout.connect(self.render_main_menu)
                    self.auto_return_timer.start(8000)

    def play_personal(self, item_id):
        import pygame
        try:
            message = self.preferences.message(item_id, self.lang["code"])
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            self.header_title.setText(str(exc))
            return
        if message is None:
            return
        sentence, wave_data = message
        self._stop_speech()
        self.show_final_output(sentence, speak=False)
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.custom_sound = pygame.mixer.Sound(file=io.BytesIO(wave_data))
            self.custom_sound.play()
        except pygame.error as exc:
            self.header_title.setText(str(exc))
            self._speak(sentence)
