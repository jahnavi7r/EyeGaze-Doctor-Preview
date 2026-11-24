import math
import time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QGridLayout, QVBoxLayout,
    QPushButton, QHBoxLayout, QLabel, QStackedWidget, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QImage, QPixmap
from ui.dwell_card import DwellCard
from ui.splash import SplashPage
from ui.bell_button import BellButton
from ui.theme import CARD_PALETTE, BACK_COLOR, NEXT_COLOR, UI_FONT
from nlp.speech_engine import SpeechEngine
from nlp.languages import LANGUAGES, LANGUAGE_ORDER, find_entry
from audio.voice import VoiceOutput
from audio import alarm
from nlp.emergency_text import EMERGENCY_TEXT

THEME = {
    "bg_window": "#14161D",
    "output_bg": "#D5E4EA",
    "output_text": "#0F4C5C",
    "card_next": NEXT_COLOR,
    "card_back": BACK_COLOR,
}

DWELL_MS = 1300
SNAP_MAX_PX = 220
HYSTERESIS_PX = 45
LOST_GAZE_S = 0.6
SHOW_POINTER = True

ITEM_SLOTS = [(0, 0), (0, 1), (0, 2), (1, 0)]
ICON_ALIAS = {"back": "pain_back", "rice": "dal_bhat"}

MAIN_ORDER = ["food", "water", "go", "pain", "help", "yesno"]
MAIN_SLOTS = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
HIDDEN_ITEMS = {"tiffin"}

LANG_WORD = {"te": "భాష", "en": "Language", "hi": "भाषा"}
BACK_WORD = {"te": "వెనుకకు", "en": "Back", "hi": "वापस"}

PAGE_MAIN = 0
PAGE_SUB = 1
PAGE_OUTPUT = 2
PAGE_LANGUAGE = 3
PAGE_SPLASH = 4
PAGE_EMERGENCY = 5

STOP_DWELL_MS = 3000
EMERGENCY_DWELL_MS = 1800
STOP_KEYS = (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_S)
FLASH_COLORS = ("#B3261E", "#E8736B")


class EmergencyPage(QWidget):
    """Full-screen alarm page."""

    def __init__(self):
        super().__init__()
        self.setObjectName("emergencyPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class GazePointerOverlay(QWidget):
    """Small always-on-top pointer that glides to the gaze point."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(60, 60)
        self._tx = self._ty = self._x = self._y = 0.0
        self._glide = QTimer(self)
        self._glide.setInterval(16)
        self._glide.timeout.connect(self._step)
        self._glide.start()
        self.show()

    def move_to_gaze(self, global_pt: QPoint):
        self._tx, self._ty = float(global_pt.x()), float(global_pt.y())

    def _step(self):
        self._x += (self._tx - self._x) * 0.22
        self._y += (self._ty - self._y) * 0.22
        self.move(int(self._x - 30), int(self._y - 30))
        self.raise_()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(255, 255, 255, 230), 3))
        painter.setBrush(QColor(0, 170, 255, 150))
        painter.drawEllipse(14, 14, 32, 32)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 255, 200, 255))
        painter.drawEllipse(25, 25, 10, 10)


from ui.personal_pages import PersonalPages
from ui.personalization import Preferences


class AACMainWindow(PersonalPages, QMainWindow):
    recalibrate_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AAC Assistive Gaze Interface")
        self.showFullScreen()

        self.preferences = Preferences()
        self.dwell_ms = self.preferences.dwell()
        self.custom_sound = None
        self.speech_engine = SpeechEngine()
        self.voice = VoiceOutput()
        self.lang = None
        self.active_category = None
        self.cards = []
        self.active_card = None
        self.sub_page = 0
        self.prev_view = ("main",)
        self.page_locked = False
        self.auto_return_timer = None
        self._last_gaze_t = time.monotonic()
        self.stage = "waiting"
        self.calibrating = False
        self.emergency = False

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.root_layout = QVBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(40, 20, 40, 20)
        self.central_widget.setStyleSheet(f"background-color: {THEME['bg_window']};")

        screen_w = QApplication.primaryScreen().geometry().width()
        pad = max(0, int(screen_w * 0.12) - 40)

        # Header with emergency bell + active language indicator + camera preview
        self.header_layout = QHBoxLayout()
        self.bell = BellButton(dwell_time_ms=EMERGENCY_DWELL_MS)
        self.bell.dwell_completed.connect(lambda *_: self.trigger_emergency())
        self.header_layout.addWidget(self.bell)

        self.header_title = QLabel("")
        self.header_title.setStyleSheet(
            f"color: #8A94A6; font-family: {UI_FONT}; font-size: 20px; font-weight: bold; padding-left: 14px;"
        )
        self.header_layout.addWidget(self.header_title)
        self.header_layout.addStretch()

        self.speed_button = QLabel()
        self.header_layout.addWidget(self.speed_button)
        self.settings_button = QPushButton("⚙ Settings")
        self.personal_button = QPushButton()
        for button, action in ((self.settings_button, self.open_settings), (self.personal_button, lambda: self.render_sub_menu("__mine__"))):
            button.clicked.connect(lambda checked=False, fn=action: fn())
            button.setStyleSheet(f"background: {NEXT_COLOR}; color: #1F2933; padding: 8px; border-radius: 6px;")
            self.header_layout.addWidget(button)
        self.speed_button.setStyleSheet("color:#DDE3EA; padding:6px;")
        self.refresh_tools()
        self.cam_preview = QLabel("Camera Loading...")
        self.cam_preview.setFixedSize(140, 95)
        self.cam_preview.setStyleSheet("border: 2px solid #00E5FF; background-color: #000; color: #FFF;")
        self.cam_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_layout.addWidget(self.cam_preview)
        self.root_layout.addLayout(self.header_layout)

        self.stacked_widget = QStackedWidget()
        self.root_layout.addWidget(self.stacked_widget, stretch=1)

        # ---------------- Page 0: Main Menu (3 x 2) ----------------
        self.main_menu_page = QWidget()
        self.main_menu_layout = QVBoxLayout(self.main_menu_page)
        self.main_menu_layout.setContentsMargins(pad, 0, pad, 0)
        self.main_grid_container = QWidget()
        self.main_grid = QGridLayout(self.main_grid_container)
        self.main_grid.setSpacing(30)
        for r in range(2):
            self.main_grid.setRowStretch(r, 1)
        for c in range(3):
            self.main_grid.setColumnStretch(c, 1)
        self.main_menu_layout.addWidget(self.main_grid_container, stretch=1)

        # ---------------- Page 1: Sub-Menu (3 x 2) ----------------
        self.sub_menu_page = QWidget()
        self.sub_menu_layout = QVBoxLayout(self.sub_menu_page)
        self.sub_menu_layout.setContentsMargins(pad, 0, pad, 0)
        self.sub_grid_container = QWidget()
        self.sub_grid = QGridLayout(self.sub_grid_container)
        self.sub_grid.setSpacing(30)
        for r in range(2):
            self.sub_grid.setRowStretch(r, 1)
        for c in range(3):
            self.sub_grid.setColumnStretch(c, 1)
        self.sub_menu_layout.addWidget(self.sub_grid_container, stretch=1)

        # ---------------- Page 2: Output ----------------
        self.output_page = QWidget()
        self.output_layout = QVBoxLayout(self.output_page)
        self.output_layout.setContentsMargins(50, 40, 50, 40)

        self.output_label = QLabel("")
        self.output_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_label.setTextFormat(Qt.TextFormat.PlainText)
        self.output_label.setWordWrap(True)
        self.output_label.setStyleSheet(f"""
            background-color: {THEME['output_bg']};
            color: {THEME['output_text']};
            font-family: {UI_FONT};
            font-size: 58px;
            font-weight: bold;
            border-radius: 20px;
            padding: 30px;
        """)
        self.output_layout.addWidget(self.output_label, stretch=2)

        self.output_back_btn = DwellCard("BACK", key="__back__", bg_color=THEME["card_back"],
                                         dwell_time_ms=self.dwell_ms)
        self.output_back_btn.icon_name = "back"
        self.output_back_btn.setMinimumHeight(120)
        self.output_back_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_back_btn.dwell_completed.connect(lambda *_: self.go_back_from_output())

        self.output_layout.addWidget(self.output_back_btn, stretch=1)

        # ---------------- Page 3: Language selection ----------------
        self.language_page = QWidget()
        self.language_layout = QVBoxLayout(self.language_page)
        self.language_layout.setContentsMargins(pad, 0, pad, 0)
        self.language_prompt = QLabel("భాషను ఎంచుకోండి   •   Select Language   •   भाषा चुनें")
        self.language_prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.language_prompt.setStyleSheet(
            f"color: #B0BEC5; font-family: {UI_FONT}; font-size: 30px; "
            "font-weight: bold; padding: 10px;"
        )
        self.language_layout.addWidget(self.language_prompt)
        self.language_grid_container = QWidget()
        self.language_grid = QGridLayout(self.language_grid_container)
        self.language_grid.setSpacing(30)
        self.language_grid.setRowStretch(0, 1)
        for c in range(len(LANGUAGE_ORDER)):
            self.language_grid.setColumnStretch(c, 1)
        self.language_layout.addWidget(self.language_grid_container, stretch=1)

        # ---------------- Page 4: Splash ----------------
        self.splash_page = SplashPage()
        self.splash_page.finished.connect(self._after_splash)

        # ---------------- Page 5: Emergency alarm ----------------
        self.emergency_page = EmergencyPage()
        em_layout = QVBoxLayout(self.emergency_page)
        em_layout.setContentsMargins(40, 40, 40, 40)
        self.emergency_title = QLabel("")
        self.emergency_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emergency_title.setWordWrap(True)
        em_layout.addWidget(self.emergency_title, stretch=3)
        self.emergency_sub = QLabel("")
        self.emergency_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emergency_sub.setWordWrap(True)
        em_layout.addWidget(self.emergency_sub, stretch=2)
        self.emergency_hint = QLabel("")
        self.emergency_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emergency_hint.setWordWrap(True)
        em_layout.addWidget(self.emergency_hint, stretch=1)
        self.stop_card = DwellCard("STOP ALARM", key="__stop__", bg_color="#F4F1E8",
                                   text_color="#8C1D18", dwell_time_ms=STOP_DWELL_MS, font_px=56)
        self.stop_card.setMinimumHeight(220)
        self.stop_card.dwell_completed.connect(lambda *_: self.stop_emergency())
        em_layout.addWidget(self.stop_card, stretch=3)
        self._flash_on = False
        self.flash_timer = QTimer(self)
        self.flash_timer.setInterval(400)
        self.flash_timer.timeout.connect(self._flash_step)

        self.stacked_widget.addWidget(self.main_menu_page)   # 0
        self.stacked_widget.addWidget(self.sub_menu_page)    # 1
        self.stacked_widget.addWidget(self.output_page)      # 2
        self.stacked_widget.addWidget(self.language_page)    # 3
        self.stacked_widget.addWidget(self.splash_page)      # 4
        self.stacked_widget.addWidget(self.emergency_page)   # 5

        self.cursor_overlay = GazePointerOverlay() if SHOW_POINTER else None

        self.watchdog = QTimer(self)
        self.watchdog.setInterval(250)
        self.watchdog.timeout.connect(self._check_gaze_alive)
        self.watchdog.start()

        self._show_header(False)
        self.stacked_widget.setCurrentIndex(PAGE_SPLASH)

    # ------------------------------------------------------------------ basics
    def closeEvent(self, event):
        alarm.stop()
        if hasattr(self, 'cursor_overlay') and self.cursor_overlay:
            self.cursor_overlay.close()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if self.emergency:
            if event.key() in STOP_KEYS:
                self.stop_emergency()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key.Key_C, Qt.Key.Key_F5):
            self.trigger_recalibration()
        elif event.key() == Qt.Key.Key_L:
            if self.stage == "running":
                self._stop_speech()
                self.render_language_menu()
        elif event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

    def lock_page_briefly(self, ms=900):
        self.page_locked = True
        self._set_active_card(None)
        for card in self.cards:
            card.set_locked(True)

        def unlock():
            self.page_locked = False
            for card in self.cards:
                card.set_locked(False)

        QTimer.singleShot(ms, unlock)

    def clear_active_cards(self):
        for card in self.cards:
            card.reset_dwell()
        self.cards.clear()
        self.active_card = None

    def _make_card(self, text, color, grid, r, c, handler, rowspan=1, colspan=1, key=None,
                   font_px=44, icon=None, dwell_ms=None):
        card = DwellCard(text, key=key, bg_color=color, dwell_time_ms=dwell_ms or self.dwell_ms, font_px=font_px,
                         icon=icon)
        card.dwell_completed.connect(handler)
        grid.addWidget(card, r, c, rowspan, colspan)
        self.cards.append(card)
        return card

    @staticmethod
    def _clear_grid(grid):
        while grid.count():
            w = grid.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _stop_auto_return(self):
        if self.auto_return_timer:
            self.auto_return_timer.stop()
            self.auto_return_timer = None

    # ---------------------------------------------------------- language helpers
    def _ui(self, key, default=""):
        lang = self.lang or LANGUAGES[LANGUAGE_ORDER[0]]
        return lang["ui"].get(key, default)

    def _menu_entry(self, entry_id):
        return find_entry(self.lang["menu"], entry_id)

    def _main_label(self, entry_id):
        if entry_id == "yesno":
            yes, no = self._menu_entry("yes"), self._menu_entry("no")
            lang_word = LANG_WORD.get(self.lang["code"], "Language")
            return f"{yes['label']} / {no['label']} / {lang_word}"
        return self._menu_entry(entry_id)["label"]

    def _speak(self, sentence):
        code = self.lang["code"]
        self.voice.stop()
        self.speech_engine.speak(sentence, code)

    def _stop_speech(self):
        if self.custom_sound is not None:
            self.custom_sound.stop()
        self.voice.stop()
        self.speech_engine.stop()

    def _show_header(self, visible: bool):
        self.speed_button.setVisible(visible)
        self.personal_button.setVisible(visible)
        self.bell.setVisible(visible)
        self.header_title.setVisible(visible)
        self.cam_preview.setVisible(visible)

    def trigger_recalibration(self):
        if self.stage != "running" or self.emergency:
            return
        self._stop_speech()
        self.calibrating = True
        self.recalibrate_requested.emit()

    # ------------------------------------------------------------------- pages
    def start_flow(self):
        if self.stage != "waiting":
            return
        self.show_splash()

    def show_splash(self):
        self.stage = "splash"
        self.calibrating = True
        self._stop_auto_return()
        self.clear_active_cards()
        self._show_header(False)
        self.stacked_widget.setCurrentIndex(PAGE_SPLASH)
        self.splash_page.start()

    def _after_splash(self):
        self.stage = "calibrating"
        self.calibrating = True
        self.recalibrate_requested.emit()

    def on_calibration_done(self, accuracy=None):
        if accuracy is None and self.stage == "calibrating":
            self.recalibrate_requested.emit()
            return
        self.calibrating = False
        if self.stage == "calibrating":
            self.stage = "running"
            self.render_language_menu()
        else:
            self.lock_page_briefly(1500)

    def render_language_menu(self, *_):
        self._stop_auto_return()
        self.clear_active_cards()
        self.lang = None
        self.refresh_tools()
        self.active_category = None
        self.header_title.setText("AAC Assistive Gaze Interface")
        self._show_header(True)
        self.stacked_widget.setCurrentIndex(PAGE_LANGUAGE)
        self._clear_grid(self.language_grid)

        for i, code in enumerate(LANGUAGE_ORDER):
            card = DwellCard(LANGUAGES[code]["name"], key=code,
                             bg_color=CARD_PALETTE[(i * 2 + 1) % len(CARD_PALETTE)],
                             dwell_time_ms=self.dwell_ms, font_px=56)
            card.dwell_completed.connect(self.select_language)
            self.language_grid.addWidget(card, 0, i)
            self.cards.append(card)
        self._update_bell_caption()

        self.lock_page_briefly(1500)

    def select_language(self, code: str):
        """Directly enter the selected language's main menu without confirmation slide."""
        self.lang = LANGUAGES[code]
        self.refresh_tools()
        self.speech_engine.set_language(code)
        self.header_title.setText(f"AAC Assistive Gaze Interface  •  {self.lang['name']}")
        self._update_bell_caption()
        self.render_main_menu()

    def go_back_to_language(self, *_):
        self._stop_speech()
        self.render_language_menu()

    def render_main_menu(self, *_):
        if self.lang is None:
            self.render_language_menu()
            return

        self._stop_auto_return()
        self.clear_active_cards()
        self.active_category = None
        self.header_title.setText(self.lang["name"])
        self.stacked_widget.setCurrentIndex(PAGE_MAIN)
        self._clear_grid(self.main_grid)

        for i, (entry_id, (r, c)) in enumerate(zip(MAIN_ORDER, MAIN_SLOTS)):
            self._make_card(self._main_label(entry_id), CARD_PALETTE[i % len(CARD_PALETTE)],
                            self.main_grid, r, c, self.handle_main_card_selection,
                            key=entry_id, icon=entry_id)

        self.lock_page_briefly()

    def render_sub_menu(self, category_id: str, page: int = 0, focus_last=False):
        mine = category_id == "__mine__"
        entry = {} if mine else self._menu_entry(category_id)
        items = [it for it in entry.get("items", []) if it["id"] not in HIDDEN_ITEMS]
        if entry.get("type") == "sentence":
            items.insert(0, entry)
        items.extend(self.preferences.cards(self.lang["code"], None if mine else category_id))
        title = self.words[1] if mine else entry["label"]
        if mine and not items:
            title += {"en":" · No saved cards", "hi":" · कोई सहेजा हुआ कार्ड नहीं", "te":" · సేవ్ చేసిన కార్డులు లేవు"}[self.lang["code"]]
        self.utility_page(title)
        self.active_category = category_id
        size = 5 if len(items) <= 5 else 4
        pages = max(1, math.ceil(len(items) / size))
        self.sub_page = page % pages
        start = self.sub_page * size
        for i, item in enumerate(items[start:start + size]):
            key = item["id"]
            self._make_card(item["label"], CARD_PALETTE[i], self.sub_grid, *divmod(i, 3),
                            self.handle_sub_card_selection, key=key, icon=item.get("icon", ICON_ALIAS.get(key, key)))
        if pages > 1:
            self.utility_card(f"{self._ui('next', 'Next')}  ›", 4, NEXT_COLOR,
                              lambda: self.render_sub_menu(category_id, page + 1), "next")
        self.utility_card(self._ui("back", "Back"), 5, BACK_COLOR, self.render_main_menu, "back")
        self.lock_page_briefly()

    def render_yes_no(self):
        """Exact layout from reference image:
        Col 0 (full height): Yes | Col 1 (full height): No | Col 2 top: Language | Col 2 bottom: Back
        """
        self._stop_auto_return()
        self.clear_active_cards()
        self.active_category = None
        self.stacked_widget.setCurrentIndex(PAGE_SUB)
        self._clear_grid(self.sub_grid)

        code = self.lang["code"]
        yes, no = self._menu_entry("yes"), self._menu_entry("no")
        lang_label = LANG_WORD.get(code, "Language")
        back_label = BACK_WORD.get(code, self._ui("back", "Back"))

        # Col 0 (full height): Yes
        self._make_card(
            yes["label"], "#A5C9B4", self.sub_grid, 0, 0,
            self.handle_yesno_selection, rowspan=2, colspan=1,
            key="yes", font_px=54, icon="yesno_yes"
        )
        # Col 1 (full height): No
        self._make_card(
            no["label"], "#E2B4BD", self.sub_grid, 0, 1,
            self.handle_yesno_selection, rowspan=2, colspan=1,
            key="no", font_px=54, icon="yesno_no"
        )
        # Col 2, Top: Language
        self._make_card(
            lang_label, "#E5BC96", self.sub_grid, 0, 2,
            self.go_back_to_language, rowspan=1, colspan=1,
            key="__lang__", font_px=44, icon="yesno_lang"
        )
        # Col 2, Bottom: Back
        self._make_card(
            back_label, "#B6BCC8", self.sub_grid, 1, 2,
            lambda *_: self.render_main_menu(), rowspan=1, colspan=1,
            key="__back__", font_px=44, icon="yesno_back"
        )

        self.lock_page_briefly()

    # ------------------------------------------------------------- emergency alarm
    def _em(self, key):
        code = self.lang["code"] if self.lang else LANGUAGE_ORDER[0]
        return EMERGENCY_TEXT[code][key]

    def _update_bell_caption(self):
        text = self._em("emergency") if self.lang else "Emergency"
        self.bell.text_label = text
        self.bell.setText(text)

    def _bell_active(self):
        return (self.stage == "running" and not self.calibrating and not self.emergency
                and self.bell.isVisible())

    def trigger_emergency(self, *_):
        if self.emergency:
            return
        self.emergency = True
        self._stop_speech()
        self._stop_auto_return()
        self.clear_active_cards()
        self._set_active_card(None)
        if self.lang is None:
            self.emergency_title.setText("EMERGENCY!")
            self.emergency_sub.setText(EMERGENCY_TEXT["te"]["title"] + "   " + EMERGENCY_TEXT["hi"]["title"])
            self.emergency_hint.setText("")
            stop_text = "STOP ALARM"
        else:
            self.emergency_title.setText(self._em("title"))
            self.emergency_sub.setText(self._em("subtitle"))
            self.emergency_hint.setText(self._em("hint"))
            stop_text = self._em("stop")
        self.stop_card.text_label = stop_text
        self.stop_card.setText(stop_text)
        self.cards.append(self.stop_card)
        self.stop_card.reset_dwell()
        self._show_header(False)
        self.stacked_widget.setCurrentIndex(PAGE_EMERGENCY)
        self._flash_on = False
        self._flash_step()
        self.flash_timer.start()
        alarm.start()
        self.lock_page_briefly(2500)

    def _flash_step(self):
        self._flash_on = not self._flash_on
        bg = FLASH_COLORS[0] if self._flash_on else FLASH_COLORS[1]
        self.emergency_page.setStyleSheet(f"#emergencyPage {{ background-color: {bg}; }}")
        base = f"font-family: {UI_FONT}; font-weight: bold; background: transparent; "
        self.emergency_title.setStyleSheet(base + "color: #FFFFFF; font-size: 150px;")
        self.emergency_sub.setStyleSheet(base + "color: #FFFFFF; font-size: 64px;")
        self.emergency_hint.setStyleSheet(base + "color: #FDECEA; font-size: 30px;")

    def stop_emergency(self, *_):
        if not self.emergency:
            return
        alarm.stop()
        self.flash_timer.stop()
        self.emergency = False
        self.clear_active_cards()
        self.emergency_page.setStyleSheet("")
        self._show_header(True)
        if self.lang is None:
            self.render_language_menu()
        else:
            self.render_main_menu()

    # ---------------------------------------------------------------- handlers
    def handle_main_card_selection(self, entry_id: str):
        if entry_id == "yesno":
            self.render_yes_no()
            return
        entry = self._menu_entry(entry_id)
        if entry is None:
            return
        if entry["type"] == "category" or self.preferences.cards(self.lang["code"], entry_id):
            self.render_sub_menu(entry_id)
        elif entry["type"] == "sentence":
            self.prev_view = ("main",)
            self.show_final_output(entry["sentence"])

    def handle_yesno_selection(self, entry_id: str):
        entry = self._menu_entry(entry_id)
        if entry is None:
            return
        if self.preferences.cards(self.lang["code"], entry_id):
            self.render_sub_menu(entry_id)
            return
        self.prev_view = ("yesno",)
        self.show_final_output(entry["sentence"])

    def handle_sub_card_selection(self, item_id: str):
        if item_id.startswith("custom-"):
            self.prev_view = ("sub", self.active_category, self.sub_page)
            self.play_personal(item_id)
            return
        category = self._menu_entry(self.active_category)
        item = category if category["id"] == item_id else find_entry(category.get("items", []), item_id)
        if item is None:
            return
        self.prev_view = ("sub", self.active_category, self.sub_page)
        self.show_final_output(item["sentence"])

    def show_final_output(self, sentence: str, speak: bool = True):
        self.clear_active_cards()
        self.output_label.setText(sentence)
        self.stacked_widget.setCurrentIndex(PAGE_OUTPUT)

        back = self._ui("back", "BACK")
        back_text = back if back.upper() == "BACK" else f"{back} (BACK)"
        self.output_back_btn.text_label = back_text
        self.output_back_btn.setText(back_text)

        self.cards.append(self.output_back_btn)
        self.output_back_btn.reset_dwell()

        if speak:
            QTimer.singleShot(200, lambda: self._speak(sentence))

        self._stop_auto_return()
        self.auto_return_timer = QTimer(self)
        self.auto_return_timer.setSingleShot(True)
        self.auto_return_timer.setInterval(8000)
        self.auto_return_timer.timeout.connect(self.render_main_menu)
        self.auto_return_timer.start()

        self.lock_page_briefly()

    def go_back_from_output(self):
        self._stop_speech()
        self._stop_auto_return()
        view = self.prev_view
        if view[0] == "sub":
            self.render_sub_menu(view[1], view[2])
        elif view[0] == "yesno":
            self.render_yes_no()
        else:
            self.render_main_menu()

    # ------------------------------------------------------------ camera/gaze
    def update_camera_preview(self, cv_img):
        if cv_img is None:
            return
        h, w, ch = cv_img.shape
        qt_img = QImage(cv_img.data, w, h, ch * w, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(qt_img).scaled(
            self.cam_preview.width(), self.cam_preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio
        )
        self.cam_preview.setPixmap(pixmap)

    def _card_distance(self, card, pt: QPoint) -> float:
        r = QRect(card.mapToGlobal(QPoint(0, 0)), card.size())
        dx = max(r.left() - pt.x(), 0, pt.x() - r.right())
        dy = max(r.top() - pt.y(), 0, pt.y() - r.bottom())
        return math.hypot(dx, dy)

    def _set_active_card(self, card):
        self.active_card = card
        for c in self.cards + [self.bell]:
            if c is card:
                c.start_dwell()
            else:
                c.reset_dwell()

    def _check_gaze_alive(self):
        if time.monotonic() - self._last_gaze_t > LOST_GAZE_S and self.active_card is not None:
            self._set_active_card(None)

    def update_gaze_point(self, screen_x: int, screen_y: int, is_blinking: bool):
        self._last_gaze_t = time.monotonic()
        pt = QPoint(int(screen_x), int(screen_y))
        if self.cursor_overlay is not None:
            self.cursor_overlay.move_to_gaze(pt)

        if self.calibrating or QApplication.activeModalWidget() is not None:
            self._set_active_card(None)
            return
        if is_blinking:
            return
        candidates = [] if self.page_locked else [c for c in self.cards if c.isEnabled()]
        if self._bell_active():
            candidates.append(self.bell)
        if not candidates:
            self._set_active_card(None)
            return
        if self.active_card not in candidates:
            self.active_card = None

        best_card, best_d = min(((c, self._card_distance(c, pt)) for c in candidates),
                                key=lambda t: t[1])
        if best_d > SNAP_MAX_PX:
            if self.active_card is not None:
                self._set_active_card(None)
            return

        if self.active_card is None:
            self._set_active_card(best_card)
        elif best_card is not self.active_card:
            cur_d = self._card_distance(self.active_card, pt)
            if best_d + HYSTERESIS_PX < cur_d:
                self._set_active_card(best_card)