"""
=============================================================================
Hydration Tracker GUI  —  Tkinter Pink UI
Wraps the HydrationEngine backend with a full graphical interface.
=============================================================================
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

# ── allow running from any working directory ──────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from hydration_engine import (
    HydrationEngine, User, WeatherService, WeatherData,
    Trimester, ActivityLevel,
    BloodPressure, BPCategory, BMICategory, ClinicalFlag,
)

# NEW — import the tips/facts parser module
from pregnancy_tips import (
    load_tips, get_random_tip, get_all_tips_for_trimester,
    get_tips_for_trimester, TipsData,
)

# =============================================================================
# Pink Color Palette
# =============================================================================
C = {
    "bg_deep":    "#2D0A1E",
    "bg_card":    "#3D1530",
    "bg_input":   "#4A1C3A",
    "bg_hover":   "#5C2248",
    "pink_light": "#FFB3D1",
    "pink_mid":   "#FF69A0",
    "pink_hot":   "#FF1493",
    "pink_pale":  "#FFE4F0",
    "green":      "#7FFFD4",
    "amber":      "#FFD166",
    "red":        "#FF6B8A",
    "white":      "#FFFFFF",
    "separator":  "#6B2D50",
    "tip_bg":     "#4E1040",   # slightly different bg for tips card
    "fact_gold":  "#FFD166",   # fact highlight colour
}

FONT_FAMILY = "Helvetica"


# =============================================================================
# Reusable Widget Helpers
# =============================================================================

def styled_label(parent, text, size=11, bold=False, color=None, **kw):
    weight = "bold" if bold else "normal"
    fg = color or C["pink_light"]
    return tk.Label(
        parent, text=text,
        font=(FONT_FAMILY, size, weight),
        fg=fg, bg=parent.cget("bg"), **kw
    )


def styled_button(parent, text, command, width=18, big=False, color=None):
    size   = 13 if big else 11
    bg_col = color or C["pink_hot"]
    btn = tk.Button(
        parent, text=text, command=command,
        font=(FONT_FAMILY, size, "bold"),
        fg=C["white"], bg=bg_col,
        activeforeground=C["white"], activebackground=C["bg_hover"],
        relief="flat", bd=0, cursor="hand2",
        padx=10, pady=8 if big else 5, width=width,
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=C["bg_hover"]))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg_col))
    return btn


def card_frame(parent, **kw):
    return tk.Frame(parent, bg=C["bg_card"], **kw)


# =============================================================================
# Circular Progress Canvas
# =============================================================================

class CircularProgress(tk.Canvas):
    """Draws an animated arc representing hydration progress."""

    RADIUS  = 90
    TRACK_W = 16

    def __init__(self, parent, **kw):
        size = (self.RADIUS + self.TRACK_W) * 2 + 10
        super().__init__(
            parent, width=size, height=size,
            bg=C["bg_card"], highlightthickness=0, **kw
        )
        self._cx = size / 2
        self._cy = size / 2
        self._draw(0.0, "0 ml", "of 0 ml")

    def _draw(self, pct: float, line1: str, line2: str):
        self.delete("all")
        cx, cy = self._cx, self._cy
        r, tw  = self.RADIUS, self.TRACK_W
        x0, y0 = cx - r, cy - r
        x1, y1 = cx + r, cy + r

        self.create_arc(
            x0 - tw/2, y0 - tw/2, x1 + tw/2, y1 + tw/2,
            start=90, extent=-360,
            style="arc", outline=C["separator"], width=tw,
        )
        if pct > 0:
            extent  = min(360, pct * 3.6)
            arc_col = C["green"] if pct >= 80 else (C["amber"] if pct >= 40 else C["red"])
            self.create_arc(
                x0 - tw/2, y0 - tw/2, x1 + tw/2, y1 + tw/2,
                start=90, extent=-extent,
                style="arc", outline=arc_col, width=tw,
            )
        self.create_text(cx, cy - 14, text=line1,
                         font=(FONT_FAMILY, 13, "bold"), fill=C["pink_pale"])
        self.create_text(cx, cy + 12, text=line2,
                         font=(FONT_FAMILY, 9), fill=C["pink_light"])
        self.create_text(cx, cy + 34, text=f"{pct:.0f}%",
                         font=(FONT_FAMILY, 15, "bold"), fill=C["pink_hot"])

    def update_progress(self, consumed_ml: float, goal_ml: float):
        pct = min(100.0, (consumed_ml / goal_ml * 100) if goal_ml else 0)
        self._draw(pct, f"{consumed_ml:.0f} ml", f"of {goal_ml:.0f} ml")


# =============================================================================
# Tips & Facts Panel  (new standalone widget)
# =============================================================================

class TipsPanel(tk.Frame):
    """
    Displays pregnancy tips and morale-boosting facts from the parsed
    Pregnancy_Tips_and_Facts.txt file, filtered to the user's trimester.

    Layout
    ------
    ┌─────────────────────────────────────────────┐
    │  🌸 Tips & Facts  ·  Trimester N            │
    │  Focus: <subtitle>                           │
    │  ┌────────────────────────────────────────┐ │
    │  │  <scrollable list of tips & facts>     │ │
    │  └────────────────────────────────────────┘ │
    │  [ ← Prev ]  Tip 2 of 6  [ Next → ]        │
    │  [ ✨ Random Tip ]                           │
    └─────────────────────────────────────────────┘
    """

    # Emoji badge per kind
    _KIND_ICON = {"tip": "💡", "fact": "✨"}
    # Wrap width for the text display (pixels)
    _WRAP_PX = 310

    def __init__(self, parent, tips_data: TipsData, trimester_number: int, **kw):
        super().__init__(parent, bg=C["tip_bg"], **kw)
        self._tips_data        = tips_data
        self._trimester_number = trimester_number
        self._items: list[tuple[str, str]] = []   # [(kind, text), ...]
        self._current_index    = 0

        self._load_items()
        self._build()
        self._show_item(0)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_items(self):
        """Pull all tips + facts for this trimester from the parsed data."""
        self._items = get_all_tips_for_trimester(
            self._tips_data, self._trimester_number
        )
        if not self._items:
            self._items = [("tip", "Stay hydrated and take good care of yourself! 💧")]

    def change_trimester(self, trimester_number: int):
        """Hot-swap to a different trimester's content without rebuilding the widget."""
        self._trimester_number = trimester_number
        self._load_items()
        self._current_index = 0
        self._show_item(0)
        self._update_focus_label()

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build(self):
        self.columnconfigure(0, weight=1)

        # ── Header row ────────────────────────────────────────────────
        header_row = tk.Frame(self, bg=C["tip_bg"])
        header_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 2))
        header_row.columnconfigure(0, weight=1)

        tk.Label(
            header_row,
            text=f"🌸  Tips & Facts  ·  Trimester {self._trimester_number}",
            font=(FONT_FAMILY, 12, "bold"),
            fg=C["pink_mid"], bg=C["tip_bg"],
        ).grid(row=0, column=0, sticky="w")

        # ── Focus subtitle ────────────────────────────────────────────
        content = get_tips_for_trimester(self._tips_data, self._trimester_number)
        focus_text = content.focus if content else ""

        self._focus_lbl = tk.Label(
            self, text=f"Focus: {focus_text}",
            font=(FONT_FAMILY, 9, "italic"),
            fg=C["pink_light"], bg=C["tip_bg"],
            wraplength=self._WRAP_PX, justify="left",
        )
        self._focus_lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))

        # ── Main text display ─────────────────────────────────────────
        # Outer frame with subtle border effect
        text_outer = tk.Frame(self, bg=C["separator"], padx=1, pady=1)
        text_outer.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))
        text_outer.columnconfigure(0, weight=1)

        text_inner = tk.Frame(text_outer, bg=C["bg_input"])
        text_inner.grid(row=0, column=0, sticky="ew")
        text_inner.columnconfigure(0, weight=1)

        # Kind badge (💡 Tip / ✨ Fact)
        self._kind_lbl = tk.Label(
            text_inner, text="",
            font=(FONT_FAMILY, 9, "bold"),
            fg=C["fact_gold"], bg=C["bg_input"],
            anchor="w",
        )
        self._kind_lbl.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))

        # Main tip / fact text — wrapping label
        self._tip_lbl = tk.Label(
            text_inner, text="",
            font=(FONT_FAMILY, 10),
            fg=C["pink_pale"], bg=C["bg_input"],
            wraplength=self._WRAP_PX,
            justify="left",
            anchor="nw",
        )
        self._tip_lbl.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 12))

        # ── Navigation row ────────────────────────────────────────────
        nav = tk.Frame(self, bg=C["tip_bg"])
        nav.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 6))
        nav.columnconfigure(1, weight=1)

        self._prev_btn = tk.Button(
            nav, text="← Prev",
            command=self._prev_item,
            font=(FONT_FAMILY, 9, "bold"),
            fg=C["white"], bg=C["bg_hover"],
            activeforeground=C["white"], activebackground=C["separator"],
            relief="flat", bd=0, cursor="hand2", padx=8, pady=4,
        )
        self._prev_btn.grid(row=0, column=0)

        self._counter_lbl = tk.Label(
            nav, text="",
            font=(FONT_FAMILY, 9),
            fg=C["pink_light"], bg=C["tip_bg"],
        )
        self._counter_lbl.grid(row=0, column=1)

        self._next_btn = tk.Button(
            nav, text="Next →",
            command=self._next_item,
            font=(FONT_FAMILY, 9, "bold"),
            fg=C["white"], bg=C["bg_hover"],
            activeforeground=C["white"], activebackground=C["separator"],
            relief="flat", bd=0, cursor="hand2", padx=8, pady=4,
        )
        self._next_btn.grid(row=0, column=2)

        # ── Random tip button ─────────────────────────────────────────
        tk.Button(
            self, text="🎲  Random Tip or Fact",
            command=self._show_random,
            font=(FONT_FAMILY, 10, "bold"),
            fg=C["white"], bg=C["pink_mid"],
            activeforeground=C["white"], activebackground=C["bg_hover"],
            relief="flat", bd=0, cursor="hand2",
            padx=10, pady=6,
        ).grid(row=4, column=0, sticky="ew", padx=12, pady=(4, 12))

    # ------------------------------------------------------------------
    # Display logic
    # ------------------------------------------------------------------

    def _show_item(self, index: int):
        """Render the tip/fact at *index* in self._items."""
        if not self._items:
            return

        # Clamp index
        index = max(0, min(index, len(self._items) - 1))
        self._current_index = index

        kind, text = self._items[index]
        icon  = self._KIND_ICON.get(kind, "💡")
        badge = f"{icon}  {'Practical Tip' if kind == 'tip' else 'Morale-Boosting Fact'}"

        self._kind_lbl.config(
            text=badge,
            fg=C["pink_mid"] if kind == "tip" else C["fact_gold"],
        )
        self._tip_lbl.config(text=text)
        self._counter_lbl.config(
            text=f"{index + 1} of {len(self._items)}"
        )

        # Grey-out nav buttons at boundaries
        self._prev_btn.config(
            state="normal" if index > 0 else "disabled",
            fg=C["white"] if index > 0 else C["separator"],
        )
        self._next_btn.config(
            state="normal" if index < len(self._items) - 1 else "disabled",
            fg=C["white"] if index < len(self._items) - 1 else C["separator"],
        )

    def _prev_item(self):
        self._show_item(self._current_index - 1)

    def _next_item(self):
        self._show_item(self._current_index + 1)

    def _show_random(self):
        import random
        if self._items:
            idx = random.randrange(len(self._items))
            self._show_item(idx)

    def _update_focus_label(self):
        content = get_tips_for_trimester(self._tips_data, self._trimester_number)
        focus_text = content.focus if content else ""
        self._focus_lbl.config(text=f"Focus: {focus_text}")


# =============================================================================
# Setup / Profile Screen
# =============================================================================

class SetupScreen(tk.Frame):
    """
    Profile intake screen — now split into three sections:

      👤 Profile          : name, location, age, trimester, pregnancy number, activity
      🩺 Clinical Vitals  : BMI, systolic/diastolic blood pressure   [NEW]
      🌤️ Weather          : temperature, humidity

    Wrapped in a scrollable canvas so it still fits on smaller screens
    now that there are 11 fields instead of 6.
    """

    # Pregnancy-number dropdown → integer gravidity mapping
    PREGNANCY_NUMBER_OPTIONS = ["1st (First pregnancy)", "2nd", "3rd",
                               "4th", "5th", "6th or more"]
    PREGNANCY_NUMBER_MAP = {
        "1st (First pregnancy)": 1, "2nd": 2, "3rd": 3,
        "4th": 4, "5th": 5, "6th or more": 6,
    }

    def __init__(self, parent, on_submit):
        super().__init__(parent, bg=C["bg_deep"])
        self._on_submit = on_submit
        self._build()

    # ------------------------------------------------------------------
    # Scrollable scaffold
    # ------------------------------------------------------------------

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Scrollable canvas wrapper ───────────────────────────────
        canvas = tk.Canvas(self, bg=C["bg_deep"], highlightthickness=0)
        vscroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")

        inner = tk.Frame(canvas, bg=C["bg_deep"])
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_inner_configure)

        def _on_canvas_configure(event):
            canvas.itemconfig(inner_id, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        inner.columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────
        hdr = card_frame(inner, pady=20, padx=30)
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        tk.Label(hdr, text="💧 HydraMaterna",
                 font=(FONT_FAMILY, 26, "bold"),
                 fg=C["pink_hot"], bg=C["bg_card"]).pack()
        tk.Label(hdr,
                 text="Dynamic Hydration Engine for Maternal Health  ·  UN SDG 3.1",
                 font=(FONT_FAMILY, 10), fg=C["pink_light"], bg=C["bg_card"]).pack(pady=(4, 0))

        self._vars: dict[str, tk.StringVar] = {}
        entry_kw = dict(font=(FONT_FAMILY, 11), fg=C["pink_pale"],
                        bg=C["bg_input"], insertbackground=C["pink_hot"],
                        relief="flat", bd=0)

        # ── Section 1: Profile ────────────────────────────────────────
        profile_card = card_frame(inner, padx=30, pady=20)
        profile_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        profile_card.columnconfigure(1, weight=1)

        tk.Label(profile_card, text="👤  Profile",
                 font=(FONT_FAMILY, 13, "bold"),
                 fg=C["pink_mid"], bg=C["bg_card"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        profile_fields = [
            ("Your Name",       "name_var",  "entry", None),
            ("Location",        "loc_var",   "entry", None),
            ("Age (years)",     "age_var",   "entry", None),
            ("Trimester",       "trim_var",  "combo", ["1st (Weeks 1–12)",
                                                        "2nd (Weeks 13–26)",
                                                        "3rd (Weeks 27–40)"]),
            ("Pregnancy Number","preg_var",  "combo", self.PREGNANCY_NUMBER_OPTIONS),
            ("Activity Level",  "act_var",   "combo", ["Light", "Moderate", "High"]),
        ]
        self._add_fields(profile_card, profile_fields, entry_kw, start_row=1)

        # ── Section 2: Clinical Vitals  [NEW] ───────────────────────
        clinical_card = card_frame(inner, padx=30, pady=20)
        clinical_card.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        clinical_card.columnconfigure(1, weight=1)

        tk.Label(clinical_card, text="🩺  Clinical Vitals",
                 font=(FONT_FAMILY, 13, "bold"),
                 fg=C["pink_mid"], bg=C["bg_card"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        tk.Label(clinical_card,
                 text="Used to fine-tune your hydration goal for safety.",
                 font=(FONT_FAMILY, 9, "italic"),
                 fg=C["pink_light"], bg=C["bg_card"]).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        clinical_fields = [
            ("BMI (pre-pregnancy)",   "bmi_var",   "entry", None),
            ("Systolic BP (mmHg)",    "sys_var",   "entry", None),
            ("Diastolic BP (mmHg)",   "dia_var",   "entry", None),
        ]
        self._add_fields(clinical_card, clinical_fields, entry_kw, start_row=2)

        # ── Section 3: Weather ───────────────────────────────────────
        weather_card = card_frame(inner, padx=30, pady=20)
        weather_card.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))
        weather_card.columnconfigure(1, weight=1)

        tk.Label(weather_card, text="🌤️  Weather",
                 font=(FONT_FAMILY, 13, "bold"),
                 fg=C["pink_mid"], bg=C["bg_card"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        weather_fields = [
            ("Temperature (°C)", "temp_var",  "entry", None),
            ("Humidity (%)",     "humid_var", "entry", None),
        ]
        self._add_fields(weather_card, weather_fields, entry_kw, start_row=1)

        # ── Defaults ──────────────────────────────────────────────────
        self._vars["name_var"].set("Amina Rahman")
        self._vars["loc_var"].set("Dhaka, BD")
        self._vars["age_var"].set("32")
        self._vars["preg_var"].set(self.PREGNANCY_NUMBER_OPTIONS[0])
        self._vars["bmi_var"].set("24.0")
        self._vars["sys_var"].set("118")
        self._vars["dia_var"].set("76")
        self._vars["temp_var"].set("34.5")
        self._vars["humid_var"].set("82")

        # ── Submit ────────────────────────────────────────────────────
        submit_wrap = tk.Frame(inner, bg=C["bg_deep"])
        submit_wrap.grid(row=4, column=0, pady=(10, 30))
        styled_button(submit_wrap, "Start Tracking  →", self._submit,
                      big=True, width=22).pack()

    def _add_fields(self, parent, fields, entry_kw, start_row):
        """Helper to lay out a list of (label, var_name, kind, options) rows."""
        for i, (label, var_name, kind, opts) in enumerate(fields):
            row = start_row + i
            styled_label(parent, label, size=10, color=C["pink_light"]).grid(
                row=row, column=0, sticky="w", pady=7, padx=(0, 14))
            if kind == "entry":
                var = tk.StringVar()
                tk.Entry(parent, textvariable=var, width=26, **entry_kw).grid(
                    row=row, column=1, sticky="ew", pady=7)
            else:
                var = tk.StringVar(value=opts[0])
                ttk.Combobox(parent, textvariable=var, values=opts,
                             state="readonly", width=24,
                             font=(FONT_FAMILY, 11)).grid(
                    row=row, column=1, sticky="ew", pady=7)
            self._vars[var_name] = var

    # ------------------------------------------------------------------
    # Validation & submit
    # ------------------------------------------------------------------

    def _submit(self):
        try:
            name  = self._vars["name_var"].get().strip() or "User"
            loc   = self._vars["loc_var"].get().strip()  or "Unknown"
            trim_s = self._vars["trim_var"].get()
            act_s  = self._vars["act_var"].get()
            preg_s = self._vars["preg_var"].get()
            temp   = float(self._vars["temp_var"].get())
            humid  = float(self._vars["humid_var"].get())

            age    = int(float(self._vars["age_var"].get()))
            bmi    = float(self._vars["bmi_var"].get())
            sys_bp = int(float(self._vars["sys_var"].get()))
            dia_bp = int(float(self._vars["dia_var"].get()))
        except ValueError:
            messagebox.showerror(
                "Input Error",
                "Age, BMI, Blood Pressure, Temperature, and Humidity "
                "must all be numbers."
            )
            return

        # ── Sanity-range validation for clinical fields ────────────
        if not (10 <= age <= 60):
            messagebox.showerror("Input Error", "Age must be between 10 and 60.")
            return
        if not (10.0 <= bmi <= 60.0):
            messagebox.showerror("Input Error", "BMI must be between 10 and 60.")
            return
        if not (60 <= sys_bp <= 250):
            messagebox.showerror("Input Error", "Systolic BP must be between 60 and 250 mmHg.")
            return
        if not (30 <= dia_bp <= 150):
            messagebox.showerror("Input Error", "Diastolic BP must be between 30 and 150 mmHg.")
            return
        if sys_bp <= dia_bp:
            messagebox.showerror("Input Error", "Systolic BP must be greater than diastolic BP.")
            return

        trim_map = {"1st (Weeks 1–12)": Trimester.FIRST,
                    "2nd (Weeks 13–26)": Trimester.SECOND,
                    "3rd (Weeks 27–40)": Trimester.THIRD}
        act_map  = {"Light": ActivityLevel.LIGHT,
                    "Moderate": ActivityLevel.MODERATE,
                    "High": ActivityLevel.HIGH}
        pregnancy_number = self.PREGNANCY_NUMBER_MAP[preg_s]

        user = User(
            name             = name,
            trimester        = trim_map[trim_s],
            activity_level   = act_map[act_s],
            location         = loc,
            age              = age,
            bmi              = bmi,
            blood_pressure   = BloodPressure(systolic=sys_bp, diastolic=dia_bp),
            pregnancy_number = pregnancy_number,
        )
        weather = WeatherData(temperature_c=temp, humidity_pct=humid,
                              description="User-provided conditions")
        self._on_submit(user, weather)


# =============================================================================
# Dashboard Screen
# =============================================================================

class DashboardScreen(tk.Frame):
    QUICK_AMOUNTS = [150, 200, 250, 300, 500]
    ALERT_POLL_MS = 30_000

    def __init__(self, parent, engine: HydrationEngine, tips_data: TipsData):
        super().__init__(parent, bg=C["bg_deep"])
        self.engine    = engine
        self._tips_data = tips_data
        self._build()
        self._refresh()
        self._schedule_alert_check()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)

        # Top bar
        topbar = tk.Frame(self, bg=C["bg_card"], pady=10, padx=20)
        topbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        topbar.columnconfigure(1, weight=1)

        tk.Label(topbar, text="💧 HydraMaterna",
                 font=(FONT_FAMILY, 18, "bold"),
                 fg=C["pink_hot"], bg=C["bg_card"]).grid(row=0, column=0, sticky="w")

        self._user_lbl = tk.Label(topbar, text="",
                                   font=(FONT_FAMILY, 10),
                                   fg=C["pink_light"], bg=C["bg_card"])
        self._user_lbl.grid(row=0, column=1, sticky="e")

        self._clock_lbl = tk.Label(topbar, text="",
                                    font=(FONT_FAMILY, 10, "bold"),
                                    fg=C["pink_mid"], bg=C["bg_card"])
        self._clock_lbl.grid(row=0, column=2, sticky="e", padx=(12, 0))

        # Left column
        left = tk.Frame(self, bg=C["bg_deep"])
        left.grid(row=1, column=0, sticky="nsew", padx=(15, 7), pady=12)
        left.columnconfigure(0, weight=1)
        self._build_progress_card(left)
        self._build_clinical_card(left)    # ← NEW: age / BMI / BP / pregnancy no.
        self._build_stats_card(left)
        self._build_weather_card(left)

        # Right column
        right = tk.Frame(self, bg=C["bg_deep"])
        right.grid(row=1, column=1, sticky="nsew", padx=(7, 15), pady=12)
        right.columnconfigure(0, weight=1)
        self._build_log_card(right)
        self._build_history_card(right)
        self._build_alert_card(right)      # alert banner + "Check Alerts Now"
        self._build_flags_card(right)      # ← NEW: clinical risk flags
        self._build_tips_card(right)

    # ── Progress ring ─────────────────────────────────────────────────
    def _build_progress_card(self, parent):
        card = card_frame(parent, padx=15, pady=15)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        styled_label(card, "Today's Progress", size=12, bold=True,
                     color=C["pink_mid"]).pack()
        self._ring = CircularProgress(card)
        self._ring.pack(pady=10)
        self._goal_lbl = styled_label(card, "", size=9, color=C["pink_light"])
        self._goal_lbl.pack()

    # ── Clinical Profile card  (NEW) ─────────────────────────────────
    def _build_clinical_card(self, parent):
        """
        Displays the four new clinical parameters: Age, BMI (with category),
        Blood Pressure (with category, colour-coded), and Pregnancy Number.
        Also includes a button to view the full goal-calculation breakdown.
        """
        card = card_frame(parent, padx=15, pady=12)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure((0, 1), weight=1)

        styled_label(card, "Clinical Profile", size=12, bold=True,
                     color=C["pink_mid"]).grid(row=0, column=0, columnspan=2,
                                               sticky="w", pady=(0, 8))

        u = self.engine.user

        # Age
        styled_label(card, "Age", size=9, color=C["pink_light"]).grid(
            row=1, column=0, sticky="w", padx=5)
        styled_label(card, f"{u.age} yrs", size=13, bold=True,
                     color=C["pink_pale"]).grid(row=2, column=0, sticky="w",
                                                padx=5, pady=(0, 6))

        # Pregnancy number
        ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(u.pregnancy_number,
                                                       f"{u.pregnancy_number}th")
        styled_label(card, "Pregnancy No.", size=9, color=C["pink_light"]).grid(
            row=1, column=1, sticky="w", padx=5)
        styled_label(card, ordinal, size=13, bold=True,
                     color=C["pink_pale"]).grid(row=2, column=1, sticky="w",
                                                padx=5, pady=(0, 6))

        # BMI — colour-coded by category
        bmi_cat = u.bmi_category
        bmi_color = {
            BMICategory.UNDERWEIGHT: C["amber"],
            BMICategory.NORMAL:      C["green"],
            BMICategory.OVERWEIGHT:  C["amber"],
            BMICategory.OBESE:       C["red"],
        }[bmi_cat]
        styled_label(card, "BMI", size=9, color=C["pink_light"]).grid(
            row=3, column=0, sticky="w", padx=5)
        styled_label(card, f"{u.bmi:.1f} ({bmi_cat.value})", size=11, bold=True,
                     color=bmi_color).grid(row=4, column=0, sticky="w",
                                           padx=5, pady=(0, 6))

        # Blood pressure — colour-coded by category
        bp_cat = u.blood_pressure.category
        bp_color = {
            BPCategory.HYPOTENSIVE:  C["amber"],
            BPCategory.NORMAL:       C["green"],
            BPCategory.ELEVATED:     C["amber"],
            BPCategory.HYPERTENSIVE: C["red"],
        }[bp_cat]
        styled_label(card, "Blood Pressure", size=9, color=C["pink_light"]).grid(
            row=3, column=1, sticky="w", padx=5)
        styled_label(card,
                     f"{u.blood_pressure.systolic}/{u.blood_pressure.diastolic}"
                     f" ({bp_cat.value})",
                     size=11, bold=True, color=bp_color).grid(
            row=4, column=1, sticky="w", padx=5, pady=(0, 6))

        # Goal breakdown button
        styled_button(card, "🧮  View Goal Breakdown",
                      self._show_goal_breakdown, width=24).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _show_goal_breakdown(self):
        """Open a small popup window showing the 8-step goal calculation."""
        popup = tk.Toplevel(self)
        popup.title("Goal Breakdown")
        popup.configure(bg=C["bg_deep"])
        popup.geometry("380x420")
        popup.resizable(False, False)

        tk.Label(popup, text="🧮  Daily Goal Breakdown",
                 font=(FONT_FAMILY, 14, "bold"),
                 fg=C["pink_hot"], bg=C["bg_deep"]).pack(pady=(16, 10))

        body = card_frame(popup, padx=18, pady=16)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        for label, value in self.engine.modifier_breakdown.items():
            row = tk.Frame(body, bg=C["bg_card"])
            row.pack(fill="x", pady=3)
            styled_label(row, label, size=10, color=C["pink_light"]).pack(
                side="left")
            sign = "+" if value >= 0 else ""
            styled_label(row, f"{sign}{value:.0f} ml", size=10, bold=True,
                         color=C["green"] if value == 0 else C["pink_hot"]).pack(
                side="right")

        sep = tk.Frame(body, bg=C["separator"], height=2)
        sep.pack(fill="x", pady=10)

        total_row = tk.Frame(body, bg=C["bg_card"])
        total_row.pack(fill="x")
        styled_label(total_row, "TOTAL DAILY GOAL", size=11, bold=True,
                     color=C["pink_mid"]).pack(side="left")
        styled_label(total_row, f"{self.engine.daily_goal_ml:.0f} ml",
                     size=13, bold=True, color=C["pink_hot"]).pack(side="right")

        styled_button(popup, "Close", popup.destroy, width=14).pack(pady=14)

    # ── Statistics ────────────────────────────────────────────────────
    def _build_stats_card(self, parent):
        card = card_frame(parent, padx=15, pady=12)
        card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure((0, 1), weight=1)
        styled_label(card, "Statistics", size=12, bold=True,
                     color=C["pink_mid"]).grid(row=0, column=0, columnspan=2,
                                               sticky="w", pady=(0, 8))
        for i, (label, attr) in enumerate([
            ("Consumed 24h", "_stat_consumed"),
            ("Remaining",    "_stat_remaining"),
            ("Last 6h",      "_stat_6h"),
            ("Log entries",  "_stat_entries"),
        ]):
            r, c = divmod(i, 2)
            styled_label(card, label, size=9, color=C["pink_light"]).grid(
                row=r*2+1, column=c, sticky="w", padx=5)
            lbl = styled_label(card, "—", size=13, bold=True, color=C["green"])
            lbl.grid(row=r*2+2, column=c, sticky="w", padx=5, pady=(0, 6))
            setattr(self, attr, lbl)

    # ── Weather ───────────────────────────────────────────────────────
    def _build_weather_card(self, parent):
        card = card_frame(parent, padx=15, pady=12)
        card.grid(row=3, column=0, sticky="ew")
        styled_label(card, "Weather Conditions", size=12, bold=True,
                     color=C["pink_mid"]).pack(anchor="w")
        self._weather_lbl = styled_label(card, "—", size=10, color=C["pink_light"])
        self._weather_lbl.pack(anchor="w", pady=(6, 0))

    # ── Log water ─────────────────────────────────────────────────────
    def _build_log_card(self, parent):
        card = card_frame(parent, padx=15, pady=12)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure(0, weight=1)

        styled_label(card, "Log Water Intake", size=12, bold=True,
                     color=C["pink_mid"]).grid(row=0, column=0, columnspan=4,
                                               sticky="w", pady=(0, 10))
        styled_label(card, "Quick add:", size=9,
                     color=C["pink_light"]).grid(row=1, column=0,
                                                  columnspan=4, sticky="w")
        for i, ml in enumerate(self.QUICK_AMOUNTS):
            tk.Button(
                card, text=f"{ml} ml",
                command=lambda m=ml: self._log(m),
                font=(FONT_FAMILY, 10, "bold"),
                fg=C["white"], bg=C["pink_mid"],
                activeforeground=C["white"], activebackground=C["bg_hover"],
                relief="flat", bd=0, cursor="hand2", padx=8, pady=5,
            ).grid(row=2, column=i, padx=3, pady=(4, 10))

        styled_label(card, "Custom amount (ml):", size=9,
                     color=C["pink_light"]).grid(row=3, column=0,
                                                  columnspan=4, sticky="w")
        self._custom_var = tk.StringVar()
        tk.Entry(card, textvariable=self._custom_var, width=10,
                 font=(FONT_FAMILY, 12), fg=C["pink_pale"], bg=C["bg_input"],
                 insertbackground=C["pink_hot"], relief="flat").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        styled_button(card, "Log →", self._log_custom, width=6).grid(
            row=4, column=3, padx=(6, 0), pady=(4, 0))

    # ── Intake history ────────────────────────────────────────────────
    def _build_history_card(self, parent):
        card = card_frame(parent, padx=15, pady=12)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        styled_label(card, "Intake History (24h)", size=12, bold=True,
                     color=C["pink_mid"]).pack(anchor="w", pady=(0, 8))
        frame = tk.Frame(card, bg=C["bg_input"])
        frame.pack(fill="both", expand=True)
        scroll = tk.Scrollbar(frame, orient="vertical", bg=C["bg_card"])
        self._hist_box = tk.Listbox(
            frame, yscrollcommand=scroll.set,
            font=(FONT_FAMILY, 10), fg=C["pink_pale"], bg=C["bg_input"],
            selectbackground=C["pink_hot"], relief="flat", bd=0, height=5,
        )
        scroll.config(command=self._hist_box.yview)
        self._hist_box.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # ── Alert status card ─────────────────────────────────────────────
    def _build_alert_card(self, parent):
        card = card_frame(parent, padx=15, pady=12)
        card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure(0, weight=1)

        styled_label(card, "Alert Status", size=12, bold=True,
                     color=C["pink_mid"]).grid(row=0, column=0, sticky="w",
                                               pady=(0, 6))
        self._alert_lbl = tk.Label(
            card, text="✅  No alerts — you're on track!",
            font=(FONT_FAMILY, 10, "bold"),
            fg=C["green"], bg=C["bg_card"],
            wraplength=320, justify="left",
        )
        self._alert_lbl.grid(row=1, column=0, sticky="w")

        styled_button(card, "Check Alerts Now", self._manual_alert_check,
                      width=18).grid(row=2, column=0, sticky="w", pady=(10, 0))

    # ── Clinical Flags card  (NEW) ────────────────────────────────────
    def _build_flags_card(self, parent):
        """
        Displays the clinical risk flags raised during goal calculation
        (e.g. elevated BP, advanced maternal age, high parity).
        Populated once from engine.clinical_flags — these don't change
        during the session since they're derived from the static profile.
        """
        card = card_frame(parent, padx=15, pady=12)
        card.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure(0, weight=1)

        styled_label(card, "Clinical Risk Flags", size=12, bold=True,
                     color=C["pink_mid"]).grid(row=0, column=0, sticky="w",
                                               pady=(0, 8))

        flags = self.engine.clinical_flags
        if not flags:
            styled_label(card, "✅  No risk flags — profile is in normal ranges.",
                         size=10, color=C["green"]).grid(row=1, column=0, sticky="w")
        else:
            for i, flag in enumerate(flags):
                tk.Label(
                    card, text=f"⚠️  {flag.value}",
                    font=(FONT_FAMILY, 9, "bold"),
                    fg=C["amber"], bg=C["bg_card"],
                    wraplength=320, justify="left", anchor="w",
                ).grid(row=1 + i, column=0, sticky="w", pady=2)

    # ── Tips & Facts card  (NEW) ──────────────────────────────────────
    def _build_tips_card(self, parent):
        """
        Build the Tips & Facts panel below the alert card.

        The TipsPanel widget handles its own internal navigation
        (Prev / Next / Random). This method just instantiates it
        and places it on the grid.
        """
        trimester_num = self.engine.user.trimester.value  # 1, 2, or 3

        self._tips_panel = TipsPanel(
            parent,
            tips_data=self._tips_data,
            trimester_number=trimester_num,
        )
        self._tips_panel.grid(row=4, column=0, sticky="ew", pady=(0, 10))

    # ------------------------------------------------------------------
    # Refresh / data logic
    # ------------------------------------------------------------------

    def _refresh(self):
        now       = datetime.now()
        consumed  = self.engine.total_intake_24h(reference_time=now)
        goal      = self.engine.daily_goal_ml or 0.0
        remaining = max(0.0, goal - consumed)
        last6h    = self.engine.intake_in_last_n_hours(6, reference_time=now)
        entries   = len(self.engine._intake_log)

        self._clock_lbl.config(text=now.strftime("%H:%M:%S"))

        u = self.engine.user
        self._user_lbl.config(
            text=f"{u.name}  ·  Trimester {u.trimester.value}  ·  {u.activity_level.name.title()}"
        )

        self._ring.update_progress(consumed, goal)
        self._goal_lbl.config(text=f"Daily goal: {goal:.0f} ml")

        self._stat_consumed.config(text=f"{consumed:.0f} ml")
        self._stat_remaining.config(
            text=f"{remaining:.0f} ml",
            fg=C["amber"] if remaining > 0 else C["green"],
        )
        self._stat_6h.config(
            text=f"{last6h:.0f} ml",
            fg=C["red"] if last6h < 200 else C["green"],
        )
        self._stat_entries.config(text=str(entries))

        w = self.engine._current_weather
        if w:
            flag = "🌡️🔥" if (w.is_hot or w.is_humid) else "🌤️"
            self._weather_lbl.config(text=(
                f"{flag}  {w.temperature_c}°C  ·  {w.humidity_pct}% RH\n"
                f"{w.description}\n"
                f"{'(+15% goal modifier applied)' if w.is_hot or w.is_humid else ''}"
            ))

        self._hist_box.delete(0, "end")
        for entry in reversed(list(self.engine._intake_log)):
            ts = entry.timestamp.strftime("%H:%M")
            self._hist_box.insert("end", f"  {ts}   +{entry.amount_ml:.0f} ml")

        self.after(1000, self._refresh)

    def _log(self, amount_ml: float):
        self.engine.log_intake(amount_ml=amount_ml)
        self._maybe_show_alert_banner()

    def _log_custom(self):
        try:
            val = float(self._custom_var.get())
            if val <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Please enter a positive number.")
            return
        self._custom_var.set("")
        self._log(val)

    def _maybe_show_alert_banner(self):
        fired = self.engine.evaluate_alerts()
        if fired:
            now    = datetime.now()
            last6h = self.engine.intake_in_last_n_hours(6)
            self._alert_lbl.config(
                text=(f"⚠️  ALERT — only {last6h:.0f} ml in the last 6 hours!\n"
                      f"Please drink water now. Checked at {now.strftime('%H:%M')}."),
                fg=C["red"],
            )
        else:
            self._alert_lbl.config(
                text="✅  No alerts — you're on track!", fg=C["green"])

    def _manual_alert_check(self):
        self._maybe_show_alert_banner()

    def _schedule_alert_check(self):
        self._maybe_show_alert_banner()
        self.after(self.ALERT_POLL_MS, self._schedule_alert_check)


# =============================================================================
# Application Root
# =============================================================================

class HydrationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HydraMaterna — Maternal Hydration Tracker")
        self.configure(bg=C["bg_deep"])
        self.resizable(True, True)
        self.geometry("900x780")
        self.minsize(780, 640)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox",
                         fieldbackground=C["bg_input"],
                         background=C["bg_input"],
                         foreground=C["pink_pale"],
                         arrowcolor=C["pink_hot"],
                         selectbackground=C["pink_hot"])

        # Load tips once at startup — shared across screens
        try:
            self._tips_data: TipsData = load_tips()
        except FileNotFoundError as exc:
            messagebox.showwarning(
                "Tips file missing",
                f"Could not load pregnancy tips:\n{exc}\n\n"
                "The app will still work; tips panel will show a placeholder.",
            )
            # Create an empty TipsData so the panel degrades gracefully
            from pregnancy_tips import TipsData as _TD
            self._tips_data = _TD()

        self._show_setup()

    def _show_setup(self):
        self._clear()
        SetupScreen(self, on_submit=self._launch_dashboard).pack(fill="both", expand=True)

    def _launch_dashboard(self, user: User, weather: WeatherData):
        engine = HydrationEngine(user=user)
        engine.calculate_daily_goal(weather_override=weather)
        self._clear()
        DashboardScreen(
            self,
            engine=engine,
            tips_data=self._tips_data,
        ).pack(fill="both", expand=True)

    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    app = HydrationApp()
    app.mainloop()
