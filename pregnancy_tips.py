"""
=============================================================================
pregnancy_tips.py
Pregnancy Tips & Facts Parser
=============================================================================

Reads `Pregnancy_Tips_and_Facts.txt` and exposes a clean, structured
dictionary of tips and morale-boosting facts keyed by trimester number
(1, 2, 3) plus a "general" bucket for content that applies to all trimesters.

Public API
----------
load_tips(filepath)  ->  TipsData
    Parse the file and return a TipsData dataclass.

get_tips_for_trimester(tips_data, trimester_number)  ->  TrimesterContent
    Filter to a specific trimester (1, 2, or 3).

get_random_tip(tips_data, trimester_number)  ->  str
    Return one random tip or fact for the given trimester,
    mixing in general content when available.
=============================================================================
"""

import os
import re
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class TrimesterContent:
    """
    All parsed content for a single trimester (or general).

    Attributes
    ----------
    trimester_num : 1, 2, 3, or 0 for general content.
    label         : Human-readable header, e.g. "The First Trimester (Weeks 1–13)".
    focus         : The focus subtitle, e.g. "Foundation, Adaptation, and Grace".
    intro         : Opening paragraph.
    tips          : List of practical tip strings (bullet * items).
    facts         : List of morale-boosting fact strings (> Fact: items).
    """
    trimester_num: int
    label: str
    focus: str
    intro: str
    tips: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)

    def all_items(self) -> list[tuple[str, str]]:
        """
        Return all tips and facts as a flat list of (kind, text) tuples.
        kind is either 'tip' or 'fact'.
        """
        items: list[tuple[str, str]] = []
        items += [("tip",  t) for t in self.tips]
        items += [("fact", f) for f in self.facts]
        return items


@dataclass
class TipsData:
    """
    Top-level container holding content for all three trimesters
    plus a general/final-note section.

    Attributes
    ----------
    trimesters : dict mapping trimester_num (1/2/3) → TrimesterContent.
    general    : Content that applies to every trimester (final note, etc.).
    source_file: Path to the parsed source file.
    """
    trimesters: dict[int, TrimesterContent] = field(default_factory=dict)
    general: list[str]                       = field(default_factory=list)
    source_file: str                          = ""


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Maps emoji/keyword markers in section headers to trimester numbers
_TRIMESTER_MARKERS: list[tuple[str, int]] = [
    ("First",  1),
    ("Second", 2),
    ("Third",  3),
]

# Regex for tip lines (bullet points starting with *)
_TIP_RE  = re.compile(r"^\*\s+(.+)$")
# Regex for fact lines (blockquote starting with > Fact:)
_FACT_RE = re.compile(r"^>\s*Fact:\s*(.+)$")
# Regex for focus subtitle
_FOCUS_RE = re.compile(r"^Focus:\s*(.+)$")


def load_tips(filepath: Optional[str] = None) -> TipsData:
    """
    Parse `Pregnancy_Tips_and_Facts.txt` and return a TipsData instance.

    Parameters
    ----------
    filepath : Absolute or relative path to the txt file.
               Defaults to a file named `Pregnancy_Tips_and_Facts.txt`
               in the same directory as this module.

    Returns
    -------
    TipsData with all trimesters and general content populated.

    Raises
    ------
    FileNotFoundError if the file cannot be located.
    """
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__),
                                "Pregnancy_Tips_and_Facts.txt")

    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(
            f"Tips file not found at: {path.resolve()}\n"
            "Place 'Pregnancy_Tips_and_Facts.txt' next to pregnancy_tips.py."
        )

    raw_text = path.read_text(encoding="utf-8")
    return _parse(raw_text, source_file=str(path))


def _parse(text: str, source_file: str = "") -> TipsData:
    """Internal parser — works on the raw file text string."""
    data = TipsData(source_file=source_file)

    lines = text.splitlines()

    current_trim: Optional[TrimesterContent] = None
    in_tips_section  = False
    in_facts_section = False
    intro_lines: list[str] = []
    past_header = False    # True once we've seen the first trimester header

    def _save_current():
        """Flush the current TrimesterContent into data."""
        nonlocal current_trim
        if current_trim is not None:
            if intro_lines:
                current_trim.intro = " ".join(intro_lines).strip()
            data.trimesters[current_trim.trimester_num] = current_trim

    for line in lines:
        stripped = line.strip()

        # ── Section divider ───────────────────────────────────────────
        if stripped == "---":
            _save_current()
            current_trim = None
            in_tips_section = False
            in_facts_section = False
            intro_lines = []
            continue

        # ── Trimester header ──────────────────────────────────────────
        detected_trim = _detect_trimester(stripped)
        if detected_trim is not None:
            past_header = True
            _save_current()
            intro_lines = []
            in_tips_section = False
            in_facts_section = False
            current_trim = TrimesterContent(
                trimester_num=detected_trim,
                label=_clean_header(stripped),
                focus="",
                intro="",
            )
            continue

        # ── Focus line ────────────────────────────────────────────────
        focus_match = _FOCUS_RE.match(stripped)
        if focus_match and current_trim is not None:
            current_trim.focus = focus_match.group(1).strip()
            continue

        # ── Section sub-headers ───────────────────────────────────────
        if stripped in ("Practical Tips & Tricks", "Practical Tips & Tricks"):
            in_tips_section  = True
            in_facts_section = False
            continue

        if stripped == "Morale-Boosting Facts":
            in_tips_section  = False
            in_facts_section = True
            continue

        # ── Tip bullet ────────────────────────────────────────────────
        tip_match = _TIP_RE.match(stripped)
        if tip_match and current_trim is not None and in_tips_section:
            current_trim.tips.append(tip_match.group(1).strip())
            continue

        # ── Fact blockquote ───────────────────────────────────────────
        fact_match = _FACT_RE.match(stripped)
        if fact_match and current_trim is not None and in_facts_section:
            current_trim.facts.append(fact_match.group(1).strip())
            continue

        # ── General / final note ──────────────────────────────────────
        if past_header and current_trim is None and stripped and stripped != "---":
            # We're between sections or after the last trimester block
            # Collect as general content
            if not stripped.startswith("A Final Note"):
                data.general.append(stripped)
            else:
                data.general.append(stripped)
            continue

        # ── Intro text ────────────────────────────────────────────────
        if (current_trim is not None
                and not in_tips_section
                and not in_facts_section
                and stripped
                and not _FOCUS_RE.match(stripped)):
            intro_lines.append(stripped)

    # Flush any final trimester not followed by ---
    _save_current()

    return data


def _detect_trimester(line: str) -> Optional[int]:
    """Return 1/2/3 if line is a trimester header, else None."""
    for keyword, num in _TRIMESTER_MARKERS:
        if keyword in line and "Trimester" in line:
            return num
    return None


def _clean_header(line: str) -> str:
    """Strip emoji and leading/trailing whitespace from a header line."""
    # Remove common emoji characters used as section markers
    cleaned = re.sub(r"[🌸☀️🌙]", "", line).strip()
    return cleaned


# ---------------------------------------------------------------------------
# Public Accessors
# ---------------------------------------------------------------------------

def get_tips_for_trimester(
    tips_data: TipsData,
    trimester_number: int,
) -> Optional[TrimesterContent]:
    """
    Return the TrimesterContent for *trimester_number* (1, 2, or 3).
    Returns None if the trimester was not found in the parsed data.
    """
    return tips_data.trimesters.get(trimester_number)


def get_random_tip(
    tips_data: TipsData,
    trimester_number: int,
    *,
    prefer_kind: Optional[str] = None,
) -> str:
    """
    Return a single random tip or fact for the given trimester.

    Parameters
    ----------
    tips_data        : Parsed TipsData from load_tips().
    trimester_number : 1, 2, or 3.
    prefer_kind      : 'tip' to prefer practical tips, 'fact' for morale facts,
                       or None for either (default).

    Returns
    -------
    Formatted string ready to display in the UI.
    """
    content = get_tips_for_trimester(tips_data, trimester_number)
    if content is None:
        return "Stay hydrated and take care of yourself! 💧"

    if prefer_kind == "tip":
        pool = content.tips or content.facts
    elif prefer_kind == "fact":
        pool = content.facts or content.tips
    else:
        pool = content.tips + content.facts

    if not pool:
        return "Keep up the great work! 🌸"

    chosen = random.choice(pool)
    kind   = "💡 Tip" if chosen in content.tips else "✨ Fact"
    return f"{kind}  ·  {chosen}"


def get_all_tips_for_trimester(
    tips_data: TipsData,
    trimester_number: int,
) -> list[tuple[str, str]]:
    """
    Return all (kind, text) pairs for a trimester.
    kind is 'tip' or 'fact'.
    Useful for populating a scrollable list in the UI.
    """
    content = get_tips_for_trimester(tips_data, trimester_number)
    if content is None:
        return []
    return content.all_items()


# ---------------------------------------------------------------------------
# Quick self-test / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pathlib
    tips = load_tips()
    print(f"Loaded from: {tips.source_file}\n")

    for num in (1, 2, 3):
        c = tips.trimesters.get(num)
        if c:
            print(f"=== Trimester {num}: {c.label} ===")
            print(f"    Focus : {c.focus}")
            print(f"    Tips  : {len(c.tips)}")
            print(f"    Facts : {len(c.facts)}")
            print(f"    Random: {get_random_tip(tips, num)}\n")

    print("General content lines:", len(tips.general))
