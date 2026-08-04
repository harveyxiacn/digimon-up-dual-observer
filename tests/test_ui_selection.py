from digimon_monitor.adb import AdbDevice
from digimon_monitor.ui import normalized_selected_serials, webhook_status_key


def _emulator(serial: str, state: str = "device") -> AdbDevice:
    return AdbDevice(serial=serial, state=state)


def test_single_mode_selects_only_first_safe_emulator_by_default() -> None:
    devices = [
        AdbDevice(serial="phone-123", state="device", model="Pixel_9"),
        _emulator("127.0.0.1:5565"),
        _emulator("emulator-5554"),
    ]

    assert normalized_selected_serials(
        devices, set(), allow_multiple=False
    ) == ["127.0.0.1:5565"]


def test_single_mode_keeps_only_one_explicit_selection() -> None:
    devices = [
        _emulator("127.0.0.1:5565"),
        _emulator("emulator-5554"),
    ]

    assert normalized_selected_serials(
        devices,
        {"127.0.0.1:5565", "emulator-5554"},
        allow_multiple=False,
    ) == ["127.0.0.1:5565"]


def test_multi_mode_keeps_two_explicit_selections() -> None:
    devices = [
        _emulator("127.0.0.1:5565"),
        _emulator("emulator-5554"),
    ]

    assert normalized_selected_serials(
        devices,
        {"127.0.0.1:5565", "emulator-5554"},
        allow_multiple=True,
    ) == ["127.0.0.1:5565", "emulator-5554"]


def test_offline_selection_falls_back_to_online_emulator() -> None:
    devices = [
        _emulator("127.0.0.1:5565", state="offline"),
        _emulator("emulator-5554"),
    ]

    assert normalized_selected_serials(
        devices,
        {"127.0.0.1:5565"},
        allow_multiple=True,
    ) == ["emulator-5554"]


def test_webhook_status_is_display_only_and_respects_discord_pause() -> None:
    webhook = "https://discord.com/api/webhooks/123456789/token"

    assert webhook_status_key("", True) == "discord.status.missing"
    assert webhook_status_key("https://example.com/hook", True) == "discord.status.invalid"
    assert webhook_status_key(webhook, False) == "discord.status.paused"
    assert webhook_status_key(webhook, True) == "discord.status.ready"
