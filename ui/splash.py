from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QVariantAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen

from ui.theme import THEME, CARD_PALETTE

# App name, split into colored parts. Change the text here to rename the app.
APP_NAME_PARTS = [
    ("Look", CARD_PALETTE[0]),   # dusty blue
    ("n", CARD_PALETTE[7]),      # slate grey
    ("Voice", CARD_PALETTE[1]),  # sage green
]
LINE_COLOR = CARD_PALETTE[3]     # lavender underline


def _clamp(t):
    return max(0.0, min(1.0, t))


def _ease_out(t):
    return 1.0 - (1.0 - _clamp(t)) ** 3


class SplashPage(QWidget):
    """Shows the app name for DURATION_MS, then emits `finished`."""
    finished = pyqtSignal()
    DURATION_MS = 4000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.progress = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(self.DURATION_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self.finished.emit)

    def start(self):
        self.progress = 0.0
        self._anim.start()

    def _on_value(self, value):
        self.progress = float(value)
        self.update()

    def paintEvent(self, event):
        p = self.progress
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(THEME["bg_window"]))

        # fade in during the first 30%, fade out during the last 15%
        alpha = _clamp(p / 0.30)
        if p > 0.85:
            alpha *= _clamp((1.0 - p) / 0.15)
        a = int(255 * alpha)
        if a <= 0:
            return

        font = QFont()
        font.setFamilies(["Segoe UI", "Nirmala UI", "sans-serif"])
        font.setBold(True)
        font.setPixelSize(max(48, int(self.height() * 0.13)))
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
        painter.setFont(font)
        fm = QFontMetrics(font)

        widths = [fm.horizontalAdvance(text) for text, _ in APP_NAME_PARTS]
        total = sum(widths)
        slide = (1.0 - _ease_out(p / 0.35)) * 18        # slides up 18px while fading in
        x = (self.width() - total) / 2
        baseline = self.height() / 2 + (fm.ascent() - fm.descent()) / 2 + slide

        for (text, color), width in zip(APP_NAME_PARTS, widths):
            c = QColor(color)
            c.setAlpha(a)
            painter.setPen(c)
            painter.drawText(int(x), int(baseline), text)
            x += width

        # thin line growing under the name (delete this block if you want only the text)
        line_progress = _ease_out((p - 0.20) / 0.40)
        if line_progress > 0:
            lc = QColor(LINE_COLOR)
            lc.setAlpha(a)
            painter.setPen(QPen(lc, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            half = total * 0.30 * line_progress
            y = int(baseline + fm.descent() + 24)
            cx = self.width() / 2
            painter.drawLine(int(cx - half), y, int(cx + half), y)