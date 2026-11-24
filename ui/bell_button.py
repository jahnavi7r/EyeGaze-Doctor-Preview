from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath

from ui.dwell_card import DwellCard, CONFIRM_BG
from ui.theme import BORDER_FOCUS

BELL_RED = "#D9645B"

# The bell sits in the top-left of the header: window margins (40, 20) + half of its 140 x 100 size.
BELL_CENTER_PX = (40 + 70, 20 + 50)


def bell_fraction(screen_w, screen_h):
    """Centre of the bell as a fraction of the screen (for the 7th calibration point)."""
    return (BELL_CENTER_PX[0] / screen_w, BELL_CENTER_PX[1] / screen_h)


class BellButton(DwellCard):
    """Round red EMERGENCY button with a bell (always visible in the top-left corner).
    Look at it for dwell_time_ms (or tap it) to sound the alarm."""

    def __init__(self, caption="Emergency", dwell_time_ms=1800):
        super().__init__(caption, key="emergency", bg_color=BELL_RED, text_color="#E8ECEF",
                         dwell_time_ms=dwell_time_ms, font_px=17, radius=0)
        self.setFixedSize(140, 100)

    @staticmethod
    def _bell_path():
        """A simple bell on a 100 x 100 grid."""
        p = QPainterPath()
        p.moveTo(20, 72)
        p.cubicTo(30, 64, 30, 50, 31, 40)
        p.cubicTo(32, 26, 42, 20, 50, 20)
        p.cubicTo(58, 20, 68, 26, 69, 40)
        p.cubicTo(70, 50, 70, 64, 80, 72)
        p.closeSubpath()
        p.addEllipse(44, 11, 12, 12)       # top knob
        p.addEllipse(41, 74, 18, 14)       # clapper
        return p

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        cx, cy, r = w / 2, 38, 30

        focused = self.is_gaze_inside and not self.is_locked
        fill = QColor(CONFIRM_BG if self._confirming else BELL_RED)
        p.setBrush(fill)
        p.setPen(QPen(QColor(BORDER_FOCUS) if focused else QColor("#F2B5AF"), 4 if focused else 2))
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))

        # the bell
        s = 0.62
        p.save()
        p.translate(cx - 50 * s, cy - 49.5 * s)
        p.scale(s, s)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawPath(self._bell_path())
        p.restore()

        # dwell progress ring around the circle
        if self.dwell_progress > 0.0 and not self.is_locked:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#FFFFFF"), 5))
            rr = r + 5
            p.drawArc(QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr), 90 * 16,
                      int(-self.dwell_progress * 360 * 16))

        # caption under the circle
        f = self._fit_font(self.text_label, w - 4, 22, 17)
        p.setFont(f)
        p.setPen(QColor(self.text_color))
        p.drawText(QRectF(0, 76, w, 24), int(Qt.AlignmentFlag.AlignCenter), self.text_label)
        p.end()