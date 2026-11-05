#!/usr/bin/env python3
"""
HardLock v1.3.0
Free open-source remake of Cold Turkey Micromanager.
Unlimited whitelist • Timed / Restart / Pomodoro / Allowance modes
Emergency stop is intentionally difficult.
Auto-update support + session resume after restart.
"""

import customtkinter as ctk
import psutil
import json
import threading
import time
import os
import sys
import random
import shutil
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

# Optional notifications
try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

# Optional Windows minimize support
HAS_WIN32 = False
if sys.platform == "win32":
    try:
        import win32gui
        import win32con
        import win32process
        HAS_WIN32 = True
    except ImportError:
        pass

# --------------- Constants ---------------
APP_NAME = "HardLock"
APP_VERSION = "1.4.1"

# Change this to your own GitHub repo once you create it
# Format: https://api.github.com/repos/USERNAME/REPO/releases/latest
UPDATE_CHECK_URL = "https://api.github.com/repos/AstroLabs-UK/HardLock/releases/latest"

APP_DIR = Path.home() / ".hardlock"
APP_DIR.mkdir(exist_ok=True)
ALLOWLIST_FILE = APP_DIR / "allowlist.json"
CONFIG_FILE = APP_DIR / "config.json"
SESSION_FILE = APP_DIR / "active_session.json"   # richer state for resume
LAST_SESSION_FILE = APP_DIR / "last_session.json"

# Permanent install location (Windows)
if sys.platform == "win32":
    INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "HardLock"
else:
    INSTALL_DIR = Path.home() / ".local" / "share" / "HardLock"
INSTALL_EXE = INSTALL_DIR / "HardLock.exe"

DEFAULT_CONFIG = {
    "force_close": True,
    "notifications": True,
    "check_interval": 1.5,
    "emergency_password": "",
    "theme": "dark",
    "pomodoro_work": 25,
    "pomodoro_break": 5,
    "check_for_updates": True,
    "update_url": UPDATE_CHECK_URL,
}

# Swiss Design / HardLock colour system
# Primary red #D82C2C, charcoal #1A1A1A, cool grey #A9B2B1
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")  # base, we override colours below


class HardLockApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME}")
        self.geometry("820x680")
        self.minsize(720, 580)
        self.configure(fg_color="#1A1A1A")

        self.config = self.load_config()
        self.allowlist = self.load_allowlist()
        self.is_blocking = False
        self.block_thread = None
        self.stop_event = threading.Event()
        self.block_end_time = None
        self.block_mode = "timed"
        self.pomodoro_state = "work"
        self.current_whitelist = set()
        self.emergency_phrase = ""
        self.resume_data = None

        # Ensure we are running from the permanent install location
        self.ensure_installed()

        self.create_widgets()
        self.load_last_session_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Check for updates shortly after launch (non-blocking)
        if self.config.get("check_for_updates", True):
            self.after(1500, self.check_for_updates)

        # Offer to resume an interrupted session
        self.after(800, self.check_resume_session)

    # --------------- Persistence ---------------
    def load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                    return {**DEFAULT_CONFIG, **data}
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def load_allowlist(self):
        if ALLOWLIST_FILE.exists():
            try:
                with open(ALLOWLIST_FILE) as f:
                    return set(json.load(f))
            except Exception:
                pass
        return set()

    def save_allowlist(self):
        with open(ALLOWLIST_FILE, "w") as f:
            json.dump(sorted(list(self.allowlist)), f, indent=2)

    def save_active_session(self):
        """Save rich state so we can resume after an update/restart."""
        if not self.is_blocking:
            if SESSION_FILE.exists():
                try:
                    SESSION_FILE.unlink()
                except Exception:
                    pass
            return

        data = {
            "version": APP_VERSION,
            "mode": self.block_mode,
            "allowlist": sorted(list(self.current_whitelist)),
            "force_close": self.config["force_close"],
            "end_time": self.block_end_time.isoformat() if self.block_end_time else None,
            "pomodoro_state": self.pomodoro_state,
            "started_at": datetime.now().isoformat(),
        }
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def clear_active_session(self):
        if SESSION_FILE.exists():
            try:
                SESSION_FILE.unlink()
            except Exception:
                pass

    def load_last_session_ui(self):
        if LAST_SESSION_FILE.exists():
            try:
                with open(LAST_SESSION_FILE) as f:
                    data = json.load(f)
                    if "allowlist" in data:
                        self.allowlist = set(data["allowlist"])
                        self.refresh_allowlist_box()
                    if "last_duration" in data and hasattr(self, "duration_entry"):
                        self.duration_entry.delete(0, "end")
                        self.duration_entry.insert(0, str(data["last_duration"]))
            except Exception:
                pass

    def save_last_session_ui(self):
        data = {
            "allowlist": sorted(list(self.allowlist)),
            "last_duration": getattr(self, "last_duration", 25),
            "mode": self.block_mode,
        }
        with open(LAST_SESSION_FILE, "w") as f:
            json.dump(data, f, indent=2)

    # --------------- UI ---------------
    def create_widgets(self):
        # Top brand bar
        top = ctk.CTkFrame(self, fg_color="#1A1A1A", height=52, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        brand = ctk.CTkLabel(
            top, text="  HARDLOCK",
            font=ctk.CTkFont(family="Helvetica", size=18, weight="bold"),
            text_color="#D82C2C"
        )
        brand.pack(side="left", padx=16, pady=12)

        version_lbl = ctk.CTkLabel(
            top, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=11),
            text_color="#A9B2B1"
        )
        version_lbl.pack(side="left", pady=14)

        # Main tab view
        self.tabs = ctk.CTkTabview(
            self,
            width=780,
            height=560,
            fg_color="#1A1A1A",
            segmented_button_fg_color="#2A2A2A",
            segmented_button_selected_color="#D82C2C",
            segmented_button_selected_hover_color="#B82424",
            segmented_button_unselected_color="#2A2A2A",
            segmented_button_unselected_hover_color="#333333",
            text_color="#F2F2F2",
            corner_radius=8
        )
        self.tabs.pack(padx=16, pady=(8, 6), fill="both", expand=True)

        self.tab_allow = self.tabs.add("Allowlist")
        self.tab_duration = self.tabs.add("Duration")
        self.tab_settings = self.tabs.add("Settings")
        self.tab_start = self.tabs.add("Start")

        self.build_allowlist_tab()
        self.build_duration_tab()
        self.build_settings_tab()
        self.build_start_tab()

        self.status_var = ctk.StringVar(value="Ready — select apps and start a focus session.")
        status = ctk.CTkLabel(
            self, textvariable=self.status_var, anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="#A9B2B1",
            fg_color="#1A1A1A"
        )
        status.pack(fill="x", padx=20, pady=(0, 10))

    def build_allowlist_tab(self):
        frame = self.tab_allow
        ctk.CTkLabel(frame, text="Only listed apps will be allowed during a block",
                     font=ctk.CTkFont(size=13)).pack(pady=(10, 5))

        list_frame = ctk.CTkFrame(frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.allow_listbox = tk.Listbox(list_frame, selectmode="extended",
                                        bg="#252525", fg="#F2F2F2",
                                        selectbackground="#D82C2C",
                                        font=("Segoe UI", 11), height=12)
        self.allow_listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.allow_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.allow_listbox.config(yscrollcommand=scrollbar.set)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=8)

        ctk.CTkButton(btn_frame, text="Add Running Apps", width=140,
                      command=self.add_running_apps).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Add EXE / Name", width=130,
                      command=self.add_manual).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Remove Selected", width=130,
                      command=self.remove_selected, fg_color="#8B0000",
                      hover_color="#A52A2A").pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Clear All", width=90,
                      command=self.clear_allowlist, fg_color="#555").pack(side="left", padx=4)

        exp_frame = ctk.CTkFrame(frame, fg_color="transparent")
        exp_frame.pack(fill="x", padx=10, pady=4)
        ctk.CTkButton(exp_frame, text="Export Allowlist", width=130,
                      command=self.export_allowlist).pack(side="left", padx=4)
        ctk.CTkButton(exp_frame, text="Import Allowlist", width=130,
                      command=self.import_allowlist).pack(side="left", padx=4)

        self.refresh_allowlist_box()

    def build_duration_tab(self):
        frame = self.tab_duration
        ctk.CTkLabel(frame, text="Block Mode", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(15, 5))

        self.mode_var = ctk.StringVar(value="timed")
        modes = ctk.CTkFrame(frame, fg_color="transparent")
        modes.pack(pady=5)
        ctk.CTkRadioButton(modes, text="Timed Block", variable=self.mode_var,
                           value="timed", command=self.on_mode_change).pack(side="left", padx=10)
        ctk.CTkRadioButton(modes, text="Until Restart", variable=self.mode_var,
                           value="restart", command=self.on_mode_change).pack(side="left", padx=10)
        ctk.CTkRadioButton(modes, text="Pomodoro", variable=self.mode_var,
                           value="pomodoro", command=self.on_mode_change).pack(side="left", padx=10)
        ctk.CTkRadioButton(modes, text="Allowance First", variable=self.mode_var,
                           value="allowance", command=self.on_mode_change).pack(side="left", padx=10)

        self.timed_frame = ctk.CTkFrame(frame)
        self.timed_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(self.timed_frame, text="Duration (minutes):").pack(side="left", padx=10)
        self.duration_entry = ctk.CTkEntry(self.timed_frame, width=80)
        self.duration_entry.insert(0, "25")
        self.duration_entry.pack(side="left", padx=5)
        presets = ctk.CTkFrame(self.timed_frame, fg_color="transparent")
        presets.pack(side="left", padx=15)
        for m in [15, 25, 45, 60, 90, 120]:
            ctk.CTkButton(presets, text=str(m), width=40,
                          command=lambda x=m: self.set_duration(x)).pack(side="left", padx=2)

        self.pomo_frame = ctk.CTkFrame(frame)
        ctk.CTkLabel(self.pomo_frame, text="Work (min):").grid(row=0, column=0, padx=10, pady=5)
        self.pomo_work = ctk.CTkEntry(self.pomo_frame, width=60)
        self.pomo_work.insert(0, str(self.config["pomodoro_work"]))
        self.pomo_work.grid(row=0, column=1, padx=5)
        ctk.CTkLabel(self.pomo_frame, text="Break (min):").grid(row=0, column=2, padx=10, pady=5)
        self.pomo_break = ctk.CTkEntry(self.pomo_frame, width=60)
        self.pomo_break.insert(0, str(self.config["pomodoro_break"]))
        self.pomo_break.grid(row=0, column=3, padx=5)
        ctk.CTkLabel(self.pomo_frame, text="Cycles:").grid(row=0, column=4, padx=10)
        self.pomo_cycles = ctk.CTkEntry(self.pomo_frame, width=50)
        self.pomo_cycles.insert(0, "4")
        self.pomo_cycles.grid(row=0, column=5, padx=5)

        self.allow_frame = ctk.CTkFrame(frame)
        ctk.CTkLabel(self.allow_frame, text="Allowance minutes:").pack(side="left", padx=10)
        self.allowance_entry = ctk.CTkEntry(self.allow_frame, width=70)
        self.allowance_entry.insert(0, "10")
        self.allowance_entry.pack(side="left", padx=5)
        ctk.CTkLabel(self.allow_frame, text="then block for (min):").pack(side="left", padx=10)
        self.allow_block_entry = ctk.CTkEntry(self.allow_frame, width=70)
        self.allow_block_entry.insert(0, "50")
        self.allow_block_entry.pack(side="left", padx=5)

        self.on_mode_change()

        info = ("• Timed: block for exact minutes\n"
                "• Until Restart: stays active until you reboot\n"
                "• Pomodoro: alternating work / break periods\n"
                "• Allowance: free time first, then the real block starts")
        ctk.CTkLabel(frame, text=info, justify="left",
                     font=ctk.CTkFont(size=12), text_color="#aaaaaa").pack(pady=15, padx=20)

    def build_settings_tab(self):
        frame = self.tab_settings

        ctk.CTkLabel(frame, text="Blocking Behaviour",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(15, 8))

        self.force_var = ctk.BooleanVar(value=self.config["force_close"])
        ctk.CTkCheckBox(frame, text="Force-close non-whitelisted apps (recommended)",
                        variable=self.force_var, command=self.update_config).pack(anchor="w", padx=30, pady=4)

        self.notify_var = ctk.BooleanVar(value=self.config["notifications"])
        ctk.CTkCheckBox(frame, text="Show desktop notifications",
                        variable=self.notify_var, command=self.update_config).pack(anchor="w", padx=30, pady=4)

        self.update_var = ctk.BooleanVar(value=self.config.get("check_for_updates", True))
        ctk.CTkCheckBox(frame, text="Check for updates on launch",
                        variable=self.update_var, command=self.update_config).pack(anchor="w", padx=30, pady=4)

        ctk.CTkLabel(frame, text="Check interval (seconds):").pack(anchor="w", padx=30, pady=(12, 2))
        self.interval_entry = ctk.CTkEntry(frame, width=80)
        self.interval_entry.insert(0, str(self.config["check_interval"]))
        self.interval_entry.pack(anchor="w", padx=30)
        self.interval_entry.bind("<FocusOut>", lambda e: self.update_config())

        ctk.CTkLabel(frame, text="Emergency Stop Password (optional but recommended)",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(25, 5))
        ctk.CTkLabel(frame, text="If set, you must enter this password + a confirmation phrase to stop a block early.",
                     text_color="#aaaaaa", wraplength=600).pack(padx=30)

        pw_frame = ctk.CTkFrame(frame, fg_color="transparent")
        pw_frame.pack(pady=8)
        self.pw_entry = ctk.CTkEntry(pw_frame, width=200, show="•")
        self.pw_entry.insert(0, self.config.get("emergency_password", ""))
        self.pw_entry.pack(side="left", padx=5)
        ctk.CTkButton(pw_frame, text="Save Password", width=110,
                      command=self.save_password).pack(side="left", padx=5)

        ctk.CTkLabel(frame, text="Note: During an active block the main window is locked.\n"
                                 "Emergency stop requires password + random phrase + final confirmation.",
                     text_color="#cc6666", justify="left").pack(pady=20, padx=30)

        # Version info
        ctk.CTkLabel(frame, text=f"Version {APP_VERSION}",
                     text_color="#666666").pack(side="bottom", pady=10)

    def build_start_tab(self):
        frame = self.tab_start

        self.summary_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=14),
                                          justify="left", wraplength=650)
        self.summary_label.pack(pady=20, padx=20)

        self.timer_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=32, weight="bold"))
        self.timer_label.pack(pady=10)

        self.progress = ctk.CTkProgressBar(frame, width=400)
        self.progress.pack(pady=10)
        self.progress.set(0)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=20)

        self.start_btn = ctk.CTkButton(btn_row, text="▶  START FOCUS BLOCK",
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       width=220, height=45,
                                       fg_color="#D82C2C", hover_color="#B82424",
                                       command=self.start_block)
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = ctk.CTkButton(btn_row, text="Emergency Stop…",
                                      width=160, height=45,
                                      fg_color="#555555", hover_color="#777777",
                                      state="disabled",
                                      command=self.request_emergency_stop)
        self.stop_btn.pack(side="left", padx=10)

        self.update_summary()

    # --------------- Allowlist helpers ---------------
    def refresh_allowlist_box(self):
        self.allow_listbox.delete(0, "end")
        for app in sorted(self.allowlist):
            self.allow_listbox.insert("end", app)

    def add_running_apps(self):
        running = set()
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name']
                if name:
                    running.add(name.lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        top = ctk.CTkToplevel(self)
        top.title("Select Running Apps")
        top.geometry("420x480")
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(top, text="Select apps to add to whitelist:").pack(pady=8)
        lb = tk.Listbox(top, selectmode="extended", bg="#252525", fg="#F2F2F2",
                        font=("Segoe UI", 11))
        lb.pack(fill="both", expand=True, padx=10, pady=5)
        for name in sorted(running):
            lb.insert("end", name)

        def add_selected():
            for i in lb.curselection():
                self.allowlist.add(lb.get(i))
            self.save_allowlist()
            self.refresh_allowlist_box()
            top.destroy()

        ctk.CTkButton(top, text="Add Selected", command=add_selected).pack(pady=10)

    def add_manual(self):
        dialog = ctk.CTkInputDialog(text="Enter process name (e.g. code.exe or chrome)\nor full path to .exe:",
                                    title="Add Application")
        value = dialog.get_input()
        if value:
            name = Path(value).name.lower() if value.lower().endswith((".exe", ".app")) else value.lower()
            self.allowlist.add(name)
            self.save_allowlist()
            self.refresh_allowlist_box()

    def remove_selected(self):
        selected = [self.allow_listbox.get(i) for i in self.allow_listbox.curselection()]
        for s in selected:
            self.allowlist.discard(s)
        self.save_allowlist()
        self.refresh_allowlist_box()

    def clear_allowlist(self):
        if messagebox.askyesno("Confirm", "Clear entire allowlist?"):
            self.allowlist.clear()
            self.save_allowlist()
            self.refresh_allowlist_box()

    def export_allowlist(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            with open(path, "w") as f:
                json.dump(sorted(list(self.allowlist)), f, indent=2)
            self.notify("Allowlist exported")

    def import_allowlist(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            try:
                with open(path) as f:
                    data = json.load(f)
                    self.allowlist.update(data)
                self.save_allowlist()
                self.refresh_allowlist_box()
                self.notify("Allowlist imported")
            except Exception as e:
                messagebox.showerror("Error", f"Could not import: {e}")

    # --------------- Mode / Config ---------------
    def on_mode_change(self):
        mode = self.mode_var.get()
        self.timed_frame.pack_forget()
        self.pomo_frame.pack_forget()
        self.allow_frame.pack_forget()
        if mode == "timed":
            self.timed_frame.pack(fill="x", padx=20, pady=10)
        elif mode == "pomodoro":
            self.pomo_frame.pack(pady=10)
        elif mode == "allowance":
            self.allow_frame.pack(pady=10)
        self.update_summary()

    def set_duration(self, mins):
        self.duration_entry.delete(0, "end")
        self.duration_entry.insert(0, str(mins))

    def update_config(self):
        self.config["force_close"] = self.force_var.get()
        self.config["notifications"] = self.notify_var.get()
        self.config["check_for_updates"] = self.update_var.get()
        try:
            self.config["check_interval"] = float(self.interval_entry.get())
        except ValueError:
            pass
        self.save_config()

    def save_password(self):
        self.config["emergency_password"] = self.pw_entry.get()
        self.save_config()
        messagebox.showinfo("Saved", "Emergency password updated.")

    def update_summary(self):
        if not hasattr(self, "summary_label"):
            return
        mode = self.mode_var.get() if hasattr(self, "mode_var") else "timed"
        apps = len(self.allowlist)
        text = f"Allowlist: {apps} app(s)\nMode: {mode.upper()}\n"
        if mode == "timed" and hasattr(self, "duration_entry"):
            text += f"Duration: {self.duration_entry.get()} minutes"
        elif mode == "restart":
            text += "Block lasts until computer restart"
        elif mode == "pomodoro" and hasattr(self, "pomo_work"):
            text += f"Work {self.pomo_work.get()} min / Break {self.pomo_break.get()} min × {self.pomo_cycles.get()} cycles"
        elif mode == "allowance" and hasattr(self, "allowance_entry"):
            text += f"Allowance {self.allowance_entry.get()} min → then block {self.allow_block_entry.get()} min"
        if hasattr(self, "force_var"):
            text += f"\nAction: {'Force-close' if self.force_var.get() else 'Minimize (best effort)'}"
        else:
            text += "\nAction: Force-close"
        self.summary_label.configure(text=text)

    # --------------- Blocking engine ---------------
    def start_block(self, resume=False):
        if not resume and not self.allowlist:
            messagebox.showwarning("Empty Allowlist",
                                   "Please add at least one application to the allowlist first.")
            return

        self.update_config()
        if not resume:
            self.current_whitelist = {a.lower() for a in self.allowlist}
        self.current_whitelist.update({
            "python", "python3", "pythonw", "python.exe", "pythonw.exe",
            "hardlock", "focus micromanager", "focusmicromanager",
            "explorer.exe", "dwm.exe", "csrss.exe", "winlogon.exe",
            "svchost.exe", "system", "idle", "finder", "dock", "windowserver"
        })

        if not resume:
            self.block_mode = self.mode_var.get()

        self.stop_event.clear()
        self.is_blocking = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color="#8B0000", hover_color="#A52A2A")
        self.tabs.configure(state="disabled")

        self.last_duration = 25
        try:
            if self.block_mode == "timed":
                if not resume:
                    mins = int(self.duration_entry.get())
                    self.last_duration = mins
                    self.block_end_time = datetime.now() + timedelta(minutes=mins)
                self.block_thread = threading.Thread(target=self.run_timed, daemon=True)
            elif self.block_mode == "restart":
                self.block_end_time = None
                self.block_thread = threading.Thread(target=self.run_until_restart, daemon=True)
            elif self.block_mode == "pomodoro":
                self.block_thread = threading.Thread(target=self.run_pomodoro, daemon=True)
            elif self.block_mode == "allowance":
                self.block_thread = threading.Thread(target=self.run_allowance, daemon=True)

            self.save_last_session_ui()
            self.save_active_session()
            self.block_thread.start()
            if not resume:
                self.notify("HardLock session started. Stay strong.")
            self.status_var.set("BLOCK ACTIVE — only allowlisted apps permitted")
            self.after(200, self.update_timer_display)
            # Periodically save session state while running
            self.after(10000, self.periodic_save)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.end_block()

    def periodic_save(self):
        if self.is_blocking:
            self.save_active_session()
            self.after(10000, self.periodic_save)

    def run_timed(self):
        interval = self.config["check_interval"]
        while not self.stop_event.is_set() and datetime.now() < self.block_end_time:
            self.enforce_once()
            time.sleep(interval)
        if not self.stop_event.is_set():
            self.after(0, lambda: self.notify("Block finished! Great work."))
        self.after(0, self.end_block)

    def run_until_restart(self):
        interval = self.config["check_interval"]
        while not self.stop_event.is_set():
            self.enforce_once()
            time.sleep(interval)
        self.after(0, self.end_block)

    def run_pomodoro(self):
        try:
            work = int(self.pomo_work.get())
            brk = int(self.pomo_break.get())
            cycles = int(self.pomo_cycles.get())
        except ValueError:
            work, brk, cycles = 25, 5, 4

        for c in range(cycles):
            if self.stop_event.is_set():
                break
            self.pomodoro_state = "work"
            self.block_end_time = datetime.now() + timedelta(minutes=work)
            self.after(0, lambda: self.status_var.set(f"POMODORO WORK ({c+1}/{cycles})"))
            while not self.stop_event.is_set() and datetime.now() < self.block_end_time:
                self.enforce_once()
                time.sleep(self.config["check_interval"])
            if self.stop_event.is_set():
                break
            self.pomodoro_state = "break"
            self.block_end_time = datetime.now() + timedelta(minutes=brk)
            self.after(0, lambda: self.status_var.set(f"POMODORO BREAK ({c+1}/{cycles}) — apps free"))
            self.after(0, lambda: self.notify("Break time! Stretch."))
            while not self.stop_event.is_set() and datetime.now() < self.block_end_time:
                time.sleep(1)
        self.after(0, lambda: self.notify("Pomodoro session complete!"))
        self.after(0, self.end_block)

    def run_allowance(self):
        try:
            allow_mins = int(self.allowance_entry.get())
            block_mins = int(self.allow_block_entry.get())
        except ValueError:
            allow_mins, block_mins = 10, 50

        self.block_end_time = datetime.now() + timedelta(minutes=allow_mins)
        self.after(0, lambda: self.status_var.set("ALLOWANCE — free use of all apps"))
        while not self.stop_event.is_set() and datetime.now() < self.block_end_time:
            time.sleep(1)

        if self.stop_event.is_set():
            self.after(0, self.end_block)
            return

        self.after(0, lambda: self.notify("Allowance over. HardLock block starting now."))
        self.block_end_time = datetime.now() + timedelta(minutes=block_mins)
        self.after(0, lambda: self.status_var.set("BLOCK ACTIVE after allowance"))
        interval = self.config["check_interval"]
        while not self.stop_event.is_set() and datetime.now() < self.block_end_time:
            self.enforce_once()
            time.sleep(interval)
        self.after(0, self.end_block)

    def enforce_once(self):
        force = self.config["force_close"]
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                name = (proc.info['name'] or "").lower()
                if not name or name in self.current_whitelist:
                    continue
                if "focus" in name or "micromanager" in name:
                    continue
                if force:
                    proc.terminate()
                else:
                    if HAS_WIN32:
                        self.minimize_process_windows(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

    def minimize_process_windows(self, pid):
        if not HAS_WIN32:
            return
        def callback(hwnd, _):
            try:
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid == pid and win32gui.IsWindowVisible(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            except Exception:
                pass
            return True
        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            pass

    def update_timer_display(self):
        if not self.is_blocking:
            return
        if self.block_end_time:
            remaining = (self.block_end_time - datetime.now()).total_seconds()
            if remaining < 0:
                remaining = 0
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            self.timer_label.configure(text=f"{mins:02d}:{secs:02d}")
            total = getattr(self, "last_duration", 25) * 60
            if total > 0:
                self.progress.set(max(0, 1 - remaining / total))
        else:
            self.timer_label.configure(text="UNTIL RESTART")
            self.progress.set(0)
        self.after(500, self.update_timer_display)

    def end_block(self):
        self.is_blocking = False
        self.stop_event.set()
        self.clear_active_session()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", fg_color="#555555")
        self.tabs.configure(state="normal")
        self.timer_label.configure(text="")
        self.progress.set(0)
        self.status_var.set("Ready. Select apps and start a focus session.")
        self.notify("HardLock session ended.")

    # --------------- Emergency stop ---------------
    def request_emergency_stop(self):
        if not self.is_blocking:
            return

        words = ["focus", "discipline", "commit", "persist", "integrity",
                 "resolve", "willpower", "dedication", "strength", "clarity"]
        phrase = " ".join(random.sample(words, 4)) + " " + str(random.randint(1000, 9999))
        self.emergency_phrase = phrase

        top = ctk.CTkToplevel(self)
        top.title("Emergency Stop — Confirmation Required")
        top.geometry("520x380")
        top.transient(self)
        top.grab_set()
        top.attributes("-topmost", True)

        ctk.CTkLabel(top, text="⚠ EMERGENCY STOP",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#D82C2C").pack(pady=15)

        ctk.CTkLabel(top, text="Stopping early defeats the purpose of a focus block.\n"
                               "Only use this if there is a genuine emergency.",
                     justify="center", wraplength=450).pack(pady=5)

        if self.config.get("emergency_password"):
            ctk.CTkLabel(top, text="Enter your emergency password:").pack(pady=(15, 2))
            pw = ctk.CTkEntry(top, width=250, show="•")
            pw.pack()
        else:
            pw = None

        ctk.CTkLabel(top, text="Type the following phrase exactly to confirm:",
                     text_color="#aaaaaa").pack(pady=(15, 2))
        ctk.CTkLabel(top, text=phrase,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#F2F2F2").pack(pady=5)

        entry = ctk.CTkEntry(top, width=400)
        entry.pack(pady=5)

        def attempt():
            if self.config.get("emergency_password"):
                if not pw or pw.get() != self.config["emergency_password"]:
                    messagebox.showerror("Wrong", "Incorrect emergency password.", parent=top)
                    return
            if entry.get().strip() != self.emergency_phrase:
                messagebox.showerror("Wrong", "Phrase does not match. Try again.", parent=top)
                return
            if messagebox.askyesno("Final Confirmation",
                                   "Are you absolutely sure you want to end the focus block early?",
                                   parent=top):
                top.destroy()
                self.stop_event.set()
                self.end_block()
                self.notify("Block stopped by emergency override.")

        ctk.CTkButton(top, text="Confirm Emergency Stop",
                      fg_color="#8B0000", hover_color="#A52A2A",
                      command=attempt).pack(pady=20)
        ctk.CTkButton(top, text="Cancel — Keep Locking",
                      command=top.destroy).pack()

    # --------------- Update system ---------------
    def ensure_installed(self):
        """Copy the EXE to a permanent location on first run (Windows)."""
        if not getattr(sys, "frozen", False):
            return  # running from source
        if sys.platform != "win32":
            return

        current = Path(sys.executable).resolve()
        try:
            INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            return

        # Already running from the install location
        try:
            if current == INSTALL_EXE.resolve():
                return
        except Exception:
            pass

        # First run or launched from Downloads / elsewhere → install
        try:
            shutil.copy2(current, INSTALL_EXE)

            # Best-effort Start Menu shortcut via PowerShell
            try:
                start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                start_menu.mkdir(parents=True, exist_ok=True)
                shortcut = start_menu / "HardLock.lnk"
                ps_cmd = (
                    "$ws = New-Object -ComObject WScript.Shell; "
                    f"$s = $ws.CreateShortcut('{shortcut}'); "
                    f"$s.TargetPath = '{INSTALL_EXE}'; "
                    f"$s.WorkingDirectory = '{INSTALL_DIR}'; "
                    "$s.Description = 'HardLock Focus Tool'; "
                    "$s.Save()"
                )
                import subprocess
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True, timeout=10
                )
            except Exception:
                pass

            # Relaunch from the installed copy and exit this instance
            import subprocess
            subprocess.Popen([str(INSTALL_EXE)], cwd=str(INSTALL_DIR))
            sys.exit(0)
        except Exception:
            # If anything fails, just continue running from current location
            pass

    def check_for_updates(self):

        """Non-blocking update check against GitHub Releases."""
        def worker():
            try:
                url = self.config.get("update_url") or UPDATE_CHECK_URL
                req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                tag = data.get("tag_name", "")
                # Accept tags like v1.0.0 or v1.0.0-42
                latest = tag.lstrip("v").split("-")[0]
                if not latest:
                    return
                if self._version_gt(latest, APP_VERSION):
                    assets = data.get("assets", [])
                    download_url = None
                    for a in assets:
                        name = a.get("name", "").lower()
                        if name == "hardlock.exe" or (name.endswith(".exe") and "hardlock" in name):
                            download_url = a.get("browser_download_url")
                            break
                    if not download_url:
                        for a in assets:
                            if a.get("name", "").lower().endswith(".exe"):
                                download_url = a.get("browser_download_url")
                                break
                    if download_url:
                        self.after(0, lambda: self._offer_update(latest, download_url))
            except Exception:
                pass  # silent fail when offline or no releases yet

        threading.Thread(target=worker, daemon=True).start()

    def _version_gt(self, a, b):
        def parts(v):
            nums = []
            for x in v.replace("-", ".").split("."):
                if x.isdigit():
                    nums.append(int(x))
            return nums
        return parts(a) > parts(b)

    def _offer_update(self, latest, download_url):
        if messagebox.askyesno(
            "Update Available",
            f"A new version ({latest}) is available.\n\n"
            f"You are running {APP_VERSION}.\n\n"
            "Download and install automatically now?\n"
            "HardLock will restart and resume any active session."
        ):
            self._perform_update(download_url, latest)

    def _perform_update(self, download_url, latest):
        """Download the new EXE and use a helper to replace + restart."""
        self.save_active_session()
        self.status_var.set("Downloading update…")
        self.update()

        def worker():
            try:
                if not getattr(sys, "frozen", False):
                    self.after(0, lambda: messagebox.showinfo(
                        "Update",
                        "You are running from source.\n"
                        "Please pull the latest code or download the new EXE from the release page."
                    ))
                    return

                # Always update the permanent install location
                target_exe = INSTALL_EXE
                try:
                    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
                except Exception:
                    target_exe = Path(sys.executable)

                temp_dir = Path(tempfile.gettempdir()) / "hardlock_update"
                temp_dir.mkdir(exist_ok=True)
                new_exe = temp_dir / "HardLock_new.exe"
                helper_bat = temp_dir / "apply_update.bat"

                # Download the new EXE
                req = urllib.request.Request(
                    download_url,
                    headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"}
                )
                with urllib.request.urlopen(req, timeout=90) as resp, open(new_exe, "wb") as out:
                    shutil.copyfileobj(resp, out)

                # Helper batch: wait for HardLock to exit, then replace and relaunch
                bat_lines = [
                    "@echo off",
                    "timeout /t 2 /nobreak >nul",
                    ":wait",
                    'tasklist /FI "IMAGENAME eq HardLock.exe" 2>NUL | find /I "HardLock.exe" >NUL',
                    "if not errorlevel 1 (",
                    "    timeout /t 1 /nobreak >nul",
                    "    goto wait",
                    ")",
                    f'copy /Y "{new_exe}" "{target_exe}" >nul',
                    f'start "" "{target_exe}"',
                    f'del "{new_exe}"',
                    'del "%~f0"',
                ]
                helper_bat.write_text("\r\n".join(bat_lines), encoding="utf-8")

                self.after(0, lambda: self.status_var.set("Installing update and restarting…"))
                import subprocess
                subprocess.Popen(
                    ["cmd", "/c", str(helper_bat)],
                    creationflags=0x00000008,  # DETACHED_PROCESS
                    close_fds=True
                )
                time.sleep(0.8)
                self.after(0, self.destroy)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Update Failed", str(e)))
                self.after(0, lambda: self.status_var.set("Ready."))

        threading.Thread(target=worker, daemon=True).start()

    # --------------- Session resume ---------------
    def check_resume_session(self):
        if not SESSION_FILE.exists():
            return
        try:
            with open(SESSION_FILE) as f:
                data = json.load(f)
            end = data.get("end_time")
            if end:
                end_dt = datetime.fromisoformat(end)
                if datetime.now() >= end_dt:
                    # Session already expired
                    self.clear_active_session()
                    return
            # Offer resume
            remaining = ""
            if end:
                secs = (datetime.fromisoformat(end) - datetime.now()).total_seconds()
                remaining = f"\nRemaining: ~{int(secs//60)} minutes"
            if messagebox.askyesno("Resume HardLock Session?",
                                   f"An interrupted focus session was found.{remaining}\n\n"
                                   "Would you like to resume it now?"):
                self.resume_data = data
                self.current_whitelist = set(data.get("allowlist", []))
                self.block_mode = data.get("mode", "timed")
                if data.get("end_time"):
                    self.block_end_time = datetime.fromisoformat(data["end_time"])
                self.pomodoro_state = data.get("pomodoro_state", "work")
                self.config["force_close"] = data.get("force_close", True)
                self.start_block(resume=True)
        except Exception:
            self.clear_active_session()

    def notify(self, message):
        if self.config.get("notifications") and HAS_PLYER:
            try:
                notification.notify(
                    title=APP_NAME,
                    message=message,
                    app_name=APP_NAME,
                    timeout=4
                )
            except Exception:
                pass

    def on_close(self):
        if self.is_blocking:
            messagebox.showwarning("Block Active",
                                   "A focus block is running.\n"
                                   "Use the Emergency Stop button on the Start tab\n"
                                   "(requires password + phrase confirmation).")
            return
        self.destroy()


def main():
    app = HardLockApp()
    app.mainloop()


if __name__ == "__main__":
    main()
