from __future__ import annotations

import argparse
from pathlib import Path
import sys

import cv2

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from digimon_monitor.config import load_config  # noqa: E402
from digimon_monitor.ocr import OcrEngine  # noqa: E402
from digimon_monitor.vision import (  # noqa: E402
    EquipmentState,
    VisionAnalyzer,
    classify_special_task,
)


EXPECTED = {
    "1aab184ba839fd8c6004fa4a0214c662.jpg": {
        "task": True,
        "equipment": EquipmentState.NONE,
    },
    "129c4d80a2c5c5c4cdfc073023aef582.jpg": {
        "task": True,
        "equipment": EquipmentState.NONE,
    },
    "ef78fe702599e67a49ea217fb90eb2e8.jpg": {
        "task": False,
        "equipment": EquipmentState.NONE,
        "special": "抽取支援型數碼寶貝",
    },
    "9d669f48509fe6503ce363393363a6c7.jpg": {
        "task": False,
        "equipment": EquipmentState.BETTER,
    },
    "e2aea18349b059445ae0c2668ec9dfee.jpg": {
        "task": False,
        "equipment": EquipmentState.WORSE,
    },
    "1cf7bba8ccd1958e2d8ec547601f6414.jpg": {
        "task": False,
        "equipment": EquipmentState.BETTER,
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Digimon monitor vision against the six reference images."
    )
    parser.add_argument("sample_dir", type=Path)
    args = parser.parse_args()

    config = load_config(PROJECT_DIR)
    analyzer = VisionAnalyzer(config.vision)
    ocr = OcrEngine(config.ocr)
    failures: list[str] = []

    for filename, expected in EXPECTED.items():
        path = args.sample_dir / filename
        frame = cv2.imread(str(path))
        if frame is None:
            failures.append(f"{filename}: file not readable")
            continue
        result = analyzer.analyze(frame)
        actual_special = None
        task_text = ""
        if "special" in expected:
            task_text = ocr.read_task(frame)
            actual_special = classify_special_task(task_text)
        print(
            f"{filename[:8]} "
            f"task={result.task_complete} score={result.task_score:.4f} "
            f"equipment={result.equipment_state.value} "
            f"green={result.green_equipment_ratio:.4f} "
            f"red={result.red_equipment_ratio:.4f} "
            f"special={actual_special or '-'}"
        )
        if result.task_complete != expected["task"]:
            failures.append(
                f"{filename}: task {result.task_complete} != {expected['task']}"
            )
        if result.equipment_state is not expected["equipment"]:
            failures.append(
                f"{filename}: equipment {result.equipment_state} "
                f"!= {expected['equipment']}"
            )
        if actual_special != expected.get("special"):
            failures.append(
                f"{filename}: special {actual_special!r} "
                f"!= {expected.get('special')!r}; OCR={task_text!r}"
            )

    if failures:
        print("\nFAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("\nPASS: all six reference images matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
