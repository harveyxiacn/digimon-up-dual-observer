from __future__ import annotations

from string import Formatter

from digimon_monitor.config import (
    load_config,
    save_ui_language,
    save_webhook,
)
from digimon_monitor.i18n import (
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
    Translator,
    normalize_language,
)


def test_all_languages_have_the_same_translation_keys() -> None:
    expected = set(TRANSLATIONS["en"])
    assert set(TRANSLATIONS) == SUPPORTED_LANGUAGES
    for language, translations in TRANSLATIONS.items():
        assert set(translations) == expected, language


def test_all_languages_preserve_format_placeholders() -> None:
    formatter = Formatter()
    for key, english in TRANSLATIONS["en"].items():
        expected = {
            field_name
            for _, field_name, _, _ in formatter.parse(english)
            if field_name
        }
        for language, translations in TRANSLATIONS.items():
            actual = {
                field_name
                for _, field_name, _, _ in formatter.parse(translations[key])
                if field_name
            }
            assert actual == expected, (language, key)


def test_translator_formats_each_language() -> None:
    expected = {
        "zh_CN": "ADB 发现 2 个设备",
        "zh_TW": "ADB 發現 2 個裝置",
        "en": "ADB found 2 device(s)",
        "ja": "ADBで2台のデバイスを検出",
    }
    for language, phrase in expected.items():
        message = Translator(language)("log.adb_found", count=2)
        assert phrase in message


def test_language_aliases_and_unknown_fallback() -> None:
    assert normalize_language("zh-Hans") == "zh_CN"
    assert normalize_language("zh-Hant") == "zh_TW"
    assert normalize_language("ja-JP") == "ja"
    assert normalize_language("unknown") == "zh_CN"


def test_dotenv_saves_language_and_webhook_without_overwriting(tmp_path) -> None:
    save_webhook(tmp_path, "https://discord.com/api/webhooks/example/token")
    save_ui_language(tmp_path, "ja")
    save_webhook(tmp_path, "https://discord.com/api/webhooks/new/token")

    config = load_config(tmp_path)
    assert config.ui.language == "ja"
    assert config.webhook_url.endswith("/new/token")
    dotenv = (tmp_path / ".env").read_text(encoding="utf-8")
    assert dotenv.count("DIGIMON_UI_LANGUAGE=") == 1
    assert dotenv.count("DIGIMON_DISCORD_WEBHOOK_URL=") == 1


def test_new_vision_thresholds_have_safe_package_defaults(tmp_path) -> None:
    config = load_config(tmp_path)

    assert config.vision.task_incomplete_red_pixel_ratio > 0
    assert 0 < config.vision.food_prompt_white_pixel_ratio < 1
    assert 0 < config.vision.food_prompt_cyan_pixel_ratio < 1
