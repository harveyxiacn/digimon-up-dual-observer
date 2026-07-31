from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable

import cv2
import numpy as np

from .config import VisionSettings


Point = tuple[int, int]
Box = tuple[int, int, int, int]


# The interaction bubble has a white tile and cyan border, with a food sprite
# in its middle.  A minimum amount of dark/brown sprite detail prevents large
# white/cyan combat effects (especially ice effects) from being clicked.
FOOD_PROMPT_DARK_CORE_RATIO = 0.05


class EquipmentState(str, Enum):
    NONE = "none"
    BETTER = "better"
    WORSE = "worse"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class VisualResult:
    task_complete: bool
    task_score: float
    task_click: Point
    reward_popup: bool
    reward_score: float
    reward_close_click: Point
    equipment_state: EquipmentState
    sell_click: Point | None
    equip_click: Point | None
    green_equipment_ratio: float = 0.0
    red_equipment_ratio: float = 0.0
    task_incomplete: bool = False
    task_progress_red_ratio: float = 0.0
    task_current_green: bool = False
    food_prompt: bool = False
    food_score: float = 0.0
    food_click: Point | None = None


def _fraction(mask: np.ndarray) -> float:
    return float(cv2.countNonZero(mask)) / float(mask.size) if mask.size else 0.0


def _crop(
    image: np.ndarray,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> np.ndarray:
    h, w = image.shape[:2]
    return image[
        max(0, int(y0 * h)) : min(h, int(y1 * h)),
        max(0, int(x0 * w)) : min(w, int(x1 * w)),
    ]


def task_geometry(
    frame_shape: tuple[int, ...],
) -> tuple[float, float, float, float, float, float]:
    """Return task-card bounds and center for common portrait aspect ratios."""
    h, w = frame_shape[:2]
    aspect = w / h
    center_x = max(0.76, min(0.85, 1.01 - 0.37 * aspect))
    center_y = max(0.57, min(0.63, 0.72 - 0.23 * aspect))
    x0 = max(0.62, center_x - 0.17)
    x1 = min(1.0, center_x + 0.17)
    y0 = center_y - 0.045
    y1 = center_y + 0.045
    return x0, y0, x1, y1, center_x, center_y


def _large_colored_buttons(
    hsv: np.ndarray,
    lower: tuple[int, int, int],
    upper: tuple[int, int, int],
) -> list[Box]:
    h, w = hsv.shape[:2]
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[Box] = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if (
            y > 0.62 * h
            and bw > 0.25 * w
            and bh > 0.035 * h
            and area > 0.009 * w * h
        ):
            boxes.append((x, y, bw, bh))
    return sorted(boxes, key=lambda box: box[2] * box[3], reverse=True)


def _center(box: Box) -> Point:
    x, y, w, h = box
    return x + w // 2, y + h // 2


def _food_prompt(
    hsv: np.ndarray,
    settings: VisionSettings,
) -> tuple[bool, float, Point | None]:
    """Detect the white food bubble beside the center Digimon.

    The food artwork varies, but the prompt consistently uses a bright white
    tile with a cyan outline in a narrow battle-area band. Local window ratios
    avoid depending on a specific food sprite.
    """
    h, w = hsv.shape[:2]
    white = cv2.inRange(hsv, (0, 0, 180), (179, 90, 255))
    cyan = cv2.inRange(hsv, (75, 80, 140), (110, 255, 255))
    brown_food = cv2.inRange(hsv, (0, 45, 25), (40, 255, 220))
    dark_food = cv2.inRange(hsv, (0, 0, 25), (179, 255, 100))
    food_core = cv2.bitwise_or(brown_food, dark_food)
    window_width = max(3, int(0.060 * w) | 1)
    window_height = max(3, int(0.035 * h) | 1)
    kernel = (window_width, window_height)
    white_ratio = cv2.boxFilter(
        white.astype(np.float32) / 255.0,
        -1,
        kernel,
        normalize=True,
    )
    cyan_ratio = cv2.boxFilter(
        cyan.astype(np.float32) / 255.0,
        -1,
        kernel,
        normalize=True,
    )
    # The core is intentionally much smaller than the tile.  Measuring it
    # separately keeps dark scenery outside a bright effect from counting as
    # a food sprite.
    core_width = max(3, int(0.025 * w) | 1)
    core_height = max(3, int(0.014 * h) | 1)
    dark_food_ratio = cv2.boxFilter(
        food_core.astype(np.float32) / 255.0,
        -1,
        (core_width, core_height),
        normalize=True,
    )
    score_map = white_ratio + 2.0 * cyan_ratio

    # The game keeps the prompt tied to the central Digimon, whose apparent
    # location moves slightly with emulator aspect ratio.  This covers both
    # the 9:16 LDPlayer layout and the taller BlueStacks layout.
    aspect = w / h
    expected_x = float(np.clip(0.27 + 0.43 * aspect, 0.46, 0.51))
    expected_y = float(np.clip(0.51 - 0.255 * aspect, 0.365, 0.395))
    x0, x1 = int((expected_x - 0.05) * w), int((expected_x + 0.05) * w)
    y0, y1 = int((expected_y - 0.017) * h), int((expected_y + 0.017) * h)
    valid_prompt = (
        (white_ratio >= settings.food_prompt_white_pixel_ratio)
        & (cyan_ratio >= settings.food_prompt_cyan_pixel_ratio)
        & (dark_food_ratio >= FOOD_PROMPT_DARK_CORE_RATIO)
    )
    search = score_map[y0:y1, x0:x1].copy()
    if search.size == 0:
        return False, 0.0, None
    search[~valid_prompt[y0:y1, x0:x1]] = -1.0
    _, score, _, location = cv2.minMaxLoc(search)
    if score < 0:
        return False, 0.0, None
    center = (x0 + location[0], y0 + location[1])
    return True, float(score), center


def _task_current_green(green_task: np.ndarray) -> bool:
    """Return whether the task's current-completion number is green.

    A complete task has a luminous green outline and a small green current
    count (``5/5`` or ``10/10``).  The target count itself is white, so a
    broad green-pixel ratio is insufficient.  We look for digit-sized green
    components only in the text portion of the card and exclude its outline
    and the lower reward icon.
    """
    height, width = green_task.shape[:2]
    x0, x1 = int(0.20 * width), int(0.86 * width)
    y0, y1 = int(0.08 * height), int(0.55 * height)
    text_green = green_task[y0:y1, x0:x1]
    if text_green.size == 0:
        return False

    component_count, _, stats, _ = cv2.connectedComponentsWithStats(
        text_green,
        cv2.CV_32S,
    )
    card_area = width * height
    min_area = max(4, int(0.0004 * card_area))
    max_area = max(min_area, int(0.025 * card_area))
    for index in range(1, component_count):
        _, _, component_width, component_height, area = stats[index]
        if (
            min_area <= area <= max_area
            and 0.01 * width <= component_width <= 0.18 * width
            and 0.02 * height <= component_height <= 0.28 * height
        ):
            return True
    return False


def _paired_buttons(
    pink_boxes: Iterable[Box],
    blue_boxes: Iterable[Box],
    frame_shape: tuple[int, ...],
) -> tuple[Box, Box] | None:
    h, _ = frame_shape[:2]
    for pink in pink_boxes:
        for blue in blue_boxes:
            pink_y = pink[1] + pink[3] / 2
            blue_y = blue[1] + blue[3] / 2
            if (
                pink[0] < blue[0]
                and abs(pink_y - blue_y) < 0.035 * h
                and 0.65 <= pink[2] / blue[2] <= 1.35
                and 0.65 <= pink[3] / blue[3] <= 1.35
            ):
                return pink, blue
    return None


class VisionAnalyzer:
    def __init__(self, settings: VisionSettings | None = None):
        self.settings = settings or VisionSettings()

    def analyze(self, frame: np.ndarray) -> VisualResult:
        if frame is None or frame.ndim != 3:
            raise ValueError("Expected a BGR color frame")
        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # The completed mission card changes its outline to luminous green.
        green = cv2.inRange(hsv, (35, 100, 100), (95, 255, 255))
        x0, y0, x1, y1, center_x, center_y = task_geometry(frame.shape)
        all_task = _crop(green, x0, y0, x1, y1)
        task_bands = [
            _crop(green, x0, y0 + 0.003, x1, y0 + 0.020),
            _crop(green, x0, y0 + 0.062, x1, y0 + 0.085),
            _crop(green, x1 - 0.035, y0 + 0.005, x1, y0 + 0.080),
        ]
        task_score = _fraction(all_task)
        band_score = max((_fraction(band) for band in task_bands), default=0.0)

        # In an unfinished mission the current count is red; after completion
        # that current count and the card outline turn green while the target
        # count remains white. A green reward icon previously leaked into the
        # broad task mask and could look like a completed frame.
        task_width = x1 - x0
        task_height = y1 - y0
        progress_roi = _crop(
            hsv,
            x0 + 0.20 * task_width,
            y0 + 0.08 * task_height,
            x0 + 0.86 * task_width,
            y0 + 0.55 * task_height,
        )
        progress_red_low = cv2.inRange(
            progress_roi, (0, 140, 140), (20, 255, 255)
        )
        progress_red_high = cv2.inRange(
            progress_roi, (170, 140, 140), (179, 255, 255)
        )
        progress_red = cv2.bitwise_or(
            progress_red_low,
            progress_red_high,
        )
        task_progress_red_ratio = _fraction(progress_red)
        task_incomplete = (
            task_progress_red_ratio
            >= self.settings.task_incomplete_red_pixel_ratio
        )
        task_current_green = _task_current_green(all_task)
        task_complete = (
            task_score >= self.settings.task_complete_min_score
            and band_score >= self.settings.task_complete_band_score
            and task_current_green
            and not task_incomplete
        )

        # Claiming a completed task opens a full-width translucent blue reward
        # layer. It is visually distinct from the narrower equipment modal.
        reward_roi = _crop(hsv, 0.0, 0.30, 1.0, 0.70)
        reward_blue = cv2.inRange(
            reward_roi,
            (95, 100, 50),
            (125, 255, 220),
        )
        reward_score = _fraction(reward_blue)
        row_coverage = np.mean(reward_blue > 0, axis=1)
        reward_row_score = (
            float(np.percentile(row_coverage, 75))
            if row_coverage.size
            else 0.0
        )
        reward_popup = reward_score >= 0.88 and reward_row_score >= 0.95
        if reward_popup:
            task_complete = False

        pink_boxes = _large_colored_buttons(
            hsv, (135, 80, 110), (179, 255, 255)
        )
        blue_boxes = _large_colored_buttons(
            hsv, (85, 100, 100), (115, 255, 255)
        )
        pair = _paired_buttons(pink_boxes, blue_boxes, frame.shape)

        equipment_state = EquipmentState.NONE
        sell_click: Point | None = None
        equip_click: Point | None = None
        green_ratio = 0.0
        red_ratio = 0.0
        if pair is not None:
            # The comparison card overlays the mission area with green stat
            # values. Suppress mission detection at the vision layer as well as
            # prioritizing equipment in the monitor state machine.
            task_complete = False
            sell_box, equip_box = pair
            sell_click = _center(sell_box)
            equip_click = _center(equip_box)

            # Arrow/status column. Red always wins because green stat numbers are
            # present in both better and worse equipment popups.
            status_roi = _crop(hsv, 0.72, 0.32, 0.89, 0.74)
            green_status = cv2.inRange(
                status_roi, (35, 120, 140), (90, 255, 255)
            )
            red_low = cv2.inRange(
                status_roi, (0, 150, 140), (20, 255, 255)
            )
            red_high = cv2.inRange(
                status_roi, (170, 150, 140), (179, 255, 255)
            )
            red_status = cv2.bitwise_or(red_low, red_high)
            green_ratio = _fraction(green_status)
            red_ratio = _fraction(red_status)
            if red_ratio >= self.settings.equipment_red_pixel_ratio:
                equipment_state = EquipmentState.WORSE
            elif green_ratio >= self.settings.equipment_green_pixel_ratio:
                equipment_state = EquipmentState.BETTER
            else:
                equipment_state = EquipmentState.UNKNOWN

        food_prompt = False
        food_score = 0.0
        food_click: Point | None = None
        if not reward_popup and pair is None:
            food_prompt, food_score, food_click = _food_prompt(
                hsv,
                self.settings,
            )

        return VisualResult(
            task_complete=task_complete,
            task_score=task_score,
            task_click=(int(center_x * w), int(center_y * h)),
            reward_popup=reward_popup,
            reward_score=reward_score,
            reward_close_click=(w // 2, int(0.82 * h)),
            equipment_state=equipment_state,
            sell_click=sell_click,
            equip_click=equip_click,
            green_equipment_ratio=green_ratio,
            red_equipment_ratio=red_ratio,
            task_incomplete=task_incomplete,
            task_progress_red_ratio=task_progress_red_ratio,
            task_current_green=task_current_green,
            food_prompt=food_prompt,
            food_score=food_score,
            food_click=food_click,
        )


def normalize_ocr_text(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).lower()


def task_progress_complete(text: str) -> bool | None:
    """Return OCR progress state, or None when no reliable fraction exists."""
    matches = re.findall(
        r"(?<!\d)(\d{1,4})\s*[/／\\|]+\s*(\d{1,4})(?!\d)",
        text,
    )
    progress = [
        (int(current), int(target))
        for current, target in matches
        if int(target) > 0
    ]
    if not progress:
        return None
    return all(current >= target for current, target in progress)


def classify_special_task(text: str) -> str | None:
    normalized = normalize_ocr_text(text)
    support_type = any(
        term in normalized
        for term in (
            "支援型",
            "支持型",
            "支援形",
            "supporttype",
            "supportdigimon",
            "サポート型",
            "支援タイプ",
        )
    )
    digimon_or_gacha = any(
        term in normalized
        for term in (
            "數碼",
            "数码",
            "寶貝",
            "宝贝",
            "轉蛋",
            "转蛋",
            "digimon",
            "gacha",
            "summon",
            "draw",
            "デジモン",
            "ガチャ",
            "ガシャ",
            "召喚",
        )
    )
    if support_type and digimon_or_gacha:
        return "support_digimon"

    has_skill = any(
        term in normalized for term in ("技能", "技熊", "skill", "スキル")
    )
    has_card = any(
        term in normalized
        for term in ("卡片", "卡牌", "技能卡", "咭", "card", "カード")
    )
    if has_skill and has_card:
        return "skill_card"
    return None


def is_ticket_insufficient(text: str) -> bool:
    normalized = normalize_ocr_text(text)
    insufficient = any(
        term in normalized
        for term in (
            "不足",
            "不夠",
            "不够",
            "缺少",
            "notenough",
            "insufficient",
            "shortage",
            "足りない",
        )
    )
    projection = any(
        term in normalized
        for term in (
            "全像",
            "全息",
            "投影",
            "hologram",
            "holographic",
            "projection",
            "ホログラム",
        )
    )
    ticket = any(
        term in normalized for term in ("券", "票", "ticket", "チケット")
    )
    return insufficient and projection and (
        ticket or "投影" in normalized or "projection" in normalized
    )
