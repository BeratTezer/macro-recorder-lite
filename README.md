# macro-recorder-lite

A lightweight desktop app to **record-like macro rows and replay them** using a global toggle key. Built with **PyQt5** UI and **pynput** for system-wide keyboard/mouse control.

> Toggle key: `"` (double-quote, typically `Shift+2`). Debounced for reliable start/stop.

---

## Features

- Global **start/stop toggle** with the `"` key (debounce 250 ms)
- Up to **10 steps** (keyboard key or mouse button + press duration in ms)
- **Repeat count** (0 = infinite loop)
- **Responsive stop**: long presses are sliced (50 ms) so stop is quick
- **Persistent state**: last macro is auto-saved to `~/.keyboardSupport.json` with **automatic backup** and restore from `~/.keyboardSupport.bak.json`
- Supports keys like `a`, `enter`, `f2`, and mouse tokens: `mouse.left`, `mouse.right`, `mouse.middle`

---

## Screenshot / Icon

Place your icons at the repo root:

- `icon.png` (app icon in PNG)
- `icon.ico` (Windows build)

---

## Installation (Dev)

### 1) Using pipenv (recommended)

```bash
pip install pipenv
pipenv install
pipenv run python macro.py
```

### 2) Using plain pip / venv

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python macro.py
```

**Requirements**

- Python 3.9+
- PyQt5
- pynput

---

## Usage

1. Run the app: `pipenv run python macro.py` (or `python macro.py` in your venv)
2. Fill up to 10 rows with **key/mouse token** and **press duration (ms)**
   - Examples: `a` (50), `enter` (120), `mouse.left` (100)
3. Set **Repeat Count** (0 = infinite)
4. Click **Başlat** or press the `"` key to start
5. Press `"` again (or click **Durdur**) to stop

### Supported Keys

- Single characters: `a`, `b`, `1`, etc.
- Function keys: `f1`..`f24`
- Special keys: `enter`, `return`, `space`, `tab`, `esc`, `backspace`, `delete`, `home`, `end`, `pageup`, `pagedown`, `up`, `down`, `left`, `right`
- Mouse: `mouse.left`, `mouse.right`, `mouse.middle`

> Durations are clamped to **0..60000 ms**.

---

## Build Windows .exe (PyInstaller)

From an activated venv:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --icon icon.ico --name MacroRecorderLite macro.py
```

Resulting binary will be in `dist/MacroRecorderLite.exe`.

If you already have a `.spec` file (e.g., `KeyboardSupport.spec`), you can build with:

```bash
pyinstaller KeyboardSupport.spec
```

**Notes**

- Some AV tools may flag PyInstaller binaries; sign the exe or add an exception.
- On Windows, global keyboard hooks may require **Run as Administrator**.

---

## File Persistence

- App saves state to `~/.keyboardSupport.json` on every edit and on exit.
- If JSON is corrupted, it auto-recovers from `~/.keyboardSupport.bak.json`.

---

## Troubleshooting

- **Toggle key not working**: ensure the active layout sends `"`; on some layouts you may need to press `Shift+2`.
- **No effect on key/mouse**: apps with elevated privileges may require you to run this app **as admin**.
- **Stops are slow**: reduce long press durations; the app slices sleep into 50 ms chunks for responsive stop.
- **PyInstaller app crashes**: ensure `PyQt5` is installed in the build venv and that the icon path is valid.

---

## License

Released under the **MIT License**. See [`LICENSE`](LICENSE).

---

## Repo Layout

```
macro-recorder-lite/
├─ macro.py
├─ Pipfile
├─ Pipfile.lock
├─ requirements.txt
├─ icon.png
├─ icon.ico
├─ KeyboardSupport.spec   # optional PyInstaller spec
├─ README.md
├─ LICENSE
├─ requirements.txt
├─ requirements-dev.txt
└─ (generated) build/ dist/ .venv/ __pycache__/  # ignored
```
