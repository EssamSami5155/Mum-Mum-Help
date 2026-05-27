"""
=============================================================================
Dynamic Algorithmic Hydration Engine
Maternal Hydration Tracker — Aligned with UN SDG 3.1 (Maternal Health)
=============================================================================

Author  : Essam Sami
Purpose : Personalized hydration goal calculation + rolling intake tracking
          + intelligent alert logic for pregnant women.

Design  :
  - User          : Holds profile data (trimester, activity level, name).
  - WeatherService: Mock service that simulates fetching local weather data.
  - HydrationEngine: Core engine — goal calculation, rolling 24-h tracker,
                     and intelligent alert evaluation.
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
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("HydrationEngine")


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Trimester(Enum):
    """Pregnancy trimesters with their respective hydration modifiers (ml)."""
    FIRST  = 1   # Weeks  1–12
    SECOND = 2   # Weeks 13–26
    THIRD  = 3   # Weeks 27–40


class ActivityLevel(Enum):
    """User's daily physical activity level."""
    LIGHT    = auto()   # Sedentary / desk work
    MODERATE = auto()   # Light walks, household chores
    HIGH     = auto()   # Exercise, physically demanding work


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Baseline daily water recommendation for pregnant women (ml)
BASELINE_ML: int = 2_300

# Additional millilitres per trimester
TRIMESTER_MODIFIERS: dict[Trimester, int] = {
    Trimester.FIRST:  200,
    Trimester.SECOND: 300,
    Trimester.THIRD:  500,
}

# Additional ml for high-activity days
HIGH_ACTIVITY_BONUS_ML: int = 300

# Weather thresholds that trigger an increased goal
HOT_TEMP_THRESHOLD_C: float  = 28.0   # °C
HIGH_HUMIDITY_THRESHOLD: float = 70.0  # percentage

# Multiplier applied when weather is hot/humid
WEATHER_INCREASE_FACTOR: float = 1.15  # +15 %

# Alert window: only alert between 08:00 and 20:00 local time
ALERT_WINDOW_START_HOUR: int = 8
ALERT_WINDOW_END_HOUR: int   = 20

# Trigger an alert if < 200 ml consumed in the past N hours
ALERT_LOOKBACK_HOURS: int = 6
ALERT_MIN_INTAKE_ML: int  = 200

# Rolling window duration
ROLLING_WINDOW_HOURS: int = 24


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class WeatherData:
    """Snapshot of local weather conditions."""
    temperature_c: float      # Celsius
    humidity_pct: float       # 0–100 %
    description: str = ""     # Human-readable label

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
    Holds a user's profile data relevant to hydration calculation.

    Attributes
    ----------
    name          : Display name of the user.
    trimester     : Current pregnancy trimester.
    activity_level: Self-reported daily activity level.
    location      : Used by the weather service (city name or coordinates).
    """
    name: str
    trimester: Trimester
    activity_level: ActivityLevel
    location: str = "Dhaka, BD"

    def __str__(self) -> str:
        return (
            f"User(name={self.name!r}, "
            f"trimester={self.trimester.name}, "
            f"activity={self.activity_level.name}, "
            f"location={self.location!r})"
        )


# ---------------------------------------------------------------------------
# Mock Weather Service
# ---------------------------------------------------------------------------

class WeatherService:
    """
    Simulates fetching real-time weather data from an external API.

    In production this would call OpenWeatherMap, WeatherAPI, etc.
    Here we either return deterministic data (via `override`) or
    generate semi-random values to mimic API responses.
    """

    @staticmethod
    def fetch(
        location: str,
        *,
        override: Optional[WeatherData] = None,
    ) -> WeatherData:
        """
        Return a WeatherData snapshot for *location*.

        Parameters
        ----------
        location : City/region string (unused in mock; logged only).
        override : If supplied, return this instead of generating data.
        """
        if override is not None:
            logger.debug("WeatherService: using overridden data -> %s", override)
            return override

        # Simulate a realistic temperature range for the location
        temperature_c = round(random.uniform(22.0, 38.0), 1)
        humidity_pct  = round(random.uniform(40.0, 95.0), 1)
        description   = "Simulated conditions"

        weather = WeatherData(
            temperature_c=temperature_c,
            humidity_pct=humidity_pct,
            description=description,
        )
        logger.debug(
            "WeatherService: fetched for %r -> %.1f degC, %.0f%% humidity",
            location, temperature_c, humidity_pct,
        )
        return weather


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class HydrationEngine:
    """
    Central engine that manages hydration goal calculation, rolling intake
    tracking, and intelligent alert evaluation.

    Parameters
    ----------
    user            : The User profile to drive personalised logic.
    weather_service : Provider of WeatherData (default: WeatherService).
    """

    def __init__(
        self,
        user: User,
        weather_service: Optional[WeatherService] = None,
    ) -> None:
        self.user = user
        self._weather_service = weather_service or WeatherService()

        # Rolling 24-h intake log — each element is an IntakeEntry.
        # deque chosen for O(1) append and popleft operations.
        self._intake_log: deque[IntakeEntry] = deque()

        # Cached goal and weather for the current "session"
        self._daily_goal_ml: Optional[float] = None
        self._current_weather: Optional[WeatherData] = None

        logger.info("HydrationEngine initialised for %s", self.user)

    # ------------------------------------------------------------------
    # 1. Dynamic Goal Calculation
    # ------------------------------------------------------------------

    def calculate_daily_goal(
        self,
        weather_override: Optional[WeatherData] = None,
    ) -> float:
        """
        Compute the personalised daily hydration goal (ml).

        Steps
        -----
        1. Start from BASELINE_ML.
        2. Add trimester modifier.
        3. Add activity bonus (if HIGH).
        4. Fetch weather; apply +15% if hot OR humid.

        Returns
        -------
        goal_ml : Recommended daily water intake in millilitres.
        """
        logger.info("--- Calculating daily hydration goal ---")

        # Step 1: Baseline
        goal = float(BASELINE_ML)
        logger.debug("Step 1 - Baseline: %.0f ml", goal)

        # Step 2: Trimester modifier
        trimester_bonus = TRIMESTER_MODIFIERS[self.user.trimester]
        goal += trimester_bonus
        logger.debug(
            "Step 2 - Trimester (%s) modifier: +%d ml -> %.0f ml",
            self.user.trimester.name, trimester_bonus, goal,
        )

        # Step 3: Activity level modifier
        if self.user.activity_level == ActivityLevel.HIGH:
            goal += HIGH_ACTIVITY_BONUS_ML
            logger.debug(
                "Step 3 - High activity bonus: +%d ml -> %.0f ml",
                HIGH_ACTIVITY_BONUS_ML, goal,
            )
        else:
            logger.debug(
                "Step 3 - Activity (%s): no bonus -> %.0f ml",
                self.user.activity_level.name, goal,
            )

        # Step 4: Weather modifier
        weather = self._weather_service.fetch(
            self.user.location, override=weather_override
        )
        self._current_weather = weather

        if weather.is_hot or weather.is_humid:
            pre_weather = goal
            goal *= WEATHER_INCREASE_FACTOR
            logger.debug(
                "Step 4 - Hot/humid weather (%.1f degC, %.0f%% RH): "
                "+15%% applied -> %.0f ml  (was %.0f ml)",
                weather.temperature_c, weather.humidity_pct, goal, pre_weather,
            )
        else:
            logger.debug(
                "Step 4 - Mild weather (%.1f degC, %.0f%% RH): no modifier -> %.0f ml",
                weather.temperature_c, weather.humidity_pct, goal,
            )

        self._daily_goal_ml = round(goal, 1)
        logger.info(
            "Daily goal for %s: %.0f ml",
            self.user.name, self._daily_goal_ml,
        )
        return self._daily_goal_ml

    @property
    def daily_goal_ml(self) -> Optional[float]:
        """Return the cached goal, or None if not yet calculated."""
        return self._daily_goal_ml

    # ------------------------------------------------------------------
    # 2. Rolling Intake Tracker
    # ------------------------------------------------------------------

    def _purge_old_entries(self, reference_time: Optional[datetime] = None) -> None:
        """
        Remove entries older than ROLLING_WINDOW_HOURS from the left of
        the deque. Accepts an optional reference_time for unit-testing.
        """
        cutoff = (reference_time or datetime.now()) - timedelta(
            hours=ROLLING_WINDOW_HOURS
        )
        purged = 0
        while self._intake_log and self._intake_log[0].timestamp < cutoff:
            self._intake_log.popleft()
            purged += 1
        if purged:
            logger.debug("Purged %d stale entries from intake log.", purged)

    def log_intake(
        self,
        amount_ml: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record a water-intake event.

        Parameters
        ----------
        amount_ml : Volume consumed in millilitres.
        timestamp : Datetime of consumption (defaults to now).
        """
        ts = timestamp or datetime.now()
        if amount_ml <= 0:
            logger.warning("log_intake: ignored non-positive amount (%.0f ml).", amount_ml)
            return

        entry = IntakeEntry(timestamp=ts, amount_ml=amount_ml)
        self._intake_log.append(entry)
        self._purge_old_entries(reference_time=ts)

        logger.info(
            "Logged %.0f ml at %s  |  24-h total: %.0f ml",
            amount_ml, ts.strftime("%H:%M:%S"), self.total_intake_24h(reference_time=ts),
        )

    def total_intake_24h(self, reference_time: Optional[datetime] = None) -> float:
        """Return total ml logged within the rolling 24-hour window."""
        self._purge_old_entries(reference_time=reference_time)
        return sum(e.amount_ml for e in self._intake_log)

    def intake_in_last_n_hours(
        self,
        hours: int,
        reference_time: Optional[datetime] = None,
    ) -> float:
        """
        Sum of intake (ml) recorded within the last *hours* hours.

        Parameters
        ----------
        hours          : Look-back window in hours.
        reference_time : Anchor time (defaults to now).
        """
        ref = reference_time or datetime.now()
        self._purge_old_entries(reference_time=ref)
        cutoff = ref - timedelta(hours=hours)
        return sum(
            e.amount_ml
            for e in self._intake_log
            if e.timestamp >= cutoff
        )

    def progress_pct(self, reference_time: Optional[datetime] = None) -> float:
        """
        Return hydration progress as a percentage of the daily goal.
        Returns 0.0 if the goal has not been calculated yet.
        """
        if not self._daily_goal_ml:
            return 0.0
        return min(
            100.0,
            (self.total_intake_24h(reference_time=reference_time) / self._daily_goal_ml) * 100,
        )

    # ------------------------------------------------------------------
    # 3. Intelligent Alert Logic
    # ------------------------------------------------------------------

    def evaluate_alerts(
        self,
        reference_time: Optional[datetime] = None,
    ) -> bool:
        """
        Evaluate whether an Intelligent Alert should be triggered.

        An alert fires when ALL of the following are true:
          * Current time is between ALERT_WINDOW_START_HOUR and ALERT_WINDOW_END_HOUR.
          * Less than ALERT_MIN_INTAKE_ML consumed in the last ALERT_LOOKBACK_HOURS.

        Parameters
        ----------
        reference_time : Evaluation anchor (defaults to now); useful for testing.

        Returns
        -------
        bool : True if an alert was triggered, False otherwise.
        """
        now = reference_time or datetime.now()
        current_hour = now.hour

        # Guard: only check within the permitted alert window
        within_window = ALERT_WINDOW_START_HOUR <= current_hour < ALERT_WINDOW_END_HOUR
        if not within_window:
            logger.debug(
                "Alert check at %s: outside alert window (%02d:00-%02d:00). No alert.",
                now.strftime("%H:%M"), ALERT_WINDOW_START_HOUR, ALERT_WINDOW_END_HOUR,
            )
            return False

        # Measure recent intake within the lookback window
        recent_ml = self.intake_in_last_n_hours(
            ALERT_LOOKBACK_HOURS, reference_time=now
        )
        logger.debug(
            "Alert check at %s: %.0f ml consumed in last %d h (threshold: %d ml).",
            now.strftime("%H:%M"), recent_ml, ALERT_LOOKBACK_HOURS, ALERT_MIN_INTAKE_ML,
        )

        if recent_ml < ALERT_MIN_INTAKE_ML:
            # ── INTELLIGENT ALERT TRIGGERED ────────────────────────────
            alert_msg = (
                "\n" + "=" * 60 + "\n"
                f"  [!] INTELLIGENT HYDRATION ALERT -- {self.user.name}\n"
                + "=" * 60 + "\n"
                f"  Time         : {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Last {ALERT_LOOKBACK_HOURS}h intake : {recent_ml:.0f} ml "
                f"(min recommended: {ALERT_MIN_INTAKE_ML} ml)\n"
                f"  24-h total   : {self.total_intake_24h(reference_time=now):.0f} ml"
                f" / {self._daily_goal_ml or 'N/A'} ml goal\n"
                f"  Action       : Please drink water soon — maternal health depends on it.\n"
                + "=" * 60 + "\n"
            )
            print(alert_msg)
            logger.warning(
                "ALERT: %s has consumed only %.0f ml in the last %d hours!",
                self.user.name, recent_ml, ALERT_LOOKBACK_HOURS,
            )
            return True

        # No alert — log positive status
        logger.info(
            "No alert: %.0f ml consumed in last %d h -- within safe range.",
            recent_ml, ALERT_LOOKBACK_HOURS,
        )
        return False

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def print_summary(self, reference_time: Optional[datetime] = None) -> None:
        """Print a formatted summary of the current hydration status."""
        now       = reference_time or datetime.now()
        total     = self.total_intake_24h(reference_time=now)
        pct       = self.progress_pct(reference_time=now)
        goal      = self._daily_goal_ml or 0.0
        remaining = max(0.0, goal - total)

        bar_filled = int(pct / 5)    # 20-block progress bar
        bar = "#" * bar_filled + "-" * (20 - bar_filled)

        weather_str = "N/A"
        if self._current_weather:
            w = self._current_weather
            weather_str = f"{w.temperature_c}degC, {w.humidity_pct}% RH  ({w.description})"

        print(
            "\n" + "-" * 60 + "\n"
            f"  HYDRATION SUMMARY -- {self.user.name}\n"
            + "-" * 60 + "\n"
            f"  Trimester  : {self.user.trimester.name.title()} ({self.user.trimester.value})\n"
            f"  Activity   : {self.user.activity_level.name.title()}\n"
            f"  Weather    : {weather_str}\n"
            f"  Daily Goal : {goal:.0f} ml\n"
            f"  Consumed   : {total:.0f} ml\n"
            f"  Remaining  : {remaining:.0f} ml\n"
            f"  Progress   : [{bar}] {pct:.1f}%\n"
            f"  Log entries: {len(self._intake_log)}\n"
            + "-" * 60 + "\n"
        )


# ---------------------------------------------------------------------------
# Simulation / Demo Block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Dynamic Algorithmic Hydration Engine -- Demo Simulation")
    print("  UN SDG 3.1 | Maternal Health | Pregnancy Hydration Tracker")
    print("=" * 60 + "\n")

    # ── 1. Create a pregnant user in her 3rd trimester ────────────────
    amina = User(
        name="Amina Rahman",
        trimester=Trimester.THIRD,
        activity_level=ActivityLevel.MODERATE,
        location="Dhaka, BD",
    )
    logger.info("Created user profile: %s", amina)

    # ── 2. Initialise the engine ──────────────────────────────────────
    engine = HydrationEngine(user=amina)

    # ── 3. Simulate a hot, humid day (Dhaka summer) ───────────────────
    hot_day = WeatherData(
        temperature_c=34.5,
        humidity_pct=82.0,
        description="Hot & humid -- typical Dhaka summer afternoon",
    )

    goal = engine.calculate_daily_goal(weather_override=hot_day)
    print(f"\n  Personalised daily goal for {amina.name}: {goal:.0f} ml\n")

    # ── 4. Log realistic water intake events throughout the day ───────
    #
    # Timeline:
    #   07:00  250 ml  morning glass
    #   08:30  300 ml  breakfast
    #   09:00  150 ml  mid-morning sip
    #   ── DRY SPELL ─────── nothing consumed from 09:00 to 15:30 ──────
    #   15:30  100 ml  tiny sip (still < 200 ml total in the 6-h window)
    #   ──  Scenario A checks at 15:31 → window covers 09:31–15:31 ─────
    #       Only 100 ml (at 15:30) is inside → 100 ml < 200 ml → ALERT
    #   18:00  400 ml  dinner
    #   ──  Scenario B checks at 19:00 → window covers 13:00–19:00 ─────
    #       100 ml + 400 ml = 500 ml → no alert
    #   ──  Scenario C checks at 23:00 → outside 08:00-20:00 window ────
    #   19:30  200 ml  evening wind-down

    today = datetime.now().date()

    def sim_ts(hour: int, minute: int = 0) -> datetime:
        """Build a datetime for today at the given hour:minute."""
        return datetime(today.year, today.month, today.day, hour, minute)

    intake_events = [
        (sim_ts(7,  0),  250, "Morning wake-up glass"),
        (sim_ts(8, 30),  300, "Breakfast + prenatal vitamins"),
        (sim_ts(9,  0),  150, "Mid-morning sip"),
        # ── 6.5-hour dry spell follows (nothing until 15:30) ──────────
        (sim_ts(15, 30), 100, "Very small sip during dry spell"),
        # Scenario A eval at 15:31: window 09:31-15:31 → only 100 ml inside
        (sim_ts(18,  0), 400, "Dinner — large glass"),
        # Scenario B eval at 19:00: window 13:00-19:00 → 100+400 = 500 ml
        (sim_ts(19, 30), 200, "Evening wind-down"),
    ]

    print("  Logging intake events...\n")
    for event_ts, ml, label in intake_events:
        logger.info("Event: '%s'", label)
        engine.log_intake(amount_ml=ml, timestamp=event_ts)

    # ── 5. Print afternoon summary ────────────────────────────────────
    engine.print_summary(reference_time=sim_ts(15, 31))

    # ── 6. Test the 6-hour intelligent alert logic ────────────────────
    print("\n  Testing Intelligent Alert Logic...\n")

    # --- Scenario A ---
    # Ref time  : 15:31
    # Lookback  : 09:31 to 15:31  (6 hours)
    # In window : 100 ml at 15:30  → 100 ml < 200 ml threshold
    # Expected  : ALERT FIRES
    print("  [Scenario A] Evaluating at 15:31")
    print("               Lookback window : 09:31 - 15:31")
    print("               Intake in window: 100 ml  (threshold: 200 ml)")
    print("               Expected        : ALERT FIRES\n")
    fired_a = engine.evaluate_alerts(reference_time=sim_ts(15, 31))
    print(f"  Alert fired: {fired_a}\n")

    # --- Scenario B ---
    # Ref time  : 19:00
    # Lookback  : 13:00 to 19:00  (6 hours)
    # In window : 100 ml (15:30) + 400 ml (18:00) = 500 ml
    # Expected  : NO ALERT
    print("  [Scenario B] Evaluating at 19:00")
    print("               Lookback window : 13:00 - 19:00")
    print("               Intake in window: 100 ml + 400 ml = 500 ml")
    print("               Expected        : No alert\n")
    fired_b = engine.evaluate_alerts(reference_time=sim_ts(19, 0))
    print(f"  Alert fired: {fired_b}\n")

    # --- Scenario C ---
    # Ref time  : 23:00 — outside the permitted 08:00-20:00 alert window
    # Expected  : NO ALERT (do-not-disturb at night)
    print("  [Scenario C] Evaluating at 23:00")
    print("               Outside the 08:00-20:00 alert window")
    print("               Expected        : No alert (do-not-disturb)\n")
    fired_c = engine.evaluate_alerts(reference_time=sim_ts(23, 0))
    print(f"  Alert fired: {fired_c}\n")

    # ── 7. Final end-of-day summary ───────────────────────────────────
    engine.print_summary(reference_time=sim_ts(20, 0))

    print("  Simulation complete. Stay hydrated!\n")
