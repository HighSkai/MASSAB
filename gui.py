"""MASSAB's window: a control panel, a strip that sits over the game, and an
optional box drawn over the part of the screen it reads.

Usage:
    python gui.py

Codes and riddles are both watched for, the whole time. Pasting only works
while Roblox is the active window, so nothing here may take focus during play:
the strip and the box can't be clicked or focused.
"""
import html
import json
import os
import re
import sys
import threading
import time

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontMetrics, QGuiApplication, QIcon, QTextDocument
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
                               QSizePolicy, QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

import chat
import setup_ai
from codereader import frames_from_screen
from engine import CODE_FPS, RIDDLE_FPS, Engine, Options
from overlay import (PASSIVE_FLAGS, AreaOverlay, AreaPicker, AreaPreview, capture_area, keep_out_of_capture,
                     monitor_rects, screen_for)
from riddle import FACTS_PATH, gpu_memory
from setup_ai import APP_DIR, DEFAULT_MODEL, MODELS, ai_installed
from theme import (TEXT3, Backdrop, Columns, Glass, Light, NavRail, PipelineBar, Segmented, Swatches, Toggle,
                   apply, cross_fade, dark_title_bar, icon, label, mark, rise_in, separator)

SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
OVERLAY_WHEN = {"never": "Never", "watching": "Watching", "always": "Always"}
HUD_CORNERS = ("bottom left", "bottom right", "bottom center", "top left", "top right")
HUD_SIZES = {"small": 9, "normal": 11, "large": 14}
HUD_HEIGHTS = {"small": 30, "normal": 36, "large": 44}   # the strip is a capsule: its radius is half of this
HUD_CHIPS = {"small": (8, 18), "normal": (9, 22), "large": (11, 26)}     # the CODE/RIDDLE chip's (pt, height)
FIELD_WIDTH = 150
SCROLL_GUTTER = 10      # every page keeps room for a scroll bar, so panels line up from tab to tab
MODEL_NAMES = {"4b": "4B", "2b": "2B"}
DEFAULTS = {
    "words": 3, "end_gap": 6.0, "paste": True, "paste_window": "Roblox", "key_delay_ms": 15,
    "monitor": 1, "region": "", "model": DEFAULT_MODEL, "ai_autoload": True,
    "hud": True, "hud_corner": "bottom left", "hud_size": "normal", "hud_opacity": 85,
    "overlay": "never", "overlay_zones": True, "overlay_reads": True, "overlay_labels": True,
    "overlay_color": "#3cc8ff", "overlay_width": 2, "overlay_opacity": 90,
    "chat_facts": True,
}
CHOICES = {"model": tuple(MODELS), "overlay": tuple(OVERLAY_WHEN), "hud_corner": HUD_CORNERS,
           "hud_size": tuple(HUD_SIZES)}
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
PAGES = ("Home", "Chat", "Overlay", "Settings")
PAGE_ICONS = ("home", "chat", "overlay", "sliders")
SUGGESTIONS = ("What rarities are there?", "When did Steal a Brainrot come out?", "How do I protect my base?")
LOW_VRAM_MIB = 500
VRAM_CHECK_MS = 3000
LOG_LINES = 1000
ANSWER_PT = (30, 11)    # the last answer's biggest and smallest size


def load_settings(path=SETTINGS_PATH):
    """Saved settings over the defaults. Anything broken or unknown just means the default."""
    settings = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        for key, value in saved.items():
            default = DEFAULTS.get(key)
            if key not in DEFAULTS or isinstance(value, bool) != isinstance(default, bool):
                continue
            if isinstance(default, (int, float)) and isinstance(value, (int, float)):
                settings[key] = type(default)(value)
            elif isinstance(value, type(default)):
                settings[key] = value
    except (OSError, ValueError, AttributeError):
        pass
    for key, allowed in CHOICES.items():
        if settings[key] not in allowed:
            settings[key] = DEFAULTS[key]
    if not COLOR.fullmatch(settings["overlay_color"]):
        settings["overlay_color"] = DEFAULTS["overlay_color"]
    return settings


def save_settings(settings, path=SETTINGS_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def parse_region(text):
    """"x,y,w,h" as a tuple, None if blank. Raises ValueError if it's neither."""
    if not text.strip():
        return None
    region = tuple(int(value) for value in text.split(","))
    if len(region) != 4 or region[2] <= 0 or region[3] <= 0:
        raise ValueError(text)
    return region


def was_pasted(note):
    return "and pasted" in note


def note_text(note):
    """"  (copied and pasted)" -> "Copied and pasted"."""
    note = note.strip().strip("()")
    return note[:1].upper() + note[1:]


class Hud(QWidget):
    """The strip over the game. It can't be clicked and never takes focus."""

    MARGIN = 16

    def __init__(self):
        super().__init__(None, PASSIVE_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.frame = QFrame(objectName="hud")
        row = QHBoxLayout(self.frame)
        row.setContentsMargins(8, 6, 16, 6)
        row.setSpacing(10)
        self.kind = QLabel(objectName="hudKind", visible=False)
        self.answer = QLabel("Waiting", objectName="hudAnswer")
        self.seconds = QLabel(objectName="hudSeconds")
        self.state = QLabel(objectName="hudState")
        self.flag = QLabel("guess", objectName="hudFlag", visible=False)
        self.flag.setToolTip("No fact matched this riddle, so the AI answered from memory")
        for widget in (self.kind, self.answer, self.seconds, self.state, self.flag):
            row.addWidget(widget)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.frame)
        self.corner, self.target = "bottom left", None
        self.set_look("bottom left", "normal", 85)

    def showEvent(self, event):
        super().showEvent(event)
        keep_out_of_capture(self)
        self.place()

    def set_look(self, corner, size, opacity, screen=None):
        """Where it sits, how big its text is, and how solid its glass is (0-100)."""
        self.corner, self.target = corner, screen
        a = opacity / 100
        pt, height = HUD_SIZES[size], HUD_HEIGHTS[size]
        chip_pt, chip_h = HUD_CHIPS[size]
        self.frame.setFixedHeight(height)
        self.frame.setStyleSheet(
            f"QFrame#hud {{ border-radius: {height // 2}px; border: 1px solid rgba(255, 255, 255, {round(60 * a)});"
            f" background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(28, 36, 86, {round(255 * a)}),"
            f" stop:1 rgba(8, 11, 34, {round(255 * a)})); }}"
            f" QFrame#hud QLabel {{ font-size: {pt}pt; }}"
            f" QFrame#hud QLabel#hudKind {{ font-size: {chip_pt}pt; border-radius: {chip_h // 2}px;"
            f" min-height: {chip_h}px; max-height: {chip_h}px; }}")
        self.place()

    def place(self):
        self.adjustSize()
        area = (self.target or QApplication.primaryScreen()).availableGeometry()
        vertical, _, horizontal = self.corner.partition(" ")
        x = {"left": area.left() + self.MARGIN, "right": area.right() - self.width() - self.MARGIN,
             "center": area.center().x() - self.width() // 2}[horizontal]
        y = area.top() + self.MARGIN if vertical == "top" else area.bottom() - self.height() - self.MARGIN
        self.move(x, y)

    def show_result(self, text, kind="", seconds="", state="", guess=False):
        """kind is CODE or RIDDLE, for the chip in front. state is how the answer got
        to the game; a guess is flagged beside it, so a pasted guess still says pasted."""
        self.kind.setText(kind)
        self.kind.setVisible(bool(kind))
        self.answer.setText(text)
        self.seconds.setText(seconds)
        self.state.setText(state)
        self.state.setProperty("plain", state in ("copied", "building"))
        self.state.style().polish(self.state)
        self.flag.setVisible(guess)
        self.place()


class ChatInput(QPlainTextEdit):
    """Enter sends, Shift+Enter starts a new line."""

    submitted = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class Panel(QMainWindow):
    """The control panel. Engine and chat events arrive on other threads, so
    they cross to the window's thread through a signal."""

    relay = Signal(str, object)

    def __init__(self, settings, settings_path=SETTINGS_PATH):
        super().__init__()
        self.settings = settings
        self.settings_path = settings_path
        self.worker = None
        self.watching = False
        self.ai_state = "off"
        self.picker = None
        self.monitors = self.find_monitors()
        self.chat_history = []
        self.chat_job = 0
        self.chat_cancel = threading.Event()
        self.chat_bubble = None     # the reply coming in, if one is
        self.chat_partial = ""
        self.chat_stop_reason = ""
        self.chat_pinned = True
        self.bubbles = []
        self.lock_notes = []
        self.titled = False
        self.setWindowTitle("MASSAB")
        self.setWindowIcon(QIcon(mark(64)))

        self.engine = Engine(self.options(), self.from_engine)
        self.relay.connect(self.on_event)
        self.hud = Hud()
        self.overlay = AreaOverlay()

        self.build()
        # Clicking a button shouldn't leave a focus ring on it; Tab still reaches every control.
        for button in self.findChildren(QAbstractButton):
            if not isinstance(button, QCheckBox):
                button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.resize(980, 640)
        self.setMinimumSize(880, 580)
        self.check_region()
        self.show_ai("off")
        self.show_watching(False)
        self.style_hud()

        app = QGuiApplication.instance()
        app.screenAdded.connect(self.screens_changed)
        app.screenRemoved.connect(self.screens_changed)
        self.vram_timer = QTimer(self, interval=VRAM_CHECK_MS, timeout=self.check_vram)
        self.vram_timer.start()
        self.check_vram()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.titled and QGuiApplication.platformName() == "windows":
            self.titled = True
            dark_title_bar(self)

    def options(self):
        s = self.settings
        # Frames come at the riddle rate, and the code reader only gets as many
        # as it's tuned for.
        return Options(words=s["words"], end_gap=s["end_gap"], no_paste=not s["paste"],
                       paste_window=s["paste_window"], key_delay=s["key_delay_ms"] / 1000, model=s["model"],
                       code_step=round(RIDDLE_FPS / CODE_FPS), show_reads=self.wants_reads())

    def wants_reads(self):
        return self.settings["overlay"] != "never" and self.settings["overlay_reads"]

    def from_engine(self, kind, now, **fields):
        """Runs on the engine's threads. A riddle needs the AI's only slot, so it
        cuts a chat reply off right here, without a trip through the window."""
        if kind == "riddle":
            self.stop_chat("a riddle came in")
        self.relay.emit(kind, fields)

    # --- building the window --------------------------------------------------

    def build(self):
        root = Backdrop()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)
        outer.addWidget(self.build_sidebar())
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self.build_header())
        self.stack = QStackedWidget()
        for build in (self.build_home, self.build_chat, self.build_overlay_page, self.build_settings_page):
            self.stack.addWidget(build())
        main.addWidget(self.stack, 1)
        outer.addLayout(main, 1)
        self.setCentralWidget(root)

    def build_sidebar(self):
        bar = Glass(radius=24, padding=12, kind="rail")
        bar.setFixedWidth(228)
        box = bar.vbox(0)
        brand = QHBoxLayout()
        brand.setContentsMargins(4, 2, 0, 0)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(mark(32))
        brand.addWidget(logo)
        brand.addWidget(label("MASSAB", "brand"))
        brand.addStretch()
        box.addLayout(brand)
        box.addSpacing(26)

        self.rail = NavRail(list(zip(PAGES, PAGE_ICONS)))
        self.nav = self.rail.group
        self.nav.idClicked.connect(self.show_page)
        box.addWidget(self.rail)
        box.addStretch()

        ai = QHBoxLayout()
        ai.setContentsMargins(4, 0, 0, 0)
        ai.setSpacing(6)
        self.ai_light = Light()
        self.ai_label = label("", "secondary")
        ai.addWidget(self.ai_light)
        ai.addWidget(self.ai_label, 1)
        box.addLayout(ai)
        box.addSpacing(10)
        self.ai_button = QPushButton(objectName="small")
        self.ai_button.clicked.connect(self.toggle_ai)
        box.addWidget(self.ai_button)
        box.addSpacing(18)
        self.vram_label = label("VRAM", "hint")
        self.vram_label.setContentsMargins(4, 0, 0, 0)
        box.addWidget(self.vram_label)
        box.addSpacing(7)
        self.vram_bar = QProgressBar(textVisible=False)
        box.addWidget(self.vram_bar)
        box.addSpacing(4)
        return bar

    def build_header(self):
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(Glass.PAD + 6, 14, Glass.PAD, 10)
        row.setSpacing(10)
        self.page_title = label(PAGES[0], "pageTitle")
        row.addWidget(self.page_title)
        row.addStretch()
        pill = QFrame(objectName="statusPill")
        pill.setFixedHeight(36)
        inner = QHBoxLayout(pill)
        inner.setContentsMargins(12, 0, 16, 0)
        inner.setSpacing(4)
        self.status_light = Light()
        self.status_label = label("", "statusText")
        inner.addWidget(self.status_light)
        inner.addWidget(self.status_label)
        row.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)
        self.start_button = QPushButton("Start", objectName="go")
        self.start_button.setFixedHeight(36)
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self.toggle_watching)
        row.addWidget(self.start_button, 0, Qt.AlignmentFlag.AlignVCenter)
        return bar

    def show_page(self, index):
        self.nav.button(index).setChecked(True)
        changed = index != self.stack.currentIndex()
        if changed and self.isVisible():
            cross_fade(self.stack, self.stack.currentWidget().grab(), self.stack.contentsRect())
        self.stack.setCurrentIndex(index)
        self.page_title.setText(PAGES[index])
        if changed and self.isVisible():
            rise_in(self.stack.currentWidget(), self.stack.contentsRect().topLeft())
        if PAGES[index] == "Chat":
            self.chat_input.setFocus()

    # The pages.

    def page(self, scroll=False):
        """A page, and the layout to fill it with. Long pages scroll."""
        page = QWidget(objectName="page")
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0 if scroll else SCROLL_GUTTER, 0)
        box.setSpacing(0)
        if not scroll:
            return page, box
        area = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Always there, and invisible when there's nothing to scroll, so the panels never jump sideways.
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        bar = area.verticalScrollBar()
        bar.rangeChanged.connect(lambda low, high, bar=bar: (bar.setProperty("idle", high <= low),
                                                             bar.style().polish(bar)))
        area.viewport().setAutoFillBackground(False)
        inner = QWidget(objectName="scrollInner")
        content = QVBoxLayout(inner)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        area.setWidget(inner)
        box.addWidget(area)
        return page, content

    def card(self, title=None, hint=None, kind="panel"):
        card = Glass(kind=kind)
        box = card.vbox(0)
        if title:
            box.addWidget(label(title, "cardTitle"))
        if hint:
            box.addSpacing(3)
            box.addWidget(label(hint, "hint", wrap=True))
        if title or hint:
            box.addSpacing(8)
        return card, box

    def lock_note(self):
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(Glass.PAD + 4, 0, 0, 6)
        row.addWidget(label("Stop watching to change the greyed-out settings.", "warning"))
        row.addStretch()
        holder.hide()
        self.lock_notes.append(holder)
        return holder

    def setting_row(self, title, widget, hint=None, tip=None):
        """A label on the left and its control on the right. A tip shows on hover;
        a hint is for the few things worth saying out loud."""
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 9, 0, 9)
        line.setSpacing(16)
        text = QVBoxLayout()
        text.setSpacing(2)
        name = label(title)
        text.addWidget(name)
        if hint:
            text.addWidget(label(hint, "hint", wrap=True))
        line.addLayout(text, 1)
        line.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        if tip:
            name.setToolTip(tip)
            widget.setToolTip(tip)
        return row

    def add_rows(self, box, rows):
        for i, row in enumerate(rows):
            if i:
                box.addWidget(separator())
            box.addWidget(row)

    def build_home(self):
        page, box = self.page()
        card, c = self.card(kind="hero")
        top = QHBoxLayout()
        top.setSpacing(12)
        self.answer_label = label("No answer yet", "answer")
        self.answer_label.setProperty("empty", True)
        self.answer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.answer_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top.addWidget(self.answer_label, 1)
        self.copy_button = QPushButton("Copy", objectName="small", enabled=False)
        self.copy_button.setIcon(icon("copy", 14))
        self.copy_button.setIconSize(QSize(14, 14))
        self.copy_button.setToolTip("Copy the answer again")
        self.copy_button.clicked.connect(self.copy_answer)
        top.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignVCenter)
        c.addLayout(top)
        c.addSpacing(2)
        self.detail_label = label("Press Start, then click the Codes box in Roblox.", "secondary", wrap=True)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        c.addWidget(self.detail_label)

        self.meta_row = QWidget()
        meta = QHBoxLayout(self.meta_row)
        meta.setContentsMargins(0, 16, 0, 0)
        meta.setSpacing(8)
        self.kind_label = label("", "chip")
        self.paste_label = label("", "chip")
        self.paste_label.hide()
        self.guess_label = label("", "warning")
        self.guess_label.hide()
        self.total_label = label("", "total")
        self.total_label.setToolTip("From the text appearing to the paste finishing")
        meta.addWidget(self.kind_label)
        meta.addWidget(self.paste_label)
        meta.addWidget(self.guess_label)
        meta.addStretch()
        meta.addWidget(self.total_label)
        self.meta_row.hide()
        c.addWidget(self.meta_row)
        self.pipeline = PipelineBar()
        self.pipeline.hide()
        c.addSpacing(6)
        c.addWidget(self.pipeline)
        box.addWidget(card)

        log_card, log_box = self.card()
        head = QHBoxLayout()
        head.addWidget(label("Activity", "cardTitle"))
        head.addStretch()
        clear = QPushButton("Clear", objectName="small")
        head.addWidget(clear)
        log_box.addLayout(head)
        log_box.addSpacing(10)
        self.log_view = QPlainTextEdit(readOnly=True, maximumBlockCount=LOG_LINES, objectName="log")
        self.log_view.setPlaceholderText("Everything MASSAB reads, answers and pastes shows up here.")
        clear.clicked.connect(self.log_view.clear)
        log_box.addWidget(self.log_view, 1)
        box.addWidget(log_card, 1)
        return page

    def build_chat(self):
        page, box = self.page()
        card, c = self.card()
        top = QHBoxLayout()
        top.setSpacing(8)
        facts = self.bind("chat_facts", Toggle())
        facts.setToolTip("Answer game questions from the fact sheet")
        facts_label = label("Use the fact sheet", "secondary")
        facts_label.setToolTip(facts.toolTip())
        top.addWidget(facts)
        top.addWidget(facts_label)
        top.addStretch()
        new = QPushButton("New chat", objectName="small")
        new.clicked.connect(self.new_chat)
        top.addWidget(new)
        c.addLayout(top)
        c.addSpacing(10)

        self.chat_banner = QWidget()
        banner = QVBoxLayout(self.chat_banner)
        banner.setContentsMargins(0, 0, 0, 0)
        banner.setSpacing(10)
        banner.addWidget(separator())
        line = QHBoxLayout()
        line.setSpacing(12)
        self.chat_banner_text = label("", "secondary", wrap=True)
        line.addWidget(self.chat_banner_text, 1)
        self.chat_load_button = QPushButton("Load AI", objectName="primary")
        self.chat_load_button.clicked.connect(self.toggle_ai)
        line.addWidget(self.chat_load_button)
        banner.addLayout(line)
        banner.addWidget(separator())
        c.addWidget(self.chat_banner)

        self.chat_scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.viewport().setAutoFillBackground(False)
        inner = QWidget(objectName="scrollInner")
        self.chat_list = QVBoxLayout(inner)
        self.chat_list.setContentsMargins(0, 10, 8, 10)
        self.chat_list.setSpacing(10)
        self.chat_empty = self.build_chat_empty()
        self.chat_list.addWidget(self.chat_empty)
        self.chat_list.addStretch()
        self.chat_scroll.setWidget(inner)
        bar = self.chat_scroll.verticalScrollBar()
        bar.valueChanged.connect(lambda value: setattr(self, "chat_pinned", value >= bar.maximum() - 40))
        bar.rangeChanged.connect(lambda low, high: self.chat_pinned and bar.setValue(high))
        c.addWidget(self.chat_scroll, 1)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.chat_input = ChatInput(objectName="chatInput")
        self.chat_input.setPlaceholderText("Ask anything. Shift+Enter for a new line.")
        self.chat_input.setFixedHeight(50)
        # Enter waits for a reply to finish; only the button stops one.
        self.chat_input.submitted.connect(lambda: self.chat_bubble is None and self.send_chat())
        self.send_button = QPushButton("Send", objectName="primary")
        self.send_button.setFixedSize(92, 50)
        self.send_button.clicked.connect(lambda: self.send_chat())
        row.addWidget(self.chat_input, 1)
        row.addWidget(self.send_button)
        c.addLayout(row)
        box.addWidget(card, 1)
        return page

    def build_chat_empty(self):
        empty = QWidget()
        box = QVBoxLayout(empty)
        box.setContentsMargins(20, 34, 20, 10)
        box.setSpacing(0)
        logo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(mark(48))
        box.addWidget(logo)
        box.addSpacing(16)
        box.addWidget(label("Ask about the game", "emptyTitle"), 0, Qt.AlignmentFlag.AlignCenter)
        box.addSpacing(6)
        hint = label("The riddle AI, running on this PC. A riddle on screen cuts its reply short.", "secondary",
                     wrap=True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(hint)
        box.addSpacing(18)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        for text in SUGGESTIONS:
            button = QPushButton(text, objectName="suggestion")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, text=text: self.send_chat(text))
            row.addWidget(button)
        row.addStretch()
        box.addLayout(row)
        return empty

    def build_overlay_page(self):
        page, box = self.page(scroll=True)
        box.addWidget(self.lock_note())

        card, c = self.card("Reading area")
        row = QHBoxLayout()
        row.setSpacing(22)
        self.preview = AreaPreview()
        self.preview.setFixedSize(280, 168)
        row.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignTop)
        right = QVBoxLayout()
        right.setSpacing(0)
        self.monitor_edit = QComboBox()
        self.fill_monitors()
        self.monitor_edit.currentIndexChanged.connect(
            lambda i: self.monitor_edit.itemData(i) is not None and self.set("monitor", self.monitor_edit.itemData(i)))
        self.region_edit = self.bind("region", QLineEdit(placeholderText="Whole monitor"))
        for field in (self.monitor_edit, self.region_edit):
            field.setFixedWidth(FIELD_WIDTH + 30)
        self.add_rows(right, [self.setting_row("Monitor", self.monitor_edit, tip="1 is your main screen"),
                              self.setting_row("Area", self.region_edit,
                                               tip="x, y, width, height in pixels. Blank reads the whole monitor.")])
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 12, 0, 0)
        buttons.setSpacing(8)
        pick = QPushButton("Pick on screen", objectName="primary")
        pick.setToolTip("Drag a box over the part of the screen to read")
        pick.clicked.connect(self.pick_area)
        whole = QPushButton("Use whole monitor")
        whole.clicked.connect(lambda: self.use_area(""))
        buttons.addWidget(pick)
        buttons.addWidget(whole)
        buttons.addStretch()
        right.addLayout(buttons)
        right.addStretch()
        row.addLayout(right, 1)
        c.addLayout(row)
        self.area_card = card
        box.addWidget(card)

        columns = Columns()
        card, c = self.card("On-screen box", "Drawn over the game. It can't be clicked, and MASSAB can't see it.")
        self.overlay_edit = self.bind("overlay", self.segmented(OVERLAY_WHEN.items()))
        self.swatches = Swatches(self.settings["overlay_color"])
        self.swatches.picked.connect(lambda color: self.set("overlay_color", color))
        self.add_rows(c, [
            self.setting_row("Show", self.overlay_edit),
            self.setting_row("Mark zones", self.bind("overlay_zones", Toggle()),
                             tip="Dashed: where code lines are found. Dotted: where riddle rows are."),
            self.setting_row("Highlight reads", self.bind("overlay_reads", Toggle()),
                             tip="Box each line of text as it's read, while watching"),
            self.setting_row("Show what it read", self.bind("overlay_labels", Toggle()),
                             tip="Label each highlight with the text OCR made of it"),
            self.setting_row("Color", self.swatches),
        ])
        columns.add(card)

        card, c = self.card("Game strip", "The answer, its time and whether it pasted, in a corner of the game.")
        self.hud_edit = self.bind("hud", Toggle())
        self.add_rows(c, [
            self.setting_row("Show", self.hud_edit),
            self.setting_row("Corner", self.bind("hud_corner", self.combo((corner, corner.capitalize())
                                                                          for corner in HUD_CORNERS))),
            self.setting_row("Size", self.bind("hud_size", self.segmented((size, size.capitalize())
                                                                          for size in HUD_SIZES))),
            self.setting_row("Background", self.slider("hud_opacity", 0, 100), tip="How solid its glass is"),
        ])
        columns.add(card)
        box.addWidget(columns)
        box.addStretch()
        return page

    def build_settings_page(self):
        page, box = self.page(scroll=True)
        box.addWidget(self.lock_note())

        columns = Columns()
        card, c = self.card("Codes")
        self.words_edit = self.bind("words", QSpinBox(minimum=0, maximum=10, suffix=" words", specialValueText="Whole code"))
        self.gap_edit = self.bind("end_gap", QDoubleSpinBox(minimum=1, maximum=30, suffix=" s", decimals=1))
        self.add_rows(c, [self.setting_row("Copy after", self.words_edit,
                                           tip="Copied once this many words are in, and updated if more come. "
                                               "Whole code waits for the end."),
                          self.setting_row("Code ends after", self.gap_edit, tip="With no new word in that time")])
        self.codes_card = card
        columns.add(card)

        card, c = self.card("Pasting")
        self.paste_edit = self.bind("paste", Toggle())
        self.window_edit = self.bind("paste_window", QLineEdit())
        self.delay_edit = self.bind("key_delay_ms", QSpinBox(minimum=5, maximum=60, suffix=" ms"))
        for field in (self.words_edit, self.gap_edit, self.window_edit, self.delay_edit):
            field.setFixedWidth(FIELD_WIDTH)
        self.add_rows(c, [self.setting_row("Paste automatically", self.paste_edit, tip="Off: answers are only copied"),
                          self.setting_row("Paste into", self.window_edit,
                                           tip="Only pastes while the active window has exactly this title"),
                          self.setting_row("Wait after each key", self.delay_edit, "Raise it if pastes go missing")])
        self.paste_card = card
        columns.add(card)
        box.addWidget(columns)

        card, c = self.card("AI")
        self.model_edit = self.bind("model", self.segmented((m, MODEL_NAMES.get(m, m)) for m in MODELS))
        facts = QPushButton("Open")
        facts.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(FACTS_PATH)))
        self.add_rows(c, [self.setting_row("Model", self.model_edit,
                                           tip="4B gives the best answers. 2B uses less VRAM, and needs "
                                               "setup_ai.py --model 2b"),
                          self.setting_row("Load when MASSAB opens", self.bind("ai_autoload", Toggle()),
                                           tip="So the first riddle doesn't wait for it"),
                          self.setting_row("Fact sheet", facts, "Changes apply the next time the AI loads",
                                           tip="Where riddle and chat answers come from")])
        box.addWidget(card)
        box.addStretch()
        return page

    # Controls bound to a setting.

    def combo(self, items):
        widget = QComboBox()
        for value, text in items:
            widget.addItem(text, value)
        return widget

    def segmented(self, items):
        return Segmented((text, value) for value, text in items)

    def slider(self, key, low, high):
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        slider = QSlider(Qt.Orientation.Horizontal, minimum=low, maximum=high)
        slider.setFixedWidth(130)
        value = label("", "secondary")
        value.setFixedWidth(38)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(lambda v: value.setText(f"{v}%"))
        self.bind(key, slider)
        value.setText(f"{slider.value()}%")
        row.addWidget(slider)
        row.addWidget(value)
        holder.slider = slider
        return holder

    def bind(self, key, widget):
        """Show a setting in a control, and save it whenever the control changes."""
        value = self.settings[key]
        if isinstance(widget, QCheckBox):
            widget.setChecked(value)
            widget.toggled.connect(lambda v: self.set(key, v))
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox, QSlider)):
            widget.setValue(value)
            widget.valueChanged.connect(lambda v: self.set(key, v))
            edit = widget.findChild(QLineEdit)
            if edit is not None:
                edit.setTextMargins(6, 0, 0, 0)     # line the number up with the text in other fields
        elif isinstance(widget, (QComboBox, Segmented)):
            widget.setCurrentIndex(max(0, widget.findData(value)))
            widget.currentIndexChanged.connect(lambda i: self.set(key, widget.itemData(i)))
        elif isinstance(widget, QLineEdit):
            widget.setText(value)
            widget.editingFinished.connect(lambda: self.set(key, widget.text().strip()))
        return widget

    # --- settings -------------------------------------------------------------

    def set(self, key, value):
        old, self.settings[key] = self.settings[key], value
        if key == "model" and value != old:
            self.engine.options.model = value
            self.engine.stop_ai()
            self.show_ai("off")
        elif key == "region":
            self.check_region()
        if key.startswith("hud") or key in ("monitor", "region"):
            self.style_hud()
        if key.startswith("overlay") or key in ("monitor", "region"):
            self.update_overlay()
        self.save()

    def save(self):
        try:
            save_settings(self.settings, self.settings_path)
        except OSError as e:
            self.log(f"Couldn't save settings: {e}")

    def check_region(self):
        try:
            parse_region(self.settings["region"])
            bad = False
        except ValueError:
            bad = True
        self.region_edit.setProperty("invalid", bad)
        self.region_edit.style().polish(self.region_edit)
        self.region_edit.setToolTip("Should look like 0,120,1280,720" if bad else
                                    "x, y, width, height in pixels. Blank reads the whole monitor.")

    def use_area(self, text):
        self.region_edit.setText(text)
        self.set("region", text)

    def pick_area(self):
        monitor = self.monitor_rect()
        screen = screen_for(monitor) if monitor else QGuiApplication.primaryScreen()
        current = self.current_area() if self.settings["region"] else None
        self.picker = AreaPicker(screen, current)
        self.picker.picked.connect(self.area_picked)
        self.picker.destroyed.connect(lambda: setattr(self, "picker", None))
        self.picker.open()

    def area_picked(self, area):
        text = ",".join(str(v) for v in area)
        self.use_area(text)
        self.log(f"Reading area set to {text}.")
        self.activateWindow()

    def find_monitors(self):
        try:
            return monitor_rects()
        except Exception:   # no capture at all, e.g. a remote session
            return []

    def fill_monitors(self):
        """One item per monitor, with its size, plus the saved one if it isn't plugged in."""
        combo, chosen = self.monitor_edit, self.settings["monitor"]
        combo.blockSignals(True)
        combo.clear()
        for n, (_, _, w, h) in enumerate(self.monitors[1:], start=1):
            combo.addItem(f"{n}  ·  {w} × {h}", n)
        if combo.findData(chosen) < 0:
            combo.addItem(f"{chosen}  ·  not connected", chosen)
        combo.setCurrentIndex(combo.findData(chosen))
        combo.blockSignals(False)

    def screens_changed(self, *_):
        self.monitors = self.find_monitors()
        self.fill_monitors()
        self.style_hud()
        self.update_overlay()

    def monitor_rect(self):
        n = self.settings["monitor"]
        return self.monitors[n] if 0 < n < len(self.monitors) else None

    def current_area(self):
        """What will be captured, in physical pixels, or None if the settings don't say anything usable."""
        try:
            region = parse_region(self.settings["region"])
        except ValueError:
            return None
        return capture_area(self.settings["monitor"], region, self.monitors)

    def update_overlay(self):
        s = self.settings
        area, monitor = self.current_area(), self.monitor_rect()
        if area is None:
            caption = "Area isn't valid" if monitor else "No such monitor"
        else:
            caption = f"{area[2]} × {area[3]}" + ("" if s["region"] else f"  ·  monitor {s['monitor']}")
        self.preview.set_state(monitor, area, s["overlay_color"], caption)
        self.overlay.set_look(s["overlay_color"], s["overlay_width"], s["overlay_opacity"], s["overlay_zones"],
                              s["overlay_labels"])
        show = area is not None and (s["overlay"] == "always" or (s["overlay"] == "watching" and self.watching))
        if show:
            self.overlay.set_area(area)
        self.overlay.setVisible(show)
        self.engine.options.show_reads = self.wants_reads()
        if not (self.watching and self.wants_reads()):
            self.overlay.set_reads([])

    def style_hud(self):
        s = self.settings
        area = self.current_area() or self.monitor_rect()
        self.hud.set_look(s["hud_corner"], s["hud_size"], s["hud_opacity"], screen_for(area) if area else None)
        self.hud.setVisible(s["hud"])

    # --- watching -------------------------------------------------------------

    def toggle_watching(self):
        if self.worker and self.worker.is_alive():
            self.start_button.setEnabled(False)
            self.start_button.setText("Stopping")
            self.engine.stop()
            return
        try:
            region = parse_region(self.settings["region"])
        except ValueError:
            self.log("The area to watch has to look like x,y,w,h, for example 0,120,1280,720.")
            return
        self.engine.options = self.options()
        self.engine.reset()
        self.engine.stopping.clear()
        self.worker = threading.Thread(target=self.watch, args=(region,), daemon=True)
        self.worker.start()
        self.show_watching(True)

    def watch(self, region):
        """Runs on the worker thread. Anything going wrong has to reach the
        window, or watching would just silently stop."""
        try:
            self.engine.run(frames_from_screen(RIDDLE_FPS, self.settings["monitor"], region, self.engine.screen_blocked))
        except Exception as e:
            self.relay.emit("error", {"message": f"Watching stopped: {e}"})
        self.relay.emit("stopped", {})

    def show_watching(self, watching):
        """Settings that are only read when watching starts can't change while it runs."""
        self.watching = watching
        for widget in (self.codes_card, self.paste_card, self.area_card, self.model_edit):
            widget.setEnabled(not watching)
        for note in self.lock_notes:
            note.setVisible(watching)
        self.start_button.setText("Stop" if watching else "Start")
        self.start_button.setProperty("running", watching)
        self.start_button.style().polish(self.start_button)
        self.status_label.setText("Watching" if watching else "Stopped")
        self.status_label.setProperty("live", watching)
        self.status_label.style().polish(self.status_label)
        self.status_light.set("", "green" if watching else "gray")
        self.update_overlay()

    # --- the AI ---------------------------------------------------------------

    def toggle_ai(self):
        model = self.settings["model"]
        if self.ai_state == "ready":
            self.engine.stop_ai()
        elif not ai_installed(model):
            self.show_ai("installing")
            threading.Thread(target=self.install_ai, args=(model,), daemon=True).start()
        else:
            self.load_ai()

    def load_ai(self):
        self.show_ai("loading")
        threading.Thread(target=self.engine.start_ai, daemon=True).start()

    def install_ai(self, model):
        try:
            setup_ai.install_runtime()
            setup_ai.install_model(model)
        except (OSError, SystemExit) as e:
            self.relay.emit("error", {"message": f"Couldn't install the AI: {e}"})
            self.relay.emit("ai", {"state": "off"})
            return
        self.relay.emit("installed", {})

    def show_ai(self, state):
        self.ai_state = state
        if state == "off" and not ai_installed(self.settings["model"]):
            text, button, light = "AI not installed", "Install AI", "gray"
        else:
            text, button, light = {"off": ("AI off", "Load AI", "gray"), "ready": ("AI ready", "Unload AI", "green"),
                                   "loading": ("AI loading", "Load AI", "amber"),
                                   "installing": ("Downloading AI", "Install AI", "amber")}[state]
        self.ai_label.setText(text)
        self.ai_light.set("", light)
        self.ai_button.setText(button)
        self.ai_button.setToolTip("About a 3 GB download" if button == "Install AI" else "")
        self.ai_button.setEnabled(state in ("off", "ready"))
        if state != "ready":
            self.stop_chat("the AI was unloaded")
        self.show_chat_state()

    def check_vram(self):
        threading.Thread(target=lambda: self.relay.emit("vram", {"memory": gpu_memory()}), daemon=True).start()

    def show_vram(self, memory):
        self.vram_bar.setVisible(memory is not None)
        if memory is None:
            self.vram_label.setText("VRAM unknown")
            return
        used, total = memory
        low = total - used < LOW_VRAM_MIB
        self.vram_label.setText(f"VRAM {'low, ' if low else ''}{used / 1024:.1f} of {total / 1024:.1f} GB")
        self.vram_label.setToolTip("The game and the AI share it. Close something if riddles slow down." if low else "")
        self.vram_bar.setMaximum(total)
        self.vram_bar.setValue(used)
        self.vram_bar.setProperty("low", low)
        self.vram_bar.style().polish(self.vram_bar)

    # --- chat -----------------------------------------------------------------

    def show_chat_state(self):
        ready = self.ai_state == "ready"
        self.send_button.setEnabled(ready or self.chat_bubble is not None)
        self.chat_banner.setVisible(not ready)
        if self.ai_state in ("loading", "installing"):
            self.chat_banner_text.setText("The AI is getting ready. You can chat once it's loaded.")
            self.chat_load_button.hide()
        else:
            installed = ai_installed(self.settings["model"])
            self.chat_banner_text.setText("Load the AI to start chatting." if installed else
                                          "Chat needs the AI, which is about a 3 GB download.")
            self.chat_load_button.setText("Load AI" if installed else "Install AI")
            self.chat_load_button.show()

    def bubble_width(self):
        return max(240, int(self.chat_scroll.viewport().width() * 0.78))

    def set_bubble_text(self, bubble, text):
        """Word-wrapped labels guess a narrow width, so size the bubble from the text itself."""
        bubble.text.setText(text)
        doc = QTextDocument()
        doc.setDefaultFont(bubble.text.font())
        doc.setDocumentMargin(0)
        if bubble.text.textFormat() == Qt.TextFormat.MarkdownText:
            doc.setMarkdown(text)
        else:
            doc.setPlainText(text)
        limit = self.bubble_width() - 32
        doc.setTextWidth(limit)
        bubble.text.setMinimumWidth(min(limit, int(doc.idealWidth()) + 4))
        bubble.setMaximumWidth(self.bubble_width())

    def add_bubble(self, role, text):
        self.chat_empty.hide()
        bubble = QFrame(objectName="bubbleUser" if role == "user" else "bubbleAi")
        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(15, 10, 15, 10)
        bubble.text = QLabel(wordWrap=True)
        bubble.text.setTextFormat(Qt.TextFormat.PlainText if role == "user" else Qt.TextFormat.MarkdownText)
        bubble.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inner.addWidget(bubble.text)
        self.set_bubble_text(bubble, text)
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            row.addStretch()
        row.addWidget(bubble)
        if role != "user":
            row.addStretch()
        self.chat_list.insertWidget(self.chat_list.count() - 1, holder)
        self.bubbles.append((holder, bubble))
        self.chat_pinned = True
        return bubble

    def send_chat(self, text=None):
        """Send the typed message, or text. While a reply comes in, the button stops it instead."""
        if self.chat_bubble is not None:
            self.stop_chat("you stopped it")
            return
        text = (self.chat_input.toPlainText() if text is None else text).strip()
        if not text or self.ai_state != "ready":
            return
        self.chat_input.clear()
        self.chat_history.append({"role": "user", "content": text})
        self.add_bubble("user", text)
        self.chat_bubble = self.add_bubble("ai", "...")
        self.chat_partial, self.chat_stop_reason = "", ""
        self.chat_job += 1
        self.chat_cancel = threading.Event()
        self.send_button.setText("Stop")
        self.show_chat_state()
        solver = self.engine.solver
        facts = solver.facts if solver and self.settings["chat_facts"] else None
        threading.Thread(target=self.chat_worker, args=(self.chat_job, list(self.chat_history), facts, self.chat_cancel),
                         daemon=True).start()

    def chat_worker(self, job, history, facts, cancel):
        """Runs on its own thread."""
        try:
            lines = chat.pick_facts(facts, history[-1]["content"]) if facts else []
            reply = chat.stream_reply(chat.build_messages(history, lines),
                                      lambda text: self.relay.emit("chat_text", {"job": job, "text": text}), cancel)
        except chat.ERRORS as e:
            self.relay.emit("chat_done", {"job": job, "reply": None, "error": str(e)})
            return
        self.relay.emit("chat_done", {"job": job, "reply": reply, "error": None})

    def stop_chat(self, reason):
        """Safe from any thread."""
        if self.chat_bubble is not None and not self.chat_cancel.is_set():
            self.chat_stop_reason = reason
            self.chat_cancel.set()

    def on_chat_text(self, e):
        if e["job"] == self.chat_job and self.chat_bubble is not None:
            self.chat_partial = e["text"]
            self.set_bubble_text(self.chat_bubble, e["text"])

    def on_chat_done(self, e):
        if e["job"] != self.chat_job or self.chat_bubble is None:
            return
        bubble, self.chat_bubble = self.chat_bubble, None
        partial = self.chat_partial.strip()
        if e["error"]:
            bubble.setObjectName("bubbleError")
            bubble.style().polish(bubble)
            self.set_bubble_text(bubble, f"Couldn't get a reply: {e['error']}")
            self.chat_history.pop()
        elif e["reply"] is None:
            note = f"*Stopped: {self.chat_stop_reason or 'cut off'}.*"
            self.set_bubble_text(bubble, f"{partial}\n\n{note}" if partial else note)
            if partial:
                self.chat_history.append({"role": "assistant", "content": partial})
            else:
                self.chat_history.pop()
        else:
            reply = e["reply"].strip() or "(no reply)"
            self.set_bubble_text(bubble, reply)
            self.chat_history.append({"role": "assistant", "content": reply})
        self.send_button.setText("Send")
        self.show_chat_state()

    def new_chat(self):
        self.stop_chat("you started a new chat")
        self.chat_bubble = None
        self.chat_job += 1
        self.chat_history.clear()
        for holder, _ in self.bubbles:
            holder.hide()
            holder.deleteLater()
        self.bubbles.clear()
        self.chat_empty.show()
        self.send_button.setText("Send")
        self.show_chat_state()

    # --- events ---------------------------------------------------------------

    def log(self, text):
        self.log_view.appendHtml(f'<span style="color:{TEXT3}">{time.strftime("%H:%M:%S")}</span>&nbsp;&nbsp;'
                                 f'<span style="white-space:pre-wrap">{html.escape(text)}</span>')

    def show_answer(self, text, kind, detail="", times=None, total=None, guess="", pasted=None):
        """times is (read, ai, paste) in seconds, for the bar under a riddle's answer.
        pasted None leaves the paste chip as it was, for an answer that didn't change."""
        self.answer_label.setText(text)
        self.answer_label.setProperty("empty", False)
        self.answer_label.style().polish(self.answer_label)
        self.fit_answer()
        self.kind_label.setText(kind)
        self.kind_label.setVisible(bool(kind))
        if pasted is not None:
            self.paste_label.setText("Pasted" if pasted else "Copied")
            self.paste_label.setProperty("tone", "good" if pasted else "plain")
            self.paste_label.style().polish(self.paste_label)
            self.paste_label.show()
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))
        self.total_label.setText(f"{total:.2f} s" if total is not None else "")
        self.total_label.setVisible(total is not None)
        self.guess_label.setText(guess)
        self.guess_label.setVisible(bool(guess))
        self.meta_row.show()
        if times:
            self.pipeline.show()
            self.pipeline.set_times(*times)
        else:
            self.pipeline.clear()
            self.pipeline.hide()
        self.copy_button.setEnabled(True)

    def fit_answer(self):
        """Shrink a long answer until it fits, rather than cutting it off."""
        text, width = self.answer_label.text(), max(120, self.answer_label.width())
        font = self.answer_label.font()
        biggest, smallest = ANSWER_PT
        for size in range(biggest, smallest - 1, -1):
            font.setPointSize(size)
            if QFontMetrics(font).horizontalAdvance(text) <= width:
                break
        self.answer_label.setStyleSheet(f"font-size: {size}pt;")

    def copy_answer(self):
        QApplication.clipboard().setText(self.answer_label.text())
        self.log(f"Copied {self.answer_label.text()}")

    def on_event(self, kind, e):
        if kind == "building":
            self.log(f"Building: {e['code']}")
            self.hud.show_result(e["code"], "CODE", state="building")
        elif kind == "code":
            # The chip says whether it pasted; the line below only explains a paste that didn't happen.
            note = note_text(e["note"])
            self.show_answer(e["code"], "CODE", note if ":" in note else "", pasted=was_pasted(e["note"]))
            self.log(f"Code: {e['code']}{e['note']}")
            self.hud.show_result(e["code"], "CODE", state="pasted" if was_pasted(e["note"]) else "copied")
        elif kind == "done":
            self.log(f"Done: {e['code']}")
        elif kind == "riddle":
            self.log(f"Riddle: {e['text']}")
            self.detail_label.setText(e["text"])
            self.detail_label.show()
            self.hud.show_result("Solving", "RIDDLE")
        elif kind == "answer":
            self.on_answer(e)
        elif kind == "no_answer":
            self.log(f"No answer from the model: {e['solved'].reply!r}")
            self.hud.show_result("No answer", "RIDDLE")
        elif kind == "rows":
            if self.watching:
                self.overlay.set_reads(e["boxes"])
        elif kind == "ai":
            self.show_ai(e["state"])
            self.log(f"AI: {e['state']}")
        elif kind == "installed":
            self.log("AI installed.")
            self.load_ai()
        elif kind == "vram":
            self.show_vram(e["memory"])
        elif kind == "chat_text":
            self.on_chat_text(e)
        elif kind == "chat_done":
            self.on_chat_done(e)
        elif kind == "error":
            self.log(f"Problem: {e['message']}")
        elif kind == "stopped":
            self.start_button.setEnabled(True)
            self.show_watching(False)

    def on_answer(self, e):
        solved, total, paste = e["solved"], e["total"], e["paste"]
        read = max(0.0, total - solved.seconds - paste)
        guess = "Guess: no fact matched this riddle" if solved.guess else ""
        self.show_answer(solved.answer, "RIDDLE", solved.riddle, (read, solved.seconds, paste), total, guess,
                         None if e["unchanged"] else was_pasted(e["note"]))
        self.log(f"Answer: {solved.answer}{e['note']}  [{total:.2f} s]" + ("  (guess)" if solved.guess else ""))
        state = "same" if e["unchanged"] else "pasted" if was_pasted(e["note"]) else "copied"
        self.hud.show_result(solved.answer, "RIDDLE", f"{total:.2f}s", state, solved.guess)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_answer()
        for _, bubble in self.bubbles:
            self.set_bubble_text(bubble, bubble.text.text())

    def closeEvent(self, event):
        self.vram_timer.stop()
        self.stop_chat("MASSAB closed")
        self.engine.stop()
        if self.worker:
            self.worker.join(2)
        self.engine.stop_ai()
        self.hud.close()
        self.overlay.close()
        self.save()
        super().closeEvent(event)


def check():
    """Try every part without opening a window, to prove a packaged build has
    what it needs. A windowed exe has no console, so results go to check.txt."""
    lines = []
    engine = Engine(Options(no_copy=True), lambda kind, now, **e: lines.append(f"{kind}: {e}"))
    try:
        frame = next(frames_from_screen(RIDDLE_FPS))
        lines.append(f"screen: {frame[1].shape}")
        from rapidocr_onnxruntime import RapidOCR
        image = np.zeros((48, 320, 3), np.uint8)
        cv2.putText(image, "KEYBOARD", (10, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        read = RapidOCR().text_recognizer([image])[0][0][0]
        lines.append(f"ocr: {read}")
        answer = ""
        if engine.start_ai():
            solved = engine.solver.solve("month and year the first fuse machine in sab released")
            answer = solved.answer
            lines.append(f"model: {answer} in {solved.seconds:.2f} s, {len(engine.solver.facts.lines)} facts")
        passed = read == "KEYBOARD" and answer == "AUGUST2025"
    except Exception as e:
        lines.append(f"failed: {e!r}")
        passed = False
    finally:
        engine.stop_ai()
    lines.append("PASSED" if passed else "FAILED")
    with open(os.path.join(APP_DIR, "check.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if passed else 1


def main():
    if "--check" in sys.argv:
        return check()
    app = QApplication(sys.argv)
    apply(app)
    app.setWindowIcon(QIcon(mark(64)))
    panel = Panel(load_settings())
    panel.show()
    # A riddle can't wait for the model to load, so start on that right away.
    if panel.settings["ai_autoload"] and ai_installed(panel.settings["model"]):
        panel.load_ai()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
