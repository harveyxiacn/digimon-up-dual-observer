from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytesseract

from .config import OcrSettings
from .vision import task_geometry


class OcrEngine:
    def __init__(self, settings: OcrSettings | None = None):
        self.settings = settings or OcrSettings()
        command = Path(self.settings.tesseract_cmd)
        if command.exists():
            pytesseract.pytesseract.tesseract_cmd = str(command)
        requested = tuple(
            language.strip()
            for language in self.settings.language.split("+")
            if language.strip()
        )
        try:
            installed = set(pytesseract.get_languages(config=""))
        except Exception:
            installed = set(requested)
        active = tuple(language for language in requested if language in installed)
        if not active and "eng" in installed:
            active = ("eng",)
        self.active_languages = active or requested or ("eng",)
        self.missing_languages = tuple(
            language for language in requested if language not in installed
        )
        self.language = "+".join(self.active_languages)

    @staticmethod
    def _crop(
        frame: np.ndarray,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        return frame[
            int(y0 * h) : int(y1 * h),
            int(x0 * w) : int(x1 * w),
        ]

    @staticmethod
    def _upscale(image: np.ndarray, factor: float = 2.5) -> np.ndarray:
        return cv2.resize(
            image,
            None,
            fx=factor,
            fy=factor,
            interpolation=cv2.INTER_CUBIC,
        )

    def read_task(self, frame: np.ndarray) -> str:
        x0, y0, x1, y1, _, _ = task_geometry(frame.shape)
        roi = self._crop(
            frame,
            max(0.0, x0 - 0.03),
            max(0.0, y0 - 0.02),
            min(1.0, x1 + 0.02),
            min(1.0, y1 + 0.015),
        )
        roi = self._upscale(roi, 3.0)
        original_text = pytesseract.image_to_string(
            roi,
            lang=self.language,
            config="--psm 6",
        ).strip()
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )[1]
        binary_text = pytesseract.image_to_string(
            binary,
            lang=self.language,
            config="--psm 6",
        ).strip()
        return "\n".join(text for text in (original_text, binary_text) if text)

    def read_dialog(self, frame: np.ndarray) -> str:
        roi = self._crop(frame, 0.08, 0.20, 0.92, 0.82)
        roi = self._upscale(roi, 1.7)
        return pytesseract.image_to_string(
            roi,
            lang=self.language,
            config="--psm 11",
        ).strip()

    def read_equipment_attributes(self, frame: np.ndarray) -> tuple[str, str]:
        """Read the current (upper) and new (lower) item panels separately."""
        panels = (
            self._crop(frame, 0.16, 0.285, 0.84, 0.535),
            self._crop(frame, 0.16, 0.55, 0.84, 0.80),
        )
        return tuple(
            pytesseract.image_to_string(
                self._upscale(panel, 2.2),
                lang=self.language,
                config="--psm 6",
            ).strip()
            for panel in panels
        )
