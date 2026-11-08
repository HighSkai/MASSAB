"""MASSAB's look: a glass control window floating over a deep indigo sky.

Qt style sheets can't blur, cast soft shadows or animate, so the backdrop, the
glass panels, the switches, the segmented controls, the rail's sliding pill,
the timing bar and the icons are painted here. The style sheet covers the rest.
"""
import ctypes
import os
import sys
import tempfile

import cv2
import numpy as np
from PySide6.QtCore import (Property, QEasingCurve, QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation,
                            QRectF, QSize, Qt, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QFontMetrics, QIcon, QImage, QLinearGradient,
                           QPainter, QPainterPath, QPalette, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QBoxLayout, QButtonGroup, QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

INK = "#f3f5ff"         # primary text
TEXT2 = "#aab3d8"       # secondary text
TEXT3 = "#858fb6"       # captions, placeholders, empty states
ACCENT = "#4d7cff"
ACCENT_HI = "#7c9dff"
VIOLET = "#8a6bff"
CYAN = "#3cc8ff"
GREEN = "#2fd38a"
AMBER = "#ffb547"
RED = "#ff5a6e"
GROUND = "#0b1140"      # the title bar, matching the top of the backdrop
POPUP = "#151b48"       # menus, drop-downs and tooltips

LIGHTS = {"green": GREEN, "amber": AMBER, "red": RED, "blue": ACCENT, "gray": "#5d6690"}
EASE = QEasingCurve.Type.OutExpo


# --- fonts ---------------------------------------------------------------------

FONTS = {}


def fonts():
    """Each type role as (family, weight). Windows 11's Segoe UI Variable when it's there, else Segoe UI."""
    if not FONTS:
        have = set(QFontDatabase.families())

        def pick(*options):
            return next((option for option in options if option[0] in have), options[-1])
        FONTS.update(
            text=pick(("Segoe UI Variable Text", 400), ("Segoe UI", 400)),
            strong=pick(("Segoe UI Variable Text Semibold", 400), ("Segoe UI Semibold", 400), ("Segoe UI", 600)),
            display=pick(("Segoe UI Variable Display Semibold", 400), ("Segoe UI Semibold", 400), ("Segoe UI", 600)),
            mono=pick(("Cascadia Mono", 400), ("Consolas", 400)))
    return FONTS


def font(role="text", pt=10.0):
    family, weight = fonts()[role]
    f = QFont(family)
    f.setPointSizeF(pt)
    f.setWeight(QFont.Weight(weight))
    return f


def css_font(role):
    family, weight = fonts()[role]
    return f'font-family: "{family}"; font-weight: {weight};'


# --- the style sheet -------------------------------------------------------------

STYLE = """
* { %(text)s font-size: 10pt; color: %(ink)s; }
QWidget#page, QWidget#scrollInner, QStackedWidget, QScrollArea { background: transparent; border: none; }
QLabel { background: transparent; }
QLabel#brand { %(display)s font-size: 13pt; }
QLabel#pageTitle { %(display)s font-size: 20pt; }
QLabel#cardTitle { %(strong)s font-size: 11pt; }
QLabel#emptyTitle { %(display)s font-size: 14pt; }
QLabel#secondary { color: %(text2)s; }
QLabel#hint { color: %(text3)s; font-size: 9pt; }
QLabel#answer { %(display)s font-size: 30pt; }
QLabel#answer[empty="true"] { color: %(text3)s; }
QLabel#total { %(display)s font-size: 14pt; }
QLabel#chip { %(strong)s font-size: 8.5pt; color: #c9d6ff; padding: 0 10px; border-radius: 11px;
    min-height: 22px; max-height: 22px; border: 1px solid rgba(125, 157, 255, 100); background: rgba(77, 124, 255, 46); }
QLabel#chip[tone="good"] { color: #93f0c4; border-color: rgba(47, 211, 138, 110); background: rgba(47, 211, 138, 34); }
QLabel#chip[tone="plain"] { color: %(text2)s; border-color: rgba(255, 255, 255, 36); background: rgba(255, 255, 255, 15); }
QLabel#warning { %(strong)s font-size: 9pt; color: #ffd08a; padding: 0 11px; border-radius: 11px;
    min-height: 22px; max-height: 22px; border: 1px solid rgba(255, 181, 71, 110); background: rgba(255, 181, 71, 33); }
QLabel#statusText { %(strong)s font-size: 9.5pt; color: %(text2)s; }
QLabel#statusText[live="true"] { color: %(ink)s; }
QFrame#statusPill { border-radius: 18px; border: 1px solid rgba(255, 255, 255, 26); background: rgba(255, 255, 255, 15); }
QFrame#sep { background: rgba(255, 255, 255, 18); max-height: 1px; min-height: 1px; border: none; }

QPushButton { %(strong)s font-size: 9.5pt; color: %(ink)s; padding: 7px 16px; border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 31); background: rgba(255, 255, 255, 20); }
QPushButton:hover { border-color: rgba(255, 255, 255, 51); background: rgba(255, 255, 255, 36); }
QPushButton:pressed { background: rgba(255, 255, 255, 13); }
QPushButton:focus { border-color: %(accent_hi)s; }
QPushButton:disabled { color: rgba(243, 245, 255, 90); border-color: rgba(255, 255, 255, 15); background: rgba(255, 255, 255, 10); }
QPushButton#primary, QPushButton#go { color: white; border: 1px solid rgba(255, 255, 255, 51);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6a93ff, stop:1 #3a5ef0); }
QPushButton#primary:hover, QPushButton#go:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #82a5ff, stop:1 #4a6cff); }
QPushButton#primary:pressed, QPushButton#go:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5279f2, stop:1 #314fd8); }
QPushButton#primary:focus, QPushButton#go:focus { border-color: white; }
QPushButton#primary:disabled { color: rgba(255, 255, 255, 110); border-color: rgba(255, 255, 255, 20); background: rgba(77, 124, 255, 56); }
QPushButton#go { %(strong)s font-size: 10.5pt; padding: 0 28px; border-radius: 18px; min-width: 64px; }
QPushButton#go[running="true"] { color: #ffd9de; border: 1px solid rgba(255, 90, 110, 140); background: rgba(255, 90, 110, 46); }
QPushButton#go[running="true"]:hover { background: rgba(255, 90, 110, 72); }
QPushButton#go:disabled { color: rgba(255, 255, 255, 110); border-color: rgba(255, 255, 255, 20); background: rgba(255, 255, 255, 15); }
QPushButton#small { font-size: 9pt; padding: 5px 13px; border-radius: 14px; }
QPushButton#suggestion { %(text)s font-size: 9.5pt; color: %(text2)s; padding: 7px 15px; border-radius: 16px; }
QPushButton#suggestion:hover { color: %(ink)s; }
QPushButton#nav { %(strong)s font-size: 10pt; color: %(text2)s; text-align: left; padding: 0 14px;
    min-height: 40px; max-height: 40px; border: 1px solid transparent; border-radius: 14px; background: transparent; }
QPushButton#nav:hover { color: %(ink)s; background: rgba(255, 255, 255, 10); }
QPushButton#nav:checked { color: %(ink)s; background: transparent; }
QPushButton#nav:focus { border-color: %(accent_hi)s; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit#chatInput {
    color: %(ink)s; border: 1px solid rgba(255, 255, 255, 26); border-radius: 11px; padding: 6px 10px;
    background: rgba(0, 0, 0, 64); selection-background-color: %(accent)s; selection-color: white; }
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QPlainTextEdit#chatInput:hover {
    border-color: rgba(255, 255, 255, 46); }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit#chatInput:focus {
    border-color: %(accent_hi)s; background: rgba(0, 0, 0, 84); }
QLineEdit[invalid="true"] { border-color: %(red)s; background: rgba(255, 90, 110, 26); }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    color: rgba(243, 245, 255, 90); border-color: rgba(255, 255, 255, 13); background: rgba(0, 0, 0, 31); }
QComboBox { padding-right: 30px; min-width: 128px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 28px; border: none; }
QComboBox::down-arrow { image: url(%(down)s); width: 10px; height: 6px; }
QComboBox QAbstractItemView { color: %(ink)s; background: %(popup)s; border: 1px solid rgba(255, 255, 255, 31);
    outline: none; padding: 4px; selection-background-color: rgba(77, 124, 255, 150); selection-color: white; }
QSpinBox, QDoubleSpinBox { padding-right: 28px; min-width: 84px; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { subcontrol-origin: border; width: 24px; border: none;
    background: transparent; }
QAbstractSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 11px; }
QAbstractSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 11px; }
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover { background: rgba(255, 255, 255, 20); }
QAbstractSpinBox::up-arrow { image: url(%(up)s); width: 8px; height: 5px; }
QAbstractSpinBox::down-arrow { image: url(%(down)s); width: 8px; height: 5px; }
QAbstractSpinBox::up-arrow:disabled { image: url(%(up_dim)s); }
QAbstractSpinBox::down-arrow:disabled, QComboBox::down-arrow:disabled { image: url(%(down_dim)s); }
QPlainTextEdit#chatInput { border-radius: 16px; padding: 8px 12px; }
QPlainTextEdit#log { %(mono)s font-size: 9pt; color: #cdd3f0; border: 1px solid rgba(255, 255, 255, 15);
    border-radius: 14px; padding: 8px 10px; background: rgba(0, 0, 0, 56);
    selection-background-color: %(accent)s; selection-color: white; }

QSlider { min-height: 22px; }
QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: rgba(255, 255, 255, 36); }
QSlider::sub-page:horizontal { height: 4px; border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6a93ff, stop:1 %(accent)s); }
QSlider::handle:horizontal { width: 18px; height: 18px; margin: -7px 0; border-radius: 9px; background: white; }
QSlider::handle:horizontal:hover { background: #e3e9ff; }
QSlider::sub-page:horizontal:disabled { background: rgba(255, 255, 255, 46); }

QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 41); border-radius: 3px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 72); }
QScrollBar[idle="true"]::handle:vertical { background: transparent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

QProgressBar { border: none; border-radius: 2px; max-height: 4px; min-height: 4px; background: rgba(255, 255, 255, 26); }
QProgressBar::chunk { border-radius: 2px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(cyan)s, stop:1 %(accent)s); }
QProgressBar[low="true"]::chunk { background: %(red)s; }

QFrame#bubbleUser { border: none; border-radius: 18px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6a93ff, stop:1 #3a5ef0); }
QFrame#bubbleUser QLabel { color: white; }
QFrame#bubbleAi { border: 1px solid rgba(255, 255, 255, 26); border-radius: 18px; background: rgba(255, 255, 255, 18); }
QFrame#bubbleError { border: 1px solid rgba(255, 90, 110, 102); border-radius: 18px; background: rgba(255, 90, 110, 31); }
QFrame#bubbleError QLabel { color: #ffc6cd; }

QMenu { background: %(popup)s; border: 1px solid rgba(255, 255, 255, 31); padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: rgba(77, 124, 255, 150); }
QMenu::item:disabled { color: %(text3)s; }
QMenu::separator { height: 1px; background: rgba(255, 255, 255, 20); margin: 4px 8px; }
QToolTip { color: %(ink)s; background: %(popup)s; border: 1px solid rgba(255, 255, 255, 41); padding: 6px 8px; }

QLabel#hudKind { %(strong)s color: white; padding: 0 9px; border: 1px solid rgba(150, 178, 255, 130);
    background: rgba(77, 124, 255, 120); }
QLabel#hudAnswer { %(display)s color: white; }
QLabel#hudSeconds { color: rgba(205, 214, 245, 200); }
QLabel#hudState { %(strong)s color: #4ee6a0; }
QLabel#hudState[plain="true"] { color: rgba(225, 231, 255, 220); }
QLabel#hudFlag { %(strong)s color: #ffc35c; }
"""


def arrow_image(path, up=False, color=TEXT2):
    """A small chevron for drop-downs and spin boxes."""
    image = QImage(20, 12, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPolyline([QPointF(3, 9), QPointF(10, 3), QPointF(17, 9)] if up else
                   [QPointF(3, 3), QPointF(10, 9), QPointF(17, 3)])
    p.end()
    image.save(path)


def style_sheet():
    """The app's style sheet. Its chevrons are drawn into the temp folder."""
    folder = os.path.join(tempfile.gettempdir(), "massab-theme-2")
    os.makedirs(folder, exist_ok=True)
    paths = {}
    for name, up, color in (("down", False, TEXT2), ("up", True, TEXT2), ("down_dim", False, "#4a5280"),
                            ("up_dim", True, "#4a5280")):
        paths[name] = os.path.join(folder, f"arrow-{name}.png").replace("\\", "/")
        if not os.path.exists(paths[name]):
            arrow_image(paths[name], up, color)
    return STYLE % {"ink": INK, "text2": TEXT2, "text3": TEXT3, "accent": ACCENT, "accent_hi": ACCENT_HI,
                    "cyan": CYAN, "red": RED, "popup": POPUP, **{role: css_font(role) for role in fonts()}, **paths}


def apply(app):
    """Dark palette, Fusion and the style sheet, so even the parts not styled here match."""
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, GROUND), (QPalette.ColorRole.WindowText, INK),
                        (QPalette.ColorRole.Base, "#0f1438"), (QPalette.ColorRole.AlternateBase, "#141a45"),
                        (QPalette.ColorRole.Text, INK), (QPalette.ColorRole.Button, "#1a2152"),
                        (QPalette.ColorRole.ButtonText, INK), (QPalette.ColorRole.Highlight, ACCENT),
                        (QPalette.ColorRole.HighlightedText, "#ffffff"), (QPalette.ColorRole.ToolTipBase, POPUP),
                        (QPalette.ColorRole.ToolTipText, INK), (QPalette.ColorRole.PlaceholderText, TEXT3),
                        (QPalette.ColorRole.Link, ACCENT_HI), (QPalette.ColorRole.BrightText, "#ffffff")):
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(243, 245, 255, 90))
    app.setPalette(palette)
    app.setFont(font("text", 10))
    app.setStyleSheet(style_sheet())


def dark_title_bar(window):
    """Windows draws the title bar. Ask it for a dark one in the backdrop's color."""
    if sys.platform != "win32":
        return
    try:
        dwm = ctypes.windll.dwmapi
        hwnd = ctypes.c_void_p(int(window.winId()))
        for attribute, value in ((20, 1), (35, colorref(GROUND)), (34, colorref(GROUND)), (36, colorref(INK))):
            value = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):
        pass


def colorref(hex_color):
    color = QColor(hex_color)
    return color.red() | color.green() << 8 | color.blue() << 16


# --- the backdrop and glass ----------------------------------------------------

# Soft light behind the glass: (x, y, radius, color, strength), positions as fractions of the window.
GLOWS = [(0.06, -0.02, 0.66, "#2f5bff", 0.62), (0.97, 0.12, 0.48, "#7b3cff", 0.42), (0.55, 1.1, 0.62, "#0090ff", 0.26)]

_noise = []


def noise():
    """A grain tile that breaks up banding in the dark gradients."""
    if not _noise:
        grain = np.random.default_rng(7).integers(0, 256, (128, 128), dtype=np.uint8)
        _noise.append(QPixmap.fromImage(QImage(grain.data, 128, 128, 128, QImage.Format.Format_Grayscale8).copy()))
    return _noise[0]


def paint_backdrop(p, w, h):
    base = QLinearGradient(0, 0, w, h)
    base.setColorAt(0, QColor("#0d1546"))
    base.setColorAt(0.55, QColor("#080c2a"))
    base.setColorAt(1, QColor("#04061a"))
    p.fillRect(QRectF(0, 0, w, h), base)
    span = max(w, h)
    for fx, fy, fr, hue, strength in GLOWS:
        glow = QRadialGradient(QPointF(fx * w, fy * h), fr * span)
        for stop, share in ((0, 1.0), (0.45, 0.35), (1, 0.0)):
            color = QColor(hue)
            color.setAlphaF(strength * share)
            glow.setColorAt(stop, color)
        p.fillRect(QRectF(0, 0, w, h), glow)
    p.setOpacity(0.028)
    p.drawTiledPixmap(QRectF(0, 0, w, h), noise())
    p.setOpacity(1)


class Backdrop(QWidget):
    """The window's background, painted once per size."""

    def __init__(self, parent=None):
        super().__init__(parent)
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
            paint_backdrop(p, self.width(), self.height())
            p.end()
        p = QPainter(self)
        p.drawPixmap(0, 0, self.cache)


_shadows = {}


def shadow(width, height, radius, blur, alpha):
    """A soft drop shadow for a rounded rect, as an alpha image 2 * blur bigger on every side."""
    key = (width, height, round(radius), blur, alpha)
    image = _shadows.get(key)
    if image is None:
        if len(_shadows) > 64:
            _shadows.clear()
        w, h = width + 4 * blur, height + 4 * blur
        mask = QImage(w, h, QImage.Format.Format_Alpha8)
        mask.fill(0)
        p = QPainter(mask)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 255))
        p.drawRoundedRect(QRectF(2 * blur, 2 * blur, width, height), radius, radius)
        p.end()
        pixels = np.frombuffer(mask.constBits(), np.uint8, count=mask.sizeInBytes()).reshape(h, mask.bytesPerLine())[:, :w]
        pixels = cv2.GaussianBlur(pixels, (0, 0), blur / 2)
        pixels = np.ascontiguousarray((pixels.astype(np.uint16) * alpha // 255).astype(np.uint8))
        image = _shadows[key] = QImage(pixels.data, w, h, w, QImage.Format.Format_Alpha8).copy()
    return image


class Glass(QFrame):
    """A frosted panel: navy-tinted glass, a rim lit from the top left, and a soft shadow.
    Its layout's margins leave PAD pixels around it for the shadow."""

    PAD = 8
    SHADOW_BLUR, SHADOW_DROP, SHADOW_ALPHA = 8, 3, 110
    FILLS = {"panel": ((12, 17, 50, 140), 0.085, 0.035), "rail": ((14, 19, 56, 150), 0.10, 0.04),
             "hero": ((14, 20, 60, 140), 0.10, 0.035)}

    def __init__(self, parent=None, radius=22, padding=18, kind="panel"):
        super().__init__(parent)
        self.radius, self.padding, self.kind = radius, padding, kind

    def margins(self):
        pad = self.PAD + self.padding
        return pad, pad, pad, pad

    def vbox(self, spacing=10):
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
        pad, r = self.PAD, self.radius
        body = QRectF(self.rect()).adjusted(pad, pad, -pad, -pad)
        if body.width() < 2 * r or body.height() < 2 * r:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        blur = self.SHADOW_BLUR
        p.drawImage(QPointF(body.left() - 2 * blur, body.top() - 2 * blur + self.SHADOW_DROP),
                    shadow(int(body.width()), int(body.height()), r, blur, self.SHADOW_ALPHA))

        base, top, bottom = self.FILLS[self.kind]
        path = QPainterPath()
        path.addRoundedRect(body, r, r)
        p.fillPath(path, QColor(*base))
        sheen = QLinearGradient(body.topLeft(), body.bottomLeft())
        sheen.setColorAt(0, QColor(255, 255, 255, round(255 * top)))
        sheen.setColorAt(1, QColor(255, 255, 255, round(255 * bottom)))
        p.fillPath(path, sheen)
        if self.kind == "hero":
            # The answer panel catches the accent light from the top left.
            light = QRadialGradient(body.topLeft() + QPointF(body.width() * 0.12, 0), body.width() * 0.75)
            light.setColorAt(0, QColor(77, 124, 255, 70))
            light.setColorAt(0.6, QColor(77, 124, 255, 14))
            light.setColorAt(1, QColor(77, 124, 255, 0))
            p.fillPath(path, light)

        rim = QLinearGradient(body.topLeft(), body.bottomRight())
        rim.setColorAt(0, QColor(170, 195, 255, 120) if self.kind == "hero" else QColor(255, 255, 255, 80))
        rim.setColorAt(0.45, QColor(255, 255, 255, 24))
        rim.setColorAt(1, QColor(255, 255, 255, 14))
        p.setPen(QPen(QBrush(rim), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), r - 0.5, r - 0.5)


class Columns(QWidget):
    """Panels side by side, stacked when the window is too narrow for them."""

    def __init__(self, breakpoint=700, parent=None):
        super().__init__(parent)
        self.breakpoint = breakpoint
        self.box = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(0)

    def add(self, widget):
        self.box.addWidget(widget, 1, Qt.AlignmentFlag.AlignTop)

    def resizeEvent(self, event):
        wide = self.width() >= self.breakpoint
        direction = QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom
        if self.box.direction() != direction:
            self.box.setDirection(direction)
        super().resizeEvent(event)


def cross_fade(parent, pixmap, rect, duration=260):
    """Lay a snapshot of the page being left over the new one, and fade it out."""
    ghost = QLabel(parent)
    ghost.setPixmap(pixmap)
    ghost.setGeometry(rect)
    ghost.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    effect = QGraphicsOpacityEffect(ghost)
    ghost.setGraphicsEffect(effect)
    ghost.show()
    ghost.raise_()
    fade = QPropertyAnimation(effect, b"opacity", ghost)
    fade.setDuration(duration)
    fade.setStartValue(1.0)
    fade.setEndValue(0.0)
    fade.setEasingCurve(EASE)
    fade.finished.connect(ghost.deleteLater)
    fade.finished.connect(ghost.hide)
    fade.start()
    return ghost


def rise_in(widget, end, distance=10, duration=260):
    """Fade a page in while it settles up into place. end is where it belongs."""
    old = getattr(widget, "_rise", None)
    if old is not None:
        old.stop()
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.35)
    widget.setGraphicsEffect(effect)
    widget.move(end + QPoint(0, distance))
    fade = QPropertyAnimation(effect, b"opacity", widget)
    fade.setDuration(duration)
    fade.setStartValue(0.35)
    fade.setEndValue(1.0)
    fade.setEasingCurve(EASE)
    slide = QPropertyAnimation(widget, b"pos", widget)
    slide.setDuration(duration)
    slide.setStartValue(end + QPoint(0, distance))
    slide.setEndValue(end)
    slide.setEasingCurve(EASE)
    group = QParallelAnimationGroup(widget)
    group.addAnimation(fade)
    group.addAnimation(slide)

    def done():
        widget.move(end)
        widget.setGraphicsEffect(None)
    group.finished.connect(done)
    widget._rise = group
    group.start()


# --- icons and the mark ------------------------------------------------------------

def _corners(path, inset, arm, size=24):
    a, b = inset, size - inset
    for (x, y), (dx, dy) in (((a, a), (1, 1)), ((b, a), (-1, 1)), ((b, b), (-1, -1)), ((a, b), (1, -1))):
        path.moveTo(x, y + dy * arm)
        path.lineTo(x, y)
        path.lineTo(x + dx * arm, y)


def icon_path(name):
    """Line icons on a 24-unit grid, drawn with one stroke weight."""
    path = QPainterPath()
    if name == "home":
        path.moveTo(3.5, 11)
        path.lineTo(12, 4)
        path.lineTo(20.5, 11)
        path.moveTo(5.8, 9.4)
        path.lineTo(5.8, 18.6)
        path.quadTo(5.8, 20.4, 7.6, 20.4)
        path.lineTo(16.4, 20.4)
        path.quadTo(18.2, 20.4, 18.2, 18.6)
        path.lineTo(18.2, 9.4)
        path.moveTo(10, 20.4)
        path.lineTo(10, 15.2)
        path.lineTo(14, 15.2)
        path.lineTo(14, 20.4)
    elif name == "chat":
        path.moveTo(8, 17)
        path.lineTo(7.2, 17)
        path.quadTo(3.6, 17, 3.6, 13.4)
        path.lineTo(3.6, 8)
        path.quadTo(3.6, 4.4, 7.2, 4.4)
        path.lineTo(16.8, 4.4)
        path.quadTo(20.4, 4.4, 20.4, 8)
        path.lineTo(20.4, 13.4)
        path.quadTo(20.4, 17, 16.8, 17)
        path.lineTo(12.6, 17)
        path.lineTo(8, 20.6)
        path.closeSubpath()
    elif name == "overlay":
        _corners(path, 3.6, 5)
        path.moveTo(8.5, 12)
        path.lineTo(15.5, 12)
    elif name == "sliders":
        for y, x in ((6.5, 9), (12, 15.5), (17.5, 7.5)):
            path.moveTo(3.6, y)
            path.lineTo(x - 2.4, y)
            path.addEllipse(QPointF(x, y), 2.4, 2.4)
            path.moveTo(x + 2.4, y)
            path.lineTo(20.4, y)
    elif name == "copy":
        path.addRoundedRect(QRectF(8.4, 8.4, 12, 12), 2.6, 2.6)
        path.moveTo(15.6, 8.4)
        path.lineTo(15.6, 6.2)
        path.quadTo(15.6, 3.6, 13, 3.6)
        path.lineTo(6.2, 3.6)
        path.quadTo(3.6, 3.6, 3.6, 6.2)
        path.lineTo(3.6, 13)
        path.quadTo(3.6, 15.6, 6.2, 15.6)
        path.lineTo(8.4, 15.6)
    return path


def icon_pixmap(name, size=18, color=INK, ratio=2.0):
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(ratio)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24, size / 24)
    p.setPen(QPen(QColor(color), 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(icon_path(name))
    p.end()
    return pixmap


def icon(name, size=18, color=INK, checked=None):
    """An icon, optionally in another color while its button is checked."""
    result = QIcon()
    result.addPixmap(icon_pixmap(name, size, color), QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(icon_pixmap(name, size, checked or color), QIcon.Mode.Normal, QIcon.State.On)
    result.addPixmap(icon_pixmap(name, size, "#5d6690"), QIcon.Mode.Disabled, QIcon.State.Off)
    return result


def mark(size=64, ratio=2.0):
    """MASSAB's mark: a glass tile with the reading box's viewfinder on it."""
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(ratio)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    tile = QRectF(0.5, 0.5, size - 1, size - 1)
    r = size * 0.28
    path = QPainterPath()
    path.addRoundedRect(tile, r, r)
    fill = QLinearGradient(tile.topLeft(), tile.bottomRight())
    fill.setColorAt(0, QColor("#6f97ff"))
    fill.setColorAt(1, QColor("#6a3dff"))
    p.fillPath(path, fill)
    sheen = QLinearGradient(tile.topLeft(), tile.bottomLeft())
    sheen.setColorAt(0, QColor(255, 255, 255, 80))
    sheen.setColorAt(0.5, QColor(255, 255, 255, 0))
    p.fillPath(path, sheen)
    rim = QLinearGradient(tile.topLeft(), tile.bottomRight())
    rim.setColorAt(0, QColor(255, 255, 255, 140))
    rim.setColorAt(1, QColor(255, 255, 255, 30))
    p.setPen(QPen(QBrush(rim), max(1.0, size / 48)))
    p.drawPath(path)
    glyph = QPainterPath()
    _corners(glyph, 6.6, 3.8)
    glyph.moveTo(9.4, 12)
    glyph.lineTo(14.6, 12)
    p.scale(size / 24, size / 24)
    p.setPen(QPen(QColor("white"), 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPath(glyph)
    p.end()
    return pixmap


# --- controls ------------------------------------------------------------------------

def focus_ring(p, rect, radius):
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(ACCENT_HI), 1.5))
    p.drawRoundedRect(rect, radius, radius)


class Toggle(QCheckBox):
    """An on/off switch. Behaves exactly like a QCheckBox."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._knob = 1.0 if checked else 0.0
        self.anim = QVariantAnimation(self, duration=220, easingCurve=EASE)
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
        return QSize(48, 30)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        track = QRectF(3, (self.height() - 24) / 2, 42, 24)
        r = track.height() / 2
        t = self._knob
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(QColor(255, 255, 255, 36))
        p.drawRoundedRect(track, r, r)
        if t > 0:
            on = QLinearGradient(track.topLeft(), track.bottomRight())
            on.setColorAt(0, QColor("#6a93ff"))
            on.setColorAt(1, QColor("#3a5ef0"))
            p.save()
            p.setOpacity(p.opacity() * t)
            p.setPen(QPen(QColor(255, 255, 255, 56), 1))
            p.setBrush(on)
            p.drawRoundedRect(track, r, r)
            p.restore()
        d = track.height() - 4
        knob = QRectF(track.left() + 2 + t * (track.width() - d - 4), track.top() + 2, d, d)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 20, 70))
        p.drawEllipse(knob.translated(0, 1))
        p.setBrush(QColor("white"))
        p.drawEllipse(knob)
        if self.hasFocus():
            focus_ring(p, track.adjusted(-2.5, -2.5, 2.5, 2.5), r + 2.5)


class Segmented(QWidget):
    """A row of choices with a glass pill that slides to the chosen one.
    Speaks enough of QComboBox's API to be bound like one."""

    currentIndexChanged = Signal(int)
    HEIGHT = 32

    def __init__(self, items=(), parent=None):
        super().__init__(parent)
        self.items = []
        self.index = -1
        self.hover = -1
        self._x = 0.0
        self.anim = QVariantAnimation(self, duration=240, easingCurve=EASE)
        self.anim.valueChanged.connect(self._slide)
        self.setFont(font("strong", 9.5))
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for text, data in items:
            self.addItem(text, data)

    def _slide(self, value):
        self._x = float(value)
        self.update()

    def addItem(self, text, data=None):
        self.items.append((text, data))
        if self.index < 0:
            self.index, self._x = 0, 0.0
        self.updateGeometry()

    def count(self):
        return len(self.items)

    def findData(self, value):
        return next((i for i, (_, data) in enumerate(self.items) if data == value), -1)

    def itemData(self, index):
        return self.items[index][1] if 0 <= index < len(self.items) else None

    def currentIndex(self):
        return self.index

    def currentData(self):
        return self.itemData(self.index)

    def setCurrentIndex(self, index):
        if index == self.index or not 0 <= index < len(self.items):
            return
        self.index = index
        self.anim.stop()
        if self.isVisible():
            self.anim.setStartValue(self._x)
            self.anim.setEndValue(float(index))
            self.anim.start()
        else:
            self._slide(index)
        self.currentIndexChanged.emit(index)

    def segment(self):
        return (self.width() - 6) / max(1, len(self.items))

    def sizeHint(self):
        metrics = QFontMetrics(self.font())
        widest = max((metrics.horizontalAdvance(text) for text, _ in self.items), default=40)
        return QSize(len(self.items) * (widest + 30) + 6, self.HEIGHT)

    def minimumSizeHint(self):
        return self.sizeHint()

    def at(self, x):
        i = int((x - 3) // self.segment())
        return i if 0 <= i < len(self.items) else -1

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCurrentIndex(self.at(event.position().x()))

    def mouseMoveEvent(self, event):
        hover = self.at(event.position().x())
        if hover != self.hover:
            self.hover = hover
            self.update()

    def leaveEvent(self, event):
        self.hover = -1
        self.update()

    def keyPressEvent(self, event):
        step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(event.key())
        if step:
            self.setCurrentIndex(self.index + step)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        track = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        r = track.height() / 2
        p.setPen(QPen(QColor(255, 255, 255, 24), 1))
        p.setBrush(QColor(0, 0, 0, 72))
        p.drawRoundedRect(track, r, r)
        seg = self.segment()
        pill = QRectF(3 + self._x * seg, 3, seg, self.height() - 6)
        fill = QLinearGradient(pill.topLeft(), pill.bottomRight())
        fill.setColorAt(0, QColor(106, 147, 255, 110))
        fill.setColorAt(1, QColor(58, 94, 240, 90))
        p.setPen(QPen(QColor(150, 178, 255, 110), 1))
        p.setBrush(fill)
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        for i, (text, _) in enumerate(self.items):
            box = QRectF(3 + i * seg, 0, seg, self.height())
            p.setPen(QColor(INK if i in (self.index, self.hover) else TEXT2))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        if self.hasFocus():
            focus_ring(p, track.adjusted(-1, -1, 1, 1), r + 1)


class Swatches(QWidget):
    """A few colors that show up over any game. Click one to pick it."""

    picked = Signal(str)
    COLORS = ("#3cc8ff", "#3ee39a", "#ffd23f", "#ff5fd2", "#ffffff")
    NAMES = ("Cyan", "Green", "Yellow", "Pink", "White")
    D, GAP = 20, 10

    def __init__(self, color="", parent=None):
        super().__init__(parent)
        self.color = color.lower()
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip("Color of the box and its labels")

    def set_color(self, color):
        self.color = color.lower()
        self.update()

    def sizeHint(self):
        n = len(self.COLORS)
        return QSize(n * self.D + (n - 1) * self.GAP + 8, self.D + 10)

    def index(self):
        return self.COLORS.index(self.color) if self.color in self.COLORS else -1

    def choose(self, i):
        if 0 <= i < len(self.COLORS) and self.COLORS[i] != self.color:
            self.set_color(self.COLORS[i])
            self.picked.emit(self.color)

    def mousePressEvent(self, event):
        self.choose(int((event.position().x() - 4 + self.GAP / 2) // (self.D + self.GAP)))

    def keyPressEvent(self, event):
        step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(event.key())
        if step:
            self.choose(max(0, self.index()) + step)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        for i, color in enumerate(self.COLORS):
            center = QPointF(4 + self.D / 2 + i * (self.D + self.GAP), self.height() / 2)
            p.setPen(QPen(QColor(255, 255, 255, 50), 1))
            p.setBrush(QColor(color))
            p.drawEllipse(center, self.D / 2 - 2, self.D / 2 - 2)
            if color == self.color:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(ACCENT_HI) if self.hasFocus() else QColor("white"), 2))
                p.drawEllipse(center, self.D / 2 + 2, self.D / 2 + 2)


class Light(QWidget):
    """A status light, with an optional label beside it."""

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
        return QSize(14 + text, max(16, self.fontMetrics().height()))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(LIGHTS.get(self.color, LIGHTS["gray"]))
        center = QPointF(7, self.height() / 2)
        halo = QColor(color)
        halo.setAlpha(60)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(center, 6, 6)
        p.setBrush(color)
        p.drawEllipse(center, 3.5, 3.5)
        if self.text:
            p.setPen(QColor(INK))
            p.drawText(QRectF(18, 0, self.width() - 18, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text)


class RailPill(QWidget):
    """The glass pill behind the chosen tab."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = QLinearGradient(body.topLeft(), body.bottomRight())
        fill.setColorAt(0, QColor(106, 147, 255, 80))
        fill.setColorAt(1, QColor(58, 94, 240, 50))
        rim = QLinearGradient(body.topLeft(), body.bottomRight())
        rim.setColorAt(0, QColor(170, 195, 255, 130))
        rim.setColorAt(1, QColor(120, 150, 255, 30))
        p.setPen(QPen(QBrush(rim), 1))
        p.setBrush(fill)
        p.drawRoundedRect(body, 14, 14)


class NavRail(QWidget):
    """The side tabs. A pill slides to whichever one is chosen."""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        self.pill = RailPill(self)
        self.group = QButtonGroup(self)
        for i, (name, icon_name) in enumerate(items):
            button = QPushButton(name, objectName="nav", checkable=True)
            button.setIcon(icon(icon_name, 18, TEXT2, checked="#ffffff"))
            button.setIconSize(QSize(18, 18))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            self.group.addButton(button, i)
            box.addWidget(button)
        self.group.button(0).setChecked(True)
        self.pill.lower()
        self.anim = QPropertyAnimation(self.pill, b"geometry", self)
        self.anim.setDuration(260)
        self.anim.setEasingCurve(EASE)
        self.group.buttonToggled.connect(lambda button, on: on and self.slide(button))

    def target(self, button=None):
        button = button or self.group.checkedButton()
        return button.geometry() if button else self.pill.geometry()

    def slide(self, button):
        self.anim.stop()
        if not self.isVisible():
            self.pill.setGeometry(self.target(button))
            return
        self.anim.setStartValue(self.pill.geometry())
        self.anim.setEndValue(self.target(button))
        self.anim.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.anim.state() != QPropertyAnimation.State.Running:
            self.pill.setGeometry(self.target())

    def showEvent(self, event):
        super().showEvent(event)
        self.pill.setGeometry(self.target())


class PipelineBar(QWidget):
    """Where an answer's time went: reading the screen, the AI, and pasting, as one proportional bar."""

    STAGES = (("Read", CYAN), ("AI", VIOLET), ("Paste", GREEN))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.times = None
        self.summary = ""
        self._grow = 1.0
        self.anim = QVariantAnimation(self, duration=700, easingCurve=EASE)
        self.anim.valueChanged.connect(self._set_grow)
        self.setFont(font("text", 9))
        self.setMinimumHeight(44)

    def _set_grow(self, value):
        self._grow = float(value)
        self.update()

    def set_times(self, read, ai, paste):
        self.times = (max(0.0, read), max(0.0, ai), max(0.0, paste))
        self.summary = "   ".join(f"{name} {t:.2f} s" for (name, _), t in zip(self.STAGES, self.times))
        self.setToolTip(self.summary)
        self.anim.stop()
        if self.isVisible():
            self.anim.setStartValue(0.0)
            self.anim.setEndValue(1.0)
            self.anim.start()
        else:
            self._set_grow(1.0)

    def clear(self):
        self.times, self.summary = None, ""
        self.update()

    def sizeHint(self):
        return QSize(320, 44)

    def paintEvent(self, event):
        if not self.times:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bar = QRectF(0, 6, self.width(), 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawRoundedRect(bar, 4, 4)
        shown = [(color, t) for (_, color), t in zip(self.STAGES, self.times) if t > 0]
        total = sum(t for _, t in shown) or 1.0
        gap = 3
        room = bar.width() - gap * (len(shown) - 1)
        x = bar.left()
        for color, t in shown:
            width = room * t / total * self._grow
            if width >= 1:
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(x, bar.top(), width, bar.height()), 4, 4)
            x += width + gap * self._grow

        metrics = QFontMetrics(self.font())
        x, y = 0.0, bar.bottom() + 10
        for (name, color), t in zip(self.STAGES, self.times):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(x + 4, y + metrics.height() / 2), 3.5, 3.5)
            text = f"{name}  {t:.2f} s"
            p.setPen(QColor(TEXT2))
            p.drawText(QRectF(x + 13, y, metrics.horizontalAdvance(text) + 4, metrics.height()),
                       Qt.AlignmentFlag.AlignVCenter, text)
            x += 13 + metrics.horizontalAdvance(text) + 22


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
