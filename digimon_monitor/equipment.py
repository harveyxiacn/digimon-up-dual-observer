from __future__ import annotations

from enum import Enum, IntEnum
import re


class EquipmentDecision(str, Enum):
    """The safe action for an equipment comparison with no usable arrow."""

    EQUIP = "equip"
    SELL = "sell"
    NO_ACTION = "no_action"


class EquipmentPriority(IntEnum):
    """User-defined equipment affix priority, from weakest to strongest."""

    NONE = 0
    SKILL_CRIT = 1
    CRIT = 2
    DUAL = 3


# OCR languages are configured independently, so recognize the attribute names
# used by each supported game language here.  The compact representation below
# deliberately leaves CJK characters intact while discarding OCR spacing and
# punctuation variations.
_SKILL_CRIT_TERMS = (
    "技能暴擊發生率",
    "技能暴击发生率",
    "技能暴擊率",
    "技能暴击率",
    "skillcriticalhitrate",
    "skillcritrate",
    "skillcriticalchance",
    "skillcritchance",
    "スキルクリティカル発生率",
    "スキルクリティカル率",
)
_CRIT_TERMS = (
    "暴擊發生率",
    "暴击发生率",
    "暴擊率",
    "暴击率",
    "criticalhitrate",
    "critrate",
    "criticalchance",
    "critchance",
    "クリティカル発生率",
    "クリティカル率",
)
_PANEL_MARKER_TERMS = (
    "攻擊力",
    "攻击力",
    "攻撃力",
    "防禦力",
    "防御力",
    "體力",
    "体力",
    "attack",
    "defense",
    "defence",
    "health",
    "stamina",
    "hp",
)


def _compact(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


def _term_spans(text: str, terms: tuple[str, ...]) -> list[tuple[int, int]]:
    return [
        (match.start(), match.end())
        for term in terms
        for match in re.finditer(re.escape(term), text)
    ]


def equipment_priority(text: str | None) -> EquipmentPriority | None:
    """Classify an item's crit attributes on the required 0--3 scale.

    ``None`` means the panel has no usable OCR.  A skill-critical label
    contains the normal critical label in Chinese, Japanese, and English;
    therefore a normal-critical match counts only when it does not overlap a
    skill-critical label.  This makes score 3 require two separate attributes.
    """
    if not text or not text.strip():
        return None

    normalized = _compact(text)
    skill_spans = _term_spans(normalized, _SKILL_CRIT_TERMS)
    crit_spans = _term_spans(normalized, _CRIT_TERMS)
    has_skill_crit = bool(skill_spans)
    has_crit = any(
        crit_end <= skill_start or skill_end <= crit_start
        for crit_start, crit_end in crit_spans
        for skill_start, skill_end in skill_spans
    ) if skill_spans else bool(crit_spans)

    if has_crit and has_skill_crit:
        return EquipmentPriority.DUAL
    if has_crit:
        return EquipmentPriority.CRIT
    if has_skill_crit:
        return EquipmentPriority.SKILL_CRIT
    # A non-empty OCR result may still be random scenery or font noise.  Tier
    # zero is valid only when at least one normal equipment-panel stat label is
    # readable; otherwise the caller must stop instead of guessing and selling.
    if any(term in normalized for term in _PANEL_MARKER_TERMS):
        return EquipmentPriority.NONE
    return None


def decide_equipment(
    current_text: str | None,
    new_text: str | None,
) -> EquipmentDecision:
    """Equip only when the new item is strictly higher priority.

    A missing OCR result is intentionally different from a recognized item
    with no target attributes: missing text causes no action, while score 0 is
    a valid lowest-priority item.
    """
    current_priority = equipment_priority(current_text)
    new_priority = equipment_priority(new_text)
    if current_priority is None or new_priority is None:
        return EquipmentDecision.NO_ACTION
    if new_priority > current_priority:
        return EquipmentDecision.EQUIP
    return EquipmentDecision.SELL
