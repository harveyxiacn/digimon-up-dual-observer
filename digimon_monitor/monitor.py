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
from .ocr import OcrEngine
from .vision import (
    EquipmentState,
    VisionAnalyzer,
    classify_special_task,
    is_ticket_insufficient,
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
        self.vision = VisionAnalyzer(config.vision)
        self.ocr = OcrEngine(config.ocr)
        self.stable = StableState()
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
            self._log("info", f"Discord 通知已发送：{message}")
        except Exception as exc:
            self._log("error", str(exc))

    def _tap(
        self,
        frame: np.ndarray,
        point: tuple[int, int],
        action_name: str,
        event_name: str,
        now: float,
    ) -> None:
        if now < self.next_action_at:
            return
        if not self.automation_enabled():
            observation = f"{event_name}:{point}"
            if observation != self.last_observation:
                self.last_observation = observation
                self._log(
                    "info",
                    f"观察模式：识别到“{action_name}”，未执行点击 {point}",
                )
            return
        self.adb.tap(self.device.serial, point[0], point[1])
        self._save_frame(frame, event_name)
        self.next_action_at = now + self.config.monitor.action_cooldown_seconds
        self.last_observation = ""
        self.stable.reset()
        self._log("info", f"已{action_name}，坐标 {point}")

    def _handle_frame(self, frame: np.ndarray, now: float) -> None:
        result = self.vision.analyze(frame)
        if result.reward_popup:
            stable_count = self.stable.update("reward:close")
            if stable_count >= self.config.monitor.stable_frames_before_click:
                self._tap(
                    frame,
                    result.reward_close_click,
                    "关闭任务奖励画面",
                    "reward_close",
                    now,
                )
            return

        equipment = result.equipment_state
        if equipment is not EquipmentState.NONE:
            stable_count = self.stable.update(f"equipment:{equipment.value}")
            if equipment is EquipmentState.UNKNOWN:
                if stable_count == 1:
                    self._log("warning", "检测到装备弹窗，但箭头方向不明确；保持不动")
                return
            if stable_count < self.config.monitor.stable_frames_before_click:
                return
            if equipment is EquipmentState.WORSE and result.sell_click:
                self._tap(frame, result.sell_click, "点击出售", "sell_worse", now)
            elif equipment is EquipmentState.BETTER and result.equip_click:
                self._tap(frame, result.equip_click, "点击装备", "equip_better", now)
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
                self._log("warning", f"任务 OCR 失败：{exc}")

        special_task = classify_special_task(task_text)
        if special_task:
            self._notify(
                f"special:{special_task}",
                self.config.notifications.special_task_cooldown_seconds,
                f"⚠️ 【{self.label}】发现特殊任务：{special_task}\n"
                f"OCR：{task_text or '未读出文字'}\n"
                "已阻止自动点击，请手动处理。",
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
                        f"🎫 【{self.label}】全像/全息投影券不足，请补充后再继续。",
                        frame,
                        now,
                    )
            except Exception as exc:
                self._log("warning", f"弹窗 OCR 失败：{exc}")

        if result.task_complete:
            stable_count = self.stable.update("task:complete")
            if special_task:
                return
            if not task_text.strip():
                if stable_count == self.config.monitor.stable_frames_before_click:
                    self._log("warning", "任务框已完成但 OCR 无结果；为防误点保持不动")
                return
            if stable_count >= self.config.monitor.stable_frames_before_click:
                self._tap(
                    frame,
                    result.task_click,
                    "领取已完成任务",
                    "task_complete",
                    now,
                )
        else:
            self.stable.update(None)

    def run(self) -> None:
        self.emit_status(self.device.serial, "LINKING")
        self._log("info", "监控线程已启动")
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
                    self._log("error", f"监控失败（{self.failure_count}）：{exc}")
                self.emit_status(self.device.serial, "RETRYING")

            elapsed = time.monotonic() - cycle_start
            wait_seconds = max(
                0.1,
                self.config.monitor.poll_interval_seconds - elapsed,
            )
            self.stop_event.wait(wait_seconds)
        self.emit_status(self.device.serial, "OFFLINE")
        self._log("info", "监控线程已停止")


class MonitorController:
    def __init__(
        self,
        config: AppConfig,
        adb: AdbClient,
        notifier: DiscordNotifier,
        log_callback: LogCallback,
        frame_callback: FrameCallback,
        status_callback: StatusCallback,
    ):
        self.config = config
        self.adb = adb
        self.notifier = notifier
        self.log_callback = log_callback
        self.frame_callback = frame_callback
        self.status_callback = status_callback
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
        mode = "自动点击" if enabled else "观察模式"
        self.log_callback("info", f"[SYSTEM] 已切换为 {mode}")

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
