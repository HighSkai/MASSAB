"""MASSAB's window: a control panel, a strip that sits over the game, and an
optional box drawn over the part of the screen it reads.

Usage:
    python gui.py

Pasting only works while Roblox is the active window, so nothing here may take
focus during play: the strip and the box can't be clicked or focused, and modes
can be switched from the game with a global hotkey.
"""
import ctypes
import json
import os
import re
import sys
import threading
import time
from ctypes import wintypes

import cv2
import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontMetrics, QGuiApplication, QIcon, QTextDocument
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

import chat
import setup_ai
from codereader import frames_from_screen
from engine import CODE_FPS, MODES, RIDDLE_FPS, Engine, Options
from overlay import (PASSIVE_FLAGS, AreaOverlay, AreaPicker, AreaPreview, capture_area, keep_out_of_capture,
                     monitor_rects, screen_for)
from riddle import FACTS_PATH, gpu_memory
from setup_ai import APP_DIR, DEFAULT_MODEL, MODELS, ai_installed
from theme import Glass, Light, Sky, Toggle, label, orb, separator, style_sheet

SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
OVERLAY_WHEN = {"never": "Never", "watching": "While watching", "always": "Always"}
HUD_CORNERS = ("bottom left", "bottom right", "bottom center", "top left", "top right")
HUD_SIZES = {"small": 9, "normal": 11, "large": 14}
HOTKEYS = tuple(f"F{n}" for n in range(1, 13))
MODEL_NAMES = {"4b": "4B, best answers", "2b": "2B, lighter on VRAM"}
DEFAULTS = {
    "mode": "auto", "words": 3, "end_gap": 6.0, "paste": True, "paste_window": "Roblox", "key_delay_ms": 15,
    "monitor": 1, "region": "", "hotkey": "F8", "model": DEFAULT_MODEL, "ai_autoload": True,
    "hud": True, "hud_corner": "bottom left", "hud_size": "normal", "hud_opacity": 85,
    "overlay": "never", "overlay_zones": True, "overlay_reads": True, "overlay_labels": True,
    "overlay_color": "#3cc8ff", "overlay_width": 2, "overlay_opacity": 90,
    "chat_facts": True,
}
CHOICES = {"mode": MODES, "model": tuple(MODELS), "hotkey": HOTKEYS, "overlay": tuple(OVERLAY_WHEN),
           "hud_corner": HUD_CORNERS, "hud_size": tuple(HUD_SIZES)}
COLOR = re.compile(r"#[0-9a-fA-F]{6}")
MODE_TIPS = {"code": "Reads codes only", "riddle": "Reads riddles only", "auto": "Both, whichever comes"}
PAGES = ("Home", "Chat", "Overlay", "Settings")
SUGGESTIONS = ("What rarities are there in Steal a Brainrot?", "When did Steal a Brainrot come out?",
               "Give me three tips for protecting my base")
LOW_VRAM_MIB = 500
VRAM_CHECK_MS = 3000
LOG_LINES = 1000


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
        row.setContentsMargins(9, 6, 13, 6)
        row.setSpacing(10)
        self.mode = QLabel(objectName="hudMode")
        self.answer = QLabel("Waiting", objectName="hudAnswer")
        self.seconds = QLabel(objectName="hudSeconds")
        self.state = QLabel(objectName="hudState")
        for widget in (self.mode, self.answer, self.seconds, self.state):
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
        """Where it sits, how big its text is, and how see-through its glass is (0-100)."""
        self.corner, self.target = corner, screen
        a = round(255 * opacity / 100)
        self.frame.setStyleSheet(
            f"QFrame#hud {{ border: 1px solid rgba(150, 215, 255, {a}); border-radius: 12px;"
            f" background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(70, 130, 185, {a}),"
            f" stop:0.5 rgba(20, 66, 112, {a}), stop:1 rgba(10, 40, 76, {a})); }}"
            f" QFrame#hud QLabel {{ font-size: {HUD_SIZES[size]}pt; }}")
        self.place()

    def place(self):
        self.adjustSize()
        area = (self.target or QApplication.primaryScreen()).availableGeometry()
        vertical, _, horizontal = self.corner.partition(" ")
        x = {"left": area.left() + self.MARGIN, "right": area.right() - self.width() - self.MARGIN,
             "center": area.center().x() - self.width() // 2}[horizontal]
        y = area.top() + self.MARGIN if vertical == "top" else area.bottom() - self.height() - self.MARGIN
        self.move(x, y)

    def show_mode(self, mode):
        self.mode.setText(mode.upper())
        self.place()

    def show_result(self, text, seconds="", state="", guess=False):
        self.answer.setText(text)
        self.seconds.setText(seconds)
        self.state.setText(state)
        self.state.setProperty("guess", guess)
        self.state.style().polish(self.state)
        self.place()


class Hotkey(QObject):
    """A global F-key, so modes can be switched while the game has focus."""

    pressed = Signal()
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.thread = None
        self.thread_id = 0
        self.ready = threading.Event()

    def set_key(self, name):
        self.stop()
        self.ready.clear()
        self.thread = threading.Thread(target=self._run, args=(name,), daemon=True)
        self.thread.start()
        self.ready.wait(1)

    def stop(self):
        if self.thread and self.thread.is_alive():
            wm_quit = 0x0012
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, wm_quit, 0, 0)
            self.thread.join(1)
        self.thread = None

    def _run(self, name):
        """RegisterHotKey delivers to the thread that called it, which needs a message loop."""
        hotkey_id, no_repeat, vk_f1, wm_hotkey = 1, 0x4000, 0x70, 0x0312
        user32 = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered = user32.RegisterHotKey(None, hotkey_id, no_repeat, vk_f1 + int(name[1:]) - 1)
        self.ready.set()
        if not registered:
            self.failed.emit(name)
            return
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == wm_hotkey:
                self.pressed.emit()
        user32.UnregisterHotKey(None, hotkey_id)


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
        self.setWindowTitle("MASSAB")
        self.setWindowIcon(QIcon(orb(64)))

        self.engine = Engine(self.options(), self.from_engine)
        self.relay.connect(self.on_event)
        self.hud = Hud()
        self.overlay = AreaOverlay()
        self.hotkey = Hotkey()
        self.hotkey.pressed.connect(self.next_mode)
        self.hotkey.failed.connect(lambda key: self.log(f"Couldn't use {key} as the hotkey, another app has it."))

        self.build()
        self.resize(720, 780)
        self.setMinimumSize(640, 640)
        self.select_mode(settings["mode"])
        self.check_region()
        self.hotkey.set_key(settings["hotkey"])
        self.show_ai("off")
        self.show_watching(False)
        self.style_hud()
        self.hud.show_mode(self.engine.next_mode)

        app = QGuiApplication.instance()
        app.screenAdded.connect(self.screens_changed)
        app.screenRemoved.connect(self.screens_changed)
        self.vram_timer = QTimer(self, interval=VRAM_CHECK_MS, timeout=self.check_vram)
        self.vram_timer.start()
        self.check_vram()

    def options(self):
        s = self.settings
        # Frames always come at the riddle rate here, so a mode switch needs no
        # restart, and the code reader only gets as many as it's tuned for.
        return Options(mode=s["mode"], words=s["words"], end_gap=s["end_gap"], no_paste=not s["paste"],
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
        root = Sky()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        self.stack = QStackedWidget()
        layout.addWidget(self.build_header())
        layout.addLayout(self.build_nav())
        for build in (self.build_home, self.build_chat, self.build_overlay_page, self.build_settings_page):
            self.stack.addWidget(build())
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.build_footer())
        self.setCentralWidget(root)

    def build_header(self):
        bar = Glass(radius=18, padding=6, bar=True)
        row = bar.hbox(10)
        logo = QLabel()
        pixmap = orb(88)
        pixmap.setDevicePixelRatio(2)
        logo.setPixmap(pixmap)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label("MASSAB", "title"))
        self.status_label = label("", "subtitle")
        titles.addWidget(self.status_label)
        row.addWidget(logo)
        row.addLayout(titles)
        row.addStretch()

        modes = QHBoxLayout()
        modes.setSpacing(0)
        self.mode_buttons = QButtonGroup(self)
        self.mode_buttons.setExclusive(True)
        for i, mode in enumerate(MODES):
            button = QPushButton(mode.capitalize(), checkable=True)
            button.setProperty("mode", mode)
            button.setProperty("seg", "first" if i == 0 else "last" if i == len(MODES) - 1 else "mid")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.mode_buttons.addButton(button)
            modes.addWidget(button)
        self.mode_buttons.buttonClicked.connect(lambda button: self.select_mode(button.property("mode")))
        row.addLayout(modes)
        row.addSpacing(6)
        self.start_button = QPushButton("Start", objectName="go")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setMinimumWidth(96)
        self.start_button.clicked.connect(self.toggle_watching)
        row.addWidget(self.start_button)
        return bar

    def build_nav(self):
        row = QHBoxLayout()
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(4)
        self.nav = QButtonGroup(self)
        for i, name in enumerate(PAGES):
            button = QPushButton(name, objectName="nav", checkable=True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav.addButton(button, i)
            row.addWidget(button)
        self.nav.button(0).setChecked(True)
        self.nav.idClicked.connect(self.show_page)
        row.addStretch()
        return row

    def show_page(self, index):
        self.nav.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)
        if PAGES[index] == "Chat":
            self.chat_input.setFocus()

    def build_footer(self):
        bar = Glass(radius=14, padding=2, bar=True)
        row = bar.hbox(8)
        self.ai_light = Light()
        self.ai_label = label("", "muted")
        self.ai_button = QPushButton(objectName="small")
        self.ai_button.clicked.connect(self.toggle_ai)
        row.addWidget(self.ai_light)
        row.addWidget(self.ai_label)
        row.addWidget(self.ai_button)
        row.addStretch()
        self.vram_label = label("VRAM", "muted")
        self.vram_bar = QProgressBar(textVisible=False)
        self.vram_bar.setFixedWidth(140)
        row.addWidget(self.vram_label)
        row.addWidget(self.vram_bar)
        return bar

    # The pages.

    def page(self, scroll=False):
        """A page, and the layout to fill it with. Long pages scroll."""
        page = QWidget(objectName="page")
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        if not scroll:
            return page, box
        area = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.viewport().setAutoFillBackground(False)
        inner = QWidget(objectName="scrollInner")
        content = QVBoxLayout(inner)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        area.setWidget(inner)
        box.addWidget(area)
        return page, content

    def card(self, title=None, hint=None):
        card = Glass()
        box = card.vbox(6)
        if title:
            box.addWidget(label(title, "heading"))
        if hint:
            box.addWidget(label(hint, "hint", wrap=True))
        return card, box

    def setting_row(self, title, widget, hint=None):
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 3, 0, 3)
        line.setSpacing(14)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(label(title))
        if hint:
            text.addWidget(label(hint, "hint", wrap=True))
        line.addLayout(text, 1)
        line.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def add_rows(self, box, rows):
        for i, row in enumerate(rows):
            if i:
                box.addWidget(separator())
            box.addWidget(row)

    def build_home(self):
        page, box = self.page()
        card, c = self.card()
        top = QHBoxLayout()
        top.addWidget(label("LAST ANSWER", "caps"))
        self.kind_label = label("", "chip")
        self.kind_label.hide()
        top.addWidget(self.kind_label)
        top.addStretch()
        self.copy_button = QPushButton("Copy", objectName="small", enabled=False)
        self.copy_button.setToolTip("Copy the answer again")
        self.copy_button.clicked.connect(self.copy_answer)
        top.addWidget(self.copy_button)
        c.addLayout(top)

        self.answer_label = label("Nothing yet", "answer")
        self.answer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.answer_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        c.addWidget(self.answer_label)
        self.detail_label = label("Press Start, click the Codes box in Roblox, and MASSAB does the rest.", "muted",
                                  wrap=True)
        c.addWidget(self.detail_label)
        bottom = QHBoxLayout()
        self.stage_label = label("", "hint")
        self.guess_label = label("", "warning")
        self.guess_label.hide()
        bottom.addWidget(self.stage_label)
        bottom.addStretch()
        bottom.addWidget(self.guess_label)
        c.addLayout(bottom)
        box.addWidget(card)

        log_card, log_box = self.card()
        head = QHBoxLayout()
        head.addWidget(label("Activity", "heading"))
        head.addStretch()
        clear = QPushButton("Clear", objectName="small")
        head.addWidget(clear)
        log_box.addLayout(head)
        self.log_view = QPlainTextEdit(readOnly=True, maximumBlockCount=LOG_LINES, objectName="log")
        clear.clicked.connect(self.log_view.clear)
        log_box.addWidget(self.log_view, 1)
        box.addWidget(log_card, 1)
        return page

    def build_chat(self):
        page, box = self.page()
        card, c = self.card()
        top = QHBoxLayout()
        top.addWidget(label("Chat", "heading"))
        top.addWidget(label("with the AI on your PC", "hint"))
        top.addStretch()
        facts = self.bind("chat_facts", Toggle())
        facts.setToolTip("Look up the fact sheet when you ask about the game")
        top.addWidget(label("Fact sheet", "muted"))
        top.addWidget(facts)
        top.addSpacing(6)
        new = QPushButton("New chat", objectName="small")
        new.clicked.connect(self.new_chat)
        top.addWidget(new)
        c.addLayout(top)
        c.addWidget(separator())

        self.chat_banner = QWidget()
        banner = QHBoxLayout(self.chat_banner)
        banner.setContentsMargins(0, 2, 0, 2)
        self.chat_banner_text = label("", "banner", wrap=True)
        banner.addWidget(self.chat_banner_text, 1)
        self.chat_load_button = QPushButton("Load AI", objectName="primary")
        self.chat_load_button.clicked.connect(self.toggle_ai)
        banner.addWidget(self.chat_load_button)
        c.addWidget(self.chat_banner)

        self.chat_scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.viewport().setAutoFillBackground(False)
        inner = QWidget(objectName="scrollInner")
        self.chat_list = QVBoxLayout(inner)
        self.chat_list.setContentsMargins(2, 6, 8, 6)
        self.chat_list.setSpacing(8)
        self.chat_empty = self.build_chat_empty()
        self.chat_list.addWidget(self.chat_empty)
        self.chat_list.addStretch()
        self.chat_scroll.setWidget(inner)
        bar = self.chat_scroll.verticalScrollBar()
        bar.valueChanged.connect(lambda value: setattr(self, "chat_pinned", value >= bar.maximum() - 40))
        bar.rangeChanged.connect(lambda low, high: self.chat_pinned and bar.setValue(high))
        c.addWidget(self.chat_scroll, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.chat_input = ChatInput(objectName="chatInput")
        self.chat_input.setPlaceholderText("Ask anything. Enter sends, Shift+Enter adds a line.")
        self.chat_input.setFixedHeight(62)
        # Enter waits for a reply to finish; only the button stops one.
        self.chat_input.submitted.connect(lambda: self.chat_bubble is None and self.send_chat())
        self.send_button = QPushButton("Send", objectName="primary")
        self.send_button.setFixedSize(84, 62)
        self.send_button.clicked.connect(lambda: self.send_chat())
        row.addWidget(self.chat_input, 1)
        row.addWidget(self.send_button)
        c.addLayout(row)
        box.addWidget(card, 1)
        return page

    def build_chat_empty(self):
        empty = QWidget()
        box = QVBoxLayout(empty)
        box.setContentsMargins(20, 26, 20, 10)
        box.setSpacing(8)
        logo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        pixmap = orb(112, "")
        pixmap.setDevicePixelRatio(2)
        logo.setPixmap(pixmap)
        box.addWidget(logo)
        box.addWidget(label("Ask me anything", "heading"), 0, Qt.AlignmentFlag.AlignCenter)
        hint = label("I'm the same small model that solves riddles, running on your PC. Game questions get "
                     "facts from the fact sheet. A riddle on screen always comes first and cuts my reply short.",
                     "hint", wrap=True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(hint)
        box.addSpacing(6)
        for text in SUGGESTIONS:
            button = QPushButton(text, objectName="suggestion")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, text=text: self.send_chat(text))
            box.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        return empty

    def build_overlay_page(self):
        page, box = self.page(scroll=True)

        card, c = self.card("Reading area", "MASSAB only reads this part of the screen. Codes and riddles show up "
                                            "near the top middle of the game.")
        self.preview = AreaPreview()
        c.addWidget(self.preview)
        self.monitor_edit = self.bind("monitor", QSpinBox(minimum=1, maximum=8))
        self.region_edit = self.bind("region", QLineEdit(placeholderText="whole monitor"))
        self.region_edit.setMinimumWidth(170)
        self.add_rows(c, [self.setting_row("Monitor", self.monitor_edit, "1 is your main screen"),
                          self.setting_row("Area", self.region_edit, "x, y, width, height in pixels. Blank reads "
                                                                     "the whole monitor.")])
        buttons = QHBoxLayout()
        pick = QPushButton("Pick on screen", objectName="primary")
        pick.setToolTip("Drag a box over the part of the screen to read")
        pick.clicked.connect(self.pick_area)
        whole = QPushButton("Use whole monitor")
        whole.clicked.connect(lambda: self.use_area(""))
        buttons.addWidget(pick)
        buttons.addWidget(whole)
        buttons.addStretch()
        c.addLayout(buttons)
        self.area_card = card
        box.addWidget(card)

        card, c = self.card("On-screen box", "Drawn over the game to show what MASSAB reads. It can't be clicked, "
                                             "and MASSAB can't see it, so it never gets in the way.")
        self.overlay_edit = self.bind("overlay", self.combo(OVERLAY_WHEN.items()))
        self.color_button = QPushButton(objectName="swatch")
        self.color_button.clicked.connect(self.pick_color)
        self.add_rows(c, [
            self.setting_row("Show the box", self.overlay_edit),
            self.setting_row("Mark the code and riddle zones", self.bind("overlay_zones", Toggle()),
                             "Dashed: where code lines are found. Dotted: where riddle rows are."),
            self.setting_row("Highlight text as it's read", self.bind("overlay_reads", Toggle()),
                             "Only while watching"),
            self.setting_row("Label with what it read", self.bind("overlay_labels", Toggle())),
            self.setting_row("Color", self.color_button),
            self.setting_row("Line width", self.bind("overlay_width", QSpinBox(minimum=1, maximum=6, suffix=" px"))),
            self.setting_row("Opacity", self.slider("overlay_opacity", 20, 100)),
        ])
        box.addWidget(card)

        card, c = self.card("Game strip", "The answer, how long it took and whether it pasted, in a corner of "
                                          "the game.")
        self.hud_edit = self.bind("hud", Toggle())
        self.add_rows(c, [
            self.setting_row("Show the strip", self.hud_edit),
            self.setting_row("Position", self.bind("hud_corner", self.combo((corner, corner.capitalize()) for corner in HUD_CORNERS))),
            self.setting_row("Size", self.bind("hud_size", self.combo((size, size.capitalize()) for size in HUD_SIZES))),
            self.setting_row("Background", self.slider("hud_opacity", 0, 100), "How solid its glass is"),
        ])
        box.addWidget(card)
        box.addStretch()
        self.show_color()
        return page

    def build_settings_page(self):
        page, box = self.page(scroll=True)
        self.lock_note = label("Stop watching to change the greyed-out settings.", "warning")
        self.lock_note.hide()
        box.addWidget(self.lock_note, 0, Qt.AlignmentFlag.AlignLeft)

        card, c = self.card("Codes")
        self.words_edit = self.bind("words", QSpinBox(minimum=0, maximum=10))
        self.gap_edit = self.bind("end_gap", QDoubleSpinBox(minimum=1, maximum=30, suffix=" s"))
        self.add_rows(c, [self.setting_row("Copy a code after this many words", self.words_edit,
                                           "It's updated if more come. 0 waits for the whole code."),
                          self.setting_row("A code ends after this long", self.gap_edit,
                                           "With no new word in that time")])
        self.codes_card = card
        box.addWidget(card)

        card, c = self.card("Pasting")
        self.paste_edit = self.bind("paste", Toggle())
        self.window_edit = self.bind("paste_window", QLineEdit())
        self.window_edit.setMinimumWidth(150)
        self.delay_edit = self.bind("key_delay_ms", QSpinBox(minimum=5, maximum=60, suffix=" ms"))
        self.add_rows(c, [self.setting_row("Paste automatically", self.paste_edit, "Otherwise answers are only copied"),
                          self.setting_row("Only paste into the window titled", self.window_edit),
                          self.setting_row("Wait after each pasted key", self.delay_edit,
                                           "Raise it if pastes go missing or come out wrong")])
        self.paste_card = card
        box.addWidget(card)

        card, c = self.card("AI")
        self.model_edit = self.bind("model", self.combo((m, MODEL_NAMES.get(m, m)) for m in MODELS))
        facts = QPushButton("Open")
        facts.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(FACTS_PATH)))
        self.add_rows(c, [self.setting_row("Model", self.model_edit, "The 2B one needs: setup_ai.py --model 2b"),
                          self.setting_row("Load the AI when MASSAB opens", self.bind("ai_autoload", Toggle()),
                                           "So the first riddle doesn't wait for it"),
                          self.setting_row("Fact sheet", facts, "What riddle and chat answers come from. Changes "
                                                                "apply the next time the AI loads.")])
        box.addWidget(card)

        card, c = self.card("Controls")
        self.hotkey_edit = self.bind("hotkey", self.combo((key, key) for key in HOTKEYS))
        self.add_rows(c, [self.setting_row("Switch modes with", self.hotkey_edit, "Works while the game has focus")])
        box.addWidget(card)
        box.addStretch()
        return page

    # Controls bound to a setting.

    def combo(self, items):
        widget = QComboBox()
        for value, text in items:
            widget.addItem(text, value)
        return widget

    def slider(self, key, low, high):
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal, minimum=low, maximum=high)
        slider.setFixedWidth(150)
        value = label("", "muted")
        value.setFixedWidth(36)
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
        elif isinstance(widget, QComboBox):
            widget.setCurrentIndex(max(0, widget.findData(value)))
            widget.currentIndexChanged.connect(lambda i: self.set(key, widget.itemData(i)))
        elif isinstance(widget, QLineEdit):
            widget.setText(value)
            widget.editingFinished.connect(lambda: self.set(key, widget.text().strip()))
        return widget

    # --- settings -------------------------------------------------------------

    def set(self, key, value):
        old, self.settings[key] = self.settings[key], value
        if key == "hotkey" and value != old:
            self.hotkey.set_key(value)
            self.show_status()
        elif key == "model" and value != old:
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
        self.region_edit.setToolTip("Should look like 0,120,1280,720" if bad else "")

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

    def pick_color(self):
        color = QColorDialog.getColor(self.settings["overlay_color"], self, "Box color")
        if color.isValid():
            self.set("overlay_color", color.name())
            self.show_color()

    def show_color(self):
        self.color_button.setStyleSheet(
            f"QPushButton#swatch {{ background: {self.settings['overlay_color']}; border: 1px solid #4f7394;"
            f" border-radius: 8px; min-width: 54px; min-height: 20px; }}")

    def find_monitors(self):
        try:
            return monitor_rects()
        except Exception:   # no capture at all, e.g. a remote session
            return []

    def screens_changed(self, *_):
        self.monitors = self.find_monitors()
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
            caption = f"{area[2]} x {area[3]}" + ("" if s["region"] else f"  ·  monitor {s['monitor']}")
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

    # --- modes ----------------------------------------------------------------

    def select_mode(self, mode):
        self.settings["mode"] = mode
        for button in self.mode_buttons.buttons():
            button.setChecked(button.property("mode") == mode)
        self.engine.set_mode(mode)
        self.hud.show_mode(mode)
        self.show_status()
        self.save()

    def next_mode(self):
        self.select_mode(MODES[(MODES.index(self.settings["mode"]) + 1) % len(MODES)])
        self.log(f"Mode: {self.settings['mode']}")

    def show_status(self):
        s = self.settings
        state = "Watching" if self.watching else "Stopped"
        self.status_label.setText(f"{state} · {s['mode'].capitalize()} mode · {s['hotkey']} to switch")
        for button in self.mode_buttons.buttons():
            button.setToolTip(f"{MODE_TIPS[button.property('mode')]}. {s['hotkey']} switches modes from the game.")

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
        self.lock_note.setVisible(watching)
        self.start_button.setText("Stop" if watching else "Start")
        self.start_button.setProperty("running", watching)
        self.start_button.style().polish(self.start_button)
        self.show_status()
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
            text, button, light = "AI not installed (about 3 GB)", "Install AI", "gray"
        else:
            text, button, light = {"off": ("AI off", "Load AI", "gray"), "ready": ("AI ready", "Unload AI", "green"),
                                   "loading": ("AI loading", "Load AI", "amber"),
                                   "installing": ("AI downloading", "Install AI", "amber")}[state]
        self.ai_label.setText(text)
        self.ai_light.set("", light)
        self.ai_button.setText(button)
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
        self.vram_label.setText(f"VRAM {used / 1024:.1f} of {total / 1024:.1f} GB" + (", running low" if low else ""))
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
                                          "Chatting needs the AI, which is about a 3 GB download.")
            self.chat_load_button.setText("Load AI" if installed else "Install AI")
            self.chat_load_button.show()

    def bubble_width(self):
        return max(240, int(self.chat_scroll.viewport().width() * 0.8))

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
        limit = self.bubble_width() - 26
        doc.setTextWidth(limit)
        bubble.text.setMinimumWidth(min(limit, int(doc.idealWidth()) + 4))
        bubble.setMaximumWidth(self.bubble_width())

    def add_bubble(self, role, text):
        self.chat_empty.hide()
        bubble = QFrame(objectName="bubbleUser" if role == "user" else "bubbleAi")
        inner = QVBoxLayout(bubble)
        inner.setContentsMargins(12, 8, 12, 8)
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
            holder.deleteLater()
        self.bubbles.clear()
        self.chat_empty.show()
        self.send_button.setText("Send")
        self.show_chat_state()

    # --- events ---------------------------------------------------------------

    def log(self, text):
        self.log_view.appendPlainText(f"{time.strftime('%H:%M:%S')}  {text}")

    def show_answer(self, text, kind, detail="", stage="", guess=""):
        self.answer_label.setText(text)
        self.fit_answer()
        self.kind_label.setText(kind)
        self.kind_label.setVisible(bool(kind))
        self.detail_label.setText(detail)
        self.stage_label.setText(stage)
        self.guess_label.setText(guess)
        self.guess_label.setVisible(bool(guess))
        self.copy_button.setEnabled(True)

    def fit_answer(self):
        """Shrink a long answer until it fits, rather than cutting it off."""
        text, width = self.answer_label.text(), max(120, self.answer_label.width())
        font = self.answer_label.font()
        for size in range(24, 10, -1):
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
            self.hud.show_result(e["code"], state="building")
        elif kind == "code":
            self.show_answer(e["code"], "CODE", note_text(e["note"]))
            self.log(f"Code: {e['code']}{e['note']}")
            self.hud.show_result(e["code"], state="pasted" if was_pasted(e["note"]) else "copied")
        elif kind == "done":
            self.log(f"Done: {e['code']}")
        elif kind == "riddle":
            self.log(f"Riddle: {e['text']}")
            self.detail_label.setText(e["text"])
            self.hud.show_result("Solving", state="")
        elif kind == "answer":
            self.on_answer(e)
        elif kind == "no_answer":
            self.log(f"No answer from the model: {e['solved'].reply!r}")
            self.hud.show_result("No answer")
        elif kind == "rows":
            if self.watching:
                self.overlay.set_reads(e["boxes"])
        elif kind == "mode":
            self.log(f"Now in {e['mode']} mode")
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
        stage = f"{total:.2f} s total  ·  read {read:.2f}  ·  AI {solved.seconds:.2f}  ·  paste {paste:.2f}"
        guess = "Guess: no fact matched this riddle" if solved.guess else ""
        self.show_answer(solved.answer, "RIDDLE", solved.riddle, stage, guess)
        self.log(f"Answer: {solved.answer}{e['note']}  [{total:.2f} s]" + ("  (guess)" if solved.guess else ""))
        state = "same" if e["unchanged"] else "pasted" if was_pasted(e["note"]) else "copied"
        self.hud.show_result(solved.answer, f"{total:.2f}s", "GUESS" if solved.guess else state, solved.guess)

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
        self.hotkey.stop()
        self.engine.stop_ai()
        self.hud.close()
        self.overlay.close()
        self.save()
        super().closeEvent(event)


def check():
    """Try every part without opening a window, to prove a packaged build has
    what it needs. A windowed exe has no console, so results go to check.txt."""
    lines = []
    engine = Engine(Options(mode="riddle", no_copy=True), lambda kind, now, **e: lines.append(f"{kind}: {e}"))
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
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    app.setStyleSheet(style_sheet())
    app.setWindowIcon(QIcon(orb(64)))
    panel = Panel(load_settings())
    panel.show()
    # A riddle can't wait for the model to load, so start on that right away.
    if panel.settings["ai_autoload"] and ai_installed(panel.settings["model"]):
        panel.load_ai()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
