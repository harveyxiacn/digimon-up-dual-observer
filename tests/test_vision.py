from __future__ import annotations

import cv2
import numpy as np

from digimon_monitor.vision import (
    EquipmentState,
    VisionAnalyzer,
    classify_special_task,
    is_ticket_insufficient,
)
from digimon_monitor.discovery import detect_running_emulators


def _equipment_frame(*, worse: bool) -> np.ndarray:
    frame = np.zeros((1000, 455, 3), dtype=np.uint8)
    # Large paired pink and cyan buttons in the lower screen.
    cv2.rectangle(frame, (60, 780), (210, 840), (215, 70, 235), -1)
    cv2.rectangle(frame, (240, 780), (390, 840), (240, 150, 15), -1)
    # Bright green stat/arrow pixels in the right status column.
    cv2.rectangle(frame, (335, 430), (365, 470), (70, 245, 130), -1)
    if worse:
        cv2.rectangle(frame, (335, 520), (365, 560), (30, 80, 255), -1)
    return frame


def test_special_support_task_tolerates_ocr_variation() -> None:
    text = "175. 抽取 0/15次\n支援型數碼賣貝轉蛋"
    assert classify_special_task(text) == "抽取支援型數碼寶貝"


def test_special_skill_card_task() -> None:
    assert classify_special_task("抽取 3/10 次 技能卡片") == "抽取技能卡片"


def test_non_special_task() -> None:
    assert classify_special_task("擊敗 5/5 次敵人") is None


def test_ticket_insufficient_variants() -> None:
    assert is_ticket_insufficient("全像投影券不足")
    assert is_ticket_insufficient("全息投影票不夠")
    assert not is_ticket_insufficient("啟動 10/10 次全像投影裝置")


def test_better_equipment_popup() -> None:
    result = VisionAnalyzer().analyze(_equipment_frame(worse=False))
    assert result.equipment_state is EquipmentState.BETTER
    assert result.sell_click is not None
    assert result.equip_click is not None


def test_worse_equipment_popup() -> None:
    result = VisionAnalyzer().analyze(_equipment_frame(worse=True))
    assert result.equipment_state is EquipmentState.WORSE


def test_full_width_blue_reward_popup() -> None:
    frame = np.zeros((1000, 455, 3), dtype=np.uint8)
    frame[300:700, :] = (160, 80, 20)
    result = VisionAnalyzer().analyze(frame)
    assert result.reward_popup
    assert not result.task_complete
    assert result.reward_close_click == (227, 820)


def test_detects_popular_emulator_processes() -> None:
    detected = detect_running_emulators(
        ["HD-Player.exe", "dnplayer.exe", "unrelated.exe"]
    )
    assert [item.name for item in detected] == [
        "BlueStacks",
        "雷电模拟器 / LDPlayer",
    ]


def test_support_process_alone_does_not_claim_emulator_running() -> None:
    assert detect_running_emulators(["BlueStacksServices.exe"]) == []
