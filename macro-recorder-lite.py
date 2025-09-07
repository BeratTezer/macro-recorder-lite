#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Macro Recorder Lite - AutoKeyPad (Kalıcı Makro + Düzeltmeler)
- Toggle tuşu: "  (tırnak, Shift+2)  → debounce'lu
- 10 satır (tuş/mouse + basılma süresi ms)
- Tekrar sayısı (0 = sonsuz)
- Son makroyu otomatik kaydeder, JSON bozulursa yedekten döner
- Basışlar dilimlenir (responsive stop)
"""
import sys
import time
import json
import shutil
import threading
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QGridLayout, QMessageBox
)
from PyQt5.QtCore import QEvent, Qt, pyqtSignal, QObject

from pynput.keyboard import (
    Controller as KeyboardController,
    Listener as KeyboardListener,
    Key, KeyCode
)
from pynput.mouse import (
    Controller as MouseController,
    Button as MouseButton
)

keyboard = KeyboardController()
mouse = MouseController()

running_evt = threading.Event()
stop_evt = threading.Event()

# Toggle key
TOGGLE_KEY = KeyCode.from_char('"')
TOGGLE_DEBOUNCE_MS = 250

STATE_PATH = Path.home() / ".keyboardSupport.json"
STATE_BAK_PATH = Path.home() / ".keyboardSupport.bak.json"

# Limits
MAX_MS = 60000  # 60 sec
SLICE_MS = 50


# ---------------- Supporter Functions ----------------
def normalize(s: str) -> str:
    return (s or "").strip().lower()


def clamp_int(value: str, default: int, min_v: int, max_v: int) -> int:
    try:
        n = int(value.strip())
        if n < min_v:
            return min_v
        if n > max_v:
            return max_v
        return n
    except Exception:
        return default


def parse_key(token: str) -> Optional[object]:
    t = normalize(token)
    if not t:
        return None

    if t.startswith('f') and t[1:].isdigit():
        n = int(t[1:])
        if 1 <= n <= 24 and hasattr(Key, f'f{n}'):
            return getattr(Key, f'f{n}')

    aliases = {
        'enter': Key.enter, 'return': Key.enter,
        'space': Key.space,
        'tab': Key.tab,
        'esc': Key.esc, 'escape': Key.esc,
        'backspace': Key.backspace,
        'delete': Key.delete, 'del': Key.delete,
        'home': Key.home, 'end': Key.end,
        'pageup': Key.page_up, 'page_up': Key.page_up,
        'pagedown': Key.page_down, 'page_down': Key.page_down,
        'up': Key.up, 'down': Key.down, 'left': Key.left, 'right': Key.right,
    }
    if t in aliases:
        return aliases[t]

    if len(t) == 1:
        return KeyCode.from_char(t)

    return None


def sliced_sleep(total_ms: int) -> bool:
    """Toplam süreyi küçük dilimlerle uyur; stop gelirse erken döner.
    Returns True if interrupted."""
    remain = max(0, total_ms)
    while remain > 0:
        if stop_evt.is_set() or not running_evt.is_set():
            return True
        chunk = min(SLICE_MS, remain)
        time.sleep(chunk / 1000.0)
        remain -= chunk
    return False


def press_keyboard(token: str, duration_ms: int):
    key_obj = parse_key(token)
    if key_obj is None:
        return
    try:
        keyboard.press(key_obj)
        interrupted = sliced_sleep(duration_ms)
    finally:
        try:
            keyboard.release(key_obj)
        except Exception:
            pass
    return interrupted


def press_mouse(token: str, duration_ms: int):
    t = normalize(token)
    btn = None
    if t == 'mouse.left':
        btn = MouseButton.left
    elif t == 'mouse.right':
        btn = MouseButton.right
    elif t == 'mouse.middle':
        btn = MouseButton.middle
    if btn is None:
        return
    try:
        mouse.press(btn)
        interrupted = sliced_sleep(duration_ms)
    finally:
        try:
            mouse.release(btn)
        except Exception:
            pass
    return interrupted


# --------------- UI <-> Thread Signals ---------------
class UiSignals(QObject):
    status = pyqtSignal(str)
    buttons = pyqtSignal(bool)  # True => running


signals = UiSignals()


# --------------- Main App ---------------
class MayinTarlasi(QWidget):
    def __init__(self):
        super().__init__()
        self.last_toggle_ts = 0.0
        self.k_listener = None
        self.initUI()
        self.hook_listeners()
        self.load_state_safe()

        signals.status.connect(self.lbl_status.setText)
        signals.buttons.connect(self._set_buttons_running)

    def initUI(self):
        layout = QGridLayout()

        title = QLabel(
            'Toggle tuşu: "  (Shift+2) — Yönetici yetkisi gerekebilir')
        title.setStyleSheet("font-weight:600;")
        layout.addWidget(title, 0, 0, 1, 3)

        self.lbl_status = QLabel("Durum: Hazır")
        layout.addWidget(self.lbl_status, 1, 0, 1, 3)

        layout.addWidget(QLabel("Kaç kere tekrar (0 = sonsuz)"), 2, 0, 1, 2)
        self.repeat_input = QLineEdit()
        self.repeat_input.setPlaceholderText("örn: 5")
        layout.addWidget(self.repeat_input, 2, 2, 1, 1)

        self.keys = []
        self.times = []

        for i in range(10):
            layout.addWidget(QLabel(f"{i+1}."), i+3, 0)

            key_input = QLineEdit()
            key_input.setPlaceholderText("örn: a, enter, f2, mouse.left")
            layout.addWidget(key_input, i+3, 1)
            self.keys.append(key_input)

            time_input = QLineEdit()
            time_input.setPlaceholderText("ms (0-60000)")
            layout.addWidget(time_input, i+3, 2)
            self.times.append(time_input)

        self.start_btn = QPushButton("Başlat (\" ile de başlar)")
        self.start_btn.clicked.connect(self.start_press)
        layout.addWidget(self.start_btn, 13, 1)

        self.stop_btn = QPushButton("Durdur (\" ile de durur)")
        self.stop_btn.clicked.connect(self.stop_press)
        layout.addWidget(self.stop_btn, 13, 2)

        self.setLayout(layout)
        self.setWindowTitle("Macro Recorder Lite")
        self.setMinimumWidth(760)

        def hook_save(_):
            self.save_state_safe()
        self.repeat_input.textChanged.connect(hook_save)
        for w in (self.keys + self.times):
            w.textChanged.connect(hook_save)

    # ---------- Listeners ----------
    def hook_listeners(self):
        # Tek global klavye dinleyici
        self.k_listener = KeyboardListener(on_press=self.global_keypress)
        self.k_listener.start()

    def unhook_listeners(self):
        try:
            if self.k_listener:
                self.k_listener.stop()
        except Exception:
            pass
        self.k_listener = None

    # ---------- State (save/load) ----------
    def save_state_safe(self):
        data = {
            "repeat": self.repeat_input.text(),
            "rows": [
                {"key": self.keys[i].text(), "ms": self.times[i].text()}
                for i in range(10)
            ],
        }
        try:
            if STATE_PATH.exists():
                shutil.copyfile(STATE_PATH, STATE_BAK_PATH)
        except Exception:
            pass
        try:
            STATE_PATH.write_text(json.dumps(
                data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            try:
                if STATE_BAK_PATH.exists():
                    shutil.copyfile(STATE_BAK_PATH, STATE_PATH)
            except Exception:
                pass

    def load_state_safe(self):
        try:
            if STATE_PATH.exists():
                data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            elif STATE_BAK_PATH.exists():
                data = json.loads(STATE_BAK_PATH.read_text(encoding="utf-8"))
            else:
                return
        except Exception:
            return

        self.repeat_input.setText(str(data.get("repeat", "") or ""))
        rows = data.get("rows", [])
        for i in range(min(10, len(rows))):
            self.keys[i].setText(rows[i].get("key", ""))
            self.times[i].setText(rows[i].get("ms", ""))

    def closeEvent(self, event: QEvent):
        self.save_state_safe()
        self.unhook_listeners()
        stop_evt.set()
        running_evt.clear()
        return super().closeEvent(event)

    # ---------- Start/Stop ----------
    def start_press(self):
        if running_evt.is_set():
            return
        repeat_count = clamp_int(
            self.repeat_input.text() or "0", 0, 0, 1_000_000)

        for i in range(10):
            k = normalize(self.keys[i].text())
            if not k:
                continue
            ms_val = clamp_int(self.times[i].text() or "0", 0, 0, MAX_MS)
            self.times[i].setText(str(ms_val))

        self.save_state_safe()
        stop_evt.clear()
        running_evt.set()
        signals.status.emit(
            f"Durum: Çalışıyor (tekrar={repeat_count or 'sonsuz'})")
        signals.buttons.emit(True)

        t = threading.Thread(target=self.run_loop,
                             args=(repeat_count,), daemon=True)
        t.start()

    def stop_press(self):
        if not running_evt.is_set():
            return
        stop_evt.set()
        running_evt.clear()
        self.save_state_safe()
        signals.status.emit("Durum: Durduruldu")
        signals.buttons.emit(False)

    def _set_buttons_running(self, is_running: bool):
        self.start_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)

    # ---------- Worker loop ----------
    def run_loop(self, repeat_count: int):
        cycle = 0
        while running_evt.is_set() and not stop_evt.is_set() and (repeat_count == 0 or cycle < repeat_count):
            for i in range(10):
                if not running_evt.is_set() or stop_evt.is_set():
                    break

                keyname = normalize(self.keys[i].text())
                if not keyname:
                    continue

                try:
                    duration = clamp_int(
                        self.times[i].text() or "0", 0, 0, MAX_MS)
                except Exception:
                    continue

                interrupted = False
                if keyname.startswith('mouse.'):
                    interrupted = press_mouse(keyname, duration) or False
                else:
                    interrupted = press_keyboard(keyname, duration) or False

                if interrupted:
                    break

            cycle += 1
            if sliced_sleep(200):
                break

        self.stop_press()

    # ---------- Global toggle ----------
    def global_keypress(self, key):
        now = time.time() * 1000.0
        if (now - self.last_toggle_ts) < TOGGLE_DEBOUNCE_MS:
            return

        try:
            if isinstance(key, KeyCode) and key.char == '"':
                self.last_toggle_ts = now
                if running_evt.is_set():
                    self.stop_press()
                else:
                    self.start_press()
                return
        except Exception:
            pass

        try:
            if hasattr(key, "vk") and key.vk == 34:
                self.last_toggle_ts = now
                if running_evt.is_set():
                    self.stop_press()
                else:
                    self.start_press()
        except Exception:
            pass


# --------------- main ---------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MayinTarlasi()
    ex.show()
    sys.exit(app.exec_())
