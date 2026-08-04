from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from digimon_monitor.equipment import EquipmentDecision
from digimon_monitor.config import FeatureSettings
from digimon_monitor.monitor import (
    Cooldowns,
    DeviceMonitor,
    ReappearingPromptLatch,
    StableState,
)
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


def test_cooldown_is_ready_before_its_first_success_and_honors_defer() -> None:
    cooldowns = Cooldowns()

    assert cooldowns.ready("ticket", 900, now=0.0)
    cooldowns.defer("ticket", 60, now=10.0)
    assert not cooldowns.ready("ticket", 900, now=69.0)
    assert cooldowns.ready("ticket", 900, now=70.0)


def test_equipment_gate_clears_cached_decision_without_ocr() -> None:
    monitor, ocr, taps = _unknown_equipment_monitor(
        current_text="攻擊力 45", new_text="暴擊發生率"
    )
    monitor.config.features = FeatureSettings(equipment_automation_enabled=False)
    monitor.equipment_decision = EquipmentDecision.EQUIP
    monitor.equipment_priorities = object()
    monitor.next_equipment_ocr = 99.0
    frame = np.zeros((10, 10, 3), dtype=np.uint8)

    monitor._handle_frame(frame, now=10.0)

    assert ocr.calls == 0
    assert taps == []
    assert monitor.equipment_decision is EquipmentDecision.NO_ACTION
    assert monitor.equipment_priorities is None
    assert monitor.next_equipment_ocr == 0.0


def test_task_gate_skips_reward_close_and_task_ocr() -> None:
    monitor = object.__new__(DeviceMonitor)
    result = SimpleNamespace(
        reward_popup=True,
        reward_close_click=(20, 30),
    )
    monitor.vision = SimpleNamespace(analyze=lambda frame: result)
    monitor.config = SimpleNamespace(
        features=FeatureSettings(task_monitoring_enabled=False),
        monitor=SimpleNamespace(stable_frames_before_click=1),
    )
    monitor.stable = StableState()
    taps: list[tuple[object, ...]] = []
    monitor._tap = lambda *args: taps.append(args) or True

    monitor._handle_frame(np.zeros((2, 2, 3), dtype=np.uint8), now=1.0)

    assert taps == []
    assert monitor.stable.count == 0


def test_food_gate_hot_switches_without_task_or_dialog_ocr() -> None:
    monitor = object.__new__(DeviceMonitor)
    result = SimpleNamespace(
        reward_popup=False,
        equipment_state=EquipmentState.NONE,
        food_prompt=True,
        food_click=(12, 34),
        task_complete=True,
        task_incomplete=False,
        task_click=(56, 78),
    )
    monitor.vision = SimpleNamespace(analyze=lambda frame: result)
    monitor.config = SimpleNamespace(
        features=FeatureSettings(
            task_monitoring_enabled=False,
            food_prompt_automation_enabled=False,
            discord_notifications_enabled=False,
        ),
        monitor=SimpleNamespace(stable_frames_before_click=1),
    )
    monitor.stable = StableState()
    monitor.food_prompt_latch = ReappearingPromptLatch(1)
    monitor.equipment_decision = EquipmentDecision.NO_ACTION
    monitor.equipment_priorities = None
    monitor.next_equipment_ocr = 0.0
    monitor.next_dialog_ocr = 0.0
    monitor.next_task_ocr = 0.0
    monitor.last_task_text = "stale"
    monitor.ocr = SimpleNamespace(
        read_dialog=lambda frame: (_ for _ in ()).throw(AssertionError()),
        read_task=lambda frame: (_ for _ in ()).throw(AssertionError()),
    )
    monitor.tr = lambda key, **kwargs: key
    taps: list[tuple[object, ...]] = []
    monitor._tap = lambda *args: taps.append(args) or True
    frame = np.zeros((2, 2, 3), dtype=np.uint8)

    monitor._handle_frame(frame, now=1.0)
    assert taps == []
    assert monitor.last_task_text == ""

    monitor.config.features = FeatureSettings(
        task_monitoring_enabled=False,
        food_prompt_automation_enabled=True,
        discord_notifications_enabled=False,
    )
    monitor._handle_frame(frame, now=2.0)
    assert taps[0][1] == (12, 34)


def test_discord_gate_does_not_send_or_consume_first_cooldown() -> None:
    monitor = object.__new__(DeviceMonitor)
    monitor.config = SimpleNamespace(
        features=FeatureSettings(discord_notifications_enabled=False)
    )
    sent: list[str] = []
    monitor.notifier = SimpleNamespace(
        send=lambda message, frame: sent.append(message)
    )
    monitor.cooldowns = Cooldowns()
    monitor._save_frame = lambda frame, event: None
    monitor._log = lambda level, message: None
    monitor.tr = lambda key, **kwargs: key
    frame = np.zeros((2, 2, 3), dtype=np.uint8)

    monitor._notify("special:test", 60.0, "message", frame, now=1.0)
    assert sent == []
    assert monitor.cooldowns.ready("special:test", 60.0, now=1.0)

    monitor.config.features = FeatureSettings(
        discord_notifications_enabled=True
    )
    monitor._notify("special:test", 60.0, "message", frame, now=1.0)
    assert sent == ["message"]
    assert not monitor.cooldowns.ready("special:test", 60.0, now=1.0)
