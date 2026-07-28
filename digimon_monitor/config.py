from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Any

import yaml


PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class MonitorSettings:
    poll_interval_seconds: float = 2.0
    ocr_interval_seconds: float = 6.0
    dialog_ocr_interval_seconds: float = 8.0
    stable_frames_before_click: int = 2
    action_cooldown_seconds: float = 2.5
    automation_enabled: bool = True
    save_action_screenshots: bool = True


@dataclass(slots=True)
class NotificationSettings:
    special_task_cooldown_seconds: float = 21600
    ticket_cooldown_seconds: float = 900


@dataclass(slots=True)
class OcrSettings:
    language: str = "chi_tra+eng"
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


@dataclass(slots=True)
class AdbSettings:
    executable: str = "adb"
    command_timeout_seconds: float = 12
    connect_addresses: list[str] = field(default_factory=list)
    device_aliases: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class VisionSettings:
    task_complete_min_score: float = 0.035
    task_complete_band_score: float = 0.08
    equipment_red_pixel_ratio: float = 0.00020
    equipment_green_pixel_ratio: float = 0.00045


@dataclass(slots=True)
class AppConfig:
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    ocr: OcrSettings = field(default_factory=OcrSettings)
    adb: AdbSettings = field(default_factory=AdbSettings)
    vision: VisionSettings = field(default_factory=VisionSettings)
    webhook_url: str = ""
    project_dir: Path = PROJECT_DIR


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    return value if isinstance(value, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(project_dir: Path = PROJECT_DIR) -> AppConfig:
    data: dict[str, Any] = {}
    for filename in ("config.yaml", "config.local.yaml"):
        path = project_dir / filename
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = _deep_merge(data, loaded)

    dotenv = _read_dotenv(project_dir / ".env")
    webhook = os.environ.get(
        "DIGIMON_DISCORD_WEBHOOK_URL",
        dotenv.get("DIGIMON_DISCORD_WEBHOOK_URL", ""),
    )
    return AppConfig(
        monitor=MonitorSettings(**_section(data, "monitor")),
        notifications=NotificationSettings(**_section(data, "notifications")),
        ocr=OcrSettings(**_section(data, "ocr")),
        adb=AdbSettings(**_section(data, "adb")),
        vision=VisionSettings(**_section(data, "vision")),
        webhook_url=webhook,
        project_dir=project_dir,
    )


def save_webhook(project_dir: Path, webhook_url: str) -> None:
    path = project_dir / ".env"
    path.write_text(
        f"DIGIMON_DISCORD_WEBHOOK_URL={webhook_url.strip()}\n",
        encoding="utf-8",
    )
