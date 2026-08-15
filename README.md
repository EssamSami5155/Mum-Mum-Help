[README (2).md](https://github.com/user-attachments/files/31107668/README.2.md)
# 💧 Mum Mum Help — Dynamic Algorithmic Hydration Engine

**A personalized, clinically-aware hydration tracking system for pregnant women, built in Python.**

Aligned with **UN Sustainable Development Goal 3.1** — *"By 2030, reduce the global maternal mortality ratio to less than 70 per 100,000 live births."*

---

## Table of Contents

- [Problem Statement](#-problem-statement)
- [Our Solution](#-our-solution)
- [Key Features](#-key-features)
- [How the Hydration Goal Is Calculated](#-how-the-hydration-goal-is-calculated)
- [Intelligent Alert System](#-intelligent-alert-system)
- [Project Structure](#-project-structure)
- [Screenshots / UI Preview](#-ui-preview)
- [Getting Started](#-getting-started)
- [Usage Guide](#-usage-guide)
- [Tech Stack](#-tech-stack)
- [Roadmap](#-roadmap)
- [Disclaimer](#-disclaimer)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Problem Statement

### What problem are we solving?

Dehydration during pregnancy is a widely underestimated but medically significant risk factor. Water requirements shift constantly throughout pregnancy — they rise with each trimester, spike in hot or humid weather, increase with physical activity, and are further affected by a woman's age, BMI, blood pressure, and how many pregnancies she has carried. Despite this complexity, most pregnant women are only ever given **one static number** ("drink 8 glasses a day") that ignores their actual physiology and environment entirely.

Even mild dehydration during pregnancy has been clinically linked to:
- Increased risk of **preterm labor** (dehydration can trigger uterine contractions)
- **Reduced amniotic fluid volume**
- **Neural tube defects** in early pregnancy when hydration is critical for fetal development
- Worsened **nausea, headaches, and fatigue**
- Complications for women who already have **hypertension** or are managing **high-risk pregnancies**

### Who experiences this problem?

- **Pregnant women themselves**, especially those in their first pregnancy who have no prior frame of reference for how much water their body actually needs.
- Women in **hot, humid climates** (e.g. South Asia, where this project originates) who face significantly elevated fluid loss through perspiration but rarely adjust their intake accordingly.
- **High-risk pregnancy groups** — teenage mothers, women of advanced maternal age (35+), women with elevated BMI, women with blood pressure abnormalities, and women with multiple prior pregnancies (high parity) — all of whom have measurably different hydration needs but are rarely told so.
- **Healthcare workers and community health programs** in low-resource settings who need a simple, low-cost, offline-capable tool to help patients self-monitor between clinic visits.

### Why is this problem important?

Maternal health directly ties into **UN SDG 3.1**, which targets a global maternal mortality ratio under 70 per 100,000 live births. Hydration is one of the few maternal-health risk factors that is:
1. **Entirely preventable** with the right information, and
2. **Cheap and universally accessible** to act on — unlike many other interventions that require clinical infrastructure.

A tool that closes the information gap around personalized hydration needs can meaningfully reduce a real, measurable class of pregnancy complications — at essentially zero cost to the end user.

### What are the existing limitations or gaps?

Looking at the current landscape of hydration and pregnancy apps:

| Gap | Why it matters |
|---|---|
| **Generic, one-size-fits-all goals** | Most water-tracking apps show the same daily target to every user, ignoring trimester, weather, or personal health data entirely. |
| **No clinical parameter integration** | Mainstream hydration apps do not factor in blood pressure, BMI, maternal age, or pregnancy number — despite these being medically relevant to fluid needs. |
| **No weather-responsiveness** | Very few apps dynamically adjust a hydration goal based on real heat/humidity conditions, even though climate is one of the largest drivers of fluid loss. |
| **No intelligent, time-aware alerting** | Most apps either spam constant notifications or none at all — few use an actual rolling-window algorithm to detect a genuine dry spell and alert only when it matters. |
| **Disconnected from maternal education** | Hydration tracking and pregnancy health education are usually built as separate products, missing an opportunity to reinforce good habits with relevant, trimester-specific guidance in the same place. |

---

## 💡 Our Solution

**HydraMaterna** is a fully offline, Python-based hydration engine and desktop application that closes these gaps directly:

1. **Personalized, 8-step hydration goal calculation** — instead of a flat number, the engine dynamically computes a daily fluid target from eight real inputs: baseline need, trimester, activity level, live weather conditions, blood pressure, BMI, maternal age, and pregnancy number (parity). Every one of these factors is backed by a documented, adjustable modifier (see [breakdown table](#-how-the-hydration-goal-is-calculated) below).

2. **Clinical risk-flagging** — the engine doesn't just adjust the number silently. It surfaces *why* — flagging conditions like elevated blood pressure, advanced maternal age, or high parity directly in the UI, so the user (or a supporting health worker) understands the reasoning, not just the output.

3. **An intelligent, rolling-window alert system** — rather than a naive fixed-interval reminder, the engine continuously tracks a **rolling 24-hour intake log** using an efficient `deque` data structure, and evaluates a genuine "dry spell" condition: if less than 200 ml has been consumed in the last 6 hours during waking hours (8 AM–8 PM), an alert fires. This means the system reacts to real behavior, not the clock.

4. **Integrated maternal-health education** — the same application parses a curated set of trimester-specific tips and morale-boosting facts directly from a plain-text knowledge file, surfacing relevant guidance right next to the hydration tracker — so health education and hydration tracking reinforce each other in one place instead of living in separate apps.

5. **Zero-dependency, fully offline design** — built entirely on Python's standard library (`tkinter`, `collections`, `dataclasses`, `datetime`, `logging`) with no external services, no internet requirement, and no paid API keys — making it realistically deployable in low-resource settings where connectivity or cost is a barrier.

The result is a tool that treats hydration not as a generic wellness habit, but as a **measurable, personalized, clinically-informed maternal health input** — directly supporting the intent behind SDG 3.1.

---

## ✨ Key Features

### 🧮 Dynamic 8-Step Hydration Goal Engine
- Personalized daily ml target computed from baseline, trimester, activity, weather, blood pressure, BMI, age, and pregnancy number.
- Full breakdown available on demand — every ml is traceable to its source.

### 🩺 Clinical Parameter Awareness
- **Blood Pressure** — classified into Hypotensive / Normal / Elevated / Hypertensive.
- **BMI** — classified into WHO-standard Underweight / Normal / Overweight / Obese categories.
- **Maternal Age** — flags teen pregnancies and advanced/very-advanced maternal age.
- **Pregnancy Number (Parity)** — flags high parity (4th–5th) and grand multipara (6th+) pregnancies.
- All flags are surfaced directly in the dashboard — never silently applied.

### ⏱️ Rolling 24-Hour Intake Tracker
- Implemented with `collections.deque` for O(1) append/purge performance.
- Automatically discards entries older than 24 hours.
- Powers both the progress ring and the alert system.

### 🚨 Intelligent, Time-Aware Alerts
- Fires only during waking hours (8 AM – 8 PM).
- Triggers when less than 200 ml has been consumed in the last 6 hours.
- Logged via Python's `logging` module *and* surfaced in the UI — never silent, never spammy.

### 🌸 Trimester-Specific Tips & Facts
- Parses a plain-text knowledge base (`Pregnancy_Tips_and_Facts.txt`) into structured, navigable content.
- Separate practical tips and morale-boosting facts for each trimester.
- Built-in "Random Tip" shuffle for daily variety.

### 🎀 Full Pink-Themed Desktop GUI
- Built entirely with Python's standard `tkinter` — no external GUI framework required.
- Circular animated progress ring, color-coded clinical badges, scrollable intake history, and a dedicated tips panel.

### 📊 Terminal-First Core Engine
- The engine (`hydration_engine.py`) is fully decoupled from the GUI and runs standalone with rich console/log output — useful for testing, scripting, or headless environments.

---

## 🧮 How the Hydration Goal Is Calculated

The engine computes the daily goal in eight sequential steps, starting from a clinical baseline and layering on personalized modifiers:

| Step | Factor | Modifier |
|---|---|---|
| 1 | **Baseline** | 2,300 ml (standard pregnancy baseline) |
| 2 | **Trimester** | 1st: +200 ml · 2nd: +300 ml · 3rd: +500 ml |
| 3 | **Activity Level** | Light: +0 · Moderate: +0 · High: +300 ml |
| 4 | **Weather** | If temperature > 28°C *or* humidity > 70%: **+15%** to running total |
| 5 | **Blood Pressure** | Hypotensive: +200 ml · Normal: +0 · Elevated: +150 ml · Hypertensive: +200 ml |
| 6 | **BMI** | Underweight: +150 ml · Normal: +0 · Overweight: +200 ml · Obese: +350 ml |
| 7 | **Maternal Age** | <20: +200 ml · 20–34: +0 · 35–44: +150 ml · 45+: +250 ml |
| 8 | **Pregnancy Number** | 1st–3rd: +0 · 4th–5th: +100 ml · 6th+: +150 ml |

Every modifier is a named constant at the top of `hydration_engine.py`, making the model transparent and easy to tune against updated clinical guidance.

---

## 🚨 Intelligent Alert System

The alert logic is deliberately conservative — it aims to catch genuine dehydration risk without becoming noise:

```
IF current_time is between 08:00 and 20:00
   AND water consumed in the last 6 hours < 200 ml
THEN trigger an Intelligent Alert
```

This is powered by `intake_in_last_n_hours()`, which queries the rolling `deque` for entries within a bounded time window — correctly excluding both stale (>24h old) and future-dated entries, so the check always reflects a real point-in-time state.

---

## 📁 Project Structure

```
hydramaterna/
├── hydration_engine.py           # Core engine — no GUI dependency, runs standalone
├── hydration_app.py               # Tkinter GUI application (pink themed)
├── pregnancy_tips.py               # Parser for the tips/facts knowledge base
├── Pregnancy_Tips_and_Facts.txt   # Trimester-by-trimester tips & facts (plain text)
└── README.md                      # You are here
```

### Module responsibilities

| File | Responsibility |
|---|---|
| `hydration_engine.py` | `User`, `BloodPressure`, `WeatherData`, `HydrationEngine` classes. All goal-calculation, intake-tracking, and alert logic. Includes a runnable `__main__` demo simulation. |
| `pregnancy_tips.py` | Parses `Pregnancy_Tips_and_Facts.txt` into structured `TipsData` per trimester. Exposes `load_tips()`, `get_random_tip()`, `get_all_tips_for_trimester()`. |
| `hydration_app.py` | Full Tkinter GUI — `SetupScreen` (profile intake), `DashboardScreen` (live tracking), `TipsPanel`, `CircularProgress` widget, and the pink color system. |

---

## 🖥️ UI Preview

The application flows through two screens:

1. **Setup Screen** — collects name, location, age, trimester, pregnancy number, activity level, BMI, blood pressure, and current weather, organized into three clearly labeled sections (👤 Profile, 🩺 Clinical Vitals, 🌤️ Weather).

2. **Dashboard** — a two-column live tracking view:
   - **Left column:** animated circular progress ring, clinical profile card (age/BMI/BP/pregnancy number with color-coded risk badges), statistics panel, weather card.
   - **Right column:** quick-add water logging, scrollable 24-hour intake history, real-time alert status, clinical risk flags, and the trimester-specific tips & facts panel.

*(Add your own screenshots here once you have the app running — drop image files into a `/screenshots` folder and reference them like `![Dashboard](screenshots/dashboard.png)`.)*

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- `tkinter` (usually bundled with Python; on Debian/Ubuntu install with `sudo apt-get install python3-tk` if missing)

No other external dependencies — the entire project runs on Python's standard library.

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/hydramaterna.git
cd hydramaterna

# (Optional) verify tkinter is available
python3 -c "import tkinter; print('tkinter OK')"
```

### Running the GUI application

```bash
python3 hydration_app.py
```

### Running the core engine standalone (terminal demo)

```bash
python3 hydration_engine.py
```

This runs a full simulation — a sample user profile, a hot-weather scenario, several logged water-intake events, and a walkthrough of all three alert scenarios (dry-spell alert, no alert, outside-alert-window) — printed directly to the console with full logging output.

### Running the tips parser standalone

```bash
python3 pregnancy_tips.py
```

Prints a quick summary of how many tips/facts were parsed per trimester, and one random tip from each.

---

## 📖 Usage Guide

1. Launch `hydration_app.py`.
2. Fill in your profile: name, location, age, trimester, pregnancy number, and activity level.
3. Enter your clinical vitals: pre-pregnancy BMI, and systolic/diastolic blood pressure.
4. Enter current weather conditions (temperature and humidity) — or wire in a real weather API in place of the mock `WeatherService` for live data.
5. Click **Start Tracking** — your personalized 8-step daily goal is calculated instantly.
6. Log water intake using the quick-add buttons or a custom amount.
7. Watch the circular progress ring, statistics, and 24-hour history update in real time.
8. If you go more than 6 daytime hours without at least 200 ml, an **Intelligent Alert** fires automatically — or check manually anytime with **"Check Alerts Now."**
9. Browse trimester-specific tips and morale-boosting facts in the panel below the alert status — use **Prev / Next** or **🎲 Random Tip or Fact**.
10. Click **🧮 View Goal Breakdown** at any time to see exactly how your daily target was calculated, step by step.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | `tkinter` (standard library) |
| Data structures | `collections.deque`, `dataclasses` |
| Time handling | `datetime` |
| Logging | `logging` (standard library) |
| Dependencies | **None** — pure standard library, fully offline |

---

## 🗺️ Roadmap

- [ ] Replace the mock `WeatherService` with a real weather API integration (e.g. OpenWeatherMap) while keeping the offline mock as a fallback.
- [ ] Persist user profiles and intake history across sessions (local file or SQLite).
- [ ] Export daily/weekly hydration reports as PDF for sharing with a healthcare provider.
- [ ] Add multi-language support for the tips & facts content.
- [ ] Mobile-friendly build (e.g. via Kivy or a web front-end) for community health worker deployment.
- [ ] Configurable clinical modifier thresholds so the engine can be tuned to local medical guidelines.

---

## ⚠️ Disclaimer

Mum Mum Help is an educational and self-monitoring tool. It is **not a substitute for professional medical advice, diagnosis, or treatment**. Blood pressure, BMI, and other clinical inputs are used only to personalize a general hydration recommendation — always consult a qualified healthcare provider for any pregnancy-related medical concerns, especially if clinical risk flags are raised.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome. Feel free to check the [issues page](../../issues) or open a pull request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source. Add your preferred license (e.g. MIT, Apache 2.0) here.

---

## 🙏 Acknowledgments

- Built in support of **UN Sustainable Development Goal 3.1** (Maternal Health).
- Pregnancy tips and facts curated for educational, morale-boosting purposes across all three trimesters.
