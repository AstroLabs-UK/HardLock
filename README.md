# HardLock

**HardLock** is a free, open-source focus tool that locks your computer to only the applications you need.

Inspired by Cold Turkey Micromanager, HardLock takes a whitelist approach: you choose the apps that are allowed, and everything else is blocked for the duration of your focus session. Once a session starts, stopping it early is deliberately difficult.

---

## Why HardLock?

Most distraction blockers let you blacklist sites or apps. HardLock does the opposite — it only lets through the programs you explicitly allow. This creates a much stricter environment that is harder to rationalise your way out of.

- Unlimited application allowlist
- Timed sessions, “until restart”, Pomodoro cycles, or allowance-then-block modes
- Force-close or minimise non-whitelisted apps
- Optional emergency password + confirmation phrase to exit early
- Session resume if the app is closed or updated mid-session
- Completely free, no accounts, no tracking, no paywalls

---

## Features

| Feature | Description |
|---------|-------------|
| **Allowlist** | Add apps from currently running processes or by name/path. Import & export lists. |
| **Timed Block** | Set any duration. The block ends automatically when time is up. |
| **Until Restart** | Session continues until you reboot the computer. |
| **Pomodoro** | Alternating work and break periods with configurable lengths and cycles. |
| **Allowance** | Free use of all apps for a set time, then the real block begins. |
| **Strict Enforcement** | Choose force-close or minimise for blocked applications. |
| **Hard Emergency Stop** | Requires optional password + random confirmation phrase + final confirmation. |
| **Session Resume** | If the app restarts or updates during a session, you can continue from the remaining time. |
| **Auto-Update Check** | Checks GitHub Releases on launch and can automatically download + install updates (with session resume). |
| **Local Only** | All settings and session data stay on your machine. |

---

## Getting Started

### Run from source

```bash
pip install -r requirements.txt
python app.py
```

For better minimise support on Windows:

```bash
pip install pywin32
```

### Build a Windows executable

```bash
pip install -r requirements.txt pyinstaller pywin32
pyinstaller --onefile --windowed --name "HardLock" --icon=icon.png app.py
```

Or simply run `build_windows.bat`.

The finished `HardLock.exe` will appear in the `dist` folder.

---

## How a Session Works

1. Add the applications you need to the Allowlist tab.
2. Choose your preferred mode and duration on the Duration & Breaks tab.
3. Review settings and click **Start Focus Block**.
4. Only allowlisted apps remain usable until the session ends (or you complete the emergency stop process).

While a block is active the main window cannot be closed normally. The Emergency Stop button requires deliberate, multi-step confirmation so that quitting early is not a casual decision.

---

## Privacy

HardLock stores everything locally in `~/.hardlock/` (or the equivalent on Windows).  
No telemetry, no accounts, no cloud services.

---

## Limitations

HardLock is a user-space application. A determined user can still terminate the process through Task Manager or Activity Monitor. It is designed to create strong friction against casual distraction, not to provide kernel-level lockdown.

---

## License

MIT License — free to use, modify, and distribute.
