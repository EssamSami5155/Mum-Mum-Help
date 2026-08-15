"""
=============================================================================
Dynamic Algorithmic Hydration Engine  v2.0
Maternal Hydration Tracker — Aligned with UN SDG 3.1 (Maternal Health)
=============================================================================

New in v2.0 — four additional clinical parameters now feed into the goal:

  BloodPressure   : Systolic / diastolic readings; category auto-classified.
  BMI             : Body-mass index; four WHO categories recognised.
  Age             : Maternal age; modifiers for teen and advanced-age pregnancies.
  Pregnancy Number: Gravidity (1st, 2nd, 3rd… pregnancy) — parity modifier.

Design
------
  BloodPressure   : Dataclass with systolic/diastolic + derived category.
  BPCategory      : HYPOTENSIVE | NORMAL | ELEVATED | HYPERTENSIVE
  BMICategory     : UNDERWEIGHT | NORMAL | OVERWEIGHT | OBESE
  ClinicalFlag    : Enum of risk flags raised during goal calculation.
  User            : Profile dataclass — now includes age, bmi,
                    blood_pressure, pregnancy_number.
  WeatherService  : Mock external weather API.
  HydrationEngine : Core engine — 8-step personalised goal, rolling 24-h
                    tracker, alert logic, risk-flag collection.
=============================================================================
"""

import logging
import random
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("HydrationEngine")


# ===========================================================================
# Enumerations
# ===========================================================================

class Trimester(Enum):
    """Pregnancy trimesters."""
    FIRST  = 1   # Weeks  1–12
    SECOND = 2   # Weeks 13–26
    THIRD  = 3   # Weeks 27–40


class ActivityLevel(Enum):
    """Daily physical activity level."""
    LIGHT    = auto()   # Sedentary / desk work
    MODERATE = auto()   # Light walks, household chores
    HIGH     = auto()   # Exercise, physically demanding work


class BPCategory(Enum):
    """
    Blood-pressure classification used for hydration modifiers.

    Thresholds follow WHO / AHA guidelines adapted for pregnancy.
    """
    HYPOTENSIVE    = "Hypotensive"       # Systolic < 90 OR Diastolic < 60
    NORMAL         = "Normal"            # Systolic 90–119, Diastolic 60–79
    ELEVATED       = "Elevated"          # Systolic 120–139, Diastolic 80–89
    HYPERTENSIVE   = "Hypertensive"      # Systolic ≥ 140 OR Diastolic ≥ 90


class BMICategory(Enum):
    """
    WHO body-mass-index classification.

    Note: BMI interpretation during pregnancy differs from standard use;
    these categories are applied to the pre-pregnancy BMI.
    """
    UNDERWEIGHT = "Underweight"   # BMI < 18.5
    NORMAL      = "Normal"        # BMI 18.5 – 24.9
    OVERWEIGHT  = "Overweight"    # BMI 25 – 29.9
    OBESE       = "Obese"         # BMI ≥ 30


class ClinicalFlag(Enum):
    """
    Risk flags raised automatically during goal calculation.
    Displayed in the UI and printed in the summary report.
    """
    TEEN_PREGNANCY           = "Teen pregnancy (age < 20)"
    ADVANCED_MATERNAL_AGE    = "Advanced maternal age (35–44)"
    VERY_ADVANCED_AGE        = "Very advanced maternal age (45+)"
    UNDERWEIGHT_BMI          = "Underweight BMI — increased nutritional need"
    OVERWEIGHT_BMI           = "Overweight BMI — higher metabolic demand"
    OBESE_BMI                = "Obese BMI — significantly elevated fluid need"
    HYPOTENSIVE_BP           = "Low BP — dehydration risk; increased goal"
    ELEVATED_BP              = "Elevated BP — monitor closely"
    HYPERTENSIVE_BP          = "Hypertensive — medical attention recommended"
    HIGH_PARITY              = "High parity (4+ pregnancies) — elevated risk"
    GRAND_MULTIPARA          = "Grand multipara (6+ pregnancies) — highest risk"
    HOT_HUMID_WEATHER        = "Hot/humid weather — 15% goal increase applied"
    HIGH_ACTIVITY            = "High activity level — bonus ml applied"


# ===========================================================================
# Constants — modifiers (ml) for each clinical dimension
# ===========================================================================

BASELINE_ML: int = 2_300

# ── Trimester ─────────────────────────────────────────────────────────────
TRIMESTER_MODIFIERS: dict[Trimester, int] = {
    Trimester.FIRST:  200,
    Trimester.SECOND: 300,
    Trimester.THIRD:  500,
}

# ── Activity ──────────────────────────────────────────────────────────────
HIGH_ACTIVITY_BONUS_ML: int = 300

# ── Weather ───────────────────────────────────────────────────────────────
HOT_TEMP_THRESHOLD_C: float    = 28.0
HIGH_HUMIDITY_THRESHOLD: float = 70.0
WEATHER_INCREASE_FACTOR: float = 1.15   # +15 %

# ── Blood pressure (ml additions) ─────────────────────────────────────────
BP_MODIFIERS: dict[BPCategory, int] = {
    BPCategory.HYPOTENSIVE:  200,   # dehydration exacerbates hypotension
    BPCategory.NORMAL:         0,
    BPCategory.ELEVATED:     150,   # extra hydration supports BP regulation
    BPCategory.HYPERTENSIVE: 200,   # + clinical flag; doctor review needed
}

# ── BMI (ml additions) ────────────────────────────────────────────────────
BMI_MODIFIERS: dict[BMICategory, int] = {
    BMICategory.UNDERWEIGHT:   150,   # higher nutritional fluid demand
    BMICategory.NORMAL:          0,
    BMICategory.OVERWEIGHT:    200,   # raised metabolic output
    BMICategory.OBESE:         350,   # significantly elevated fluid need
}

# ── Maternal age (ml additions) ───────────────────────────────────────────
AGE_MODIFIERS: list[tuple[range, int, Optional[ClinicalFlag]]] = [
    # (age_range,            bonus_ml,  flag_or_None)
    (range(0,   20),          200,  ClinicalFlag.TEEN_PREGNANCY),
    (range(20,  35),            0,  None),
    (range(35,  45),          150,  ClinicalFlag.ADVANCED_MATERNAL_AGE),
    (range(45, 120),          250,  ClinicalFlag.VERY_ADVANCED_AGE),
]

# ── Parity / pregnancy number (ml additions) ──────────────────────────────
PARITY_MODIFIERS: list[tuple[range, int, Optional[ClinicalFlag]]] = [
    # (pregnancy_num_range,  bonus_ml,  flag_or_None)
    (range(1, 4),               0,  None),          # 1st–3rd: no bonus
    (range(4, 6),             100,  ClinicalFlag.HIGH_PARITY),
    (range(6, 99),            150,  ClinicalFlag.GRAND_MULTIPARA),
]

# ── Alert thresholds ──────────────────────────────────────────────────────
ALERT_WINDOW_START_HOUR: int = 8
ALERT_WINDOW_END_HOUR: int   = 20
ALERT_LOOKBACK_HOURS: int    = 6
ALERT_MIN_INTAKE_ML: int     = 200
ROLLING_WINDOW_HOURS: int    = 24


# ===========================================================================
# Data Structures
# ===========================================================================

@dataclass
class BloodPressure:
    """
    A single blood-pressure reading (mmHg).

    Attributes
    ----------
    systolic  : Upper number — pressure during heartbeat.
    diastolic : Lower number — pressure between heartbeats.
    """
    systolic: int    # mmHg
    diastolic: int   # mmHg

    @property
    def category(self) -> BPCategory:
        """Classify this reading into a BPCategory."""
        s, d = self.systolic, self.diastolic
        if s < 90 or d < 60:
            return BPCategory.HYPOTENSIVE
        if s >= 140 or d >= 90:
            return BPCategory.HYPERTENSIVE
        if s >= 120 or d >= 80:
            return BPCategory.ELEVATED
        return BPCategory.NORMAL

    def __str__(self) -> str:
        return f"{self.systolic}/{self.diastolic} mmHg ({self.category.value})"


@dataclass
class WeatherData:
    """Snapshot of local weather conditions."""
    temperature_c: float
    humidity_pct: float
    description: str = ""

    @property
    def is_hot(self) -> bool:
        return self.temperature_c > HOT_TEMP_THRESHOLD_C

    @property
    def is_humid(self) -> bool:
        return self.humidity_pct > HIGH_HUMIDITY_THRESHOLD


@dataclass
class IntakeEntry:
    """A single recorded water-intake event."""
    timestamp: datetime
    amount_ml: float


@dataclass
class User:
    """
    Holds all profile data that feeds into the hydration goal calculation.

    Core fields (original)
    ----------------------
    name           : Display name.
    trimester      : Current pregnancy trimester (Trimester enum).
    activity_level : Daily activity level (ActivityLevel enum).
    location       : City/region string for weather lookup.

    Clinical fields (new in v2.0)
    ------------------------------
    age              : Maternal age in years.
    bmi              : Pre-pregnancy body-mass index.
    blood_pressure   : BloodPressure dataclass (systolic/diastolic in mmHg).
    pregnancy_number : Gravidity — 1 = first pregnancy, 2 = second, etc.
    """
    name:             str
    trimester:        Trimester
    activity_level:   ActivityLevel
    location:         str           = "Dhaka, BD"

    # ── v2.0 clinical parameters ──────────────────────────────────────
    age:              int           = 25
    bmi:              float         = 22.0
    blood_pressure:   BloodPressure = field(
        default_factory=lambda: BloodPressure(systolic=115, diastolic=75)
    )
    pregnancy_number: int           = 1   # 1 = first pregnancy

    @property
    def bmi_category(self) -> BMICategory:
        if self.bmi < 18.5:
            return BMICategory.UNDERWEIGHT
        if self.bmi < 25.0:
            return BMICategory.NORMAL
        if self.bmi < 30.0:
            return BMICategory.OVERWEIGHT
        return BMICategory.OBESE

    def __str__(self) -> str:
        return (
            f"User(name={self.name!r}, trimester={self.trimester.name}, "
            f"activity={self.activity_level.name}, age={self.age}, "
            f"bmi={self.bmi} [{self.bmi_category.value}], "
            f"bp={self.blood_pressure}, "
            f"pregnancy_no={self.pregnancy_number}, location={self.location!r})"
        )


# ===========================================================================
# Mock Weather Service
# ===========================================================================

class WeatherService:
    """Simulates fetching real-time weather data."""

    @staticmethod
    def fetch(
        location: str,
        *,
        override: Optional[WeatherData] = None,
    ) -> WeatherData:
        if override is not None:
            logger.debug("WeatherService: using override -> %s", override)
            return override
        temperature_c = round(random.uniform(22.0, 38.0), 1)
        humidity_pct  = round(random.uniform(40.0, 95.0), 1)
        weather = WeatherData(temperature_c=temperature_c,
                              humidity_pct=humidity_pct,
                              description="Simulated conditions")
        logger.debug("WeatherService: %r -> %.1f°C, %.0f%% RH",
                     location, temperature_c, humidity_pct)
        return weather


# ===========================================================================
# Core Engine
# ===========================================================================

class HydrationEngine:
    """
    Central engine — 8-step personalised hydration goal, rolling 24-h
    intake tracker, intelligent alert evaluation, and clinical flag system.

    Goal Calculation Steps
    ----------------------
    Step 1  Baseline (2 300 ml)
    Step 2  Trimester modifier
    Step 3  Activity modifier
    Step 4  Weather modifier  (+15 % if hot or humid)
    Step 5  Blood-pressure modifier          [NEW v2.0]
    Step 6  BMI modifier                     [NEW v2.0]
    Step 7  Maternal age modifier            [NEW v2.0]
    Step 8  Parity / pregnancy-number modifier [NEW v2.0]
    """

    def __init__(
        self,
        user: User,
        weather_service: Optional[WeatherService] = None,
    ) -> None:
        self.user             = user
        self._weather_service = weather_service or WeatherService()
        self._intake_log: deque[IntakeEntry] = deque()
        self._daily_goal_ml:  Optional[float] = None
        self._current_weather: Optional[WeatherData] = None
        # Clinical flags raised during the most recent goal calculation
        self.clinical_flags: list[ClinicalFlag] = []
        # Modifier breakdown from the most recent calculation
        self.modifier_breakdown: dict[str, float] = {}
        logger.info("HydrationEngine v2.0 initialised for %s", self.user)

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    def _apply_bp_modifier(self) -> tuple[int, Optional[ClinicalFlag]]:
        """Return (bonus_ml, flag_or_None) for the user's blood pressure."""
        cat   = self.user.blood_pressure.category
        bonus = BP_MODIFIERS[cat]
        flag  = None
        if cat == BPCategory.HYPOTENSIVE:
            flag = ClinicalFlag.HYPOTENSIVE_BP
        elif cat == BPCategory.ELEVATED:
            flag = ClinicalFlag.ELEVATED_BP
        elif cat == BPCategory.HYPERTENSIVE:
            flag = ClinicalFlag.HYPERTENSIVE_BP
        return bonus, flag

    def _apply_bmi_modifier(self) -> tuple[int, Optional[ClinicalFlag]]:
        """Return (bonus_ml, flag_or_None) for the user's BMI category."""
        cat   = self.user.bmi_category
        bonus = BMI_MODIFIERS[cat]
        flag  = None
        if cat == BMICategory.UNDERWEIGHT:
            flag = ClinicalFlag.UNDERWEIGHT_BMI
        elif cat == BMICategory.OVERWEIGHT:
            flag = ClinicalFlag.OVERWEIGHT_BMI
        elif cat == BMICategory.OBESE:
            flag = ClinicalFlag.OBESE_BMI
        return bonus, flag

    def _apply_age_modifier(self) -> tuple[int, Optional[ClinicalFlag]]:
        """Return (bonus_ml, flag_or_None) for the user's maternal age."""
        age = self.user.age
        for age_range, bonus, flag in AGE_MODIFIERS:
            if age in age_range:
                return bonus, flag
        # Fallback for any edge-case age outside defined ranges
        return 0, None

    def _apply_parity_modifier(self) -> tuple[int, Optional[ClinicalFlag]]:
        """Return (bonus_ml, flag_or_None) for the pregnancy number."""
        pn = max(1, self.user.pregnancy_number)
        for pn_range, bonus, flag in PARITY_MODIFIERS:
            if pn in pn_range:
                return bonus, flag
        # Pregnancy number beyond defined ranges — use grand-multipara values
        return 150, ClinicalFlag.GRAND_MULTIPARA

    # ------------------------------------------------------------------
    # 1. Dynamic Goal Calculation (8 steps)
    # ------------------------------------------------------------------

    def calculate_daily_goal(
        self,
        weather_override: Optional[WeatherData] = None,
    ) -> float:
        """
        Compute the personalised daily hydration goal (ml) across 8 steps.

        Returns
        -------
        goal_ml : Recommended daily water intake in millilitres.
        """
        logger.info("=== Calculating daily hydration goal (8-step) ===")
        self.clinical_flags   = []
        self.modifier_breakdown = {}

        # Step 1 — Baseline
        goal = float(BASELINE_ML)
        self.modifier_breakdown["Baseline"] = goal
        logger.debug("Step 1 — Baseline: %.0f ml", goal)

        # Step 2 — Trimester
        trim_bonus = TRIMESTER_MODIFIERS[self.user.trimester]
        goal += trim_bonus
        self.modifier_breakdown["Trimester"] = trim_bonus
        logger.debug("Step 2 — Trimester (%s): +%d ml -> %.0f ml",
                     self.user.trimester.name, trim_bonus, goal)

        # Step 3 — Activity
        act_bonus = 0
        if self.user.activity_level == ActivityLevel.HIGH:
            act_bonus = HIGH_ACTIVITY_BONUS_ML
            self.clinical_flags.append(ClinicalFlag.HIGH_ACTIVITY)
        goal += act_bonus
        self.modifier_breakdown["Activity"] = act_bonus
        logger.debug("Step 3 — Activity (%s): +%d ml -> %.0f ml",
                     self.user.activity_level.name, act_bonus, goal)

        # Step 4 — Weather
        weather = self._weather_service.fetch(self.user.location,
                                               override=weather_override)
        self._current_weather = weather
        weather_bonus = 0.0
        if weather.is_hot or weather.is_humid:
            pre = goal
            goal *= WEATHER_INCREASE_FACTOR
            weather_bonus = goal - pre
            self.clinical_flags.append(ClinicalFlag.HOT_HUMID_WEATHER)
        self.modifier_breakdown["Weather (+15%)"] = round(weather_bonus, 1)
        logger.debug("Step 4 — Weather (%.1f°C, %.0f%% RH): +%.0f ml -> %.0f ml",
                     weather.temperature_c, weather.humidity_pct, weather_bonus, goal)

        # Step 5 — Blood pressure  [NEW]
        bp_bonus, bp_flag = self._apply_bp_modifier()
        goal += bp_bonus
        if bp_flag:
            self.clinical_flags.append(bp_flag)
        self.modifier_breakdown["Blood Pressure"] = bp_bonus
        logger.debug("Step 5 — BP (%s, %s): +%d ml -> %.0f ml",
                     self.user.blood_pressure,
                     self.user.blood_pressure.category.value,
                     bp_bonus, goal)

        # Step 6 — BMI  [NEW]
        bmi_bonus, bmi_flag = self._apply_bmi_modifier()
        goal += bmi_bonus
        if bmi_flag:
            self.clinical_flags.append(bmi_flag)
        self.modifier_breakdown["BMI"] = bmi_bonus
        logger.debug("Step 6 — BMI (%.1f, %s): +%d ml -> %.0f ml",
                     self.user.bmi, self.user.bmi_category.value,
                     bmi_bonus, goal)

        # Step 7 — Maternal age  [NEW]
        age_bonus, age_flag = self._apply_age_modifier()
        goal += age_bonus
        if age_flag:
            self.clinical_flags.append(age_flag)
        self.modifier_breakdown["Maternal Age"] = age_bonus
        logger.debug("Step 7 — Age (%d): +%d ml -> %.0f ml",
                     self.user.age, age_bonus, goal)

        # Step 8 — Parity / pregnancy number  [NEW]
        parity_bonus, parity_flag = self._apply_parity_modifier()
        goal += parity_bonus
        if parity_flag:
            self.clinical_flags.append(parity_flag)
        self.modifier_breakdown["Parity"] = parity_bonus
        logger.debug("Step 8 — Pregnancy no. %d: +%d ml -> %.0f ml",
                     self.user.pregnancy_number, parity_bonus, goal)

        self._daily_goal_ml = round(goal, 1)

        if self.clinical_flags:
            logger.warning("Clinical flags raised: %s",
                           [f.value for f in self.clinical_flags])
        logger.info("Final daily goal for %s: %.0f ml | Flags: %d",
                    self.user.name, self._daily_goal_ml, len(self.clinical_flags))
        return self._daily_goal_ml

    @property
    def daily_goal_ml(self) -> Optional[float]:
        return self._daily_goal_ml

    # ------------------------------------------------------------------
    # 2. Rolling Intake Tracker
    # ------------------------------------------------------------------

    def _purge_old_entries(self, reference_time: Optional[datetime] = None) -> None:
        cutoff = (reference_time or datetime.now()) - timedelta(hours=ROLLING_WINDOW_HOURS)
        purged = 0
        while self._intake_log and self._intake_log[0].timestamp < cutoff:
            self._intake_log.popleft()
            purged += 1
        if purged:
            logger.debug("Purged %d stale entries.", purged)

    def log_intake(self, amount_ml: float,
                   timestamp: Optional[datetime] = None) -> None:
        ts = timestamp or datetime.now()
        if amount_ml <= 0:
            logger.warning("Ignored non-positive intake: %.0f ml", amount_ml)
            return
        self._intake_log.append(IntakeEntry(timestamp=ts, amount_ml=amount_ml))
        self._purge_old_entries(reference_time=ts)
        logger.info("Logged %.0f ml at %s | 24-h total: %.0f ml",
                    amount_ml, ts.strftime("%H:%M:%S"),
                    self.total_intake_24h(reference_time=ts))

    def total_intake_24h(self, reference_time: Optional[datetime] = None) -> float:
        ref = reference_time or datetime.now()
        self._purge_old_entries(reference_time=ref)
        cutoff = ref - timedelta(hours=ROLLING_WINDOW_HOURS)
        # Bounded on both ends: excludes stale entries AND entries that are
        # chronologically "in the future" relative to the reference time
        # (relevant for simulations where events are logged out of order).
        return sum(e.amount_ml for e in self._intake_log
                  if cutoff <= e.timestamp <= ref)

    def intake_in_last_n_hours(self, hours: int,
                                reference_time: Optional[datetime] = None) -> float:
        ref = reference_time or datetime.now()
        self._purge_old_entries(reference_time=ref)
        cutoff = ref - timedelta(hours=hours)
        return sum(e.amount_ml for e in self._intake_log
                  if cutoff <= e.timestamp <= ref)

    def progress_pct(self, reference_time: Optional[datetime] = None) -> float:
        if not self._daily_goal_ml:
            return 0.0
        return min(100.0, (self.total_intake_24h(reference_time=reference_time)
                           / self._daily_goal_ml) * 100)

    # ------------------------------------------------------------------
    # 3. Intelligent Alert Logic
    # ------------------------------------------------------------------

    def evaluate_alerts(self,
                        reference_time: Optional[datetime] = None) -> bool:
        now          = reference_time or datetime.now()
        current_hour = now.hour
        within_window = ALERT_WINDOW_START_HOUR <= current_hour < ALERT_WINDOW_END_HOUR
        if not within_window:
            logger.debug("Alert check at %s: outside window. No alert.",
                         now.strftime("%H:%M"))
            return False

        recent_ml = self.intake_in_last_n_hours(ALERT_LOOKBACK_HOURS,
                                                 reference_time=now)
        logger.debug("Alert check at %s: %.0f ml in last %d h (threshold %d ml).",
                     now.strftime("%H:%M"), recent_ml,
                     ALERT_LOOKBACK_HOURS, ALERT_MIN_INTAKE_ML)

        if recent_ml < ALERT_MIN_INTAKE_ML:
            msg = (
                "\n" + "=" * 60 + "\n"
                f"  [!] INTELLIGENT HYDRATION ALERT -- {self.user.name}\n"
                + "=" * 60 + "\n"
                f"  Time         : {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Last {ALERT_LOOKBACK_HOURS}h intake : {recent_ml:.0f} ml "
                f"(min: {ALERT_MIN_INTAKE_ML} ml)\n"
                f"  24-h total   : {self.total_intake_24h(reference_time=now):.0f} ml"
                f" / {self._daily_goal_ml or 'N/A'} ml\n"
                f"  Action       : Drink water now — maternal health depends on it.\n"
                + "=" * 60 + "\n"
            )
            print(msg)
            logger.warning("ALERT: %s — only %.0f ml in last %d h!",
                           self.user.name, recent_ml, ALERT_LOOKBACK_HOURS)
            return True

        logger.info("No alert: %.0f ml in last %d h — safe.", recent_ml, ALERT_LOOKBACK_HOURS)
        return False

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def print_summary(self, reference_time: Optional[datetime] = None) -> None:
        now       = reference_time or datetime.now()
        total     = self.total_intake_24h(reference_time=now)
        pct       = self.progress_pct(reference_time=now)
        goal      = self._daily_goal_ml or 0.0
        remaining = max(0.0, goal - total)
        bar       = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))

        w_str = "N/A"
        if self._current_weather:
            w = self._current_weather
            w_str = f"{w.temperature_c}°C, {w.humidity_pct}% RH"

        flags_str = (
            "\n".join(f"  ⚠️   {f.value}" for f in self.clinical_flags)
            if self.clinical_flags else "  None"
        )

        breakdown_str = "\n".join(
            f"    {k:<22}: +{v:.0f} ml"
            for k, v in self.modifier_breakdown.items()
        )

        print(
            "\n" + "=" * 64 + "\n"
            f"  HYDRATION SUMMARY — {self.user.name}\n"
            + "=" * 64 + "\n"
            f"  Age              : {self.user.age} yrs\n"
            f"  Trimester        : {self.user.trimester.name.title()} ({self.user.trimester.value})\n"
            f"  Pregnancy No.    : {self.user.pregnancy_number}\n"
            f"  Activity         : {self.user.activity_level.name.title()}\n"
            f"  BMI              : {self.user.bmi:.1f} ({self.user.bmi_category.value})\n"
            f"  Blood Pressure   : {self.user.blood_pressure}\n"
            f"  Weather          : {w_str}\n"
            + "-" * 64 + "\n"
            f"  Goal Breakdown:\n{breakdown_str}\n"
            + "-" * 64 + "\n"
            f"  Daily Goal       : {goal:.0f} ml\n"
            f"  Consumed (24h)   : {total:.0f} ml\n"
            f"  Remaining        : {remaining:.0f} ml\n"
            f"  Progress         : [{bar}] {pct:.1f}%\n"
            + "-" * 64 + "\n"
            f"  Clinical Flags:\n{flags_str}\n"
            + "=" * 64 + "\n"
        )


# ===========================================================================
# Simulation / Demo Block
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 64)
    print("  Dynamic Algorithmic Hydration Engine v2.0 — Demo Simulation")
    print("  UN SDG 3.1 | Maternal Health | 8-Step Personalised Goal")
    print("=" * 64 + "\n")

    # ── User profile — 3rd trimester, with clinical parameters ────────
    amina = User(
        name             = "Amina Rahman",
        trimester        = Trimester.THIRD,
        activity_level   = ActivityLevel.MODERATE,
        location         = "Dhaka, BD",
        age              = 36,                           # advanced maternal age
        bmi              = 27.4,                         # overweight
        blood_pressure   = BloodPressure(systolic=138, diastolic=88),  # elevated
        pregnancy_number = 2,                            # second pregnancy
    )
    logger.info("User profile: %s", amina)

    engine = HydrationEngine(user=amina)

    # ── Simulate a hot, humid Dhaka summer day ─────────────────────────
    hot_day = WeatherData(
        temperature_c = 34.5,
        humidity_pct  = 82.0,
        description   = "Hot & humid — Dhaka summer",
    )

    goal = engine.calculate_daily_goal(weather_override=hot_day)
    print(f"\n  Personalised daily goal for {amina.name}: {goal:.0f} ml\n")

    # ── Log intake events (with a deliberate 6-h dry spell) ───────────
    today = datetime.now().date()

    def sim_ts(h: int, m: int = 0) -> datetime:
        return datetime(today.year, today.month, today.day, h, m)

    for ts, ml, label in [
        (sim_ts(7,  0), 250, "Morning glass"),
        (sim_ts(8, 30), 300, "Breakfast"),
        (sim_ts(9,  0), 150, "Mid-morning sip"),
        (sim_ts(15,30), 100, "Small sip during dry spell"),
        (sim_ts(18, 0), 400, "Dinner"),
        (sim_ts(19,30), 200, "Evening wind-down"),
    ]:
        logger.info("Event: %s", label)
        engine.log_intake(amount_ml=ml, timestamp=ts)

    engine.print_summary(reference_time=sim_ts(15, 31))

    # ── Alert scenarios ────────────────────────────────────────────────
    print("\n  Alert Scenarios\n")
    for label, ref in [
        ("A — 15:31 (only 100 ml in last 6h → ALERT)", sim_ts(15, 31)),
        ("B — 19:00 (500 ml in last 6h → no alert)",   sim_ts(19,  0)),
        ("C — 23:00 (outside alert window)",            sim_ts(23,  0)),
    ]:
        print(f"  [{label}]")
        fired = engine.evaluate_alerts(reference_time=ref)
        print(f"  Alert fired: {fired}\n")

    engine.print_summary(reference_time=sim_ts(20, 0))
    print("  Simulation complete. Stay hydrated!\n")
