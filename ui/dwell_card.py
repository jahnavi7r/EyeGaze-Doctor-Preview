import threading
from PyQt6.QtWidgets import QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen, QFont, QFontMetrics,
                         QPainterPath)

from ui.theme import (
    CARD_PALETTE, CARD_TEXT, BORDER_IDLE, BORDER_FOCUS,
    BORDER_SELECTED, RING_COLOR, UI_FONT,
)
from ui.symbols import get_icon

CONFIRM_BG = "#8FC9A2"     # soft green flash when a card is chosen
CONFIRM_MS = 450

try:
    import winsound
except ImportError:        # not Windows: no beep
    winsound = None


def _families(css_font_stack):
    return [f.strip().strip("'\"") for f in css_font_stack.split(",") if f.strip()]


def _beep():
    if winsound is None:
        return
    threading.Thread(target=lambda: winsound.Beep(880, 120), daemon=True).start()


def _draw_custom_icon(p: QPainter, icon_name: str, box: QRectF):
    """Paints custom vector icons matching the app's bold-outlined illustration style."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx, cy = box.center().x(), box.center().y()
    s = min(box.width(), box.height())
    r = s * 0.44
    stroke = QColor("#1E2733")
    stroke_w = max(3.5, s * 0.032)

    if icon_name == "yesno_yes":
        p.setPen(QPen(stroke, stroke_w * 1.3))
        p.setBrush(QColor("#63A876"))
        p.drawEllipse(QPointF(cx, cy), r, r)

        check_pen = QPen(stroke, stroke_w * 1.75, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(check_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(cx - r * 0.42, cy + r * 0.03)
        path.lineTo(cx - r * 0.10, cy + r * 0.36)
        path.lineTo(cx + r * 0.46, cy - r * 0.28)
        p.drawPath(path)

    elif icon_name == "yesno_no":
        p.setPen(QPen(stroke, stroke_w * 1.3))
        p.setBrush(QColor("#DF6B53"))
        p.drawEllipse(QPointF(cx, cy), r, r)

        cross_pen = QPen(stroke, stroke_w * 1.75, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap)
        p.setPen(cross_pen)
        d = r * 0.38
        p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
        p.drawLine(QPointF(cx + d, cy - d), QPointF(cx - d, cy + d))

    elif icon_name == "yesno_lang":
        globe_rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#689AC8"))
        p.drawEllipse(globe_rect)

        p.save()
        clip = QPainterPath()
        clip.addEllipse(globe_rect)
        p.setClipPath(clip)

        p.setPen(QPen(stroke, stroke_w * 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - r * 0.46, cy - r, r * 0.92, 2 * r))
        p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
        p.drawLine(QPointF(cx - r, cy - r * 0.34), QPointF(cx + r, cy - r * 0.34))
        p.drawLine(QPointF(cx - r, cy + r * 0.34), QPointF(cx + r, cy + r * 0.34))
        p.restore()

        p.setPen(QPen(stroke, stroke_w * 1.35))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(globe_rect)

    elif icon_name == "yesno_back":
        arrow_pen = QPen(stroke, stroke_w * 1.75, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(arrow_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        x_left = cx - r * 0.56
        x_right = cx + r * 0.56
        head = r * 0.44
        p.drawLine(QPointF(x_left, cy), QPointF(x_right, cy))
        p.drawLine(QPointF(x_left + head, cy - head), QPointF(x_left, cy))
        p.drawLine(QPointF(x_left + head, cy + head), QPointF(x_left, cy))

    elif icon_name == "dal":
        bw, bh = s * 0.72, s * 0.46
        bx, by = cx - bw / 2, cy - bh * 0.15

        steam_pen = QPen(stroke, stroke_w * 0.85, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(steam_pen)
        for dx in (-bw * 0.20, 0.0, bw * 0.20):
            sp = QPainterPath()
            sy0 = by - s * 0.06
            sp.moveTo(cx + dx, sy0)
            sp.cubicTo(cx + dx - s * 0.03, sy0 - s * 0.07,
                       cx + dx + s * 0.03, sy0 - s * 0.13,
                       cx + dx, sy0 - s * 0.20)
            p.drawPath(sp)

        p.setPen(QPen(stroke, stroke_w))
        p.setBrush(QColor("#9AC2DF"))
        p.drawRoundedRect(QRectF(cx - bw * 0.24, by + bh * 0.86, bw * 0.48, bh * 0.14), 4, 4)

        bowl_path = QPainterPath()
        bowl_path.moveTo(bx, by + bh * 0.22)
        bowl_path.quadTo(bx, by + bh * 0.92, cx, by + bh * 0.92)
        bowl_path.quadTo(bx + bw, by + bh * 0.92, bx + bw, by + bh * 0.22)
        bowl_path.closeSubpath()
        p.drawPath(bowl_path)

        rim = QRectF(bx, by, bw, bh * 0.42)
        p.setBrush(QColor("#F6F8FA"))
        p.drawEllipse(rim)
        dal_rect = QRectF(bx + bw * 0.07, by + bh * 0.08, bw * 0.86, bh * 0.30)
        p.setBrush(QColor("#F3B73F"))
        p.drawEllipse(dal_rect)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#D95338"))
        p.drawEllipse(QPointF(cx - bw * 0.12, by + bh * 0.22), s * 0.022, s * 0.015)
        p.setBrush(QColor("#4C9A5A"))
        p.drawEllipse(QPointF(cx + bw * 0.10, by + bh * 0.24), s * 0.024, s * 0.015)

    elif icon_name == "roti":
        rw, rh = s * 0.76, s * 0.56
        rx, ry = cx - rw / 2, cy - rh / 2

        p.setPen(QPen(stroke, stroke_w))
        p.setBrush(QColor("#E6C587"))
        p.drawEllipse(QRectF(rx + s * 0.02, ry + s * 0.04, rw, rh))

        p.setBrush(QColor("#F7E2B2"))
        p.drawEllipse(QRectF(rx, ry, rw, rh))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#B97A3D"))
        spots = [
            (-0.18, -0.08, 0.055, 0.038),
            (0.14, -0.10, 0.060, 0.040),
            (-0.04, 0.06, 0.070, 0.045),
            (0.20, 0.08, 0.048, 0.034),
            (-0.22, 0.10, 0.045, 0.032),
            (0.02, -0.14, 0.042, 0.028),
        ]
        for dx, dy, sw_f, sh_f in spots:
            p.drawEllipse(QRectF(cx + rw * dx, cy + rh * dy, s * sw_f, s * sh_f))

    elif icon_name == "curry":
        bw, bh = s * 0.74, s * 0.50
        bx, by = cx - bw / 2, cy - bh * 0.22

        p.setPen(QPen(stroke, stroke_w))
        p.setBrush(QColor("#D87C5A"))
        p.drawRoundedRect(QRectF(cx - bw * 0.25, by + bh * 0.86, bw * 0.50, bh * 0.14), 4, 4)

        bowl_path = QPainterPath()
        bowl_path.moveTo(bx, by + bh * 0.22)
        bowl_path.quadTo(bx, by + bh * 0.92, cx, by + bh * 0.92)
        bowl_path.quadTo(bx + bw, by + bh * 0.92, bx + bw, by + bh * 0.22)
        bowl_path.closeSubpath()
        p.drawPath(bowl_path)

        rim = QRectF(bx, by, bw, bh * 0.42)
        p.setBrush(QColor("#F8F5F0"))
        p.drawEllipse(rim)
        curry_rect = QRectF(bx + bw * 0.06, by + bh * 0.07, bw * 0.88, bh * 0.31)
        p.setBrush(QColor("#C85A32"))
        p.drawEllipse(curry_rect)

        p.setPen(QPen(stroke, stroke_w * 0.65))
        p.setBrush(QColor("#F2C14E"))
        p.drawRoundedRect(QRectF(cx - bw * 0.20, by + bh * 0.15, s * 0.08, s * 0.055), 3, 3)
        p.drawRoundedRect(QRectF(cx + bw * 0.06, by + bh * 0.18, s * 0.085, s * 0.055), 3, 3)
        p.setBrush(QColor("#58A55C"))
        p.drawEllipse(QPointF(cx - bw * 0.02, by + bh * 0.24), s * 0.032, s * 0.020)

    p.restore()


CUSTOM_ICONS = {"yesno_yes", "yesno_no", "yesno_lang", "yesno_back", "dal", "roti", "curry"}


class DwellCard(QPushButton):
    """A card that is 'clicked' by looking at it for dwell_time_ms."""
    dwell_completed = pyqtSignal(str)

    def __init__(self, text, key=None, bg_color=CARD_PALETTE[0],
                 text_color=CARD_TEXT, dwell_time_ms=1300, font_px=44,
                 radius=24, icon=None, parent=None):
        super().__init__(text, parent)
        self.text_label = text
        self.key = key if key is not None else text
        self.bg_color = bg_color
        self.text_color = text_color
        self.font_px = font_px
        self.radius = radius
        self.dwell_time_ms = dwell_time_ms
        self.icon_name = icon
        self.dwell_progress = 0.0
        self.is_locked = False
        self.is_gaze_inside = False
        self.is_selected = False
        self._confirming = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clicked.connect(self._manual_click)

        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._update_dwell)

        self._confirm_timer = QTimer(self)
        self._confirm_timer.setSingleShot(True)
        self._confirm_timer.setInterval(CONFIRM_MS)
        self._confirm_timer.timeout.connect(self._emit_after_confirm)

    # ------------------------------------------------------------ state
    def setText(self, text):
        self.text_label = text
        super().setText(text)
        self.update()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update()

    def set_locked(self, locked: bool):
        self.is_locked = locked
        if locked:
            self.reset_dwell()

    def start_dwell(self):
        if self.is_locked or self._confirming:
            return
        if not self.is_gaze_inside:
            self.is_gaze_inside = True
            self.timer.start()
            self.update()

    def reset_dwell(self):
        if self._confirming:
            return
        if self.is_gaze_inside or self.dwell_progress > 0.0:
            self.is_gaze_inside = False
            self.timer.stop()
            self.dwell_progress = 0.0
            self.update()

    # ------------------------------------------------------------ selecting
    def _manual_click(self):
        if not self.is_locked and not self._confirming:
            self._confirm()

    def _update_dwell(self):
        if self.is_locked or not self.is_gaze_inside:
            self.reset_dwell()
            return
        self.dwell_progress += 20 / self.dwell_time_ms
        if self.dwell_progress >= 1.0:
            self.timer.stop()
            self._confirm()
        self.update()

    def _confirm(self):
        self._confirming = True
        self.timer.stop()
        self.dwell_progress = 0.0
        _beep()
        self.update()
        self._confirm_timer.start()

    def _emit_after_confirm(self):
        self.dwell_completed.emit(self.key)
        self._confirming = False
        self.is_gaze_inside = False
        self.update()

    # ------------------------------------------------------------ painting
    def _fit_font(self, text, max_w, max_h, start_px):
        px = start_px
        while px > 14:
            f = QFont()
            f.setFamilies(_families(UI_FONT))
            f.setBold(True)
            f.setPixelSize(px)
            r = QFontMetrics(f).boundingRect(
                0, 0, int(max_w), 10000,
                int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter), text)
            if r.width() <= max_w and r.height() <= max_h:
                return f
            px -= 2
        f = QFont()
        f.setFamilies(_families(UI_FONT))
        f.setBold(True)
        f.setPixelSize(14)
        return f

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        focused = self.is_gaze_inside and not self.is_locked
        if focused:
            border_c, border_w = QColor(BORDER_FOCUS), 4
        elif self.is_selected:
            border_c, border_w = QColor(BORDER_SELECTED), 4
        else:
            border_c, border_w = QColor(BORDER_IDLE), 2
        half = border_w / 2
        card = QRectF(half, half, w - border_w, h - border_w)
        path = QPainterPath()
        path.addRoundedRect(card, self.radius, self.radius)

        bg = QColor(CONFIRM_BG if self._confirming else self.bg_color)
        p.fillPath(path, bg)

        if self.dwell_progress > 0.0 and not self.is_locked:
            p.save()
            p.setClipPath(path)
            p.fillRect(QRectF(0, 0, w * self.dwell_progress, h), QColor(31, 41, 51, 45))
            p.restore()

        p.setPen(QPen(border_c, border_w))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        text = ("✓  " + self.text_label) if self._confirming else self.text_label
        is_custom = self.icon_name in CUSTOM_ICONS
        pm = None if is_custom else get_icon(self.icon_name)
        lang_pm = get_icon("language") if self.icon_name == "yesno" else None
        pad = max(10, int(min(w, h) * 0.06))
        inner_w, inner_h = w - 2 * pad, h - 2 * pad
        p.setPen(QColor(self.text_color))

        if is_custom:
            if h > w * 1.35:
                icon_side = min(inner_w * 0.62, inner_h * 0.30)
                text_h = inner_h * 0.16
                gap = pad * 0.6
                block_h = icon_side + gap + text_h
                top = pad + (inner_h - block_h) / 2
                f = self._fit_font(text, inner_w, text_h, int(self.font_px * 0.95))
            else:
                icon_side = min(inner_w * 0.72, inner_h * 0.58)
                text_h = inner_h * 0.28
                gap = pad * 0.45
                block_h = icon_side + gap + text_h
                top = pad + (inner_h - block_h) / 2
                f = self._fit_font(text, inner_w, text_h, int(self.font_px * 0.85))

            p.setFont(f)
            _draw_custom_icon(
                p, self.icon_name,
                QRectF((w - icon_side) / 2, top, icon_side, icon_side)
            )
            p.drawText(
                QRectF(pad, top + icon_side + gap, inner_w, text_h),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap),
                text
            )
        elif pm is None:
            f = self._fit_font(text, inner_w, inner_h, self.font_px)
            p.setFont(f)
            p.drawText(QRectF(pad, pad, inner_w, inner_h),
                       int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), text)
        elif w > 1.8 * h:
            side = int(inner_h * 0.85)
            gap = pad
            f = self._fit_font(text, inner_w - side - gap, inner_h, int(self.font_px * 0.8))
            p.setFont(f)
            tw = QFontMetrics(f).boundingRect(
                0, 0, int(inner_w - side - gap), 10000,
                int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter), text).width()
            x0 = (w - (side + gap + tw)) / 2
            p.drawPixmap(QRectF(x0, (h - side) / 2, side, side), pm, QRectF(pm.rect()))
            p.drawText(QRectF(x0 + side + gap, pad, tw + 4, inner_h),
                       int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), text)
        elif lang_pm is not None:              # two stacked rows: ✓✗ on top, globe below
            text_h = inner_h * 0.26
            f = self._fit_font(text, inner_w, text_h, int(self.font_px * 0.72))
            p.setFont(f)
            avail_h = inner_h - text_h - pad * 0.4
            v_gap = pad * 0.35
            top_side = min(inner_w * 0.62, (avail_h - v_gap) * 0.48)
            bot_side = min(inner_w * 0.44, (avail_h - v_gap) * 0.42)
            total_icon_h = top_side + v_gap + bot_side
            top_y = pad + (avail_h - total_icon_h) / 2
            p.drawPixmap(QRectF((w - top_side) / 2, top_y, top_side, top_side),
                         pm, QRectF(pm.rect()))
            p.drawPixmap(QRectF((w - bot_side) / 2, top_y + top_side + v_gap, bot_side, bot_side),
                         lang_pm, QRectF(lang_pm.rect()))
            p.drawText(QRectF(pad, pad + avail_h + pad * 0.4, inner_w, text_h),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                           | Qt.TextFlag.TextWordWrap), text)
        else:
            text_h = inner_h * 0.30
            f = self._fit_font(text, inner_w, text_h, int(self.font_px * 0.8))
            p.setFont(f)
            side = min(inner_w, inner_h - text_h - pad * 0.5) * 0.95
            top = pad + (inner_h - text_h - side - pad * 0.5) / 2
            p.drawPixmap(QRectF((w - side) / 2, top, side, side), pm, QRectF(pm.rect()))
            p.drawText(QRectF(pad, top + side + pad * 0.5, inner_w, text_h),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                           | Qt.TextFlag.TextWordWrap), text)

        if self.dwell_progress > 0.0 and not self.is_locked:
            r = min(20, h / 2 - 10)
            cx, cy = w - r - 16, r + 16
            p.setPen(QPen(QColor(RING_COLOR), 7))
            p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 90 * 16,
                      int(-self.dwell_progress * 360 * 16))
        p.end()