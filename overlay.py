"""Windows that draw on the screen: the area MASSAB reads, the text it's reading
right now, and a picker for choosing that area by dragging over it.

Screen capture works in physical pixels and Qt in scaled ones. Qt keeps each
screen's top-left corner the same in both, so a point converts by its offset
from that corner and the screen's scale.
"""
import ctypes

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from codereader import ROI
from riddle import BAND
from theme import INK, TEXT3, font

ZONES = (("code lines", ROI, Qt.PenStyle.DashLine), ("riddle rows", BAND, Qt.PenStyle.DotLine))


def monitor_rects():
    """Each monitor as (x, y, w, h) in physical pixels, numbered like screen capture: [0] is all of them."""
    import mss
    with mss.MSS() as sct:
        return [(m["left"], m["top"], m["width"], m["height"]) for m in sct.monitors]


def capture_area(monitor, region, monitors):
    """What gets captured, as (x, y, w, h) in physical pixels, or None if that monitor doesn't exist."""
    if region:
        return tuple(region)
    return tuple(monitors[monitor]) if 0 < monitor < len(monitors) else None


def to_logical(rect, origin, ratio):
    x, y, w, h = rect
    ox, oy = origin
    return ox + (x - ox) / ratio, oy + (y - oy) / ratio, w / ratio, h / ratio


def to_native(rect, origin, ratio):
    x, y, w, h = rect
    ox, oy = origin
    return round(ox + (x - ox) * ratio), round(oy + (y - oy) * ratio), round(w * ratio), round(h * ratio)


def native_rect(screen):
    g = screen.geometry()
    ratio = screen.devicePixelRatio()
    return g.x(), g.y(), round(g.width() * ratio), round(g.height() * ratio)


def screen_for(rect):
    """The screen holding the middle of a physical-pixel rect, or the primary one."""
    x, y, w, h = rect
    cx, cy = x + w / 2, y + h / 2
    for screen in QGuiApplication.screens():
        sx, sy, sw, sh = native_rect(screen)
        if sx <= cx < sx + sw and sy <= cy < sy + sh:
            return screen
    return QGuiApplication.primaryScreen()


def logical_rect(rect):
    screen = screen_for(rect)
    origin = (screen.geometry().x(), screen.geometry().y())
    return QRectF(*to_logical(rect, origin, screen.devicePixelRatio())).toAlignedRect()


def keep_out_of_capture(widget):
    """Click-through, never focused, and invisible to screen capture, so MASSAB can't read its own drawing."""
    gwl_exstyle, noactivate, transparent, toolwindow, layered = -20, 0x08000000, 0x20, 0x80, 0x80000
    exclude_from_capture = 0x11
    user32 = ctypes.windll.user32
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    hwnd = int(widget.winId())
    style = user32.GetWindowLongPtrW(hwnd, gwl_exstyle)
    user32.SetWindowLongPtrW(hwnd, gwl_exstyle, style | noactivate | transparent | toolwindow | layered)
    user32.SetWindowDisplayAffinity(hwnd, exclude_from_capture)


PASSIVE_FLAGS = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.WindowTransparentForInput)


def tag(p, point, text, color, scale):
    """A small rounded label with its top-left at point, drawn in frame pixels
    (scale = frame pixels per screen pixel)."""
    face = font("strong")
    face.setPixelSize(max(8, round(12 * scale)))
    p.setFont(face)
    metrics = p.fontMetrics()
    pad = 6 * scale
    w, h = metrics.horizontalAdvance(text) + 2 * pad, metrics.height() + pad
    box = QRectF(point.x(), point.y(), w, h)
    rim = QColor(color)
    rim.setAlpha(200)
    p.setPen(QPen(rim, max(1.0, scale)))
    p.setBrush(QColor(10, 14, 40, 225))
    p.drawRoundedRect(box, h / 2, h / 2)
    p.setPen(QColor("white"))
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


class AreaOverlay(QWidget):
    """Draws the reading area and what's being read over the screen. Can't be clicked or captured."""

    def __init__(self):
        super().__init__(None, PASSIVE_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.area = None        # physical pixels, (x, y, w, h)
        self.reads = []
        self.color, self.line_width, self.opacity = QColor("#3cc8ff"), 2, 0.9
        self.zones, self.labels = True, True

    def showEvent(self, event):
        super().showEvent(event)
        keep_out_of_capture(self)

    def set_area(self, area):
        self.area = area
        if area:
            self.setGeometry(logical_rect(area))
        self.update()

    def set_look(self, color, width, opacity, zones, labels):
        self.color, self.line_width, self.opacity = QColor(color), width, opacity / 100
        self.zones, self.labels = zones, labels
        self.update()

    def set_reads(self, boxes):
        if boxes or self.reads:
            self.reads = boxes
            self.update()

    def paintEvent(self, event):
        if not self.area:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self.opacity)
        aw, ah = self.area[2], self.area[3]
        p.scale(self.width() / aw, self.height() / ah)
        scale = aw / max(1, self.width())     # frame pixels per screen pixel
        line = self.line_width * scale

        # The capture area: a faint outline with bright corners, like a viewfinder.
        edge = QRectF(line / 2, line / 2, aw - line, ah - line)
        faint = QColor(self.color)
        faint.setAlpha(110)
        p.setPen(QPen(faint, line))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(edge)
        p.setPen(QPen(self.color, line * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        arm = min(aw, ah) * 0.06
        for corner, dx, dy in ((edge.topLeft(), 1, 1), (edge.topRight(), -1, 1),
                               (edge.bottomLeft(), 1, -1), (edge.bottomRight(), -1, -1)):
            p.drawLine(corner, corner + QPointF(dx * arm, 0))
            p.drawLine(corner, corner + QPointF(0, dy * arm))

        if self.zones:
            for i, (name, (x0, y0, x1, y1), style) in enumerate(ZONES):
                zone = QRectF(x0 * aw, y0 * ah, (x1 - x0) * aw, (y1 - y0) * ah)
                color = QColor(self.color) if i == 0 else QColor(self.color).lighter(135)
                p.setPen(QPen(color, line, style))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(zone)
                if self.labels:
                    # The code zone is the outer one. Its tag goes at the bottom and the
                    # riddle zone's at the top, so neither sits on the other's line.
                    corner = zone.bottomLeft() + QPointF(6 * scale, -28 * scale) if i == 0 else \
                        zone.topLeft() + QPointF(6 * scale, 6 * scale)
                    tag(p, corner, name, color, scale)

        for x0, y0, x1, y1, text in self.reads:
            box = QRectF(x0, y0, x1 - x0, y1 - y0).adjusted(-4 * scale, -3 * scale, 4 * scale, 3 * scale)
            fill = QColor(self.color)
            fill.setAlpha(45)
            p.setPen(QPen(self.color, line))
            p.setBrush(fill)
            p.drawRoundedRect(box, 5 * scale, 5 * scale)
            if self.labels and text:
                # Beside the box: overlay lines are too close together for a label above one.
                text = text if len(text) <= 60 else text[:57] + "..."
                tag(p, QPointF(box.right() + 8 * scale, box.center().y() - 10 * scale), text, self.color, scale)


class AreaPicker(QWidget):
    """Covers a screen so the area to read can be dragged out. Esc or right-click cancels."""

    picked = Signal(tuple)      # (x, y, w, h) in physical pixels
    cancelled = Signal()
    MIN_SIZE = 40

    def __init__(self, screen, current=None):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.origin = (screen.geometry().x(), screen.geometry().y())
        self.ratio = screen.devicePixelRatio()
        self.setGeometry(screen.geometry())
        self.current = None
        if current:
            x, y, w, h = to_logical(current, self.origin, self.ratio)
            self.current = QRectF(x - self.origin[0], y - self.origin[1], w, h)
        self.start = self.end = None
        self.done = False

    def open(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def selection(self):
        if self.start is None:
            return None
        return QRectF(self.start, self.end).normalized()

    def native_selection(self):
        rect = self.selection()
        return to_native((rect.x() + self.origin[0], rect.y() + self.origin[1], rect.width(), rect.height()),
                         self.origin, self.ratio)

    def finish(self, area=None):
        if self.done:
            return
        self.done = True
        if area:
            self.picked.emit(area)
        else:
            self.cancelled.emit()
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finish()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.finish()
            return
        self.start = self.end = event.position()
        self.update()

    def mouseMoveEvent(self, event):
        if self.start is not None:
            self.end = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.start is None:
            return
        self.end = event.position()
        rect = self.selection()
        if rect.width() >= self.MIN_SIZE and rect.height() >= self.MIN_SIZE:
            self.finish(self.native_selection())
        else:
            self.start = self.end = None
            self.update()

    def closeEvent(self, event):
        if not self.done:
            self.done = True
            self.cancelled.emit()
        super().closeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        rect = self.selection()
        if rect is not None:
            hole = QPainterPath()
            hole.addRect(rect)
            shade = shade.subtracted(hole)
        p.fillPath(shade, QColor(3, 5, 20, 140))

        if self.current is not None and rect is None:
            p.setPen(QPen(QColor(255, 255, 255, 160), 1.5, Qt.PenStyle.DashLine))
            p.drawRect(self.current)

        if rect is not None:
            p.setPen(QPen(QColor("#3cc8ff"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(rect)
            _, _, w, h = self.native_selection()
            tag(p, rect.bottomRight() + QPointF(-110, 8), f"{w} × {h}", QColor("#3cc8ff"), 1)

        # Instructions on a glass capsule near the top.
        text = "Drag over the area MASSAB should read. Esc cancels."
        p.setFont(font("text", 11))
        width = p.fontMetrics().horizontalAdvance(text) + 48
        card = QRectF((self.width() - width) / 2, 40, width, 44)
        fill = QLinearGradient(card.topLeft(), card.bottomLeft())
        fill.setColorAt(0, QColor(30, 38, 90, 240))
        fill.setColorAt(1, QColor(12, 16, 46, 240))
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.setBrush(fill)
        p.drawRoundedRect(card, 22, 22)
        p.setPen(QColor(INK))
        p.drawText(card, Qt.AlignmentFlag.AlignCenter, text)


class AreaPreview(QWidget):
    """A little monitor showing what part of the screen is read, and where in it each kind of text is looked for."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.monitor = None     # physical pixels
        self.area = None
        self.color = QColor("#3cc8ff")
        self.caption = ""

    def set_state(self, monitor, area, color, caption=""):
        self.monitor, self.area, self.color, self.caption = monitor, area, QColor(color), caption
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        mw, mh = (self.monitor[2], self.monitor[3]) if self.monitor else (16, 9)
        scale = min((self.width() - 2) / mw, (self.height() - 2) / mh)
        sw, sh = mw * scale, mh * scale
        screen = QRectF((self.width() - sw) / 2, (self.height() - sh) / 2, sw, sh)

        # The monitor as a dark glass pane with a faint grid, so the area reads as part of a screen.
        pane = QPainterPath()
        pane.addRoundedRect(screen, 12, 12)
        fill = QLinearGradient(screen.topLeft(), screen.bottomRight())
        fill.setColorAt(0, QColor(30, 40, 96, 200))
        fill.setColorAt(1, QColor(6, 9, 30, 220))
        p.fillPath(pane, fill)
        p.save()
        p.setClipPath(pane)
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        for i in range(1, 8):
            x = screen.left() + screen.width() * i / 8
            p.drawLine(QPointF(x, screen.top()), QPointF(x, screen.bottom()))
        for i in range(1, 5):
            y = screen.top() + screen.height() * i / 5
            p.drawLine(QPointF(screen.left(), y), QPointF(screen.right(), y))
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 46), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(screen.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)

        if self.monitor and self.area:
            ax, ay, aw, ah = self.area
            area = QRectF(screen.left() + (ax - self.monitor[0]) * scale, screen.top() + (ay - self.monitor[1]) * scale,
                          aw * scale, ah * scale).intersected(screen)
            if not area.isEmpty():
                p.save()
                p.setClipPath(pane)
                p.setPen(QPen(self.color, 1.5))
                fill = QColor(self.color)
                fill.setAlpha(34)
                p.setBrush(fill)
                p.drawRect(area.adjusted(0.75, 0.75, -0.75, -0.75))
                for i, (_, (x0, y0, x1, y1), style) in enumerate(ZONES):
                    zone = QRectF(area.left() + x0 * area.width(), area.top() + y0 * area.height(),
                                  (x1 - x0) * area.width(), (y1 - y0) * area.height())
                    color = QColor(self.color) if i == 0 else QColor(self.color).lighter(140)
                    p.setPen(QPen(color, 1, style))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRect(zone)
                p.restore()
        if self.caption:
            p.setPen(QColor(INK if self.area else TEXT3))
            p.setFont(font("text", 8.5))
            p.drawText(screen.adjusted(10, 6, -10, -8), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                       self.caption)

    def sizeHint(self):
        return QRect(0, 0, 320, 170).size()
