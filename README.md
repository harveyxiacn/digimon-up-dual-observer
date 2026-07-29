# DIGIMON UP // OBSERVER

[简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | **English** | [日本語](README.ja.md)

A Windows screen monitor and safe automation helper for Digimon UP running in popular Android emulators. It captures and taps through ADB instead of controlling the Windows mouse, so the emulator can be minimized or placed on another display. One emulator is monitored by default; multi-emulator mode supports up to two.

![Pixel-style emulator monitor UI](docs/ui-preview.png)

## Features

- Selects and monitors one safe ADB emulator by default, with one live preview.
- Optional multi-emulator mode displays and monitors up to two instances.
- Detects BlueStacks, LDPlayer, NoxPlayer, MuMu Player, MEmu, and Genymotion processes without administrator privileges.
- Confirms a completed green task frame across two screenshots before claiming it.
- Detects and closes the full-width blue reward screen after a claim.
- Blocks automatic claims and sends a Discord screenshot for skill-card or support-type Digimon draw tasks.
- Equipment flow requires both large Sell and Equip buttons:
  - green up arrows: Equip;
  - the replaced item then shows red down arrows: Sell;
  - red down arrows on the initial popup: Sell directly;
  - unclear arrows: do nothing and write a warning.
- Sends a rate-limited Discord screenshot when OCR detects insufficient hologram/projection tickets.
- Automatic clicks can be disabled at any time for observation-only mode.
- UI, runtime logs, dialogs, main errors, and Discord notifications support Simplified Chinese, Traditional Chinese, English, and Japanese.

## Install and run

With dependencies already installed:

```powershell
.\run.ps1
```

You can also double-click `start-monitor.bat`.

First-time installation:

```powershell
.\install.ps1
.\run.ps1
```

Then:

1. Enable ADB/local debugging in the emulator settings.
2. Start the emulator and Digimon UP.
3. Open the monitor and select **Refresh ADB**.
4. Copy `config.local.example.yaml` to `config.local.yaml`, then add local ADB ports and optional device aliases. This file is excluded from Git.
5. Keep single-emulator mode for one account, or enable multi-emulator mode and select a second instance.
6. Start in observation-only mode for a few minutes before enabling automatic clicks after a game UI update.

The process detector uses the native Windows Tool Help process snapshot API. It reads only executable filenames and does not require administrator privileges or read account data, window titles, executable paths, command lines, or emulator files.

- [Official BlueStacks ADB guide](https://support.bluestacks.com/hc/en-us/articles/23925869130381-How-to-enable-Android-Debug-Bridge-on-BlueStacks-5)
- [LDPlayer local ADB guide](https://pre-prod-web-next.ldplayer.net/blog/introduction-to-version-4.0.37-and-3.102-features.html)
- [Official MuMu developer guide](https://www.mumuplayer.com/help/win/developers-essentials-manual.html)

## Language selection

Use the language selector in the top-right corner. The change is applied immediately and stored locally as `DIGIMON_UI_LANGUAGE` in `.env`. Supported values are:

- `zh_CN` — Simplified Chinese
- `zh_TW` — Traditional Chinese
- `en` — English
- `ja` — Japanese

The bundled Fusion Pixel font selects matching Latin, Simplified Chinese, Traditional Chinese, or Japanese glyph variants. Missing font files fall back to the corresponding Windows UI font.

## Game OCR languages

The default OCR request is `chi_tra+chi_sim+jpn+eng`. At runtime, the monitor automatically uses the installed Tesseract language packs and logs any missing pack instead of failing the whole OCR pipeline.

Chinese, English, and Japanese variants are recognized for:

- skill-card draw tasks;
- support-type Digimon draw tasks;
- insufficient hologram/projection ticket dialogs.

Install the Tesseract Japanese trained data (`jpn`) if Japanese game text is required. UI language and game OCR language are independent.

## Discord Webhook and privacy

Configure the Webhook in either of these ways:

1. Paste it into the masked **Discord Link** field and send a test signal or start monitoring.
2. Copy `.env.example` to `.env` and set `DIGIMON_DISCORD_WEBHOOK_URL`.

`.env`, `config.local.yaml`, `captures/`, and `logs/` are excluded by `.gitignore`. Never place a real Webhook in `config.yaml`, source code, issues, screenshots, or commits. Delete and regenerate a Webhook immediately if it becomes public.

## Safety boundaries

- ADB taps use screenshot coordinates and never move the Windows mouse.
- Task claiming requires a green frame, non-empty OCR, and two consecutive confirmations.
- Reward closing requires a blue overlay covering almost the full middle width; equipment dialogs do not satisfy it.
- Special draw tasks take priority over automatic claims.
- Equipment actions require a paired pink Sell button and blue Equip button.
- Unknown equipment state always means no action.
- Actions are separated by at least 2.5 seconds by default; Discord events also have deduplication and cooldowns.

Thresholds and timing are in [config.yaml](config.yaml). Return to observation-only mode and recalibrate after major game UI, language, or aspect-ratio changes.

## Verification

Run unit tests:

```powershell
python -m pytest
```

Run the six original reference screenshots through the visual/OCR regression tool:

```powershell
python tools\analyze_samples.py "path\to\screenshots"
```

## UI and font

The interface combines a dark Digital World background, cyan circuit grid, D-3-style status colors, D-Ark card borders, and D-Scanner red/blue alert areas. It does not copy anime logos, character art, or game textures.

The project bundles **Fusion Pixel 12px Proportional** language variants under SIL Open Font License 1.1, with upstream notices in `assets/fonts/`.

- [Fusion Pixel Font and license](https://github.com/TakWolf/fusion-pixel-font)
- [Bandai D-Scanner visual reference](https://www.bandai.co.jp/catalog/item.php?jan_cd=4543112120243000)
- [Bandai D-Scanner color reference](https://www.atpress.ne.jp/news/328455)

## Project layout

```text
digimon_monitor/
  i18n.py                Four-language translations and language selection
  adb.py                 ADB devices, screenshots, and taps
  vision.py              Task, reward, and equipment visual recognition
  ocr.py                 Multilingual OCR with installed-pack fallback
  monitor.py             Stable-frame state machine, cooldowns, notifications
  discord_notifier.py    Private Discord Webhook and image attachments
  ui.py / theme.py       PySide6 pixel-style desktop UI and localized fonts
tools/analyze_samples.py Reference screenshot regression tool
tests/                   Vision, language, configuration, and selection tests
```
