# DIGIMON UP // OBSERVER

[简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | **English** | [日本語](README.ja.md)

A Windows screen monitor and safe automation helper for Digimon UP running in popular Android emulators. It captures and taps through ADB instead of controlling the Windows mouse, so the emulator can be minimized or placed on another display. One emulator is monitored by default; multi-emulator mode supports up to two.

![Pixel-style emulator monitor UI](docs/ui-preview.png)

## Features

- Selects and monitors one safe ADB emulator by default, with one live preview.
- Optional multi-emulator mode displays and monitors up to two instances.
- Detects BlueStacks, LDPlayer, NoxPlayer, MuMu Player, MEmu, and Genymotion processes without administrator privileges.
- Claims a task only after two frames show a green completion border, a green current count, and no red current-progress digits. The slash and required count may remain white. A white border, a red current count, or an OCR fraction such as `1/2` blocks the click.
- Detects the white food bubble beside the center Digimon, clicks it once, and waits for it to disappear before re-arming.
- Detects and closes the full-width blue reward screen after a claim.
- Blocks automatic claims and sends a Discord screenshot for skill-card or support-type Digimon draw tasks.
- Equipment flow requires both large Sell and Equip buttons:
  - green up arrows: Equip;
  - the replaced item then shows red down arrows: Sell;
  - red down arrows on the initial popup: Sell directly;
  - unclear arrows: compare OCR-readable affixes by priority (both Crit Rate + Skill Crit Rate, Crit Rate only, Skill Crit Rate only, then none); equip only when the new item is strictly higher, otherwise sell it;
  - unreliable affix OCR: do nothing and write a warning.
- Sends a rate-limited Discord screenshot when OCR detects insufficient hologram/projection tickets.
- Automatic clicks can be disabled at any time for observation-only mode.
- UI, runtime logs, dialogs, main errors, and Discord notifications support Simplified Chinese, Traditional Chinese, English, and Japanese.

### Independent automation switches

The **master** switch gates every ADB tap (off = observation mode). Four feature switches can be changed independently and persist locally: **task monitoring & claiming**, **equipment handling**, **food-bubble clicks**, and **automatic Discord notifications**. A long-running task can be paused without stopping the other features and resumed later. The manual Discord **Test** button always sends when a valid Webhook is configured, even if automatic notifications are paused.

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

The completed Discord path captures the current emulator screenshot, adds the device label and OCR/task context when available, and posts it as an attachment. A first event can notify immediately; duplicate events respect their cooldown, and failures are deferred before retrying. Discord rate limits and invalid/deleted Webhooks temporarily suppress repeated sends. Clearing the Webhook field removes the locally saved secret. `.env` is plain text on this machine and must not be shared; OS environment variables take precedence over the UI and `.env`. Screenshots and OCR text can contain game/task data and device labels, so treat Discord and local logs as sensitive.

## Safety boundaries

- ADB taps use screenshot coordinates and never move the Windows mouse.
- Task claiming requires a green border, a green current count with no red current-progress digits, non-empty OCR, and two consecutive confirmations. A white border, a red current count, or a recognized incomplete fraction always blocks the click.
- Food prompts require two consecutive detections, fire once per appearance, and re-arm only after two frames confirm that the bubble disappeared.
- Reward closing requires a blue overlay covering almost the full middle width; equipment dialogs do not satisfy it.
- Special draw tasks take priority over automatic claims.
- Equipment actions require a paired pink Sell button and blue Equip button.
- When no green/red arrow is present, the OCR affix fallback only equips a strictly higher-priority item; ties and lower priorities are sold, while unreliable OCR always means no action.
- Unreadable equipment panels or missing paired action buttons always mean no action.
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
  equipment.py           Multilingual affix ranking and safe decisions
  monitor.py             Stable-frame state machine, cooldowns, notifications
  discord_notifier.py    Private Discord Webhook and image attachments
  ui.py / theme.py       PySide6 pixel-style desktop UI and localized fonts
tools/analyze_samples.py Reference screenshot regression tool
tests/                   Vision, language, configuration, and selection tests
```
