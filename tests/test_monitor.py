from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from digimon_monitor.equipment import EquipmentDecision
from digimon_monitor.monitor import DeviceMonitor, StableState
from digimon_monitor.vision import EquipmentState


def _unknown_equipment_monitor(
    *,
    current_text: str,
    new_text: str,
) -> tuple[DeviceMonitor, SimpleNamespace, list[tuple[object, ...]]]:
    monitor = object.__new__(DeviceMonitor)
    result = SimpleNamespace(
        reward_popup=False,
        equipment_state=EquipmentState.UNKNOWN,
        sell_click=(10, 10),
        equip_click=(20, 20),
    )
    monitor.vision = SimpleNamespace(analyze=lambda frame: result)
    monitor.config = SimpleNamespace(
        monitor=SimpleNamespace(
            dialog_ocr_interval_seconds=8.0,
            stable_frames_before_click=2,
        )
    )
    monitor.ocr = SimpleNamespace(
        calls=0,
        read_equipment_attributes=lambda frame: (
            setattr(monitor.ocr, "calls", monitor.ocr.calls + 1)
            or (current_text, new_text)
        ),
    )
    monitor.stable = StableState()
    monitor.next_equipment_ocr = 0.0
    monitor.equipment_decision = EquipmentDecision.NO_ACTION
    monitor.equipment_priorities = None
    monitor.tr = lambda key, **kwargs: key
    monitor._log = lambda level, message: None
    taps: list[tuple[object, ...]] = []
    monitor._tap = lambda *args: taps.append(args) or True
    return monitor, monitor.ocr, taps


def test_unknown_equipment_uses_cached_ocr_decision_until_throttle_expires() -> None:
    monitor, ocr, taps = _unknown_equipment_monitor(
        current_text="攻擊力 45",
        new_text="暴擊發生率\n技能暴擊發生率",
    )
    frame = np.zeros((10, 10, 3), dtype=np.uint8)

    monitor._handle_frame(frame, now=10.0)
    assert ocr.calls == 1
    assert taps == []

    monitor._handle_frame(frame, now=11.0)
    assert ocr.calls == 1
    assert taps[0][1] == (20, 20)


def test_unknown_equipment_sells_equal_priority_item() -> None:
    monitor, ocr, taps = _unknown_equipment_monitor(
        current_text="暴擊發生率",
        new_text="暴擊發生率",
    )
    frame = np.zeros((10, 10, 3), dtype=np.uint8)

    monitor._handle_frame(frame, now=10.0)
    monitor._handle_frame(frame, now=11.0)

    assert ocr.calls == 1
    assert taps[0][1] == (10, 10)


def test_unknown_equipment_with_empty_panel_never_taps() -> None:
    monitor, ocr, taps = _unknown_equipment_monitor(
        current_text="",
        new_text="暴擊發生率",
    )
    frame = np.zeros((10, 10, 3), dtype=np.uint8)

    monitor._handle_frame(frame, now=10.0)
    monitor._handle_frame(frame, now=11.0)

    assert ocr.calls == 1
    assert taps == []
