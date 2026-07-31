from __future__ import annotations

import cv2
import numpy as np

from digimon_monitor.vision import (
    EquipmentState,
    VisionAnalyzer,
    classify_special_task,
    is_ticket_insufficient,
    task_geometry,
    task_progress_complete,
)
from digimon_monitor.discovery import detect_running_emulators
from digimon_monitor.monitor import ReappearingPromptLatch


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


def _task_frame(*, incomplete: bool) -> np.ndarray:
    frame = np.zeros((1000, 455, 3), dtype=np.uint8)
    x0, y0, x1, y1, _, _ = task_geometry(frame.shape)
    left, top = int(x0 * 455), int(y0 * 1000)
    right, bottom = int(x1 * 455), int(y1 * 1000)
    cv2.rectangle(
        frame,
        (left, top),
        (right - 1, bottom - 1),
        (30, 240, 80),
        8,
    )
    if not incomplete:
        cv2.rectangle(
            frame,
            (
                int((x0 + 0.58 * (x1 - x0)) * 455),
                int((y0 + 0.20 * (y1 - y0)) * 1000),
            ),
            (
                int((x0 + 0.64 * (x1 - x0)) * 455),
                int((y0 + 0.42 * (y1 - y0)) * 1000),
            ),
            (30, 240, 80),
            -1,
        )
    else:
        cv2.rectangle(
            frame,
            (
                int((x0 + 0.34 * (x1 - x0)) * 455),
                int((y0 + 0.38 * (y1 - y0)) * 1000),
            ),
            (
                int((x0 + 0.40 * (x1 - x0)) * 455),
                int((y0 + 0.55 * (y1 - y0)) * 1000),
            ),
            (20, 40, 255),
            -1,
        )
    return frame


def _food_prompt_frame(
    *,
    cyan_outline: bool = True,
    dark_core: bool = True,
    shape: tuple[int, int] = (1000, 455),
) -> np.ndarray:
    height, width = shape
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    aspect = width / height
    center = (
        int(np.clip(0.27 + 0.43 * aspect, 0.46, 0.51) * width),
        int(np.clip(0.51 - 0.255 * aspect, 0.365, 0.395) * height),
    )
    half_width = max(4, int(0.033 * width))
    half_height = max(4, int(0.021 * height))
    outline = (255, 255, 0) if cyan_outline else (245, 245, 245)
    cv2.rectangle(
        frame,
        (center[0] - half_width, center[1] - half_height),
        (center[0] + half_width, center[1] + half_height),
        outline,
        -1,
    )
    cv2.rectangle(
        frame,
        (center[0] - int(0.024 * width), center[1] - int(0.016 * height)),
        (center[0] + int(0.024 * width), center[1] + int(0.016 * height)),
        (245, 245, 245),
        -1,
    )
    cv2.rectangle(
        frame,
        (center[0] - int(0.012 * width), center[1] - int(0.006 * height)),
        (center[0] + int(0.014 * width), center[1] + int(0.007 * height)),
        (60, 90, 150) if dark_core else (220, 220, 220),
        -1,
    )
    return frame


def test_special_support_task_tolerates_ocr_variation() -> None:
    text = "175. 抽取 0/15次\n支援型數碼賣貝轉蛋"
    assert classify_special_task(text) == "support_digimon"


def test_special_skill_card_task() -> None:
    assert classify_special_task("抽取 3/10 次 技能卡片") == "skill_card"


def test_international_special_task_variants() -> None:
    assert (
        classify_special_task("Draw 0/15 support-type Digimon")
        == "support_digimon"
    )
    assert classify_special_task("スキルカードを3回引く") == "skill_card"


def test_non_special_task() -> None:
    assert classify_special_task("擊敗 5/5 次敵人") is None


def test_task_progress_parser_handles_ocr_slash_variants() -> None:
    assert task_progress_complete("擊敗 5/5 次敵人") is True
    assert task_progress_complete("啟動 10//10 次裝置") is True
    assert task_progress_complete("完成討伐 1/2 次") is False
    assert task_progress_complete("完成討伐 /2 次") is None


def test_ticket_insufficient_variants() -> None:
    assert is_ticket_insufficient("全像投影券不足")
    assert is_ticket_insufficient("全息投影票不夠")
    assert not is_ticket_insufficient("啟動 10/10 次全像投影裝置")
    assert is_ticket_insufficient("Not enough hologram tickets")
    assert is_ticket_insufficient("ホログラムチケットが足りない")


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


def test_red_current_progress_blocks_green_task_false_positive() -> None:
    complete = VisionAnalyzer().analyze(_task_frame(incomplete=False))
    incomplete = VisionAnalyzer().analyze(_task_frame(incomplete=True))
    assert complete.task_complete
    assert not complete.task_incomplete
    assert complete.task_current_green
    assert not incomplete.task_complete
    assert incomplete.task_incomplete
    assert not incomplete.task_current_green


def test_green_task_outline_without_green_current_count_is_not_complete() -> None:
    result = VisionAnalyzer().analyze(_task_frame(incomplete=True))
    assert not result.task_complete
    assert not result.task_current_green


def test_food_prompt_uses_white_tile_and_cyan_outline() -> None:
    result = VisionAnalyzer().analyze(_food_prompt_frame())
    assert result.food_prompt
    assert result.food_click is not None
    assert abs(result.food_click[0] / 455 - 0.464) < 0.03
    assert abs(result.food_click[1] / 1000 - 0.366) < 0.03

    no_outline = VisionAnalyzer().analyze(
        _food_prompt_frame(cyan_outline=False)
    )
    assert not no_outline.food_prompt

    no_food_core = VisionAnalyzer().analyze(
        _food_prompt_frame(dark_core=False)
    )
    assert not no_food_core.food_prompt


def test_food_prompt_tracks_tall_bluestacks_layout() -> None:
    frame = _food_prompt_frame(shape=(2816, 1280))
    result = VisionAnalyzer().analyze(frame)
    assert result.food_prompt
    assert result.food_click is not None
    assert abs(result.food_click[0] / 1280 - 0.466) < 0.03
    assert abs(result.food_click[1] / 2816 - 0.394) < 0.02


def test_food_prompt_latch_rearms_only_after_disappearance() -> None:
    latch = ReappearingPromptLatch(stable_frames=2)
    assert not latch.update(True)
    assert latch.update(True)
    latch.mark_handled()
    assert not latch.update(True)
    assert not latch.update(True)
    assert not latch.update(False)
    assert not latch.update(False)
    assert not latch.update(True)
    assert latch.update(True)


def test_detects_popular_emulator_processes() -> None:
    detected = detect_running_emulators(
        ["HD-Player.exe", "dnplayer.exe", "unrelated.exe"]
    )
    assert [item.key for item in detected] == ["bluestacks", "ldplayer"]


def test_support_process_alone_does_not_claim_emulator_running() -> None:
    assert detect_running_emulators(["BlueStacksServices.exe"]) == []
