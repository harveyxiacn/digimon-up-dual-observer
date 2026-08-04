from dataclasses import replace

from digimon_monitor.config import (
    FeatureSettings,
    load_config,
    save_monitor_preferences,
    save_ui_language,
    save_webhook,
)


def test_feature_defaults_and_strict_environment_overrides(
    tmp_path, monkeypatch
) -> None:
    (tmp_path / "config.yaml").write_text(
        "features:\n  task_monitoring_enabled: false\n", encoding="utf-8"
    )
    (tmp_path / ".env").write_text(
        "DIGIMON_EQUIPMENT_AUTOMATION_ENABLED=false\n"
        "DIGIMON_FOOD_PROMPT_AUTOMATION_ENABLED=not-a-bool\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DIGIMON_TASK_MONITORING_ENABLED", "true")
    monkeypatch.setenv("DIGIMON_DISCORD_NOTIFICATIONS_ENABLED", "false")
    monkeypatch.setenv("DIGIMON_AUTOMATION_ENABLED", "false")

    config = load_config(tmp_path)

    assert config.monitor.automation_enabled is False
    assert config.features == FeatureSettings(
        task_monitoring_enabled=True,
        equipment_automation_enabled=False,
        food_prompt_automation_enabled=True,
        discord_notifications_enabled=False,
    )


def test_saves_preserve_unknown_dotenv_values_and_clear_webhook(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        "UNRELATED=value\nDIGIMON_DISCORD_WEBHOOK_URL=old\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    config.monitor.automation_enabled = False
    features = replace(
        config.features,
        task_monitoring_enabled=False,
        discord_notifications_enabled=False,
    )

    save_monitor_preferences(tmp_path, config.monitor, features)
    save_ui_language(tmp_path, "ja")
    save_webhook(tmp_path, "")

    values = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "UNRELATED=value" in values
    assert "DIGIMON_DISCORD_WEBHOOK_URL=" in values
    assert "DIGIMON_AUTOMATION_ENABLED=false" in values
    restored = load_config(tmp_path)
    assert restored.monitor.automation_enabled is False
    assert restored.features == features
    assert restored.ui.language == "ja"
    assert restored.webhook_url == ""
