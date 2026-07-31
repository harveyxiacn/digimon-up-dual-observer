from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import threading
import time

import cv2
import numpy as np

from .adb import AdbClient, AdbDevice
from .config import AppConfig
from .discord_notifier import DiscordNotifier
from .i18n import Translator
from .ocr import OcrEngine
from .vision import (
    EquipmentState,
    VisionAnalyzer,
    classify_special_task,
    is_ticket_insufficient,
    task_progress_complete,
)


LogCallback = Callable[[str, str], None]
FrameCallback = Callable[[str, np.ndarray], None]
StatusCallback = Callable[[str, str], None]


def build_logger(project_dir: Path) -> logging.Logger:
    logs_dir = project_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("digimon_monitor")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            logs_dir / "monitor.log",
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


class StableState:
    def __init__(self) -> None:
        self.value: str | None = None
        self.count = 0

    def update(self, value: str | None) -> int:
        if value is None:
            self.value = None
            self.count = 0
        elif value == self.value:
            self.count += 1
        else:
            self.value = value
            self.count = 1
        return self.count

    def reset(self) -> None:
        self.value = None
        self.count = 0


class Cooldowns:
    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def ready(self, key: str, seconds: float, now: float) -> bool:
        previous = self._last.get(key, 0.0)
        return now - previous >= seconds

    def mark(self, key: str, now: float) -> None:
        self._last[key] = now


class ReappearingPromptLatch:
    """Fire once per prompt appearance and re-arm after stable absence."""

    def __init__(self, stable_frames: int) -> None:
        self.stable_frames = max(1, stable_frames)
        self.present_frames = 0
        self.absent_frames = 0
        self.armed = True

    def update(self, present: bool) -> bool:
        if present:
            self.absent_frames = 0
            if not self.armed:
                return False
            self.present_frames += 1
            return self.present_frames >= self.stable_frames

        self.present_frames = 0
        if not self.armed:
            self.absent_frames += 1
            if self.absent_frames >= self.stable_frames:
                self.armed = True
                self.absent_frames = 0
        return False

    def mark_handled(self) -> None:
        self.armed = False
        self.present_frames = 0
        self.absent_frames = 0


class DeviceMonitor(threading.Thread):
    def __init__(
        self,
        device: AdbDevice,
        config: AppConfig,
        adb: AdbClient,
        notifier: DiscordNotifier,
        automation_enabled: Callable[[], bool],
        stop_event: threading.Event,
        logger: logging.Logger,
        log_callback: LogCallback,
        frame_callback: FrameCallback,
        status_callback: StatusCallback,
        translator: Translator,
    ):
        super().__init__(
            name=f"monitor-{device.serial}",
            daemon=True,
        )
        self.device = device
        self.config = config
        self.adb = adb
        self.notifier = notifier
        self.automation_enabled = automation_enabled
        self.stop_event = stop_event
        self.logger = logger
        self.emit_log = log_callback
        self.emit_frame = frame_callback
        self.emit_status = status_callback
        self.tr = translator
        self.vision = VisionAnalyzer(config.vision)
        self.ocr = OcrEngine(config.ocr)
        self.stable = StableState()
        self.food_prompt_latch = ReappearingPromptLatch(
            config.monitor.stable_frames_before_click
        )
        self.cooldowns = Cooldowns()
        self.next_task_ocr = 0.0
        self.next_dialog_ocr = 0.0
        self.next_action_at = 0.0
        self.last_task_text = ""
        self.last_observation = ""
        self.failure_count = 0

    @property
    def label(self) -> str:
        alias = self.config.adb.device_aliases.get(self.device.serial, "")
        model = self.device.model.replace("_", " ")
        return alias or model or self.device.serial

    def _log(self, level: str, message: str) -> None:
        full = f"[{self.label}] {message}"
        getattr(self.logger, level.lower(), self.logger.info)(full)
        self.emit_log(level, full)

    def _save_frame(self, frame: np.ndarray, event_name: str) -> Path | None:
        if not self.config.monitor.save_action_screenshots:
            return None
        safe_serial = re.sub(r"[^a-zA-Z0-9._-]+", "_", self.device.serial)
        folder = self.config.project_dir / "captures" / safe_serial
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = folder / f"{stamp}_{event_name}.jpg"
        return path if cv2.imwrite(str(path), frame) else None

    def _notify(
        self,
        key: str,
        cooldown_seconds: float,
        message: str,
        frame: np.ndarray,
        now: float,
    ) -> None:
        if not self.cooldowns.ready(key, cooldown_seconds, now):
            return
        try:
            self.notifier.send(message, frame)
            self.cooldowns.mark(key, now)
            self._save_frame(frame, key.replace(":", "_"))
            self._log("info", self.tr("log.discord_sent", message=message))
        except Exception as exc:
            self._log("error", str(exc))

    def _tap(
        self,
        frame: np.ndarray,
        point: tuple[int, int],
        action_name: str,
        event_name: str,
        now: float,
    ) -> bool:
        if now < self.next_action_at:
            return False
        if not self.automation_enabled():
            observation = f"{event_name}:{point}"
            if observation != self.last_observation:
                self.last_observation = observation
                self._log(
                    "info",
                    self.tr(
                        "log.observe_action",
                        action=action_name,
                        point=point,
                    ),
                )
            return False
        self.adb.tap(self.device.serial, point[0], point[1])
        self._save_frame(frame, event_name)
        self.next_action_at = now + self.config.monitor.action_cooldown_seconds
        self.last_observation = ""
        self.stable.reset()
        self._log(
            "info",
            self.tr(
                "log.action_done",
                action=action_name,
                point=point,
            ),
        )
        return True

    def _handle_frame(self, frame: np.ndarray, now: float) -> None:
        result = self.vision.analyze(frame)
        if result.reward_popup:
            stable_count = self.stable.update("reward:close")
            if stable_count >= self.config.monitor.stable_frames_before_click:
                self._tap(
                    frame,
                    result.reward_close_click,
                    self.tr("action.close_reward"),
                    "reward_close",
                    now,
                )
            return

        equipment = result.equipment_state
        if equipment is not EquipmentState.NONE:
            stable_count = self.stable.update(f"equipment:{equipment.value}")
            if equipment is EquipmentState.UNKNOWN:
                if stable_count == 1:
                    self._log(
                        "warning",
                        self.tr("log.equipment_unknown"),
                    )
                return
            if stable_count < self.config.monitor.stable_frames_before_click:
                return
            if equipment is EquipmentState.WORSE and result.sell_click:
                self._tap(
                    frame,
                    result.sell_click,
                    self.tr("action.sell"),
                    "sell_worse",
                    now,
                )
            elif equipment is EquipmentState.BETTER and result.equip_click:
                self._tap(
                    frame,
                    result.equip_click,
                    self.tr("action.equip"),
                    "equip_better",
                    now,
                )
            return

        food_prompt_ready = self.food_prompt_latch.update(
            result.food_prompt
        )
        if food_prompt_ready and result.food_click:
            handled = self._tap(
                frame,
                result.food_click,
                self.tr("action.food_prompt"),
                "food_prompt",
                now,
            )
            if handled:
                self.food_prompt_latch.mark_handled()
            return

        task_text = self.last_task_text
        force_task_ocr = result.task_complete
        if force_task_ocr or now >= self.next_task_ocr:
            try:
                task_text = self.ocr.read_task(frame)
                self.last_task_text = task_text
                self.next_task_ocr = now + self.config.monitor.ocr_interval_seconds
            except Exception as exc:
                task_text = ""
                self._log(
                    "warning",
                    self.tr("log.task_ocr_failed", error=exc),
                )

        special_task_key = classify_special_task(task_text)
        if special_task_key:
            special_task = self.tr(f"special.{special_task_key}")
            self._notify(
                f"special:{special_task_key}",
                self.config.notifications.special_task_cooldown_seconds,
                self.tr(
                    "notify.special",
                    label=self.label,
                    special=special_task,
                    ocr=task_text or self.tr("notify.ocr_empty"),
                ),
                frame,
                now,
            )

        if now >= self.next_dialog_ocr:
            try:
                dialog_text = self.ocr.read_dialog(frame)
                self.next_dialog_ocr = (
                    now + self.config.monitor.dialog_ocr_interval_seconds
                )
                if is_ticket_insufficient(dialog_text):
                    self._notify(
                        "ticket:insufficient",
                        self.config.notifications.ticket_cooldown_seconds,
                        self.tr("notify.ticket", label=self.label),
                        frame,
                        now,
                    )
            except Exception as exc:
                self._log(
                    "warning",
                    self.tr("log.dialog_ocr_failed", error=exc),
                )

        if result.task_incomplete:
            stable_count = self.stable.update("task:incomplete")
            if stable_count == self.config.monitor.stable_frames_before_click:
                self._log(
                    "info",
                    self.tr("log.task_incomplete"),
                )
            return

        if result.task_complete:
            stable_count = self.stable.update("task:complete")
            if special_task_key:
                return
            if not task_text.strip():
                if stable_count == self.config.monitor.stable_frames_before_click:
                    self._log(
                        "warning",
                        self.tr("log.task_no_ocr"),
                    )
                return
            if task_progress_complete(task_text) is False:
                if (
                    stable_count
                    == self.config.monitor.stable_frames_before_click
                ):
                    self._log(
                        "info",
                        self.tr("log.task_incomplete"),
                    )
                return
            if stable_count >= self.config.monitor.stable_frames_before_click:
                self._tap(
                    frame,
                    result.task_click,
                    self.tr("action.claim_task"),
                    "task_complete",
                    now,
                )
        else:
            self.stable.update(None)

    def run(self) -> None:
        self.emit_status(self.device.serial, "LINKING")
        self._log("info", self.tr("log.thread_started"))
        if self.ocr.missing_languages:
            self._log(
                "warning",
                self.tr(
                    "log.ocr_languages",
                    active="+".join(self.ocr.active_languages),
                    missing="+".join(self.ocr.missing_languages),
                ),
            )
        while not self.stop_event.is_set():
            cycle_start = time.monotonic()
            try:
                frame = self.adb.screenshot(self.device.serial)
                self.failure_count = 0
                self.emit_status(self.device.serial, "ONLINE")
                self.emit_frame(self.device.serial, frame)
                self._handle_frame(frame, cycle_start)
            except Exception as exc:
                self.failure_count += 1
                if self.failure_count == 1 or self.failure_count % 10 == 0:
                    self._log(
                        "error",
                        self.tr(
                            "log.monitor_failed",
                            count=self.failure_count,
                            error=exc,
                        ),
                    )
                self.emit_status(self.device.serial, "RETRYING")

            elapsed = time.monotonic() - cycle_start
            wait_seconds = max(
                0.1,
                self.config.monitor.poll_interval_seconds - elapsed,
            )
            self.stop_event.wait(wait_seconds)
        self.emit_status(self.device.serial, "OFFLINE")
        self._log("info", self.tr("log.thread_stopped"))


class MonitorController:
    def __init__(
        self,
        config: AppConfig,
        adb: AdbClient,
        notifier: DiscordNotifier,
        log_callback: LogCallback,
        frame_callback: FrameCallback,
        status_callback: StatusCallback,
        translator: Translator | None = None,
    ):
        self.config = config
        self.adb = adb
        self.notifier = notifier
        self.log_callback = log_callback
        self.frame_callback = frame_callback
        self.status_callback = status_callback
        self.tr = translator or Translator(config.ui.language)
        self.logger = build_logger(config.project_dir)
        self._automation_enabled = config.monitor.automation_enabled
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._workers: list[DeviceMonitor] = []

    @property
    def running(self) -> bool:
        return any(worker.is_alive() for worker in self._workers)

    def automation_enabled(self) -> bool:
        with self._state_lock:
            return self._automation_enabled

    def set_automation_enabled(self, enabled: bool) -> None:
        with self._state_lock:
            self._automation_enabled = enabled
        mode = self.tr(
            "mode.automation" if enabled else "mode.observation"
        )
        self.log_callback(
            "info",
            self.tr("log.automation_mode", mode=mode),
        )

    def start(self, devices: list[AdbDevice]) -> None:
        if self.running:
            return
        self._stop_event = threading.Event()
        self._workers = [
            DeviceMonitor(
                device=device,
                config=self.config,
                adb=self.adb,
                notifier=self.notifier,
                automation_enabled=self.automation_enabled,
                stop_event=self._stop_event,
                logger=self.logger,
                log_callback=self.log_callback,
                frame_callback=self.frame_callback,
                status_callback=self.status_callback,
                translator=self.tr,
            )
            for device in devices
        ]
        for worker in self._workers:
            worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        for worker in self._workers:
            worker.join(timeout=3.0)
        self._workers = []
