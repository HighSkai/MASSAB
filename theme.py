"""MASSAB's look: Frutiger Aero, all sky, glass and gloss.

Qt style sheets can't do soft shadows, layered gloss or switches, so the
background, the glass cards, the toggles and the status lights are painted
here, and the style sheet covers everything else.
"""
import os
import tempfile

from PySide6.QtCore import Property, QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

INK = "#0e3557"
MUTED = "#4a6f91"

# Status light colors.
LIGHTS = {"green": ("#d4ff9e", "#4fc21d", "#2d7d0c"), "amber": ("#fff1a8", "#f2b21c", "#a06a00"),
          "red": ("#ffc9bd", "#e8452c", "#9a1d0b"), "blue": ("#d6f3ff", "#2ea6ee", "#145f9c"),
          "gray": ("#f4f8fb", "#a9bccd", "#6d8399")}

STYLE = """
* { font-family: "Segoe UI"; font-size: 10pt; color: %(ink)s; }
QStackedWidget, QScrollArea, QWidget#page, QWidget#scrollInner { background: transparent; border: none; }
QLabel { background: transparent; }
QLabel#title { font-family: "Segoe UI Semibold"; font-size: 16pt; color: #0b3d6b; }
QLabel#subtitle { color: #3a6990; font-size: 9pt; }
QLabel#heading { font-family: "Segoe UI Semibold"; font-size: 11pt; color: #0b3d6b; }
QLabel#caps { color: #2f7fbf; font-size: 8pt; font-weight: 700; }
QLabel#muted { color: %(muted)s; }
QLabel#hint { color: #5d7f9d; font-size: 9pt; }
QLabel#answer { font-family: "Segoe UI Semibold"; font-size: 24pt; color: #0b3d6b; }
QLabel#chip { color: #1d5f93; font-size: 8pt; font-weight: 700; padding: 1px 8px; border-radius: 8px;
    border: 1px solid #9cc7e8; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #d9eefc); }
QLabel#warning { color: #7a4a00; padding: 2px 10px; border-radius: 9px; border: 1px solid #e6b54a;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fff8dc, stop:0.5 #ffeaa6, stop:1 #ffe08a); }
QLabel#banner { color: #164a75; }
QFrame#sep { background: rgba(110, 160, 205, 70); max-height: 1px; min-height: 1px; border: none; }

QPushButton {
    color: %(ink)s; border: 1px solid #8fb3d3; border-radius: 8px; padding: 5px 14px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.49 #eef6fd, stop:0.5 #d9eaf8, stop:1 #eef7ff);
}
QPushButton:hover { border-color: #4fa3e0;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.49 #e6f5ff, stop:0.5 #c3e4fb, stop:1 #e2f4ff); }
QPushButton:pressed { padding-top: 6px; padding-bottom: 4px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #bfdff6, stop:1 #e6f4ff); }
QPushButton:disabled { color: #93aac0; border-color: #c7d8e7; background: rgba(240, 246, 251, 170); }

QPushButton#primary { color: white; font-weight: 600; border: 1px solid #1a6aa8;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #a3ddff, stop:0.48 #4caeea, stop:0.52 #1f8fd6, stop:1 #56c3ff); }
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c0e8ff, stop:0.48 #66bdf0, stop:0.52 #2f9fe6, stop:1 #74d0ff); }
QPushButton#primary:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1c7fc2, stop:1 #4bb4f0); }
QPushButton#primary:disabled { color: #e8f2fa; border-color: #9fc0da;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d6ebf8, stop:1 #b5d4ea); }

QPushButton#go { color: white; font-family: "Segoe UI Semibold"; font-size: 11pt; padding: 7px 22px;
    border: 1px solid #2f7d12; border-radius: 15px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #cdf7a8, stop:0.48 #74d040, stop:0.52 #4bb11d, stop:1 #8ee659); }
QPushButton#go:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ddfbc2, stop:0.48 #87dc55, stop:0.52 #5cc22b, stop:1 #a2ef72); }
QPushButton#go[running="true"] { border-color: #9c2412;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffcabd, stop:0.48 #f06a50, stop:0.52 #d63c22, stop:1 #f9805f); }
QPushButton#go[running="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffd9d0, stop:0.48 #f57d65, stop:0.52 #e34c31, stop:1 #ff9576); }
QPushButton#go:disabled { color: #f4f4f4; border-color: #a8b7c4;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e9eef2, stop:1 #bccad6); }

QPushButton[seg] { border-radius: 0; padding: 5px 15px; }
QPushButton[seg="first"] { border-top-left-radius: 12px; border-bottom-left-radius: 12px; }
QPushButton[seg="last"] { border-top-right-radius: 12px; border-bottom-right-radius: 12px; }
QPushButton[seg="mid"], QPushButton[seg="last"] { border-left: none; }
QPushButton[seg]:checked { color: white; font-weight: 600; border-color: #1a6aa8;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #a3ddff, stop:0.48 #4caeea, stop:0.52 #1f8fd6, stop:1 #56c3ff); }

QPushButton#nav { border: 1px solid transparent; border-radius: 14px; padding: 5px 18px; background: transparent;
    color: #1f5683; font-weight: 600; }
QPushButton#nav:hover { border-color: rgba(255, 255, 255, 200); background: rgba(255, 255, 255, 110); }
QPushButton#nav:checked { color: #0b3d6b; border: 1px solid #7fb7e2;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.5 #eaf6ff, stop:0.51 #d3ecfd, stop:1 #f1faff); }

QPushButton#suggestion { border-radius: 13px; padding: 5px 12px; color: #1d5f93; text-align: left; }
QPushButton#small { padding: 3px 10px; font-size: 9pt; }
QPushButton#swatch { min-width: 54px; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit#chatInput {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e7f0f8, stop:0.14 #ffffff, stop:1 #ffffff);
    border: 1px solid #93b6d4; border-radius: 7px; padding: 4px 8px;
    selection-background-color: #3aa0e8; selection-color: white;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit#chatInput:focus {
    border: 1px solid #2f97e6; }
QLineEdit[invalid="true"] { border: 1px solid #e0492f; background: #fff4f1; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { color: #8ea6bb; background: #eef3f7; }
QComboBox { padding-right: 24px; min-width: 90px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 22px; border: none; }
QComboBox::down-arrow { image: url(%(down)s); width: 10px; height: 6px; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #8fb3d3; outline: none; padding: 2px;
    selection-background-color: #3aa0e8; selection-color: white; }
QSpinBox, QDoubleSpinBox { padding-right: 22px; min-width: 70px; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { subcontrol-origin: border; width: 18px; border: none;
    border-left: 1px solid #c9dbea; background: transparent; }
QAbstractSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 7px; }
QAbstractSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 7px; }
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover { background: rgba(79, 182, 240, 50); }
QAbstractSpinBox::up-arrow { image: url(%(up)s); width: 8px; height: 5px; }
QAbstractSpinBox::down-arrow { image: url(%(down)s); width: 8px; height: 5px; }

QPlainTextEdit#log { background: rgba(255, 255, 255, 150); border: 1px solid rgba(143, 179, 211, 150);
    border-radius: 9px; padding: 4px; font-family: "Cascadia Mono", Consolas; font-size: 9pt; color: #234d70;
    selection-background-color: #3aa0e8; selection-color: white; }

QSlider::groove:horizontal { height: 6px; border-radius: 3px; border: 1px solid #a7c3db;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #cfdeeb, stop:1 #f2f8fc); }
QSlider::sub-page:horizontal { height: 6px; border-radius: 3px; border: 1px solid #2a86c6;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #9ddcff, stop:1 #2b97e0); }
QSlider::handle:horizontal { width: 16px; height: 16px; margin: -6px 0; border-radius: 9px; border: 1px solid #5a8fbd;
    background: qradialgradient(cx:0.5, cy:0.35, radius:0.7, fx:0.45, fy:0.25, stop:0 #ffffff, stop:0.6 #e3f1fb, stop:1 #b4d4ec); }
QSlider::handle:horizontal:hover { border-color: #2f97e6; }

QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
QScrollBar::handle:vertical { border: 1px solid #8db8da; border-radius: 4px; min-height: 30px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e4f3fd, stop:0.5 #c4e2f7, stop:1 #a9d2f0); }
QScrollBar::handle:vertical:hover { border-color: #4fa3e0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

QProgressBar { border: 1px solid #93b6d4; border-radius: 5px; max-height: 10px; min-height: 10px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #d7e4ef, stop:1 #f7fbff); }
QProgressBar::chunk { border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c4f59c, stop:0.5 #62c62f, stop:0.51 #48aa1c, stop:1 #7fd94f); }
QProgressBar[low="true"]::chunk {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffc4b6, stop:0.5 #ec5a3f, stop:0.51 #d23a20, stop:1 #f57e60); }

QFrame#bubbleUser { border: 1px solid #1d78b8; border-radius: 14px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #94d6ff, stop:0.5 #49b0ef, stop:1 #2b93dc); }
QFrame#bubbleUser QLabel { color: white; }
QFrame#bubbleAi { border: 1px solid #a9c8e2; border-radius: 14px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #e8f4fd); }
QFrame#bubbleError { border: 1px solid #e6a090; border-radius: 14px; background: #fff1ed; }
QFrame#bubbleError QLabel { color: #8a2a14; }

QMenu { background: #ffffff; border: 1px solid #8fb3d3; padding: 3px; }
QMenu::item { padding: 4px 18px; border-radius: 5px; }
QMenu::item:selected { background: #3aa0e8; color: white; }
QMenu::item:disabled { color: #9fb2c4; }
QToolTip { color: %(ink)s; background: #f4fbff; border: 1px solid #7fb2dc; padding: 4px; }

QFrame#hud { border-radius: 12px; }
QLabel#hudMode { color: white; font-weight: 700; padding: 1px 8px; border-radius: 8px; border: 1px solid rgba(160, 225, 255, 160);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(120, 205, 255, 230), stop:0.5 rgba(40, 150, 225, 230),
    stop:1 rgba(30, 120, 200, 230)); }
QLabel#hudAnswer { color: white; font-weight: 600; }
QLabel#hudSeconds { color: rgba(220, 238, 255, 200); }
QLabel#hudState { color: #8dff6a; font-weight: 600; }
QLabel#hudState[guess="true"] { color: #ffd34d; }
"""


def arrow_image(path, up=False, color=INK):
    """A small chevron for combo boxes and spin boxes."""
    image = QImage(20, 12, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    points = [QPointF(3, 9), QPointF(10, 3), QPointF(17, 9)] if up else [QPointF(3, 3), QPointF(10, 9), QPointF(17, 3)]
    p.drawPolyline(points)
    p.end()
    image.save(path)


def style_sheet():
    """The app's style sheet. Its arrow images are drawn into the temp folder."""
    folder = os.path.join(tempfile.gettempdir(), "massab-theme")
    os.makedirs(folder, exist_ok=True)
    paths = {}
    for name, up in (("down", False), ("up", True)):
        paths[name] = os.path.join(folder, f"arrow-{name}.png").replace("\\", "/")
        if not os.path.exists(paths[name]):
            arrow_image(paths[name], up)
    return STYLE % {"ink": INK, "muted": MUTED, **paths}


# --- painted pieces ----------------------------------------------------------

# Bubbles in the sky: (x, y, radius) as fractions of the window.
BUBBLES = [(0.08, 0.16, 0.07), (0.9, 0.1, 0.11), (0.78, 0.36, 0.035), (0.16, 0.58, 0.05), (0.94, 0.66, 0.06),
           (0.55, 0.06, 0.03), (0.4, 0.82, 0.04), (0.68, 0.9, 0.025), (0.28, 0.3, 0.02)]


def paint_bubble(p, center, radius):
    rim = QRadialGradient(center, radius)
    rim.setColorAt(0, QColor(255, 255, 255, 8))
    rim.setColorAt(0.75, QColor(220, 245, 255, 40))
    rim.setColorAt(0.95, QColor(255, 255, 255, 120))
    rim.setColorAt(1, QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(rim)
    p.drawEllipse(center, radius, radius)
    shine = QRadialGradient(center + QPointF(-0.35 * radius, -0.45 * radius), 0.45 * radius)
    shine.setColorAt(0, QColor(255, 255, 255, 190))
    shine.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(shine)
    p.drawEllipse(center + QPointF(-0.35 * radius, -0.45 * radius), 0.4 * radius, 0.28 * radius)


def paint_sky(p, w, h):
    sky = QLinearGradient(0, 0, 0, h)
    sky.setColorAt(0, QColor("#6fc1f0"))
    sky.setColorAt(0.35, QColor("#b9e5fd"))
    sky.setColorAt(0.75, QColor("#eaf8ff"))
    sky.setColorAt(1, QColor("#e3f7d6"))
    p.fillRect(QRectF(0, 0, w, h), sky)
    glow = QRadialGradient(QPointF(w * 0.18, -h * 0.08), max(w, h) * 0.75)
    glow.setColorAt(0, QColor(255, 255, 255, 190))
    glow.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(QRectF(0, 0, w, h), glow)

    # Two grassy waves along the bottom, the back one paler.
    for top, color_top, color_bottom, alpha in ((0.80, "#b9ec8a", "#79cf47", 120), (0.87, "#a3e36b", "#4fb52a", 170)):
        wave = QPainterPath(QPointF(0, h * top))
        wave.cubicTo(QPointF(w * 0.3, h * (top - 0.07)), QPointF(w * 0.62, h * (top + 0.08)), QPointF(w, h * (top - 0.02)))
        wave.lineTo(w, h)
        wave.lineTo(0, h)
        wave.closeSubpath()
        fill = QLinearGradient(0, h * (top - 0.05), 0, h)
        a, b = QColor(color_top), QColor(color_bottom)
        a.setAlpha(alpha)
        b.setAlpha(alpha + 40)
        fill.setColorAt(0, a)
        fill.setColorAt(1, b)
        p.setPen(QPen(QColor(255, 255, 255, 150), 2))
        p.setBrush(fill)
        p.drawPath(wave)

    for fx, fy, fr in BUBBLES:
        paint_bubble(p, QPointF(fx * w, fy * h), fr * min(w, h) * 1.4)


class Sky(QWidget):
    """The window background, painted once per size."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sky")
        self.cache = None

    def resizeEvent(self, event):
        self.cache = None
        super().resizeEvent(event)

    def paintEvent(self, event):
        ratio = self.devicePixelRatioF()
        if self.cache is None or self.cache.size() != self.size() * ratio:
            self.cache = QPixmap(self.size() * ratio)
            self.cache.setDevicePixelRatio(ratio)
            p = QPainter(self.cache)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            paint_sky(p, self.width(), self.height())
            p.end()
        p = QPainter(self)
        p.drawPixmap(event.rect(), self.cache, QRectF(event.rect().topLeft() * ratio, event.rect().size() * ratio).toRect())


class Glass(QFrame):
    """A frosted glass card with a soft shadow. Its layout's margins leave room for the shadow."""

    SHADOW = 6

    def __init__(self, parent=None, radius=14, padding=12, bar=False):
        super().__init__(parent)
        self.radius, self.padding, self.bar = radius, padding, bar

    def margins(self):
        s, pad = self.SHADOW, self.padding
        return s + pad, s - 2 + pad, s + pad, s + 2 + pad

    def vbox(self, spacing=8):
        box = QVBoxLayout(self)
        box.setContentsMargins(*self.margins())
        box.setSpacing(spacing)
        return box

    def hbox(self, spacing=10):
        box = QHBoxLayout(self)
        box.setContentsMargins(*self.margins())
        box.setSpacing(spacing)
        return box

    def paintEvent(self, event):
        s, r = self.SHADOW, self.radius
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(self.rect()).adjusted(s, s - 2, -s, -s - 2)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(s, 0, -1):
            p.setBrush(QColor(20, 70, 125, 7))
            p.drawRoundedRect(body.adjusted(-i, -i + 2, i, i + 2), r + i, r + i)

        fill = QLinearGradient(body.topLeft(), body.bottomLeft())
        if self.bar:
            fill.setColorAt(0, QColor(255, 255, 255, 215))
            fill.setColorAt(1, QColor(196, 230, 252, 200))
        else:
            fill.setColorAt(0, QColor(255, 255, 255, 228))
            fill.setColorAt(1, QColor(234, 246, 255, 196))
        p.setBrush(fill)
        p.setPen(QPen(QColor(70, 130, 190, 110), 1))
        p.drawRoundedRect(body, r, r)

        # Gloss over the top, and a bright inner edge.
        path = QPainterPath()
        path.addRoundedRect(body.adjusted(1, 1, -1, -1), r - 1, r - 1)
        p.setClipPath(path)
        gloss_h = min(body.height() * 0.5, 46)
        gloss = QLinearGradient(0, body.top(), 0, body.top() + gloss_h)
        gloss.setColorAt(0, QColor(255, 255, 255, 150 if self.bar else 110))
        gloss.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(body.left(), body.top(), body.width(), gloss_h), gloss)
        p.setClipping(False)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 235), 1))
        p.drawRoundedRect(body.adjusted(1, 1, -1, -1), r - 1, r - 1)


class Toggle(QCheckBox):
    """A glossy on/off switch. Behaves exactly like a QCheckBox."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._knob = 1.0 if checked else 0.0
        self.anim = QVariantAnimation(self, duration=140, easingCurve=QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._move)
        self.toggled.connect(self._animate)

    def _get_knob(self):
        return self._knob

    def _move(self, value):
        self._knob = float(value)
        self.update()

    knob = Property(float, _get_knob, _move)

    def _animate(self, checked):
        self.anim.stop()
        if not self.isVisible():
            self._move(1.0 if checked else 0.0)
            return
        self.anim.setStartValue(self._knob)
        self.anim.setEndValue(1.0 if checked else 0.0)
        self.anim.start()

    def sizeHint(self):
        return QSize(46, 26)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        track = QRectF(1, 2, 44, 22)
        radius = track.height() / 2
        off, on = (QColor("#eef3f8"), QColor("#c7d5e2")), (QColor("#c6f39d"), QColor("#4cb51f"))
        t = self._knob
        top = QColor.fromRgbF(*(a + (b - a) * t for a, b in zip(off[0].getRgbF()[:3], on[0].getRgbF()[:3])))
        bottom = QColor.fromRgbF(*(a + (b - a) * t for a, b in zip(off[1].getRgbF()[:3], on[1].getRgbF()[:3])))
        fill = QLinearGradient(track.topLeft(), track.bottomLeft())
        fill.setColorAt(0, bottom)
        fill.setColorAt(1, top)
        p.setPen(QPen(QColor("#2f7d12") if t > 0.5 else QColor("#8ea9c2"), 1))
        p.setBrush(fill)
        p.drawRoundedRect(track, radius, radius)
        gloss = QLinearGradient(track.topLeft(), QPointF(track.left(), track.center().y()))
        gloss.setColorAt(0, QColor(255, 255, 255, 150))
        gloss.setColorAt(1, QColor(255, 255, 255, 20))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gloss)
        p.drawRoundedRect(track.adjusted(3, 1.5, -3, -track.height() / 2), radius / 2, radius / 2)

        d = track.height() - 2
        x = track.left() + 1 + t * (track.width() - d - 2)
        knob = QRectF(x, track.top() + 1, d, d)
        shade = QRadialGradient(knob.center() + QPointF(0, -d * 0.2), d * 0.7)
        shade.setColorAt(0, QColor("#ffffff"))
        shade.setColorAt(0.7, QColor("#e6f0f8"))
        shade.setColorAt(1, QColor("#b8cde0"))
        p.setPen(QPen(QColor("#7d9cb8"), 1))
        p.setBrush(shade)
        p.drawEllipse(knob)


class Light(QWidget):
    """A glossy status light with a label beside it."""

    def __init__(self, text="", color="gray", parent=None):
        super().__init__(parent)
        self.text, self.color = text, color

    def set(self, text, color):
        self.text, self.color = text, color
        self.setToolTip(text)
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        text = self.fontMetrics().horizontalAdvance(self.text) + 8 if self.text else 0
        return QSize(17 + text, max(20, self.fontMetrics().height() + 4))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        light, mid, edge = LIGHTS.get(self.color, LIGHTS["gray"])
        d = 13
        dot = QRectF(2, (self.height() - d) / 2, d, d)
        fill = QRadialGradient(dot.center() + QPointF(0, -d * 0.15), d * 0.65)
        fill.setColorAt(0, QColor(light))
        fill.setColorAt(0.65, QColor(mid))
        fill.setColorAt(1, QColor(edge))
        p.setPen(QPen(QColor(edge), 1))
        p.setBrush(fill)
        p.drawEllipse(dot)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 170))
        p.drawEllipse(QRectF(dot.left() + 3, dot.top() + 1.5, d - 6, d * 0.38))
        p.setPen(QColor(INK))
        p.drawText(QRectF(22, 0, self.width() - 22, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text)


def orb(size=64, letter="M"):
    """MASSAB's logo: a glossy aqua orb."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    r = QRectF(2, 2, size - 4, size - 4)
    body = QRadialGradient(QPointF(size * 0.5, size * 0.72), size * 0.62)
    body.setColorAt(0, QColor("#8ff0ff"))
    body.setColorAt(0.55, QColor("#22a4e6"))
    body.setColorAt(1, QColor("#0b5aa0"))
    p.setPen(QPen(QColor("#0a4f8c"), max(1.0, size / 48)))
    p.setBrush(body)
    p.drawEllipse(r)
    if letter:
        font = QFont("Segoe UI", 1, QFont.Weight.Bold)
        font.setPixelSize(int(size * 0.5))
        p.setFont(font)
        p.setPen(QColor(0, 50, 100, 90))
        p.drawText(r.translated(0, size * 0.03), Qt.AlignmentFlag.AlignCenter, letter)
        p.setPen(QColor("white"))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, letter)
    shine = QLinearGradient(0, r.top(), 0, r.top() + r.height() * 0.5)
    shine.setColorAt(0, QColor(255, 255, 255, 230))
    shine.setColorAt(1, QColor(255, 255, 255, 25))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(shine))
    p.drawEllipse(QRectF(r.left() + r.width() * 0.16, r.top() + r.height() * 0.04, r.width() * 0.68, r.height() * 0.46))
    p.end()
    return pixmap


def separator():
    line = QFrame(objectName="sep")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line


def label(text, name=None, wrap=False):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget
