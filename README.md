# HardLock (Modular)

**HardLock** is a free, open-source focus tool that locks your computer to only the applications you need.

This is a modular refactor of the original [AstroLabs-UK/HardLock](https://github.com/AstroLabs-UK/HardLock) project.

Inspired by Cold Turkey Micromanager, HardLock takes a whitelist approach: you choose the apps that are allowed, and everything else is blocked for the duration of your focus session. Once a session starts, stopping it early is deliberately difficult.

---

## Why HardLock?

Most distraction blockers let you blacklist sites or apps. HardLock does the opposite — it only lets through the programs you explicitly allow. This creates a much stricter environment that is harder to rationalise your way out of.

- Unlimited application allowlist + **named profiles**
- Timed sessions, “until restart”, Pomodoro cycles, or allowance-then-block modes
- **+10 min extend** button during timed blocks
- Force-close or minimise non-whitelisted apps
- Optional aggressive Task Manager / Process Explorer blocking
- Optional emergency password + confirmation phrase to exit early
- Session resume if the app is closed or updated mid-session
- Completely free, no accounts, no tracking, no paywalls

---

## Project Structure

```
hardlock/
├── __init__.py
├── __main__.py          # python -m hardlock
├── app.py               # Main CustomTkinter UI
├── config.py            # Paths, defaults, load/save
├── session.py           # Active session persistence & resume
├── allowlist.py         # Allowlist + profiles
├── enforcer.py          # Process scanning & force-close/minimize
├── modes.py             # Timed / Restart / Pomodoro / Allowance runners
├── emergency.py         # High-friction emergency stop dialog
├── updater.py           # GitHub Releases auto-update
└── platform/
    ├── windows.py       # win32 helpers
    ├── macos.py         # stubs
    └── linux.py         # stubs
```

---

## Getting Started

### Run from source

```bash
pip install -r requirements.txt
# Recommended on Windows:
pip install pywin32

python -m hardlock
```

### Build a Windows executable

```bash
pip install -r requirements.txt pyinstaller pywin32
pyinstaller --onefile --windowed --name "HardLock" --icon=icon.png -m hardlock
```

Or simply run `build_windows.bat`.

The finished `HardLock.exe` will appear in the `dist` folder.

---

## How a Session Works

1. Add the applications you need to the Allowlist tab (or load a Profile).
2. Choose your preferred mode and duration on the Duration tab.
3. Review settings and click **Start Focus Block**.
4. Only allowlisted apps remain usable until the session ends (or you complete the emergency stop process).

While a block is active the main window cannot be closed normally. The Emergency Stop button requires deliberate, multi-step confirmation so that quitting early is not a casual decision.

During a timed block you can click **+10 min** to extend the session without stopping.

---

## Privacy

HardLock stores everything locally in `~/.hardlock/` (or the equivalent on Windows).

No telemetry, no accounts, no cloud services.

---

## Limitations

HardLock is a user-space application. A determined user can still terminate the process through Task Manager (unless the aggressive protection option is enabled). It is designed to create strong friction against casual distraction, not to provide kernel-level lockdown.

Future improvements (watchdog process, stronger process protection, system tray, scheduling, statistics) are planned on top of this modular base.

---

## License

MIT License — free to use, modify, and distribute.
