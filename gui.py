"""MASSAB's window: a control panel, and a small strip that sits over the game.

Usage:
    python gui.py

Pasting only works while Roblox is the active window, so nothing here may take
focus during play: the strip can't be clicked or focused, and modes can be
switched from the game with a global hotkey.
"""
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

import cv2
import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)

import setup_ai
from codereader import frames_from_screen
from engine import CODE_FPS, MODES, RIDDLE_FPS, Engine, Options
from riddle import gpu_memory, load_system_prompt
from setup_ai import APP_DIR, DEFAULT_MODEL, MODELS, ai_installed

SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
DEFAULTS = {
    "mode": "auto", "words": 3, "end_gap": 6.0, "paste": True, "paste_window": "Roblox", "key_delay_ms": 15, "monitor": 1,
    "region": "", "hotkey": "F8", "hud": True, "model": DEFAULT_MODEL, "system_prompt": None,
}
LOW_VRAM_MIB = 500
VRAM_CHECK_MS = 3000
LOG_LINES = 1000

STYLE = """
* { font-family: "Segoe UI"; font-size: 10pt; color: #e6e8ec; }
QMainWindow, QWidget#root { background: #16181d; }
QFrame#card { background: #1f2229; border-radius: 8px; }
QLabel#answer { font-size: 22pt; font-weight: 600; }
QLabel#muted { color: #9aa1ad; }
QLabel#warning { color: #fbbf24; }
QPushButton { background: #2a2e37; border: none; border-radius: 6px; padding: 7px 14px; }
QPushButton:hover { background: #343945; }
QPushButton:checked, QPushButton#primary { background: #3b6fd8; }
QPushButton:disabled { background: #22252c; color: #666c78; }
QTabWidget::pane { border: none; background: #1f2229; border-radius: 8px; }
QTabBar::tab { background: transparent; padding: 7px 14px; color: #9aa1ad; }
QTabBar::tab:selected { color: #e6e8ec; border-bottom: 2px solid #3b6fd8; }
QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #16181d; border: 1px solid #2f333d; border-radius: 6px; padding: 5px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #343945; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QProgressBar { background: #16181d; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #3b6fd8; border-radius: 4px; }
QProgressBar[low="true"]::chunk { background: #f87171; }
QFrame#hud { background: rgba(16, 18, 22, 215); border-radius: 8px; }
QFrame#hud QLabel { font-size: 11pt; }
QLabel#hudMode { color: #7fa8ff; font-weight: 600; }
QLabel#hudAnswer { font-weight: 600; }
QLabel#hudState { color: #4ade80; }
QLabel#hudState[guess="true"] { color: #fbbf24; }
"""


def load_settings(path=SETTINGS_PATH):
    """Saved settings over the defaults. A broken file just means defaults."""
    settings = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        settings.update({key: value for key, value in saved.items() if key in DEFAULTS})
    except (OSError, ValueError, AttributeError):
        pass
    if settings["mode"] not in MODES:
        settings["mode"] = DEFAULTS["mode"]
    if settings["model"] not in MODELS:
        settings["model"] = DEFAULTS["model"]
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


def make_passive(widget):
    """Stop a window ever taking focus from the game, and keep it out of screen
    captures so MASSAB can't read its own text."""
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


class Hud(QWidget):
    """The strip over the game. It can't be clicked and never takes focus."""

    MARGIN = 16

    def __init__(self):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.WindowTransparentForInput)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        frame = QFrame(objectName="hud")
        row = QHBoxLayout(frame)
        row.setContentsMargins(12, 7, 12, 7)
        row.setSpacing(12)
        self.mode = QLabel(objectName="hudMode")
        self.answer = QLabel("Waiting", objectName="hudAnswer")
        self.seconds = QLabel(objectName="muted")
        self.state = QLabel(objectName="hudState")
        for label in (self.mode, self.answer, self.seconds, self.state):
            row.addWidget(label)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

    def showEvent(self, event):
        super().showEvent(event)
        make_passive(self)
        self.place()

    def place(self):
        """Bottom left, well clear of the overlay at the top of the screen."""
        self.adjustSize()
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.left() + self.MARGIN, area.bottom() - self.height() - self.MARGIN)

    def show_mode(self, mode):
        self.mode.setText(f"[{mode.upper()}]")
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


class Panel(QMainWindow):
    """The control panel. Engine events arrive on other threads, so they cross
    to the window's thread through a signal."""

    event = Signal(str, object)

    def __init__(self, settings, settings_path=SETTINGS_PATH):
        super().__init__()
        self.settings = settings
        self.settings_path = settings_path
        self.worker = None
        self.ai_state = "off"
        self.setWindowTitle("MASSAB")
        self.resize(560, 640)

        self.engine = Engine(self.options(), lambda kind, now, **fields: self.event.emit(kind, fields))
        self.event.connect(self.on_event)
        self.hud = Hud()
        self.hotkey = Hotkey()
        self.hotkey.pressed.connect(self.next_mode)
        self.hotkey.failed.connect(lambda key: self.log(f"Couldn't use {key} as the hotkey, another app has it."))

        self.build()
        self.select_mode(settings["mode"])
        self.hotkey.set_key(settings["hotkey"])
        self.show_ai("off")
        self.hud.show_mode(self.engine.next_mode)
        if settings["hud"]:
            self.hud.show()

        self.vram_timer = QTimer(self, interval=VRAM_CHECK_MS, timeout=self.check_vram)
        self.vram_timer.start()
        self.check_vram()

    def options(self):
        s = self.settings
        # Frames always come at the riddle rate here, so a mode switch needs no
        # restart, and the code reader only gets as many as it's tuned for.
        return Options(mode=s["mode"], words=s["words"], end_gap=s["end_gap"], no_paste=not s["paste"],
                       paste_window=s["paste_window"], key_delay=s["key_delay_ms"] / 1000, model=s["model"],
                       system_prompt=s["system_prompt"],
                       code_step=round(RIDDLE_FPS / CODE_FPS))

    # --- building the window --------------------------------------------------

    def build(self):
        root = QWidget(objectName="root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(self.build_controls())
        layout.addWidget(self.build_result())
        layout.addWidget(self.build_tabs(), 1)
        self.setCentralWidget(root)

    def build_controls(self):
        row = QHBoxLayout()
        self.mode_buttons = QButtonGroup(self)
        self.mode_buttons.setExclusive(True)
        for mode in MODES:
            button = QPushButton(mode.capitalize(), checkable=True)
            button.setProperty("mode", mode)
            self.mode_buttons.addButton(button)
            row.addWidget(button)
        self.mode_buttons.buttonClicked.connect(lambda button: self.select_mode(button.property("mode")))
        row.addStretch()
        self.start_button = QPushButton("Start", objectName="primary")
        self.start_button.clicked.connect(self.toggle_watching)
        row.addWidget(self.start_button)
        return row

    def build_result(self):
        card = QFrame(objectName="card")
        box = QVBoxLayout(card)
        status = QHBoxLayout()
        self.watch_label = QLabel("Stopped", objectName="muted")
        self.ai_label = QLabel(objectName="muted")
        self.ai_button = QPushButton()
        self.ai_button.clicked.connect(self.toggle_ai)
        status.addWidget(self.watch_label)
        status.addStretch()
        status.addWidget(self.ai_label)
        status.addWidget(self.ai_button)
        box.addLayout(status)

        self.answer_label = QLabel("Nothing yet", objectName="answer")
        self.answer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.answer_label)
        self.detail_label = QLabel(objectName="muted")
        self.detail_label.setWordWrap(True)
        box.addWidget(self.detail_label)
        self.stage_label = QLabel(objectName="muted")
        box.addWidget(self.stage_label)
        self.guess_label = QLabel(objectName="warning")
        box.addWidget(self.guess_label)

        vram = QHBoxLayout()
        self.vram_label = QLabel("VRAM", objectName="muted")
        self.vram_bar = QProgressBar(textVisible=False)
        vram.addWidget(self.vram_label)
        vram.addWidget(self.vram_bar, 1)
        box.addLayout(vram)
        return card

    def build_tabs(self):
        tabs = QTabWidget()
        self.log_view = QPlainTextEdit(readOnly=True, maximumBlockCount=LOG_LINES)
        tabs.addTab(self.log_view, "Log")
        tabs.addTab(self.build_prompt_tab(), "System prompt")
        self.settings_tab = self.build_settings_tab()
        tabs.addTab(self.settings_tab, "Settings")
        return tabs

    def build_prompt_tab(self):
        page = QWidget()
        box = QVBoxLayout(page)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlainText(self.settings["system_prompt"] or load_system_prompt())
        self.prompt_edit.textChanged.connect(self.check_prompt)
        box.addWidget(self.prompt_edit, 1)
        self.prompt_warning = QLabel("The reply has to contain \"ANSWER:\", or MASSAB can't find the answer.",
                                     objectName="warning", visible=False)
        box.addWidget(self.prompt_warning)
        row = QHBoxLayout()
        save = QPushButton("Save", objectName="primary")
        save.clicked.connect(self.save_prompt)
        reset = QPushButton("Reset to default")
        reset.clicked.connect(self.reset_prompt)
        row.addWidget(save)
        row.addWidget(reset)
        row.addStretch()
        box.addLayout(row)
        return page

    def build_settings_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        s = self.settings
        self.words_edit = QSpinBox(minimum=0, maximum=10, value=s["words"])
        self.gap_edit = QDoubleSpinBox(minimum=1, maximum=30, value=s["end_gap"], suffix=" s")
        self.paste_edit = QCheckBox(checked=s["paste"])
        self.window_edit = QLineEdit(s["paste_window"])
        self.delay_edit = QSpinBox(minimum=5, maximum=60, value=s["key_delay_ms"], suffix=" ms")
        self.monitor_edit = QSpinBox(minimum=1, maximum=8, value=s["monitor"])
        self.region_edit = QLineEdit(s["region"], placeholderText="x,y,w,h (blank = whole monitor)")
        self.hotkey_edit = QComboBox()
        self.hotkey_edit.addItems([f"F{n}" for n in range(1, 13)])
        self.hotkey_edit.setCurrentText(s["hotkey"])
        self.hud_edit = QCheckBox(checked=s["hud"])
        self.model_edit = QComboBox()
        self.model_edit.addItems(list(MODELS))
        self.model_edit.setCurrentText(s["model"])

        form.addRow("Copy a code after this many words", self.words_edit)
        form.addRow("A code ends after this long", self.gap_edit)
        form.addRow("Paste automatically", self.paste_edit)
        form.addRow("Only paste into the window titled", self.window_edit)
        form.addRow("Wait after each pasted key", self.delay_edit)
        form.addRow("Monitor", self.monitor_edit)
        form.addRow("Watch only this area", self.region_edit)
        form.addRow("Mode hotkey", self.hotkey_edit)
        form.addRow("Show the strip over the game", self.hud_edit)
        form.addRow("AI model", self.model_edit)

        for edit, signal in [(self.words_edit, "valueChanged"), (self.gap_edit, "valueChanged"),
                             (self.paste_edit, "toggled"), (self.window_edit, "editingFinished"),
                             (self.delay_edit, "valueChanged"),
                             (self.monitor_edit, "valueChanged"), (self.region_edit, "editingFinished"),
                             (self.hotkey_edit, "currentTextChanged"), (self.hud_edit, "toggled"),
                             (self.model_edit, "currentTextChanged")]:
            getattr(edit, signal).connect(self.read_settings)
        return page

    # --- settings -------------------------------------------------------------

    def read_settings(self):
        s = self.settings
        hotkey, model = s["hotkey"], s["model"]
        s.update(words=self.words_edit.value(), end_gap=self.gap_edit.value(), paste=self.paste_edit.isChecked(),
                 paste_window=self.window_edit.text(), key_delay_ms=self.delay_edit.value(),
                 monitor=self.monitor_edit.value(),
                 region=self.region_edit.text(), hotkey=self.hotkey_edit.currentText(),
                 hud=self.hud_edit.isChecked(), model=self.model_edit.currentText())
        self.hud.setVisible(s["hud"])
        if s["hotkey"] != hotkey:
            self.hotkey.set_key(s["hotkey"])
        if s["model"] != model:
            self.engine.options.model = s["model"]
            self.engine.stop_ai()
            self.show_ai("off")
        self.save()

    def save(self):
        try:
            save_settings(self.settings, self.settings_path)
        except OSError as e:
            self.log(f"Couldn't save settings: {e}")

    def check_prompt(self):
        self.prompt_warning.setVisible("ANSWER:" not in self.prompt_edit.toPlainText())

    def save_prompt(self):
        prompt = self.prompt_edit.toPlainText()
        self.settings["system_prompt"] = None if prompt == load_system_prompt() else prompt
        self.engine.set_system_prompt(prompt)
        self.save()
        self.log("System prompt saved.")

    def reset_prompt(self):
        self.prompt_edit.setPlainText(load_system_prompt())
        self.save_prompt()

    # --- modes ----------------------------------------------------------------

    def select_mode(self, mode):
        self.settings["mode"] = mode
        for button in self.mode_buttons.buttons():
            button.setChecked(button.property("mode") == mode)
        self.engine.set_mode(mode)
        self.hud.show_mode(mode)
        self.save()

    def next_mode(self):
        self.select_mode(MODES[(MODES.index(self.settings["mode"]) + 1) % len(MODES)])
        self.log(f"Mode: {self.settings['mode']}")

    # --- watching -------------------------------------------------------------

    def toggle_watching(self):
        if self.worker and self.worker.is_alive():
            self.start_button.setEnabled(False)
            self.watch_label.setText("Stopping")
            self.engine.stop()
            return
        try:
            region = parse_region(self.settings["region"])
        except ValueError:
            self.log("The area to watch has to look like x,y,w,h, for example 0,120,1280,720.")
            return
        prompt = self.engine.options.system_prompt
        self.engine.options = self.options()
        self.engine.options.system_prompt = prompt
        self.engine.reset()
        self.engine.stopping.clear()
        self.settings_tab.setEnabled(False)
        self.start_button.setText("Stop")
        self.watch_label.setText("Watching")
        self.worker = threading.Thread(target=self.watch, args=(region,), daemon=True)
        self.worker.start()

    def watch(self, region):
        """Runs on the worker thread. Anything going wrong has to reach the
        window, or watching would just silently stop."""
        try:
            self.engine.run(frames_from_screen(RIDDLE_FPS, self.settings["monitor"], region, self.engine.screen_blocked))
        except Exception as e:
            self.event.emit("error", {"message": f"Watching stopped: {e}"})
        self.event.emit("stopped", {})

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
            self.event.emit("error", {"message": f"Couldn't install the AI: {e}"})
            self.event.emit("ai", {"state": "off"})
            return
        self.event.emit("installed", {})

    def show_ai(self, state):
        self.ai_state = state
        if state == "off" and not ai_installed(self.settings["model"]):
            text, button = "AI: not installed (about 3 GB)", "Install AI"
        else:
            text, button = {"off": ("AI: off", "Load AI"), "ready": ("AI: ready", "Unload AI"),
                            "loading": ("AI: loading", "Load AI"),
                            "installing": ("AI: downloading", "Install AI")}[state]
        self.ai_label.setText(text)
        self.ai_button.setText(button)
        self.ai_button.setEnabled(state in ("off", "ready"))

    def check_vram(self):
        threading.Thread(target=lambda: self.event.emit("vram", {"memory": gpu_memory()}), daemon=True).start()

    def show_vram(self, memory):
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

    # --- events ---------------------------------------------------------------

    def log(self, text):
        self.log_view.appendPlainText(f"{time.strftime('%H:%M:%S')}  {text}")

    def show_answer(self, text, detail=""):
        self.answer_label.setText(text)
        self.detail_label.setText(detail)
        self.stage_label.setText("")
        self.guess_label.setText("")

    def on_event(self, kind, e):
        if kind == "building":
            self.log(f"Building: {e['code']}")
            self.hud.show_result(e["code"], state="building")
        elif kind == "code":
            self.show_answer(e["code"], "Code")
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
        elif kind == "error":
            self.log(f"Problem: {e['message']}")
        elif kind == "stopped":
            self.settings_tab.setEnabled(True)
            self.start_button.setEnabled(True)
            self.start_button.setText("Start")
            self.watch_label.setText("Stopped")

    def on_answer(self, e):
        solved, total, paste = e["solved"], e["total"], e["paste"]
        read = max(0.0, total - solved.seconds - paste)
        self.answer_label.setText(solved.answer)
        self.detail_label.setText(solved.riddle)
        self.stage_label.setText(f"{total:.2f} s total    read {read:.2f}    AI {solved.seconds:.2f}    paste {paste:.2f}")
        self.guess_label.setText("Guess: no fact matched this riddle" if solved.guess else "")
        self.log(f"Answer: {solved.answer}{e['note']}  [{total:.2f} s]" + ("  (guess)" if solved.guess else ""))
        state = "same" if e["unchanged"] else "pasted" if was_pasted(e["note"]) else "copied"
        self.hud.show_result(solved.answer, f"{total:.2f}s", "GUESS" if solved.guess else state, solved.guess)

    def closeEvent(self, event):
        self.vram_timer.stop()
        self.engine.stop()
        if self.worker:
            self.worker.join(2)
        self.hotkey.stop()
        self.engine.stop_ai()
        self.hud.close()
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
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    panel = Panel(load_settings())
    panel.show()
    # A riddle can't wait for the model to load, so start on that right away.
    if ai_installed(panel.settings["model"]):
        panel.load_ai()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
