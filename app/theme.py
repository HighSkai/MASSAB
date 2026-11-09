"""MASSAB's look: a black instrument sheet. Flat near-black planes cut by 1px
rules, tall condensed type for names and the answer, monospace for every label
and number, and one light slab for the last answer.

Motion is springs, the way Apple describes them: a perceptual duration and a
bounce, and a spring that's retargeted mid-flight keeps its velocity. Qt has no
springs, so they're computed here. When Windows' animation effects are off,
everything snaps to its place instead.

Qt style sheets can't animate, so the switches, the segmented controls, the
rail's selection block, the timing bar and page transitions are painted or
driven here. The style sheet covers the rest.
"""
import ctypes
import math
import os
import sys
import tempfile

from PySide6.QtCore import (Property, QElapsedTimer, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QIcon, QImage, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QBoxLayout, QButtonGroup, QCheckBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

GROUND = "#0b0b0c"      # the window
PANEL = "#131314"
RAISED = "#1b1b1d"      # hover, the rail's selection, the AI's chat replies
RULE = "#232326"
RULE_STRONG = "#3a3a40"
INK = "#ededee"
TEXT2 = "#9b9ba3"
TEXT3 = "#81818a"
ICE = "#a9c8e0"         # focus and small selection details only
SLAB = "#e4ecf2"        # the last answer's slab
SLAB_INK = "#0b0b0c"
SLAB_INK2 = "#46525d"
SLAB_INK3 = "#7a8794"
MINT = "#5ee0a0"
AMBER = "#f5b041"
RED = "#ff5c5c"

LIGHTS = {"green": MINT, "amber": AMBER, "red": RED, "blue": ICE, "gray": "#55555c"}

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_FILES = ("BigShouldersDisplay.ttf", "MartianMono.ttf")


# --- fonts ---------------------------------------------------------------------

FONTS = {}


def fonts():
    """Each type role as (family, weight). The bundled faces when they load, Windows' own when they don't."""
    if not FONTS:
        for name in FONT_FILES:
            QFontDatabase.addApplicationFont(os.path.join(BASE, "fonts", name))
        have = set(QFontDatabase.families())

        def pick(*options):
            return next((option for option in options if option[0] in have), options[-1])
        FONTS.update(
            text=pick(("Segoe UI Variable Text", 400), ("Segoe UI", 400)),
            strong=pick(("Segoe UI Variable Text Semibold", 400), ("Segoe UI", 600)),
            display=pick(("Big Shoulders Display", 900), ("Segoe UI", 700)),
            title=pick(("Big Shoulders Display", 800), ("Segoe UI", 700)),
            mono=pick(("Martian Mono", 400), ("Cascadia Mono", 400), ("Consolas", 400)),
            mono_strong=pick(("Martian Mono", 500), ("Cascadia Mono", 600), ("Consolas", 700)))
    return FONTS


def font(role="text", pt=10.0, caps=False):
    family, weight = fonts()[role]
    f = QFont(family)
    f.setPointSizeF(pt)
    f.setWeight(QFont.Weight(weight))
    if caps:
        f.setCapitalization(QFont.Capitalization.AllUppercase)
    return f


def css_font(role):
    family, weight = fonts()[role]
    return f'font-family: "{family}"; font-weight: {weight};'


def caps(widget):
    """Draw a widget's text in capitals without changing the text itself. Style sheets keep this."""
    f = widget.font()
    f.setCapitalization(QFont.Capitalization.AllUppercase)
    widget.setFont(f)
    return widget


# --- the style sheet -------------------------------------------------------------

STYLE = """
* { %(text)s font-size: 10pt; color: %(ink)s; }
QWidget#page, QWidget#scrollInner, QStackedWidget, QScrollArea { background: transparent; border: none; }
QLabel { background: transparent; }
QLabel#brand { %(display)s font-size: 23pt; }
QLabel#pageTitle { %(title)s font-size: 28pt; }
QLabel#panelTitle { %(mono_strong)s font-size: 8.5pt; color: %(text2)s; }
QLabel#emptyTitle { %(title)s font-size: 22pt; }
QLabel#secondary { color: %(text2)s; }
QLabel#hint { color: %(text3)s; font-size: 9pt; }
QLabel#mono { %(mono)s font-size: 8pt; color: %(text2)s; }
QLabel#statusText { %(mono_strong)s font-size: 8.5pt; color: %(text2)s; }
QLabel#statusText[live="true"] { color: %(ink)s; }
QFrame#sep, QFrame#rule { background: %(rule)s; max-height: 1px; min-height: 1px; border: none; }

QFrame#panel { background: %(panel)s; border: 1px solid %(rule)s; border-radius: 2px; }
QFrame#slab { background: %(slab)s; border: none; border-radius: 2px; }
QFrame#slab QLabel { color: %(slab_ink)s; }
QFrame#slab QLabel#secondary { color: %(slab_ink2)s; }
QLabel#answer { %(display)s font-size: 44pt; }
QLabel#answer[empty="true"] { color: %(slab_ink3)s; }
QLabel#total { %(title)s font-size: 24pt; }
QLabel#chip { %(mono_strong)s font-size: 8pt; color: %(ink)s; padding: 0 8px; min-height: 20px; max-height: 20px;
    border: 1px solid %(rule_strong)s; border-radius: 2px; }
QFrame#slab QLabel#chip { color: %(slab_ink)s; border-color: %(slab_ink)s; }
QFrame#slab QLabel#chip[tone="good"] { color: %(slab)s; background: %(slab_ink)s; }
QLabel#warning { %(mono_strong)s font-size: 8pt; color: #1a1205; padding: 0 8px; min-height: 20px; max-height: 20px;
    border-radius: 2px; background: %(amber)s; }
QFrame#slab QLabel#warning { color: #1a1205; }

QPushButton { %(mono_strong)s font-size: 8.5pt; color: %(ink)s; padding: 8px 14px; border: 1px solid %(rule_strong)s;
    border-radius: 2px; background: transparent; }
QPushButton:hover { border-color: #55555c; background: %(raised)s; }
QPushButton:pressed { background: #0f0f10; }
QPushButton:focus { border-color: %(ice)s; }
QPushButton:disabled { color: #55555c; border-color: %(rule)s; background: transparent; }
QPushButton#primary, QPushButton#go { color: %(ground)s; border: 1px solid %(ink)s; background: %(ink)s; }
QPushButton#primary:hover, QPushButton#go:hover { border-color: white; background: white; }
QPushButton#primary:pressed, QPushButton#go:pressed { border-color: #c9c9cd; background: #c9c9cd; }
QPushButton#primary:focus, QPushButton#go:focus { border-color: %(ice)s; }
QPushButton#primary:disabled, QPushButton#go:disabled { color: #6b6b72; border-color: %(rule)s; background: %(rule)s; }
QPushButton#go { padding: 0 22px; min-width: 72px; }
QPushButton#go[running="true"] { color: %(red)s; border: 1px solid %(red)s; background: transparent; }
QPushButton#go[running="true"]:hover { background: rgba(255, 92, 92, 28); }
QPushButton#small { font-size: 8pt; padding: 5px 10px; }
QFrame#slab QPushButton { color: %(slab_ink)s; border: 1px solid %(slab_ink)s; background: transparent; }
QFrame#slab QPushButton:hover { color: %(slab)s; background: %(slab_ink)s; }
QFrame#slab QPushButton:disabled { color: #9aa7b2; border-color: #b9c5cf; background: transparent; }
QPushButton#suggestion { %(text)s font-size: 9.5pt; color: %(text2)s; padding: 9px 14px; text-align: left; }
QPushButton#suggestion:hover { color: %(ink)s; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { %(mono)s font-size: 8.5pt; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit#chatInput {
    color: %(ink)s; border: 1px solid %(rule_strong)s; border-radius: 2px; padding: 7px 10px; background: #0e0e0f;
    selection-background-color: %(ink)s; selection-color: %(ground)s; }
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QPlainTextEdit#chatInput:hover {
    border-color: #55555c; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit#chatInput:focus {
    border-color: %(ice)s; }
QLineEdit[invalid="true"] { border-color: %(red)s; background: rgba(255, 92, 92, 20); }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    color: #55555c; border-color: %(rule)s; background: transparent; }
QComboBox { padding-right: 30px; min-width: 120px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 28px; border: none; }
QComboBox::down-arrow { image: url(%(down)s); width: 10px; height: 6px; }
QComboBox::down-arrow:disabled, QAbstractSpinBox::down-arrow:disabled { image: url(%(down_dim)s); }
QComboBox QAbstractItemView { %(mono)s font-size: 8.5pt; color: %(ink)s; background: #151516;
    border: 1px solid %(rule_strong)s; outline: none; padding: 2px; selection-background-color: %(ink)s;
    selection-color: %(ground)s; }
QSpinBox, QDoubleSpinBox { padding-right: 28px; min-width: 84px; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { subcontrol-origin: border; width: 24px; border: none;
    background: transparent; }
QAbstractSpinBox::up-button { subcontrol-position: top right; }
QAbstractSpinBox::down-button { subcontrol-position: bottom right; }
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover { background: %(raised)s; }
QAbstractSpinBox::up-arrow { image: url(%(up)s); width: 8px; height: 5px; }
QAbstractSpinBox::down-arrow { image: url(%(down)s); width: 8px; height: 5px; }
QAbstractSpinBox::up-arrow:disabled { image: url(%(up_dim)s); }
QPlainTextEdit#chatInput { %(text)s font-size: 10pt; padding: 10px 12px; }
QPlainTextEdit#log { %(mono)s font-size: 8.5pt; color: #c9c9ce; border: none; padding: 0; background: transparent;
    selection-background-color: %(ink)s; selection-color: %(ground)s; }

QSlider { min-height: 20px; }
QSlider::groove:horizontal { height: 2px; background: %(rule_strong)s; }
QSlider::sub-page:horizontal { height: 2px; background: %(ink)s; }
QSlider::handle:horizontal { width: 12px; height: 12px; margin: -5px 0; border-radius: 1px; background: %(ink)s; }
QSlider::handle:horizontal:hover { background: white; }
QSlider::sub-page:horizontal:disabled, QSlider::handle:horizontal:disabled { background: #55555c; }

QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #2c2c30; border-radius: 1px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #45454b; }
QScrollBar[idle="true"]::handle:vertical { background: transparent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

QProgressBar { border: none; border-radius: 0; max-height: 3px; min-height: 3px; background: %(rule)s; }
QProgressBar::chunk { background: %(ink)s; }
QProgressBar[low="true"]::chunk { background: %(red)s; }

QFrame#bubbleUser { border: none; border-radius: 2px; background: %(ink)s; }
QFrame#bubbleUser QLabel { color: %(ground)s; }
QFrame#bubbleAi { border: 1px solid %(rule)s; border-radius: 2px; background: %(raised)s; }
QFrame#bubbleError { border: 1px solid %(red)s; border-radius: 2px; background: rgba(255, 92, 92, 20); }
QFrame#bubbleError QLabel { color: #ffb4ac; }

QMenu { background: #151516; border: 1px solid %(rule_strong)s; padding: 3px; }
QMenu::item { padding: 6px 18px; }
QMenu::item:selected { color: %(ground)s; background: %(ink)s; }
QMenu::item:disabled { color: %(text3)s; }
QMenu::separator { height: 1px; background: %(rule)s; margin: 3px 6px; }
QToolTip { color: %(ink)s; background: #151516; border: 1px solid %(rule_strong)s; padding: 6px 8px; }

QLabel#hudKind { %(mono_strong)s color: %(ground)s; padding: 0 7px; border-radius: 1px; background: %(ink)s; }
QLabel#hudAnswer { %(display)s color: white; }
QLabel#hudSeconds { %(mono)s color: rgba(205, 205, 212, 210); }
QLabel#hudState { %(mono_strong)s color: %(mint)s; }
QLabel#hudState[plain="true"] { color: %(ink)s; }
QLabel#hudFlag { %(mono_strong)s color: %(amber)s; }
"""


def arrow_image(path, up=False, color=TEXT2):
    """A small chevron for drop-downs and spin boxes."""
    image = QImage(20, 12, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
    p.drawPolyline([QPointF(3, 9), QPointF(10, 3), QPointF(17, 9)] if up else
                   [QPointF(3, 3), QPointF(10, 9), QPointF(17, 3)])
    p.end()
    image.save(path)


def style_sheet():
    """The app's style sheet. Its chevrons are drawn into the temp folder."""
    folder = os.path.join(tempfile.gettempdir(), "massab-theme-3")
    os.makedirs(folder, exist_ok=True)
    paths = {}
    for name, up, color in (("down", False, TEXT2), ("up", True, TEXT2), ("down_dim", False, "#45454b"),
                            ("up_dim", True, "#45454b")):
        paths[name] = os.path.join(folder, f"arrow-{name}.png").replace("\\", "/")
        if not os.path.exists(paths[name]):
            arrow_image(paths[name], up, color)
    return STYLE % {"ground": GROUND, "panel": PANEL, "raised": RAISED, "rule": RULE, "rule_strong": RULE_STRONG,
                    "ink": INK, "text2": TEXT2, "text3": TEXT3, "ice": ICE, "slab": SLAB, "slab_ink": SLAB_INK,
                    "slab_ink2": SLAB_INK2, "slab_ink3": SLAB_INK3, "mint": MINT, "amber": AMBER, "red": RED,
                    **{role: css_font(role) for role in fonts()}, **paths}


def apply(app):
    """Dark palette, Fusion and the style sheet, so even the parts not styled here match."""
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, GROUND), (QPalette.ColorRole.WindowText, INK),
                        (QPalette.ColorRole.Base, "#0e0e0f"), (QPalette.ColorRole.AlternateBase, PANEL),
                        (QPalette.ColorRole.Text, INK), (QPalette.ColorRole.Button, PANEL),
                        (QPalette.ColorRole.ButtonText, INK), (QPalette.ColorRole.Highlight, INK),
                        (QPalette.ColorRole.HighlightedText, GROUND), (QPalette.ColorRole.ToolTipBase, "#151516"),
                        (QPalette.ColorRole.ToolTipText, INK), (QPalette.ColorRole.PlaceholderText, TEXT3),
                        (QPalette.ColorRole.Link, ICE), (QPalette.ColorRole.BrightText, "#ffffff")):
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#55555c"))
    app.setPalette(palette)
    app.setFont(font("text", 10))
    app.setStyleSheet(style_sheet())


def dark_title_bar(window):
    """Windows draws the title bar. Ask it for one in the window's own black."""
    if sys.platform != "win32":
        return
    try:
        dwm = ctypes.windll.dwmapi
        hwnd = ctypes.c_void_p(int(window.winId()))
        for attribute, value in ((20, 1), (35, colorref(GROUND)), (34, colorref(RULE)), (36, colorref(INK))):
            value = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):
        pass


def colorref(hex_color):
    color = QColor(hex_color)
    return color.red() | color.green() << 8 | color.blue() << 16


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def icon_pixmap(size):
    """The logo: the title's first letter, set like the title. app/massab.ico is this too."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(GROUND))
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    f = font("display")
    f.setPixelSize(round(size * 0.86))
    p.setFont(f)
    p.setPen(QColor(INK))
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "M")
    p.end()
    return pixmap


def window_icon():
    """The logo drawn at each size Windows asks for, so the taskbar and Alt+Tab stay sharp."""
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(icon_pixmap(size))
    return icon


def use_own_taskbar_icon(app_id="MASSAB.App"):
    """Run under MASSAB's own taskbar identity. Without one, Windows groups the
    window with pythonw.exe and shows Python's icon instead of the M. Call it
    before any window is made."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except (AttributeError, OSError):
            pass


# --- springs -------------------------------------------------------------------------

MOTION = {"mode": "on"}     # "on", "off", or "windows" to follow Windows' Animation effects


def set_motion(mode):
    MOTION["mode"] = mode


def windows_animates():
    """Whether Windows' "Animation effects" setting is on."""
    if sys.platform == "win32":
        try:
            value = ctypes.c_int(1)
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0):
                return bool(value.value)
        except (AttributeError, OSError):
            pass
    return True


def motion_enabled():
    """False when motion is turned off, so every spring snaps to its end instead."""
    mode = MOTION["mode"]
    return mode == "on" or (mode == "windows" and windows_animates())


def spring_state(x0, v0, duration, bounce, t):
    """Offset from the target and velocity, t seconds after starting at offset x0 with velocity v0.
    Apple's model: stiffness (2 pi / duration)^2, mass 1, damping ratio 1 - bounce."""
    w0 = 2 * math.pi / duration
    zeta = 1 - max(0.0, min(bounce, 0.95))
    if zeta >= 1:
        decay = math.exp(-w0 * t)
        return (x0 + (v0 + w0 * x0) * t) * decay, (v0 - w0 * (v0 + w0 * x0) * t) * decay
    wd = w0 * math.sqrt(1 - zeta * zeta)
    decay = math.exp(-zeta * w0 * t)
    c, s = math.cos(wd * t), math.sin(wd * t)
    x = decay * (x0 * c + (v0 + zeta * w0 * x0) / wd * s)
    v = decay * (v0 * c - (x0 * w0 * w0 + zeta * w0 * v0) / wd * s)
    return x, v


class Spring(QObject):
    """Moves a few numbers toward targets on a spring. Retargeting mid-flight starts
    from where they are, at the speed they're going, so motion never jumps."""

    finished = Signal()

    def __init__(self, apply, duration=0.4, bounce=0.0, epsilon=0.5, parent=None):
        super().__init__(parent)
        self.apply, self.duration, self.bounce, self.epsilon = apply, duration, bounce, epsilon
        self.values = self.velocity = self.target = self.origin = self.v0 = None
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(8)
        self.timer.timeout.connect(self.step)

    def running(self):
        return self.timer.isActive()

    def jump(self, values):
        self.timer.stop()
        self.values, self.target = list(values), list(values)
        self.velocity = [0.0] * len(self.values)
        self.apply(self.values)

    def to(self, target, kick=None):
        """Head for target. kick adds launch velocity, like the flick that ends a gesture."""
        target = list(target)
        if self.values is None or not motion_enabled():
            self.jump(target)
            self.finished.emit()
            return
        self.target = target
        self.origin = [value - goal for value, goal in zip(self.values, target)]
        self.v0 = [v + k for v, k in zip(self.velocity, kick)] if kick else list(self.velocity)
        self.clock.start()
        if not self.timer.isActive():
            self.timer.start()

    def step(self):
        t = self.clock.nsecsElapsed() / 1e9
        values, velocity = [], []
        for x0, v0, goal in zip(self.origin, self.v0, self.target):
            x, v = spring_state(x0, v0, self.duration, self.bounce, t)
            values.append(goal + x)
            velocity.append(v)
        settled = all(abs(value - goal) <= self.epsilon and abs(v) <= self.epsilon * 12
                      for value, goal, v in zip(values, self.target, velocity))
        if settled or t > 4 * self.duration + 1:
            self.timer.stop()
            self.values, self.velocity = list(self.target), [0.0] * len(self.target)
            self.apply(self.values)
            self.finished.emit()
            return
        self.values, self.velocity = values, velocity
        self.apply(values)


# Duration and bounce. Apple calls about 0.15 a small bounce and 0.3 a noticeable one, and
# past about 0.4 too much. These sit near the top of that range, and the rail and pages
# launch with velocity like a flick, so the hop overshoots enough to see (about 5px).
SMOOTH = (0.35, 0.0)
RAIL = (0.42, 0.35)
HOP = (0.5, 0.35)
HOP_DISTANCE, HOP_KICK = 36.0, 450.0     # px, px/s
RAIL_KICK = (12.0, 600.0)                # px/s per px of travel, and the most it gets


# --- panels and pages --------------------------------------------------------------

class Backdrop(QWidget):
    """The window's ground."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(GROUND))


class Sheet(QFrame):
    """A flat panel with a 1px rule, or the light slab the last answer sits on."""

    PAD = 0

    def __init__(self, parent=None, padding=18, kind="panel"):
        super().__init__(parent, objectName=kind)
        self.padding = padding

    def margins(self):
        return (self.padding,) * 4

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


class Rail(QFrame):
    """The left column: the window's own black, with a rule down its right edge."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(GROUND))
        p.fillRect(QRect(self.width() - 1, 0, 1, self.height()), QColor(RULE))


class Columns(QWidget):
    """Panels side by side, stacked when the window is too narrow for them."""

    def __init__(self, breakpoint=720, spacing=12, parent=None):
        super().__init__(parent)
        self.breakpoint = breakpoint
        self.box = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(spacing)

    def add(self, widget):
        self.box.addWidget(widget, 1, Qt.AlignmentFlag.AlignTop)

    def resizeEvent(self, event):
        wide = self.width() >= self.breakpoint
        direction = QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom
        if self.box.direction() != direction:
            self.box.setDirection(direction)
        super().resizeEvent(event)


def hop(parent, snapshot, rect, page, end, direction):
    """Switch pages the way iOS does: the old page fades away quickly while the new one
    hops in from the side it lives on. direction is +1 for a later tab, -1 for an earlier one."""
    if not motion_enabled():
        return
    ghost = QLabel(parent)
    ghost.setPixmap(snapshot)
    ghost.setGeometry(rect)
    ghost.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    fade = QGraphicsOpacityEffect(ghost)
    ghost.setGraphicsEffect(fade)
    ghost.show()
    ghost.raise_()

    def leave(values):
        fade.setOpacity(max(0.0, min(1.0, values[0])))
        ghost.move(rect.topLeft() + QPoint(0, round(values[1])))
    out = Spring(leave, 0.22, 0.0, epsilon=0.01, parent=ghost)
    out.jump([1.0, 0.0])
    out.finished.connect(ghost.deleteLater)
    out.to([0.0, -10.0 * direction])

    old = getattr(page, "_hop", None)
    if old is not None:
        for spring in old:
            spring.timer.stop()
    effect = QGraphicsOpacityEffect(page)
    page.setGraphicsEffect(effect)

    def settle(values):
        page.move(end + QPoint(0, round(values[0])))

    def show(values):
        if page.graphicsEffect() is effect:
            effect.setOpacity(max(0.0, min(1.0, values[0])))
    rise = Spring(settle, *HOP, epsilon=0.3, parent=page)
    rise.jump([HOP_DISTANCE * direction])
    rise.to([0.0], kick=[-HOP_KICK * direction])
    appear = Spring(show, 0.3, 0.0, epsilon=0.01, parent=page)
    appear.jump([0.0])
    appear.to([1.0])
    appear.finished.connect(lambda: page.graphicsEffect() is effect and page.setGraphicsEffect(None))
    page._hop = (rise, appear)


# --- controls ------------------------------------------------------------------------

def focus_ring(p, rect):
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(ICE), 1))
    p.drawRect(rect)


class Toggle(QCheckBox):
    """A square on/off switch. Behaves exactly like a QCheckBox."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._knob = 1.0 if checked else 0.0
        self.spring = Spring(lambda values: self._move(values[0]), 0.34, 0.32, epsilon=0.003, parent=self)
        self.spring.jump([self._knob])
        self.toggled.connect(self._animate)

    def _get_knob(self):
        return self._knob

    def _move(self, value):
        self._knob = float(value)
        self.update()

    knob = Property(float, _get_knob, _move)

    def _animate(self, checked):
        if self.isVisible():
            self.spring.to([1.0 if checked else 0.0])
        else:
            self.spring.jump([1.0 if checked else 0.0])

    def sizeHint(self):
        return QSize(44, 26)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        if not self.isEnabled():
            p.setOpacity(0.4)
        track = QRectF(2.5, (self.height() - 20) / 2 + 0.5, 38, 19)
        t = self._knob
        on = max(0.0, min(1.0, t))
        p.setPen(QPen(QColor(RULE_STRONG if on < 0.5 else INK), 1))
        fill = QColor(INK)
        fill.setAlphaF(on)
        p.setBrush(QColor(PANEL))
        p.drawRect(track)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawRect(track.adjusted(0.5, 0.5, 0, 0))
        travel = track.width() - 17
        knob = QRectF(track.left() + 3 + t * travel, track.top() + 3, 13, 13)
        p.setBrush(QColor(GROUND) if on >= 0.5 else QColor(TEXT2))
        p.drawRect(knob)
        if self.hasFocus():
            focus_ring(p, track.adjusted(-2, -2, 2, 2))


class Segmented(QWidget):
    """A row of choices in square cells, with a white block that springs to the chosen one.
    Speaks enough of QComboBox's API to be bound like one."""

    currentIndexChanged = Signal(int)
    HEIGHT = 30

    def __init__(self, items=(), parent=None):
        super().__init__(parent)
        self.items = []
        self.index = -1
        self.hover = -1
        self._x = 0.0
        self.spring = Spring(lambda values: self._slide(values[0]), 0.36, 0.3, epsilon=0.003, parent=self)
        self.face = font("mono_strong", 8, caps=True)
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
            self.index = 0
            self.spring.jump([0.0])
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
        if self.isVisible():
            self.spring.to([float(index)])
        else:
            self.spring.jump([float(index)])
        self.currentIndexChanged.emit(index)

    def segment(self):
        return (self.width() - 2) / max(1, len(self.items))

    def sizeHint(self):
        metrics = QFontMetrics(self.face)
        widest = max((metrics.horizontalAdvance(text.upper()) for text, _ in self.items), default=40)
        return QSize(len(self.items) * (widest + 26) + 2, self.HEIGHT)

    def minimumSizeHint(self):
        return self.sizeHint()

    def at(self, x):
        i = int((x - 1) // self.segment())
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
        if not self.isEnabled():
            p.setOpacity(0.4)
        track = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(RULE_STRONG), 1))
        p.setBrush(QColor("#0e0e0f"))
        p.drawRect(track)
        p.setFont(self.face)
        seg = self.segment()
        p.setPen(QPen(QColor(RULE), 1))
        for i in range(1, len(self.items)):
            x = round(1 + i * seg) + 0.5
            p.drawLine(QPointF(x, 4), QPointF(x, self.height() - 4))
        block = QRectF(1 + self._x * seg, 1, seg, self.height() - 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawRect(block)
        for i, (text, _) in enumerate(self.items):
            box = QRectF(1 + i * seg, 0, seg, self.height())
            p.setClipRect(box)
            p.setPen(QColor(INK if i == self.hover else TEXT2))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
            # Where the white block covers this cell, its text is black.
            p.setClipRect(box.intersected(block))
            p.setPen(QColor(GROUND))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
            p.setClipping(False)
        if self.hasFocus():
            focus_ring(p, track.adjusted(-1.5, -1.5, 1.5, 1.5))


class Swatches(QWidget):
    """A few colors that show up over any game. Click one to pick it."""

    picked = Signal(str)
    COLORS = ("#3cc8ff", "#3ee39a", "#ffd23f", "#ff5fd2", "#ffffff")
    SIZE, GAP = 18, 8

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
        return QSize(n * self.SIZE + (n - 1) * self.GAP + 8, self.SIZE + 10)

    def index(self):
        return self.COLORS.index(self.color) if self.color in self.COLORS else -1

    def choose(self, i):
        if 0 <= i < len(self.COLORS) and self.COLORS[i] != self.color:
            self.set_color(self.COLORS[i])
            self.picked.emit(self.color)

    def mousePressEvent(self, event):
        self.choose(int((event.position().x() - 4 + self.GAP / 2) // (self.SIZE + self.GAP)))

    def keyPressEvent(self, event):
        step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(event.key())
        if step:
            self.choose(max(0, self.index()) + step)
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        if not self.isEnabled():
            p.setOpacity(0.4)
        top = (self.height() - self.SIZE) / 2
        for i, color in enumerate(self.COLORS):
            cell = QRectF(4 + i * (self.SIZE + self.GAP), top, self.SIZE, self.SIZE)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawRect(cell.adjusted(2, 2, -2, -2) if color != self.color else cell)
            if color == self.color:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(ICE if self.hasFocus() else INK), 1))
                p.drawRect(cell.adjusted(-3.5, -3.5, 3.5, 3.5))


class Light(QWidget):
    """A square status light, with an optional label beside it."""

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
        return QSize(12 + text, max(14, self.fontMetrics().height()))

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(QRectF(2, self.height() / 2 - 3.5, 7, 7), QColor(LIGHTS.get(self.color, LIGHTS["gray"])))
        if self.text:
            p.setPen(QColor(INK))
            p.drawText(QRectF(16, 0, self.width() - 16, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text)


class NavButton(QPushButton):
    """A tab in the rail: its name, and the number of its Ctrl shortcut."""

    def __init__(self, name, number, parent=None):
        super().__init__(name, parent)
        self.number = str(number)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(38)
        self.setToolTip(f"Ctrl+{number}")
        self.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0; }")

    def paintEvent(self, event):
        p = QPainter(self)
        lit = self.isChecked() or self.underMouse()
        p.setFont(font("mono_strong", 9, caps=True))
        p.setPen(QColor(INK if lit else TEXT2))
        box = QRectF(self.rect()).adjusted(14, 0, -14, 0)
        p.drawText(box, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        p.setFont(font("mono", 8))
        p.setPen(QColor(TEXT2 if self.isChecked() else TEXT3))
        p.drawText(box, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, self.number)
        if self.hasFocus():
            focus_ring(p, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))


class RailBlock(QWidget):
    """The raised block behind the chosen tab, with a short ink bar on its left edge."""

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(RAISED))
        p.fillRect(QRect(0, 0, 1, self.height()), QColor(INK))


class NavRail(QWidget):
    """The tabs. A block springs to whichever one is chosen."""

    def __init__(self, names, parent=None):
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        self.block = RailBlock(self)
        self.group = QButtonGroup(self)
        for i, name in enumerate(names):
            button = NavButton(name, i + 1)
            self.group.addButton(button, i)
            box.addWidget(button)
        self.group.button(0).setChecked(True)
        self.block.lower()
        self.spring = Spring(self._place, *RAIL, epsilon=0.3, parent=self)
        self.group.buttonToggled.connect(lambda button, on: on and self.slide(button))

    def _place(self, values):
        self.block.setGeometry(0, round(values[0]), self.width(), round(values[1]))

    def target(self, button=None):
        button = button or self.group.checkedButton()
        g = button.geometry()
        return [float(g.y()), float(g.height())]

    def slide(self, button):
        target = self.target(button)
        if self.isVisible() and self.spring.values is not None:
            # Launch toward the new tab, faster the farther it is, so the block lands with a hop.
            travel = target[0] - self.spring.values[0]
            per_px, most = RAIL_KICK
            self.spring.to(target, kick=[math.copysign(min(abs(travel) * per_px, most), travel), 0.0])
        else:
            self.spring.jump(target)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.spring.running():
            self.spring.jump(self.target())

    def showEvent(self, event):
        super().showEvent(event)
        self.spring.jump(self.target())


class PipelineBar(QWidget):
    """Where an answer's time went: reading the screen, the AI, and pasting, as one
    proportional bar. Drawn for the light answer slab."""

    STAGES = (("Read", "#8a99a6"), ("AI", "#3f6482"), ("Paste", SLAB_INK))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.times = None
        self.summary = ""
        self._grow = 1.0
        self.spring = Spring(lambda values: self._set_grow(values[0]), 0.6, 0.0, epsilon=0.002, parent=self)
        self.spring.jump([1.0])
        self.face = font("mono", 8)
        self.setMinimumHeight(40)

    def _set_grow(self, value):
        self._grow = max(0.0, value)
        self.update()

    def set_times(self, read, ai, paste):
        self.times = (max(0.0, read), max(0.0, ai), max(0.0, paste))
        self.summary = "   ".join(f"{name} {t:.2f} s" for (name, _), t in zip(self.STAGES, self.times))
        self.setToolTip(self.summary)
        if self.isVisible():
            self.spring.jump([0.0])
            self.spring.to([1.0])
        else:
            self.spring.jump([1.0])

    def clear(self):
        self.times, self.summary = None, ""
        self.update()

    def sizeHint(self):
        return QSize(320, 40)

    def paintEvent(self, event):
        if not self.times:
            return
        p = QPainter(self)
        bar = QRectF(0, 4, self.width(), 6)
        p.fillRect(bar, QColor("#cdd7df"))
        shown = [(color, t) for (_, color), t in zip(self.STAGES, self.times) if t > 0]
        total = sum(t for _, t in shown) or 1.0
        gap = 2
        room = bar.width() - gap * (len(shown) - 1)
        x = bar.left()
        for color, t in shown:
            width = room * t / total * self._grow
            if width >= 1:
                p.fillRect(QRectF(x, bar.top(), width, bar.height()), QColor(color))
            x += width + gap * self._grow

        p.setFont(self.face)
        metrics = QFontMetrics(self.face)
        x, y = 0.0, bar.bottom() + 10
        for (name, color), t in zip(self.STAGES, self.times):
            p.fillRect(QRectF(x, y + metrics.height() / 2 - 3, 6, 6), QColor(color))
            text = f"{name.upper()} {t:.2f} s"
            p.setPen(QColor(SLAB_INK2))
            p.drawText(QRectF(x + 12, y, metrics.horizontalAdvance(text) + 4, metrics.height()),
                       Qt.AlignmentFlag.AlignVCenter, text)
            x += 12 + metrics.horizontalAdvance(text) + 20


def separator():
    line = QFrame(objectName="sep")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line


def label(text, name=None, wrap=False, upper=False):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    if upper:
        caps(widget)
    return widget
