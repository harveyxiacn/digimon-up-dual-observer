from __future__ import annotations

import pytest

from digimon_monitor.equipment import (
    EquipmentDecision,
    decide_equipment,
    equipment_priority,
)


@pytest.mark.parametrize(
    ("text", "priority"),
    [
        ("暴擊發生率 4.35%\n技能暴擊發生率 4.35%", 3),
        ("暴击发生率 4.35%\n技能暴击发生率 4.35%", 3),
        ("Critical Hit Rate 4.35%\nSkill Critical Hit Rate 4.35%", 3),
        ("クリティカル発生率 4.35%\nスキルクリティカル発生率 4.35%", 3),
        ("暴擊發生率 4.35%", 2),
        ("Critical Hit Rate 4.35%", 2),
        ("技能暴擊發生率 4.35%", 1),
        ("Skill Critical Hit Rate 4.35%", 1),
        ("スキルクリティカル発生率 4.35%", 1),
        ("攻擊力 45\n防禦力 45", 0),
        ("unrelated OCR noise", None),
    ],
)
def test_equipment_priority_supports_localized_attribute_names(
    text: str,
    priority: int | None,
) -> None:
    assert equipment_priority(text) == priority


@pytest.mark.parametrize(
    "text",
    [
        "技能暴擊發生率 4.35%",
        "技能暴击发生率 4.35%",
        "Skill Critical Hit Rate 4.35%",
        "スキルクリティカル発生率 4.35%",
    ],
)
def test_skill_critical_rate_does_not_also_count_as_critical_rate(
    text: str,
) -> None:
    assert equipment_priority(text) == 1


@pytest.mark.parametrize(
    ("current_text", "new_text", "decision"),
    [
        ("暴擊發生率", "暴擊發生率\n技能暴擊發生率", EquipmentDecision.EQUIP),
        ("技能暴擊發生率", "暴擊發生率", EquipmentDecision.EQUIP),
        ("暴擊發生率", "暴擊發生率", EquipmentDecision.SELL),
        ("暴擊發生率\n技能暴擊發生率", "暴擊發生率", EquipmentDecision.SELL),
        ("攻擊力", "防禦力", EquipmentDecision.SELL),
        ("random noise", "暴擊發生率", EquipmentDecision.NO_ACTION),
        ("", "暴擊發生率", EquipmentDecision.NO_ACTION),
        ("暴擊發生率", "   ", EquipmentDecision.NO_ACTION),
        (None, "暴擊發生率", EquipmentDecision.NO_ACTION),
    ],
)
def test_equipment_decision_requires_both_panels_and_strict_improvement(
    current_text: str | None,
    new_text: str | None,
    decision: EquipmentDecision,
) -> None:
    assert decide_equipment(current_text, new_text) is decision
