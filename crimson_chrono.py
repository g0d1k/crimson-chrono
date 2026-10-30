#!/usr/bin/env python3
"""
Crimson Chrono — A unique red/black neon-style clock app
Features: Digital/Analog clock, World Clocks, Alarms (recurring + snooze), Timer, Stopwatch
Built with CustomTkinter
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import json
import os
import math
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones
import platform
import subprocess
import sys

# =============================================================================
# Configuration & Persistence
# =============================================================================
DATA_FILE = os.path.join(os.path.expanduser("~"), ".crimson_chrono.json")
# Bundled files live in sys._MEIPASS when frozen by PyInstaller
RESOURCE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_FILE = os.path.join(RESOURCE_DIR, "icon.png")
ACCENT = "#FF1A1A"          # Bright red
ACCENT_DARK = "#CC0000"
BG_DARK = "#0D0D0D"
BG_LIGHT = "#F5F5F5"
CARD_DARK = "#1A1A1A"
CARD_LIGHT = "#FFFFFF"
TEXT_DARK = "#FFFFFF"
TEXT_LIGHT = "#111111"
NEON_GLOW = "#FF3333"
NEUTRAL = "#3A3A3A"          # Neutral button color that fits red/black scheme
NEUTRAL_HOVER = "#4A4A4A"

class DataStore:
    def __init__(self):
        self.data = {
            "appearance": "dark",
            "clock_mode": "digital",   # digital | analog
            "time_format": "24h",      # 24h | 12h
            "world_clocks": ["America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"],
            "alarms": [],
            "timer_presets": []
        }
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception:
                pass

    def save(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Save error: {e}")

store = DataStore()

# =============================================================================
# Sound helper (cross-platform fallback)
# =============================================================================
def play_alarm_sound():
    system = platform.system()
    try:
        if system == "Windows":
            import winsound
            winsound.Beep(1000, 500)
            winsound.Beep(1200, 300)
        elif system == "Darwin":
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False, capture_output=True)
        else:  # Linux
            # Try common sounds, fallback to bell
            for cmd in [
                ["paplay", "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"],
                ["paplay", "/usr/share/sounds/alsa/Front_Center.wav"],
                ["beep", "-f", "1000", "-l", "400"],
            ]:
                try:
                    subprocess.run(cmd, check=False, timeout=2, capture_output=True)
                    return
                except Exception:
                    continue
            # Final fallback
            print("\a", end="", flush=True)
    except Exception:
        print("\a", end="", flush=True)

# =============================================================================
# Theme & custom widgets
# =============================================================================
def apply_crimson_theme():
    """Recolor the stock CTk theme so no default blue leaks into any widget."""
    t = ctk.ThemeManager.theme
    red, red_dark = [ACCENT, ACCENT], [ACCENT_DARK, ACCENT_DARK]
    t["CTkButton"].update(fg_color=red, hover_color=red_dark)
    t["CTkOptionMenu"].update(fg_color=["#4A4A4A", NEUTRAL], button_color=red_dark,
                              button_hover_color=red, text_color=["#FFFFFF", "#FFFFFF"])
    t["DropdownMenu"].update(hover_color=["#FFD6D6", "#4A1414"])
    t["CTkCheckBox"].update(fg_color=red, hover_color=red_dark)
    t["CTkRadioButton"].update(fg_color=red, hover_color=red_dark)
    t["CTkSwitch"].update(progress_color=red)
    t["CTkProgressBar"].update(progress_color=red)
    t["CTkSlider"].update(button_color=red, button_hover_color=red_dark)
    t["CTkSegmentedButton"].update(selected_color=red, selected_hover_color=red_dark)
    t["CTkScrollbar"].update(button_hover_color=["#C06060", "#5A1A1A"])
    t["CTkEntry"].update(border_color=["#BBBBBB", NEUTRAL])


class WheelPicker(ctk.CTkFrame):
    """Compact scroll-wheel selector: mouse wheel, drag, click above/below, or Up/Down keys."""
    ROW = 30

    def __init__(self, master, values, initial=None, width=60, wrap=True, command=None):
        is_dark = ctk.get_appearance_mode() == "Dark"
        self._wbg = CARD_DARK if is_dark else CARD_LIGHT
        self._band = "#2B0D0D" if is_dark else "#FFE3E3"
        self._center = ACCENT if is_dark else ACCENT_DARK
        self._near = "#808080" if is_dark else "#8A8A8A"
        self._far = "#454545" if is_dark else "#C8C8C8"
        super().__init__(master, fg_color=self._wbg, corner_radius=10, border_width=1,
                         border_color=NEUTRAL if is_dark else "#CCCCCC")

        self.values = list(values)
        self.index = self.values.index(initial) if initial in self.values else 0
        self.wrap = wrap
        self.command = command
        self._cw, self._ch = width, self.ROW * 3
        self._offset = 0.0
        self._anim = None
        self._drag_y = None
        self._dragged = False

        c = self.canvas = tk.Canvas(self, width=self._cw, height=self._ch, bg=self._wbg,
                                    highlightthickness=0, takefocus=1, cursor="sb_v_double_arrow")
        c.pack(padx=5, pady=5)
        c.bind("<MouseWheel>", self._on_wheel)
        c.bind("<Button-4>", lambda e: self.step(-1))
        c.bind("<Button-5>", lambda e: self.step(1))
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Up>", lambda e: self.step(-1))
        c.bind("<Down>", lambda e: self.step(1))
        self._redraw()

    def get(self):
        return self.values[self.index]

    def set(self, value):
        if value in self.values:
            self.index = self.values.index(value)
            self._offset = 0.0
            self._redraw()

    def destroy(self):
        if self._anim:
            self.after_cancel(self._anim)
            self._anim = None
        super().destroy()

    def _value_at(self, i):
        if self.wrap:
            return self.values[i % len(self.values)]
        return self.values[i] if 0 <= i < len(self.values) else None

    def _move(self, delta):
        """Shift the selection by delta; returns False at a non-wrapping end."""
        new = self.index + delta
        if self.wrap:
            new %= len(self.values)
        elif not 0 <= new < len(self.values):
            return False
        self.index = new
        if self.command:
            self.command(self.get())
        return True

    def step(self, delta):
        if self._move(delta):
            # Start displaced by one row and glide into place
            self._offset = max(-2 * self.ROW, min(2 * self.ROW, self._offset + delta * self.ROW))
            self._start_anim()
        return "break"

    def _start_anim(self):
        if self._anim is None:
            self._anim = self.after(16, self._animate)

    def _animate(self):
        self._offset *= 0.55
        if abs(self._offset) < 0.5:
            self._offset = 0.0
            self._anim = None
        else:
            self._anim = self.after(16, self._animate)
        self._redraw()

    def _on_wheel(self, e):
        if e.delta:
            self.step(-1 if e.delta > 0 else 1)
        return "break"

    def _on_press(self, e):
        self.canvas.focus_set()
        self._drag_y = e.y
        self._dragged = False

    def _on_drag(self, e):
        dy = e.y - self._drag_y
        if not self._dragged and abs(dy) < 4:
            return
        self._dragged = True
        self._drag_y = e.y
        self._offset += dy
        half = self.ROW / 2
        while self._offset > half and self._move(-1):
            self._offset -= self.ROW
        while self._offset < -half and self._move(1):
            self._offset += self.ROW
        self._offset = max(-half, min(half, self._offset))
        self._redraw()

    def _on_release(self, e):
        if not self._dragged:
            if e.y < self.ROW:
                self.step(-1)
            elif e.y > 2 * self.ROW:
                self.step(1)
        self._start_anim()

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        cy = self._ch / 2
        half = self.ROW / 2
        c.create_rectangle(0, cy - half, self._cw, cy + half, fill=self._band, outline="")
        c.create_line(0, cy - half, self._cw, cy - half, fill=ACCENT_DARK)
        c.create_line(0, cy + half, self._cw, cy + half, fill=ACCENT_DARK)
        for k in range(-2, 3):
            v = self._value_at(self.index + k)
            if v is None:
                continue
            y = cy + k * self.ROW + self._offset
            dist = abs(y - cy) / self.ROW
            if dist < 0.5:
                color, font = self._center, ("Helvetica", 18, "bold")
            elif dist < 1.5:
                color, font = self._near, ("Helvetica", 13)
            else:
                color, font = self._far, ("Helvetica", 11)
            c.create_text(self._cw / 2, y, text=str(v), fill=color, font=font)

# =============================================================================
# Main Application
# =============================================================================
class CrimsonChrono(ctk.CTk):
    def __init__(self):
        super().__init__(className="crimson-chrono")  # matches StartupWMClass in the .desktop file
        self.title("Crimson Chrono")
        self.set_app_icon()
        self.geometry("1050x680")
        self.minsize(950, 600)

        # Appearance
        mode = store.data.get("appearance", "dark")
        ctk.set_appearance_mode(mode)
        ctk.set_default_color_theme("dark-blue")  # base, recolored below
        apply_crimson_theme()

        self.configure(fg_color=BG_DARK if mode == "dark" else BG_LIGHT)

        # State
        self.current_view = "clock"
        self.analog_mode = store.data.get("clock_mode", "digital") == "analog"
        self.use_12h = store.data.get("time_format", "24h") == "12h"
        self.world_clock_widgets = []
        self.alarm_widgets = []
        self.stopwatch_running = False
        self.stopwatch_start = None
        self.stopwatch_elapsed = 0.0
        self.stopwatch_laps = []
        self.timer_running = False
        self.timer_end = None
        self.timer_remaining = 0
        self.snooze_alarms = {}  # id -> wake time

        self.setup_ui()
        self.load_world_clocks()
        self.load_alarms()
        self.update_loop()

    def set_app_icon(self):
        try:
            img = tk.PhotoImage(file=ICON_FILE)
            # Window managers prefer smaller icons; ~256px from the 1254px source
            self._icon = img.subsample(max(1, img.width() // 256))
            self.iconphoto(True, self._icon)  # True = also applies to popups
        except Exception as e:
            print(f"Icon load error: {e}")

    def setup_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=CARD_DARK if ctk.get_appearance_mode() == "Dark" else "#E8E8E8")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        logo = ctk.CTkLabel(self.sidebar, text="CRIMSON\nCHRONO", font=ctk.CTkFont(size=20, weight="bold"),
                            text_color=ACCENT)
        logo.pack(pady=(30, 20))

        self.nav_buttons = {}
        for name, icon in [("Clock", "🕐"), ("World", "🌍"), ("Alarms", "⏰"), ("Timer", "⏳"), ("Stopwatch", "⏱️")]:
            btn = ctk.CTkButton(self.sidebar, text=f" {icon}  {name}", anchor="w",
                                fg_color="transparent", hover_color=ACCENT_DARK,
                                text_color=TEXT_DARK if ctk.get_appearance_mode() == "Dark" else TEXT_LIGHT,
                                command=lambda n=name.lower(): self.switch_view(n))
            btn.pack(fill="x", padx=10, pady=4)
            self.nav_buttons[name.lower()] = btn

        # Theme & mode toggles at bottom
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=20, padx=10)

        self.theme_btn = ctk.CTkButton(bottom, text="🌙 Dark" if ctk.get_appearance_mode() == "Dark" else "☀️ Light",
                                       command=self.toggle_theme, fg_color=ACCENT, hover_color=ACCENT_DARK)
        self.theme_btn.pack(fill="x", pady=4)

        self.mode_btn = ctk.CTkButton(bottom, text="Switch to Analog" if not self.analog_mode else "Switch to Digital",
                                      command=self.toggle_clock_mode, fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER)
        self.mode_btn.pack(fill="x", pady=4)

        self.format_btn = ctk.CTkButton(bottom, text="Switch to 12h" if not self.use_12h else "Switch to 24h",
                                        command=self.toggle_time_format, fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER)
        self.format_btn.pack(fill="x", pady=4)

        # Main content area
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.views = {}
        self.build_clock_view()
        self.build_world_view()
        self.build_alarms_view()
        self.build_timer_view()
        self.build_stopwatch_view()

        self.switch_view("clock")

    def switch_view(self, name):
        for v in self.views.values():
            v.pack_forget()
        self.views[name].pack(fill="both", expand=True)
        self.current_view = name
        # Highlight nav
        for k, btn in self.nav_buttons.items():
            if k == name:
                btn.configure(fg_color=ACCENT, text_color="white")
            else:
                btn.configure(fg_color="transparent",
                              text_color=TEXT_DARK if ctk.get_appearance_mode() == "Dark" else TEXT_LIGHT)

    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        new_mode = "light" if current == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        store.data["appearance"] = new_mode
        store.save()
        self.theme_btn.configure(text="🌙 Dark" if new_mode == "dark" else "☀️ Light")
        # Force redraw of dynamic elements
        self.update_theme_colors()

    def update_theme_colors(self):
        is_dark = ctk.get_appearance_mode() == "Dark"
        self.configure(fg_color=BG_DARK if is_dark else BG_LIGHT)
        self.sidebar.configure(fg_color=CARD_DARK if is_dark else "#E8E8E8")
        # Rebuild views so clock area and cards pick up the new colors
        current = self.current_view
        self.build_clock_view()
        self.build_world_view()
        self.load_world_clocks()
        self.build_alarms_view()
        self.load_alarms()
        self.build_timer_view()
        self.build_stopwatch_view()
        self.switch_view(current)

    def toggle_time_format(self):
        self.use_12h = not self.use_12h
        store.data["time_format"] = "12h" if self.use_12h else "24h"
        store.save()
        self.format_btn.configure(text="Switch to 24h" if self.use_12h else "Switch to 12h")
        # Refresh displays and selectors
        if self.current_view == "clock" and not self.analog_mode:
            self.build_clock_view()
            self.switch_view("clock")
        if self.current_view == "world":
            self.load_world_clocks()
        if self.current_view == "alarms":
            self.build_alarms_view()
            self.load_alarms()
            self.switch_view("alarms")

    def toggle_clock_mode(self):
        self.analog_mode = not self.analog_mode
        store.data["clock_mode"] = "analog" if self.analog_mode else "digital"
        store.save()
        self.mode_btn.configure(text="Switch to Digital" if self.analog_mode else "Switch to Analog")
        self.build_clock_view()  # rebuild
        self.switch_view("clock")

    # -------------------------------------------------------------------------
    # Clock View
    # -------------------------------------------------------------------------
    def build_clock_view(self):
        if "clock" in self.views:
            self.views["clock"].destroy()

        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.views["clock"] = frame

        is_dark = ctk.get_appearance_mode() == "Dark"
        card_bg = CARD_DARK if is_dark else CARD_LIGHT
        text_c = TEXT_DARK if is_dark else TEXT_LIGHT

        card = ctk.CTkFrame(frame, fg_color=card_bg, corner_radius=20, border_width=2, border_color=ACCENT)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        if self.analog_mode:
            self.canvas = tk.Canvas(card, width=420, height=420, bg=card_bg, highlightthickness=0)
            self.canvas.pack(pady=(20, 8))
            self.draw_analog()
        else:
            self.time_label = ctk.CTkLabel(card, text="00:00:00",
                                           font=ctk.CTkFont(family="Consolas", size=92, weight="bold"),
                                           text_color=ACCENT)
            self.time_label.pack(pady=(60, 10))
        self.date_label = ctk.CTkLabel(card, text=datetime.now().strftime("%A, %B %d, %Y"),
                                       font=ctk.CTkFont(size=24), text_color=text_c)
        self.date_label.pack()

        self.tz_label = ctk.CTkLabel(card, text="Local Time", font=ctk.CTkFont(size=16), text_color=text_c)
        self.tz_label.pack(pady=10)

    def draw_analog(self):
        c = self.canvas
        c.delete("all")
        w, h = 420, 420
        cx, cy = w // 2, h // 2
        r = 180
        is_dark = ctk.get_appearance_mode() == "Dark"
        face = "#111111" if is_dark else "#FAFAFA"
        tick = ACCENT if is_dark else "#AA0000"

        # Face
        c.create_oval(cx-r-8, cy-r-8, cx+r+8, cy+r+8, outline=ACCENT, width=4)
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill=face, outline="")

        # Ticks
        for i in range(60):
            ang = math.radians(i * 6 - 90)
            length = 14 if i % 5 == 0 else 7
            x1 = cx + (r - length) * math.cos(ang)
            y1 = cy + (r - length) * math.sin(ang)
            x2 = cx + r * math.cos(ang)
            y2 = cy + r * math.sin(ang)
            c.create_line(x1, y1, x2, y2, fill=tick, width=2 if i % 5 == 0 else 1)

        # Numbers
        for i in range(1, 13):
            ang = math.radians(i * 30 - 90)
            x = cx + (r - 35) * math.cos(ang)
            y = cy + (r - 35) * math.sin(ang)
            c.create_text(x, y, text=str(i), fill=ACCENT, font=("Helvetica", 16, "bold"))

        now = datetime.now()
        sec = now.second
        minute = now.minute + sec / 60
        hour = (now.hour % 12) + minute / 60

        def hand(angle_deg, length, width, color):
            ang = math.radians(angle_deg - 90)
            x = cx + length * math.cos(ang)
            y = cy + length * math.sin(ang)
            c.create_line(cx, cy, x, y, fill=color, width=width, capstyle="round")

        hand(hour * 30, r * 0.5, 8, "#FFFFFF" if is_dark else "#222222")
        hand(minute * 6, r * 0.75, 5, ACCENT)
        hand(sec * 6, r * 0.85, 2, "#FF6666")

        c.create_oval(cx-6, cy-6, cx+6, cy+6, fill=ACCENT, outline="")

    # -------------------------------------------------------------------------
    # World Clocks
    # -------------------------------------------------------------------------
    def build_world_view(self):
        if "world" in self.views:
            self.views["world"].destroy()
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.views["world"] = frame

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="World Clocks", font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=ACCENT).pack(side="left")

        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.pack(fill="x", pady=5)
        self.tz_search = ctk.CTkEntry(search_frame, placeholder_text="Search timezone (e.g. Tokyo, London, New_York)...",
                                      width=400)
        self.tz_search.pack(side="left", padx=(0, 10))
        ctk.CTkButton(search_frame, text="Add", command=self.add_world_clock,
                      fg_color=ACCENT, hover_color=ACCENT_DARK).pack(side="left")

        self.world_scroll = ctk.CTkScrollableFrame(frame, height=420)
        self.world_scroll.pack(fill="both", expand=True, pady=10)

    def load_world_clocks(self):
        for card, _, _ in self.world_clock_widgets:
            card.destroy()
        self.world_clock_widgets.clear()

        for tz_name in store.data["world_clocks"]:
            self.add_world_clock_widget(tz_name)

    def add_world_clock_widget(self, tz_name):
        is_dark = ctk.get_appearance_mode() == "Dark"
        card = ctk.CTkFrame(self.world_scroll, fg_color=CARD_DARK if is_dark else CARD_LIGHT,
                            corner_radius=12, border_width=1, border_color=ACCENT)
        card.pack(fill="x", pady=6, padx=4)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=15, pady=10)
        name_lbl = ctk.CTkLabel(left, text=tz_name.replace("_", " "), font=ctk.CTkFont(size=16, weight="bold"))
        name_lbl.pack(anchor="w")
        time_lbl = ctk.CTkLabel(left, text="--:--:--", font=ctk.CTkFont(size=22), text_color=ACCENT)
        time_lbl.pack(anchor="w")

        def remove():
            if tz_name in store.data["world_clocks"]:
                store.data["world_clocks"].remove(tz_name)
                store.save()
                self.load_world_clocks()

        ctk.CTkButton(card, text="✕", width=40, command=remove,
                      fg_color="#333", hover_color="#555").pack(side="right", padx=10)

        self.world_clock_widgets.append((card, time_lbl, tz_name))

    def add_world_clock(self):
        query = self.tz_search.get().strip().lower()
        if not query:
            return
        all_tz = available_timezones()
        matches = [tz for tz in all_tz if query in tz.lower() or query in tz.replace("_", " ").lower()]
        if not matches:
            messagebox.showinfo("No match", "No timezone found. Try a city or region name.")
            return
        if len(matches) == 1:
            chosen = matches[0]
        else:
            # Simple selection dialog
            dialog = ctk.CTkToplevel(self)
            dialog.title("Select Timezone")
            dialog.geometry("400x300")
            dialog.transient(self)
            dialog.grab_set()
            lb = tk.Listbox(dialog, font=("Consolas", 11))
            for m in sorted(matches)[:50]:
                lb.insert("end", m)
            lb.pack(fill="both", expand=True, padx=10, pady=10)
            chosen = [None]
            def select():
                sel = lb.curselection()
                if sel:
                    chosen[0] = lb.get(sel[0])
                    dialog.destroy()
            ctk.CTkButton(dialog, text="Add Selected", command=select).pack(pady=5)
            self.wait_window(dialog)
            if not chosen[0]:
                return
            chosen = chosen[0]

        if chosen not in store.data["world_clocks"]:
            store.data["world_clocks"].append(chosen)
            store.save()
            self.load_world_clocks()
        self.tz_search.delete(0, "end")

    # -------------------------------------------------------------------------
    # Alarms
    # -------------------------------------------------------------------------
    def build_alarms_view(self):
        if "alarms" in self.views:
            self.views["alarms"].destroy()
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.views["alarms"] = frame

        ctk.CTkLabel(frame, text="Alarms", font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=ACCENT).pack(anchor="w", pady=(0, 10))

        form = ctk.CTkFrame(frame)
        form.pack(fill="x", pady=5)

        # Scroll-wheel time selectors that respect 12h/24h
        if self.use_12h:
            self.alarm_hour = WheelPicker(form, [f"{i}" for i in range(1, 13)], initial="7")
            self.alarm_ampm = WheelPicker(form, ["AM", "PM"], initial="AM", wrap=False)
        else:
            self.alarm_hour = WheelPicker(form, [f"{i:02d}" for i in range(24)], initial="07")
            self.alarm_ampm = None

        self.alarm_hour.pack(side="left", padx=(10, 2), pady=8)
        ctk.CTkLabel(form, text=":", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=ACCENT).pack(side="left")
        self.alarm_min = WheelPicker(form, [f"{i:02d}" for i in range(60)], initial="00")
        self.alarm_min.pack(side="left", padx=2, pady=8)
        if self.alarm_ampm:
            self.alarm_ampm.pack(side="left", padx=(6, 4), pady=8)

        self.alarm_label = ctk.CTkEntry(form, width=180, placeholder_text="Label")
        self.alarm_label.pack(side="left", padx=8)
        self.alarm_repeat = ctk.CTkOptionMenu(form, values=["Once", "Daily", "Weekdays", "Weekends", "Custom"],
                                              width=120)
        self.alarm_repeat.pack(side="left", padx=4)
        ctk.CTkButton(form, text="+ Add Alarm", command=self.add_alarm,
                      fg_color=ACCENT, hover_color=ACCENT_DARK).pack(side="left", padx=8)

        self.alarm_scroll = ctk.CTkScrollableFrame(frame, height=380)
        self.alarm_scroll.pack(fill="both", expand=True, pady=10)

    def load_alarms(self):
        for w in self.alarm_widgets:
            w.destroy()
        self.alarm_widgets.clear()
        for alarm in store.data["alarms"]:
            self.render_alarm(alarm)

    def render_alarm(self, alarm):
        is_dark = ctk.get_appearance_mode() == "Dark"
        card = ctk.CTkFrame(self.alarm_scroll, fg_color=CARD_DARK if is_dark else CARD_LIGHT,
                            corner_radius=10, border_width=1, border_color=ACCENT)
        card.pack(fill="x", pady=4, padx=4)

        enabled = alarm.get("enabled", True)
        status = "ON" if enabled else "OFF"
        color = ACCENT if enabled else "#666"

        # Display time in current format
        try:
            h, m = map(int, alarm["time"].split(":"))
            if self.use_12h:
                ampm = "AM" if h < 12 else "PM"
                h12 = h % 12
                if h12 == 0:
                    h12 = 12
                display_time = f"{h12}:{m:02d} {ampm}"
            else:
                display_time = alarm["time"]
        except Exception:
            display_time = alarm["time"]

        info = ctk.CTkLabel(card, text=f"{display_time}  |  {alarm['label']}  |  {alarm['repeat']}  [{status}]",
                            font=ctk.CTkFont(size=15), text_color=color)
        info.pack(side="left", padx=15, pady=8)

        def toggle():
            alarm["enabled"] = not alarm.get("enabled", True)
            store.save()
            self.load_alarms()

        def delete():
            store.data["alarms"] = [a for a in store.data["alarms"] if a.get("id") != alarm.get("id")]
            store.save()
            self.load_alarms()

        ctk.CTkButton(card, text="Toggle", width=70, command=toggle, fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER).pack(side="right", padx=4)
        ctk.CTkButton(card, text="Del", width=50, fg_color="#555555", hover_color="#666666", command=delete).pack(side="right", padx=4)

        self.alarm_widgets.append(card)

    def add_alarm(self):
        try:
            h_str = self.alarm_hour.get()
            m_str = self.alarm_min.get()
            h = int(h_str)
            m = int(m_str)
            if self.use_12h and self.alarm_ampm:
                ampm = self.alarm_ampm.get()
                if ampm == "PM" and h != 12:
                    h += 12
                elif ampm == "AM" and h == 12:
                    h = 0
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            messagebox.showerror("Invalid", "Please select a valid time")
            return
        label = self.alarm_label.get().strip() or "Alarm"
        repeat = self.alarm_repeat.get()
        alarm = {
            "id": int(time.time() * 1000),
            "time": f"{h:02d}:{m:02d}",
            "label": label,
            "repeat": repeat,
            "enabled": True,
            "days": []  # for Custom later
        }
        store.data["alarms"].append(alarm)
        store.save()
        self.load_alarms()
        self.alarm_label.delete(0, "end")

    def check_alarms(self):
        now = datetime.now()
        current = now.strftime("%H:%M")
        weekday = now.weekday()  # 0=Mon

        for alarm in store.data["alarms"]:
            if not alarm.get("enabled", True):
                continue
            aid = alarm["id"]
            if aid in self.snooze_alarms:
                if datetime.now() >= self.snooze_alarms[aid]:
                    self.trigger_alarm(alarm)
                    del self.snooze_alarms[aid]
                continue

            if alarm["time"] != current:
                continue

            # Check if already triggered this minute (simple debounce via last_trigger)
            last = alarm.get("_last_trigger")
            if last == current:
                continue
            alarm["_last_trigger"] = current

            should = False
            rep = alarm["repeat"]
            if rep == "Once":
                should = True
                alarm["enabled"] = False  # auto-disable after once
            elif rep == "Daily":
                should = True
            elif rep == "Weekdays" and weekday < 5:
                should = True
            elif rep == "Weekends" and weekday >= 5:
                should = True
            elif rep == "Custom":
                should = True  # expand later

            if should:
                self.trigger_alarm(alarm)
                store.save()

    def trigger_alarm(self, alarm):
        play_alarm_sound()
        # In-app popup
        popup = ctk.CTkToplevel(self)
        popup.title("ALARM")
        popup.geometry("420x220")
        popup.transient(self)
        popup.attributes("-topmost", True)
        popup.configure(fg_color="#1A0000")

        ctk.CTkLabel(popup, text="⏰ ALARM", font=ctk.CTkFont(size=32, weight="bold"),
                     text_color=ACCENT).pack(pady=20)
        ctk.CTkLabel(popup, text=alarm["label"], font=ctk.CTkFont(size=18)).pack()
        ctk.CTkLabel(popup, text=alarm["time"], font=ctk.CTkFont(size=16), text_color="#FF6666").pack(pady=5)

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=20)

        def snooze():
            self.snooze_alarms[alarm["id"]] = datetime.now() + timedelta(minutes=5)
            popup.destroy()

        def dismiss():
            popup.destroy()

        ctk.CTkButton(btn_frame, text="Snooze 5 min", command=snooze, fg_color="#444").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Dismiss", command=dismiss, fg_color=ACCENT).pack(side="left", padx=10)

    # -------------------------------------------------------------------------
    # Timer
    # -------------------------------------------------------------------------
    def build_timer_view(self):
        # Keep the chosen duration across rebuilds (e.g. theme toggle)
        if hasattr(self, "timer_h"):
            prev = (self.timer_h.get(), self.timer_m.get(), self.timer_s.get())
        else:
            prev = ("00", "05", "00")
        if "timer" in self.views:
            self.views["timer"].destroy()
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.views["timer"] = frame

        ctk.CTkLabel(frame, text="Timer", font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=ACCENT).pack(anchor="w")

        self.timer_display = ctk.CTkLabel(frame, text="00:00:00",
                                          font=ctk.CTkFont(size=72, weight="bold"), text_color=ACCENT)
        self.timer_display.pack(pady=40)

        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.pack(pady=10)

        def picker(values, initial, unit):
            w = WheelPicker(input_frame, values, initial=initial, command=self._on_timer_pick)
            w.pack(side="left", padx=4)
            ctk.CTkLabel(input_frame, text=unit, font=ctk.CTkFont(size=16),
                         text_color=ACCENT).pack(side="left", padx=(0, 10))
            return w

        self.timer_h = picker([f"{i:02d}" for i in range(24)], prev[0], "h")
        self.timer_m = picker([f"{i:02d}" for i in range(60)], prev[1], "m")
        self.timer_s = picker([f"{i:02d}" for i in range(60)], prev[2], "s")
        self._timer_preview()

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text="Start", command=self.start_timer, fg_color=ACCENT, hover_color=ACCENT_DARK).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Pause", command=self.pause_timer, fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Reset", command=self.reset_timer, fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER).pack(side="left", padx=8)

    def _timer_preview(self):
        """Show the paused time, or the wheel selection when idle."""
        if self.timer_running:
            return
        if self.timer_remaining > 0:
            total = int(self.timer_remaining)
        else:
            total = int(self.timer_h.get()) * 3600 + int(self.timer_m.get()) * 60 + int(self.timer_s.get())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        self.timer_display.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

    def _on_timer_pick(self, _value):
        if not self.timer_running:
            self.timer_remaining = 0  # a new selection replaces any paused countdown
            self._timer_preview()

    def start_timer(self):
        if self.timer_running:
            return
        if self.timer_remaining > 0:
            total = self.timer_remaining  # resume after pause
        else:
            total = int(self.timer_h.get()) * 3600 + int(self.timer_m.get()) * 60 + int(self.timer_s.get())
            if total <= 0:
                return
        self.timer_remaining = total
        self.timer_end = time.time() + total
        self.timer_running = True

    def pause_timer(self):
        if self.timer_running:
            self.timer_remaining = max(0, self.timer_end - time.time())
            self.timer_running = False

    def reset_timer(self):
        self.timer_running = False
        self.timer_remaining = 0
        self._timer_preview()

    # -------------------------------------------------------------------------
    # Stopwatch
    # -------------------------------------------------------------------------
    def build_stopwatch_view(self):
        if "stopwatch" in self.views:
            self.views["stopwatch"].destroy()
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.views["stopwatch"] = frame

        ctk.CTkLabel(frame, text="Stopwatch", font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=ACCENT).pack(anchor="w")

        self.sw_display = ctk.CTkLabel(frame, text="00:00:00.00",
                                       font=ctk.CTkFont(size=64, weight="bold"), text_color=ACCENT)
        self.sw_display.pack(pady=40)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Start / Pause", command=self.toggle_stopwatch, fg_color=ACCENT, hover_color=ACCENT_DARK).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Lap", command=self.lap_stopwatch, fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER).pack(side="left", padx=8)
        ctk.CTkButton(btn_frame, text="Reset", command=self.reset_stopwatch, fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER).pack(side="left", padx=8)

        self.laps_frame = ctk.CTkScrollableFrame(frame, height=280)
        self.laps_frame.pack(fill="both", expand=True, pady=10)
        self.laps_labels = []

    def toggle_stopwatch(self):
        if not self.stopwatch_running:
            self.stopwatch_start = time.time() - self.stopwatch_elapsed
            self.stopwatch_running = True
        else:
            self.stopwatch_elapsed = time.time() - self.stopwatch_start
            self.stopwatch_running = False

    def lap_stopwatch(self):
        if self.stopwatch_running:
            elapsed = time.time() - self.stopwatch_start
            self.stopwatch_laps.append(elapsed)
            self.update_laps_display()

    def reset_stopwatch(self):
        self.stopwatch_running = False
        self.stopwatch_elapsed = 0.0
        self.stopwatch_laps.clear()
        self.sw_display.configure(text="00:00:00.00")
        self.update_laps_display()

    def update_laps_display(self):
        for lbl in self.laps_labels:
            lbl.destroy()
        self.laps_labels.clear()
        for i, lap in enumerate(reversed(self.stopwatch_laps), 1):
            mins, secs = divmod(lap, 60)
            hrs, mins = divmod(mins, 60)
            text = f"Lap {len(self.stopwatch_laps)-i+1}: {int(hrs):02d}:{int(mins):02d}:{secs:05.2f}"
            lbl = ctk.CTkLabel(self.laps_frame, text=text, font=ctk.CTkFont(size=14))
            lbl.pack(anchor="w", padx=10, pady=2)
            self.laps_labels.append(lbl)

    # -------------------------------------------------------------------------
    # Main update loop
    # -------------------------------------------------------------------------
    def update_loop(self):
        now = datetime.now()

        # Clock
        if self.current_view == "clock":
            if self.analog_mode and hasattr(self, "canvas"):
                self.draw_analog()
            else:
                fmt = "%I:%M:%S %p" if self.use_12h else "%H:%M:%S"
                self.time_label.configure(text=now.strftime(fmt))
            self.date_label.configure(text=now.strftime("%A, %B %d, %Y"))

        # World clocks
        if self.current_view == "world":
            fmt = "%I:%M:%S %p" if self.use_12h else "%H:%M:%S"
            for card, lbl, tz_name in self.world_clock_widgets:
                try:
                    tz_time = datetime.now(ZoneInfo(tz_name))
                    lbl.configure(text=tz_time.strftime(fmt))
                except Exception:
                    lbl.configure(text="Error")

        # Timer
        if self.timer_running and self.timer_end:
            rem = max(0, self.timer_end - time.time())
            if rem <= 0:
                self.timer_running = False
                self.timer_remaining = 0
                self.timer_display.configure(text="00:00:00")
                play_alarm_sound()
                messagebox.showinfo("Timer", "Time's up!")
            else:
                h, rem = divmod(int(rem), 3600)
                m, s = divmod(rem, 60)
                self.timer_display.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

        # Stopwatch
        if self.stopwatch_running:
            elapsed = time.time() - self.stopwatch_start
            mins, secs = divmod(elapsed, 60)
            hrs, mins = divmod(mins, 60)
            self.sw_display.configure(text=f"{int(hrs):02d}:{int(mins):02d}:{secs:05.2f}")

        # Alarms (check every second)
        self.check_alarms()

        self.after(100, self.update_loop)  # ~10 fps for smooth analog, 100ms is fine

# =============================================================================
# Entry point
# =============================================================================
if __name__ == "__main__":
    app = CrimsonChrono()
    app.mainloop()
