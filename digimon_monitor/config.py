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


@dataclass(frozen=True, slots=True)
class FeatureSettings:
    """Runtime-selectable monitoring capabilities.

    This is deliberately immutable: monitors receive a complete snapshot for a
    frame instead of observing a partially changed collection of flags.
    """

    task_monitoring_enabled: bool = True
    equipment_automation_enabled: bool = True
    food_prompt_automation_enabled: bool = True
    discord_notifications_enabled: bool = True


@dataclass(slots=True)
class NotificationSettings:
    special_task_cooldown_seconds: float = 21600
    ticket_cooldown_seconds: float = 900


@dataclass(slots=True)
class OcrSettings:
    language: str = "chi_tra+chi_sim+jpn+eng"
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
    task_incomplete_red_pixel_ratio: float = 0.004
    food_prompt_white_pixel_ratio: float = 0.28
    food_prompt_cyan_pixel_ratio: float = 0.06
    equipment_red_pixel_ratio: float = 0.00020
    equipment_green_pixel_ratio: float = 0.00045


@dataclass(slots=True)
class UiSettings:
    language: str = "zh_CN"


@dataclass(slots=True)
class AppConfig:
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    features: FeatureSettings = field(default_factory=FeatureSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    ocr: OcrSettings = field(default_factory=OcrSettings)
    adb: AdbSettings = field(default_factory=AdbSettings)
    vision: VisionSettings = field(default_factory=VisionSettings)
    ui: UiSettings = field(default_factory=UiSettings)
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


def _strict_bool(value: str | None, default: bool) -> bool:
    """Apply only explicit true/false environment values.

    Ignoring malformed values avoids a typo unexpectedly disabling automation.
    """
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return default


def _env_value(dotenv: dict[str, str], key: str) -> str | None:
    return os.environ[key] if key in os.environ else dotenv.get(key)


def load_config(project_dir: Path = PROJECT_DIR) -> AppConfig:
    data: dict[str, Any] = {}
    for filename in ("config.yaml", "config.local.yaml"):
        path = project_dir / filename
        if path.exists():
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = _deep_merge(data, loaded)

    dotenv = _read_dotenv(project_dir / ".env")
    webhook = _env_value(dotenv, "DIGIMON_DISCORD_WEBHOOK_URL") or ""
    ui = UiSettings(**_section(data, "ui"))
    ui.language = _env_value(dotenv, "DIGIMON_UI_LANGUAGE") or ui.language
    monitor = MonitorSettings(**_section(data, "monitor"))
    monitor.automation_enabled = _strict_bool(
        _env_value(dotenv, "DIGIMON_AUTOMATION_ENABLED"),
        monitor.automation_enabled,
    )
    features = FeatureSettings(**_section(data, "features"))
    feature_env_names = {
        "task_monitoring_enabled": "DIGIMON_TASK_MONITORING_ENABLED",
        "equipment_automation_enabled": "DIGIMON_EQUIPMENT_AUTOMATION_ENABLED",
        "food_prompt_automation_enabled": "DIGIMON_FOOD_PROMPT_AUTOMATION_ENABLED",
        "discord_notifications_enabled": "DIGIMON_DISCORD_NOTIFICATIONS_ENABLED",
    }
    feature_values = {
        field_name: _strict_bool(_env_value(dotenv, env_name), getattr(features, field_name))
        for field_name, env_name in feature_env_names.items()
    }
    return AppConfig(
        monitor=monitor,
        features=FeatureSettings(**feature_values),
        notifications=NotificationSettings(**_section(data, "notifications")),
        ocr=OcrSettings(**_section(data, "ocr")),
        adb=AdbSettings(**_section(data, "adb")),
        vision=VisionSettings(**_section(data, "vision")),
        ui=ui,
        webhook_url=webhook,
        project_dir=project_dir,
    )


def _save_dotenv_values(project_dir: Path, values: dict[str, str]) -> None:
    """Atomically replace selected .env keys without disturbing unrelated keys."""
    path = project_dir / ".env"
    lines = (
        path.read_text(encoding="utf-8").splitlines()
        if path.exists()
        else []
    )
    replacements = {key: f"{key}={value.strip()}" for key, value in values.items()}
    replaced = set[str]()
    updated: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in replacements:
            if key not in replaced:
                updated.append(replacements[key])
                replaced.add(key)
        else:
            updated.append(line)
    for key, replacement in replacements.items():
        if key not in replaced:
            updated.append(replacement)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    temporary.replace(path)


def _save_dotenv_value(project_dir: Path, key: str, value: str) -> None:
    _save_dotenv_values(project_dir, {key: value})


def save_webhook(project_dir: Path, webhook_url: str) -> None:
    _save_dotenv_value(
        project_dir,
        "DIGIMON_DISCORD_WEBHOOK_URL",
        webhook_url,
    )


def save_ui_language(project_dir: Path, language: str) -> None:
    _save_dotenv_value(project_dir, "DIGIMON_UI_LANGUAGE", language)


def save_monitor_preferences(
    project_dir: Path,
    monitor: MonitorSettings,
    features: FeatureSettings,
) -> None:
    """Persist all runtime switches together, so they cannot be half-saved."""
    _save_dotenv_values(
        project_dir,
        {
            "DIGIMON_AUTOMATION_ENABLED": str(monitor.automation_enabled).lower(),
            "DIGIMON_TASK_MONITORING_ENABLED": str(features.task_monitoring_enabled).lower(),
            "DIGIMON_EQUIPMENT_AUTOMATION_ENABLED": str(features.equipment_automation_enabled).lower(),
            "DIGIMON_FOOD_PROMPT_AUTOMATION_ENABLED": str(features.food_prompt_automation_enabled).lower(),
            "DIGIMON_DISCORD_NOTIFICATIONS_ENABLED": str(features.discord_notifications_enabled).lower(),
        },
    )
