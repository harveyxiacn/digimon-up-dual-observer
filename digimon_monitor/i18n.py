from __future__ import annotations

from dataclasses import dataclass
import threading


DEFAULT_LANGUAGE = "zh_CN"
LANGUAGES = (
    ("zh_CN", "简体中文"),
    ("zh_TW", "繁體中文"),
    ("en", "English"),
    ("ja", "日本語"),
)
SUPPORTED_LANGUAGES = frozenset(code for code, _ in LANGUAGES)


TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app.subtitle": (
            "DIGITAL WORLD LINK  •  TASK WATCH  •  EQUIPMENT PROTOCOL"
        ),
        "language.label": "LANGUAGE",
        "group.devices": "01 // EMULATOR LINK",
        "devices.multi": "Multi-emulator mode (show / monitor up to 2)",
        "devices.scanning": "Scanning emulator processes…",
        "devices.refresh": "Refresh ADB",
        "devices.connect": "Connect",
        "group.discord": "02 // Discord Link",
        "discord.test": "Send test signal",
        "group.protocol": "03 // Automation Protocol",
        "automation.enable": "Enable automatic clicks",
        "protocol.text": (
            "[OK] Green frame + green current count → Claim\n"
            "[OK] White food bubble → Tap once\n"
            "[OK] Green up arrow → Equip, then sell old item\n"
            "[OK] Red down arrow → Sell\n"
            "[!] Special draw / ticket shortage → Discord"
        ),
        "preview.single": "LIVE // SINGLE CHANNEL",
        "preview.multi": "LIVE // MULTI CHANNEL",
        "group.events": "EVENT STREAM // LOG",
        "preview.waiting": "Waiting for emulator video\n\nADB SCREEN CHANNEL",
        "preview.link_waiting": "LINK {index} // WAITING",
        "status.online": "ONLINE",
        "status.linking": "LINKING",
        "status.retrying": "RETRYING",
        "status.offline": "OFFLINE",
        "device.default_excluded": "  [not selected by default]",
        "device.android": "Android device",
        "discovery.process_scan": (
            "Process scan: {names}\n"
            "ADB connected to {count} emulator(s). Select devices and start."
        ),
        "discovery.connected": (
            "ADB connected to {count} emulator(s). Select devices and start."
        ),
        "discovery.detected_no_adb": (
            "Emulator processes detected, but no usable ADB device:\n{hints}"
        ),
        "discovery.none": (
            "No common emulator process or ADB device found. Start an emulator "
            "and enable ADB/local connection in its settings."
        ),
        "log.adb_found": "[SYSTEM] ADB found {count} device(s)",
        "mode.multi": "MULTI // UP TO 2",
        "mode.single": "SINGLE // 1",
        "mode.automation": "AUTOMATION",
        "mode.observation": "OBSERVATION",
        "log.mode_changed": "[SYSTEM] Monitor mode changed to {mode}",
        "log.max_two": "[SYSTEM] Multi-emulator mode supports up to 2 devices",
        "dialog.adb_connect_failed": "ADB connection failed",
        "dialog.select_device_title": "Select an emulator",
        "dialog.select_device_body": "Select at least one online emulator.",
        "dialog.max_two_title": "Two channels maximum",
        "dialog.max_two_body": (
            "This version monitors up to two emulators at once. "
            "Deselect any extra devices."
        ),
        "log.links_started": (
            "[SYSTEM] {count} link(s) started // MODE={mode}"
        ),
        "log.links_stopped": "[SYSTEM] All monitor links stopped",
        "discord.test_message": (
            "🟦 DIGIMON UP // OBSERVER test signal connected."
        ),
        "discord.test_success": "Discord test signal sent successfully",
        "discord.test_failed": "Discord test failed",
        "action.start": "START LINK",
        "action.stop": "STOP",
        "language.changed": "[SYSTEM] Language changed to {language}",
        "log.discord_sent": "Discord notification sent: {message}",
        "log.observe_action": (
            "Observation mode: detected “{action}”; click {point} was not sent"
        ),
        "log.action_done": "Action complete: {action}, coordinates {point}",
        "action.close_reward": "close task reward screen",
        "action.sell": "tap Sell",
        "action.equip": "tap Equip",
        "action.claim_task": "claim completed task",
        "action.food_prompt": "tap the food bubble",
        "log.equipment_unknown": (
            "Equipment dialog detected, but arrow direction is unclear; "
            "no action taken"
        ),
        "log.task_ocr_failed": "Task OCR failed: {error}",
        "special.support_digimon": "Draw support-type Digimon",
        "special.skill_card": "Draw skill cards",
        "notify.special": (
            "⚠️ [{label}] Special task detected: {special}\n"
            "OCR: {ocr}\n"
            "Automatic clicking was blocked. Please handle it manually."
        ),
        "notify.ocr_empty": "no text recognized",
        "notify.ticket": (
            "🎫 [{label}] Not enough hologram/projection tickets. "
            "Please replenish them before continuing."
        ),
        "log.dialog_ocr_failed": "Dialog OCR failed: {error}",
        "log.task_no_ocr": (
            "Task frame is complete but OCR returned no text; "
            "no action taken for safety"
        ),
        "log.task_incomplete": (
            "Task progress is still incomplete; no click was sent"
        ),
        "log.thread_started": "Monitor thread started",
        "log.monitor_failed": "Monitor failed ({count}): {error}",
        "log.thread_stopped": "Monitor thread stopped",
        "log.automation_mode": "[SYSTEM] Switched to {mode}",
        "log.ocr_languages": "OCR active: {active}; missing: {missing}",
        "error.adb_missing": (
            "adb was not found. Install Android platform-tools or set "
            "adb.executable in config.yaml."
        ),
        "error.adb_timeout": "ADB command timed out: {command}",
        "error.adb_address": "ADB address must look like 127.0.0.1:5555",
        "error.adb_connect": "Unable to connect to {address}",
        "error.adb_screenshot": "Screenshot failed for {serial}",
        "error.adb_invalid_screenshot": (
            "{serial} returned an invalid screenshot"
        ),
        "error.adb_negative_tap": "Refusing a tap with negative coordinates",
        "error.webhook_missing": "Discord Webhook is not configured",
        "error.webhook_invalid": "Discord Webhook URL is invalid",
        "error.discord_connect": "Discord connection failed: {error}",
        "error.discord_http": "Discord returned HTTP {status}{detail}",
        "emulator.bluestacks.name": "BlueStacks",
        "emulator.bluestacks.hint": (
            "Settings → Advanced → enable Android Debug Bridge (ADB), "
            "save, and note the port."
        ),
        "emulator.ldplayer.name": "LDPlayer",
        "emulator.ldplayer.hint": (
            "Settings → Other settings → ADB debugging → Enable local connection."
        ),
        "emulator.nox.name": "NoxPlayer",
        "emulator.nox.hint": (
            "Enable Root/ADB debugging in Settings; the first instance commonly "
            "uses local port 62001."
        ),
        "emulator.mumu.name": "MuMu Player",
        "emulator.mumu.hint": (
            "Check the ADB port in Diagnostics or Multi-instance Manager; "
            "some versions use 7555."
        ),
        "emulator.memu.name": "MEmu",
        "emulator.memu.hint": (
            "Start the emulator and enable ADB; the first instance commonly "
            "uses local port 21503."
        ),
        "emulator.genymotion.name": "Genymotion",
        "emulator.genymotion.hint": (
            "Select the local Android SDK in Android SDK settings, "
            "then refresh ADB."
        ),
    },
    "zh_CN": {
        "app.subtitle": "数码世界连接  •  任务监控  •  装备协议",
        "language.label": "界面语言",
        "group.devices": "01 // 模拟器连接",
        "devices.multi": "多模拟器模式（同时显示 / 监控最多 2 台）",
        "devices.scanning": "正在扫描模拟器进程…",
        "devices.refresh": "刷新 ADB",
        "devices.connect": "连接",
        "group.discord": "02 // Discord 通讯",
        "discord.test": "发送测试信号",
        "group.protocol": "03 // 自动处理协议",
        "automation.enable": "启用自动点击",
        "protocol.text": (
            "[OK] 绿色框 + 当前完成数绿色 → 领取\n"
            "[OK] 白底食物气泡 → 只点击一次\n"
            "[OK] 绿色上箭头 → 装备后出售旧件\n"
            "[OK] 红色下箭头 → 出售\n"
            "[!] 特殊抽卡 / 投影券不足 → Discord"
        ),
        "preview.single": "LIVE // 单通道画面",
        "preview.multi": "LIVE // 多通道画面",
        "group.events": "EVENT STREAM // 事件日志",
        "preview.waiting": "等待模拟器画面\n\nADB SCREEN CHANNEL",
        "preview.link_waiting": "LINK {index} // 等待中",
        "status.online": "在线",
        "status.linking": "连接中",
        "status.retrying": "重试中",
        "status.offline": "离线",
        "device.default_excluded": "  [默认不勾选]",
        "device.android": "安卓设备",
        "discovery.process_scan": (
            "进程扫描：{names}\n"
            "ADB 已连接 {count} 台模拟器，可勾选后启动。"
        ),
        "discovery.connected": (
            "ADB 已连接 {count} 台模拟器，可勾选后启动。"
        ),
        "discovery.detected_no_adb": (
            "检测到模拟器进程，但没有可用 ADB 设备：\n{hints}"
        ),
        "discovery.none": (
            "未发现常见模拟器进程或 ADB 设备。请先启动模拟器，"
            "并在其设置中开启 ADB/本地连接。"
        ),
        "log.adb_found": "[SYSTEM] ADB 发现 {count} 个设备",
        "mode.multi": "MULTI // 最多 2 台",
        "mode.single": "SINGLE // 1 台",
        "mode.automation": "自动点击",
        "mode.observation": "观察模式",
        "log.mode_changed": "[SYSTEM] 监控模式切换为 {mode}",
        "log.max_two": "[SYSTEM] 多模拟器模式最多选择 2 台",
        "dialog.adb_connect_failed": "ADB 连接失败",
        "dialog.select_device_title": "请选择模拟器",
        "dialog.select_device_body": "至少勾选一个在线模拟器。",
        "dialog.max_two_title": "最多两个通道",
        "dialog.max_two_body": (
            "本版本同时监控最多两个模拟器，请取消多余勾选。"
        ),
        "log.links_started": "[SYSTEM] {count} 条链路启动 // MODE={mode}",
        "log.links_stopped": "[SYSTEM] 所有监控链路已停止",
        "discord.test_message": (
            "🟦 DIGIMON UP // OBSERVER 测试信号已连接。"
        ),
        "discord.test_success": "Discord 测试信号发送成功",
        "discord.test_failed": "Discord 测试失败",
        "action.start": "启动监控",
        "action.stop": "停止",
        "language.changed": "[SYSTEM] 界面语言已切换为 {language}",
        "log.discord_sent": "Discord 通知已发送：{message}",
        "log.observe_action": (
            "观察模式：识别到“{action}”，未执行点击 {point}"
        ),
        "log.action_done": "已执行“{action}”，坐标 {point}",
        "action.close_reward": "关闭任务奖励画面",
        "action.sell": "点击出售",
        "action.equip": "点击装备",
        "action.claim_task": "领取已完成任务",
        "action.food_prompt": "点击食物气泡",
        "log.equipment_unknown": (
            "检测到装备弹窗，但箭头方向不明确；保持不动"
        ),
        "log.task_ocr_failed": "任务 OCR 失败：{error}",
        "special.support_digimon": "抽取支援型数码宝贝",
        "special.skill_card": "抽取技能卡片",
        "notify.special": (
            "⚠️ 【{label}】发现特殊任务：{special}\n"
            "OCR：{ocr}\n"
            "已阻止自动点击，请手动处理。"
        ),
        "notify.ocr_empty": "未读出文字",
        "notify.ticket": (
            "🎫 【{label}】全息/投影券不足，请补充后再继续。"
        ),
        "log.dialog_ocr_failed": "弹窗 OCR 失败：{error}",
        "log.task_no_ocr": (
            "任务框已完成但 OCR 无结果；为防误点保持不动"
        ),
        "log.task_incomplete": "任务进度尚未完成；不会发送点击",
        "log.thread_started": "监控线程已启动",
        "log.monitor_failed": "监控失败（{count}）：{error}",
        "log.thread_stopped": "监控线程已停止",
        "log.automation_mode": "[SYSTEM] 已切换为 {mode}",
        "log.ocr_languages": "OCR 已启用：{active}；缺少：{missing}",
        "error.adb_missing": (
            "找不到 adb。请安装 Android platform-tools，"
            "或在 config.yaml 设置 adb.executable。"
        ),
        "error.adb_timeout": "ADB 命令超时：{command}",
        "error.adb_address": "ADB 地址格式应为 127.0.0.1:5555",
        "error.adb_connect": "无法连接 {address}",
        "error.adb_screenshot": "{serial} 截图失败",
        "error.adb_invalid_screenshot": "{serial} 返回了无效截图",
        "error.adb_negative_tap": "拒绝负坐标点击",
        "error.webhook_missing": "Discord Webhook 尚未设置",
        "error.webhook_invalid": "Discord Webhook URL 格式不正确",
        "error.discord_connect": "Discord 连接失败：{error}",
        "error.discord_http": "Discord 返回 HTTP {status}{detail}",
        "emulator.bluestacks.name": "BlueStacks",
        "emulator.bluestacks.hint": (
            "设置 → 高级 → 开启“Android 调试(ADB)”，保存并记下端口。"
        ),
        "emulator.ldplayer.name": "雷电模拟器 / LDPlayer",
        "emulator.ldplayer.hint": (
            "设置 → 其他设置 → ADB 调试 → 开启本地连接。"
        ),
        "emulator.nox.name": "夜神模拟器 / NoxPlayer",
        "emulator.nox.hint": (
            "设置中开启 Root/ADB 调试；首个实例通常使用本地 62001 端口。"
        ),
        "emulator.mumu.name": "MuMu 模拟器",
        "emulator.mumu.hint": (
            "在问题诊断或多开器中查看 ADB 端口；部分版本使用 7555。"
        ),
        "emulator.memu.name": "逍遥模拟器 / MEmu",
        "emulator.memu.hint": (
            "启动模拟器并开启 ADB；首个实例常见本地端口为 21503。"
        ),
        "emulator.genymotion.name": "Genymotion",
        "emulator.genymotion.hint": (
            "在 Android SDK 设置中选择使用本机 SDK，然后刷新 ADB。"
        ),
    },
    "zh_TW": {
        "app.subtitle": "數碼世界連線  •  任務監控  •  裝備協定",
        "language.label": "介面語言",
        "group.devices": "01 // 模擬器連線",
        "devices.multi": "多模擬器模式（同時顯示 / 監控最多 2 台）",
        "devices.scanning": "正在掃描模擬器程序…",
        "devices.refresh": "重新整理 ADB",
        "devices.connect": "連線",
        "group.discord": "02 // Discord 通訊",
        "discord.test": "傳送測試訊號",
        "group.protocol": "03 // 自動處理協定",
        "automation.enable": "啟用自動點擊",
        "protocol.text": (
            "[OK] 綠色框 + 目前完成數綠色 → 領取\n"
            "[OK] 白底食物氣泡 → 只點擊一次\n"
            "[OK] 綠色上箭頭 → 裝備後出售舊件\n"
            "[OK] 紅色下箭頭 → 出售\n"
            "[!] 特殊抽卡 / 投影券不足 → Discord"
        ),
        "preview.single": "LIVE // 單通道畫面",
        "preview.multi": "LIVE // 多通道畫面",
        "group.events": "EVENT STREAM // 事件記錄",
        "preview.waiting": "等待模擬器畫面\n\nADB SCREEN CHANNEL",
        "preview.link_waiting": "LINK {index} // 等待中",
        "status.online": "上線",
        "status.linking": "連線中",
        "status.retrying": "重試中",
        "status.offline": "離線",
        "device.default_excluded": "  [預設不勾選]",
        "device.android": "Android 裝置",
        "discovery.process_scan": (
            "程序掃描：{names}\n"
            "ADB 已連線 {count} 台模擬器，可勾選後啟動。"
        ),
        "discovery.connected": (
            "ADB 已連線 {count} 台模擬器，可勾選後啟動。"
        ),
        "discovery.detected_no_adb": (
            "偵測到模擬器程序，但沒有可用 ADB 裝置：\n{hints}"
        ),
        "discovery.none": (
            "未發現常見模擬器程序或 ADB 裝置。請先啟動模擬器，"
            "並在其設定中開啟 ADB/本機連線。"
        ),
        "log.adb_found": "[SYSTEM] ADB 發現 {count} 個裝置",
        "mode.multi": "MULTI // 最多 2 台",
        "mode.single": "SINGLE // 1 台",
        "mode.automation": "自動點擊",
        "mode.observation": "觀察模式",
        "log.mode_changed": "[SYSTEM] 監控模式切換為 {mode}",
        "log.max_two": "[SYSTEM] 多模擬器模式最多選擇 2 台",
        "dialog.adb_connect_failed": "ADB 連線失敗",
        "dialog.select_device_title": "請選擇模擬器",
        "dialog.select_device_body": "至少勾選一個上線模擬器。",
        "dialog.max_two_title": "最多兩個通道",
        "dialog.max_two_body": (
            "本版本同時監控最多兩個模擬器，請取消多餘勾選。"
        ),
        "log.links_started": "[SYSTEM] {count} 條連線啟動 // MODE={mode}",
        "log.links_stopped": "[SYSTEM] 所有監控連線已停止",
        "discord.test_message": (
            "🟦 DIGIMON UP // OBSERVER 測試訊號已連線。"
        ),
        "discord.test_success": "Discord 測試訊號傳送成功",
        "discord.test_failed": "Discord 測試失敗",
        "action.start": "啟動監控",
        "action.stop": "停止",
        "language.changed": "[SYSTEM] 介面語言已切換為 {language}",
        "log.discord_sent": "Discord 通知已傳送：{message}",
        "log.observe_action": (
            "觀察模式：識別到「{action}」，未執行點擊 {point}"
        ),
        "log.action_done": "已執行「{action}」，座標 {point}",
        "action.close_reward": "關閉任務獎勵畫面",
        "action.sell": "點擊出售",
        "action.equip": "點擊裝備",
        "action.claim_task": "領取已完成任務",
        "action.food_prompt": "點擊食物氣泡",
        "log.equipment_unknown": (
            "偵測到裝備彈窗，但箭頭方向不明確；保持不動"
        ),
        "log.task_ocr_failed": "任務 OCR 失敗：{error}",
        "special.support_digimon": "抽取支援型數碼寶貝",
        "special.skill_card": "抽取技能卡片",
        "notify.special": (
            "⚠️ 【{label}】發現特殊任務：{special}\n"
            "OCR：{ocr}\n"
            "已阻止自動點擊，請手動處理。"
        ),
        "notify.ocr_empty": "未讀出文字",
        "notify.ticket": (
            "🎫 【{label}】全像/投影券不足，請補充後再繼續。"
        ),
        "log.dialog_ocr_failed": "彈窗 OCR 失敗：{error}",
        "log.task_no_ocr": (
            "任務框已完成但 OCR 無結果；為防誤點保持不動"
        ),
        "log.task_incomplete": "任務進度尚未完成；不會傳送點擊",
        "log.thread_started": "監控執行緒已啟動",
        "log.monitor_failed": "監控失敗（{count}）：{error}",
        "log.thread_stopped": "監控執行緒已停止",
        "log.automation_mode": "[SYSTEM] 已切換為 {mode}",
        "log.ocr_languages": "OCR 已啟用：{active}；缺少：{missing}",
        "error.adb_missing": (
            "找不到 adb。請安裝 Android platform-tools，"
            "或在 config.yaml 設定 adb.executable。"
        ),
        "error.adb_timeout": "ADB 指令逾時：{command}",
        "error.adb_address": "ADB 位址格式應為 127.0.0.1:5555",
        "error.adb_connect": "無法連線 {address}",
        "error.adb_screenshot": "{serial} 截圖失敗",
        "error.adb_invalid_screenshot": "{serial} 傳回了無效截圖",
        "error.adb_negative_tap": "拒絕負座標點擊",
        "error.webhook_missing": "Discord Webhook 尚未設定",
        "error.webhook_invalid": "Discord Webhook URL 格式不正確",
        "error.discord_connect": "Discord 連線失敗：{error}",
        "error.discord_http": "Discord 傳回 HTTP {status}{detail}",
        "emulator.bluestacks.name": "BlueStacks",
        "emulator.bluestacks.hint": (
            "設定 → 進階 → 開啟「Android 偵錯(ADB)」，儲存並記下連接埠。"
        ),
        "emulator.ldplayer.name": "雷電模擬器 / LDPlayer",
        "emulator.ldplayer.hint": (
            "設定 → 其他設定 → ADB 偵錯 → 開啟本機連線。"
        ),
        "emulator.nox.name": "夜神模擬器 / NoxPlayer",
        "emulator.nox.hint": (
            "在設定中開啟 Root/ADB 偵錯；首個執行個體通常使用"
            "本機 62001 連接埠。"
        ),
        "emulator.mumu.name": "MuMu 模擬器",
        "emulator.mumu.hint": (
            "在問題診斷或多開器中查看 ADB 連接埠；部分版本使用 7555。"
        ),
        "emulator.memu.name": "逍遙模擬器 / MEmu",
        "emulator.memu.hint": (
            "啟動模擬器並開啟 ADB；首個執行個體常用本機連接埠 21503。"
        ),
        "emulator.genymotion.name": "Genymotion",
        "emulator.genymotion.hint": (
            "在 Android SDK 設定中選擇使用本機 SDK，然後重新整理 ADB。"
        ),
    },
    "ja": {
        "app.subtitle": "デジタルワールド接続  •  ミッション監視  •  装備プロトコル",
        "language.label": "表示言語",
        "group.devices": "01 // エミュレーター接続",
        "devices.multi": "複数エミュレーターモード（最大2台を表示・監視）",
        "devices.scanning": "エミュレーターのプロセスを検索中…",
        "devices.refresh": "ADBを更新",
        "devices.connect": "接続",
        "group.discord": "02 // Discord 通信",
        "discord.test": "テスト信号を送信",
        "group.protocol": "03 // 自動処理プロトコル",
        "automation.enable": "自動クリックを有効化",
        "protocol.text": (
            "[OK] 緑枠 + 現在の完了数が緑 → 受け取る\n"
            "[OK] 白い食べ物バブル → 1回だけクリック\n"
            "[OK] 緑の上矢印 → 装備後、旧装備を売却\n"
            "[OK] 赤の下矢印 → 売却\n"
            "[!] 特別ガチャ / チケット不足 → Discord"
        ),
        "preview.single": "LIVE // シングルチャンネル",
        "preview.multi": "LIVE // マルチチャンネル",
        "group.events": "EVENT STREAM // イベントログ",
        "preview.waiting": (
            "エミュレーター画面を待機中\n\nADB SCREEN CHANNEL"
        ),
        "preview.link_waiting": "LINK {index} // 待機中",
        "status.online": "オンライン",
        "status.linking": "接続中",
        "status.retrying": "再試行中",
        "status.offline": "オフライン",
        "device.default_excluded": "  [初期状態では未選択]",
        "device.android": "Androidデバイス",
        "discovery.process_scan": (
            "プロセス検索：{names}\n"
            "ADBで{count}台のエミュレーターに接続済み。選択して開始できます。"
        ),
        "discovery.connected": (
            "ADBで{count}台のエミュレーターに接続済み。選択して開始できます。"
        ),
        "discovery.detected_no_adb": (
            "エミュレーターのプロセスを検出しましたが、"
            "使用可能なADBデバイスがありません：\n{hints}"
        ),
        "discovery.none": (
            "一般的なエミュレーターのプロセスまたはADBデバイスが"
            "見つかりません。エミュレーターを起動し、設定で"
            "ADB/ローカル接続を有効にしてください。"
        ),
        "log.adb_found": "[SYSTEM] ADBで{count}台のデバイスを検出",
        "mode.multi": "MULTI // 最大2台",
        "mode.single": "SINGLE // 1台",
        "mode.automation": "自動クリック",
        "mode.observation": "監視のみ",
        "log.mode_changed": "[SYSTEM] 監視モードを{mode}に変更",
        "log.max_two": "[SYSTEM] 複数モードで選択できるのは最大2台です",
        "dialog.adb_connect_failed": "ADB接続に失敗",
        "dialog.select_device_title": "エミュレーターを選択",
        "dialog.select_device_body": (
            "オンラインのエミュレーターを1台以上選択してください。"
        ),
        "dialog.max_two_title": "最大2チャンネル",
        "dialog.max_two_body": (
            "同時に監視できるエミュレーターは最大2台です。"
            "余分な選択を解除してください。"
        ),
        "log.links_started": (
            "[SYSTEM] {count}件の接続を開始 // MODE={mode}"
        ),
        "log.links_stopped": "[SYSTEM] すべての監視接続を停止",
        "discord.test_message": (
            "🟦 DIGIMON UP // OBSERVER テスト信号を接続しました。"
        ),
        "discord.test_success": "Discordテスト信号の送信に成功",
        "discord.test_failed": "Discordテストに失敗",
        "action.start": "監視開始",
        "action.stop": "停止",
        "language.changed": "[SYSTEM] 表示言語を{language}に変更",
        "log.discord_sent": "Discord通知を送信：{message}",
        "log.observe_action": (
            "監視のみ：{action}を検出しましたが、"
            "クリック{point}は実行しませんでした"
        ),
        "log.action_done": "{action}を実行、座標 {point}",
        "action.close_reward": "ミッション報酬画面を閉じる",
        "action.sell": "「売却」をクリック",
        "action.equip": "「装備」をクリック",
        "action.claim_task": "完了ミッションの報酬を受け取る",
        "action.food_prompt": "食べ物バブルをクリック",
        "log.equipment_unknown": (
            "装備ダイアログを検出しましたが矢印の方向が不明なため、"
            "操作しません"
        ),
        "log.task_ocr_failed": "ミッションOCRに失敗：{error}",
        "special.support_digimon": "支援型デジモンを引く",
        "special.skill_card": "スキルカードを引く",
        "notify.special": (
            "⚠️ 【{label}】特別ミッションを検出：{special}\n"
            "OCR：{ocr}\n"
            "自動クリックを停止しました。手動で処理してください。"
        ),
        "notify.ocr_empty": "文字を認識できませんでした",
        "notify.ticket": (
            "🎫 【{label}】ホログラム/投影チケットが不足しています。"
            "補充してから続行してください。"
        ),
        "log.dialog_ocr_failed": "ダイアログOCRに失敗：{error}",
        "log.task_no_ocr": (
            "ミッション完了枠を検出しましたがOCR結果がないため、"
            "安全のため操作しません"
        ),
        "log.task_incomplete": (
            "ミッション進捗が未完了のため、クリックしません"
        ),
        "log.thread_started": "監視スレッドを開始",
        "log.monitor_failed": "監視に失敗（{count}）：{error}",
        "log.thread_stopped": "監視スレッドを停止",
        "log.automation_mode": "[SYSTEM] {mode}に切り替えました",
        "log.ocr_languages": "OCR有効：{active}；未導入：{missing}",
        "error.adb_missing": (
            "adbが見つかりません。Android platform-toolsをインストールするか、"
            "config.yamlのadb.executableを設定してください。"
        ),
        "error.adb_timeout": "ADBコマンドがタイムアウト：{command}",
        "error.adb_address": "ADBアドレスは127.0.0.1:5555形式で入力してください",
        "error.adb_connect": "{address}に接続できません",
        "error.adb_screenshot": "{serial}のスクリーンショット取得に失敗",
        "error.adb_invalid_screenshot": (
            "{serial}から無効なスクリーンショットが返されました"
        ),
        "error.adb_negative_tap": "負の座標へのクリックを拒否しました",
        "error.webhook_missing": "Discord Webhookが設定されていません",
        "error.webhook_invalid": "Discord Webhook URLの形式が正しくありません",
        "error.discord_connect": "Discord接続に失敗：{error}",
        "error.discord_http": "DiscordがHTTP {status}を返しました{detail}",
        "emulator.bluestacks.name": "BlueStacks",
        "emulator.bluestacks.hint": (
            "設定 → 詳細設定 → Android Debug Bridge (ADB)を有効にし、"
            "保存してポートを確認してください。"
        ),
        "emulator.ldplayer.name": "LDPlayer",
        "emulator.ldplayer.hint": (
            "設定 → その他の設定 → ADBデバッグ → "
            "ローカル接続を有効にしてください。"
        ),
        "emulator.nox.name": "NoxPlayer",
        "emulator.nox.hint": (
            "設定でRoot/ADBデバッグを有効にしてください。"
            "最初のインスタンスは通常ローカルポート62001を使用します。"
        ),
        "emulator.mumu.name": "MuMu Player",
        "emulator.mumu.hint": (
            "診断またはマルチインスタンス管理でADBポートを確認してください。"
            "一部のバージョンは7555を使用します。"
        ),
        "emulator.memu.name": "MEmu",
        "emulator.memu.hint": (
            "エミュレーターを起動してADBを有効にしてください。"
            "最初のインスタンスは通常ローカルポート21503を使用します。"
        ),
        "emulator.genymotion.name": "Genymotion",
        "emulator.genymotion.hint": (
            "Android SDK設定でローカルSDKを選択し、ADBを更新してください。"
        ),
    },
}


def normalize_language(code: str | None) -> str:
    if not code:
        return DEFAULT_LANGUAGE
    normalized = code.replace("-", "_")
    aliases = {
        "zh": "zh_CN",
        "zh_Hans": "zh_CN",
        "zh_hans": "zh_CN",
        "zh_TW": "zh_TW",
        "zh_Hant": "zh_TW",
        "zh_hant": "zh_TW",
        "en_US": "en",
        "en_GB": "en",
        "ja_JP": "ja",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


@dataclass(frozen=True, slots=True)
class LanguageOption:
    code: str
    name: str


class Translator:
    def __init__(self, language: str = DEFAULT_LANGUAGE):
        self._lock = threading.RLock()
        self._language = normalize_language(language)

    @property
    def language(self) -> str:
        with self._lock:
            return self._language

    def set_language(self, language: str) -> str:
        with self._lock:
            self._language = normalize_language(language)
            return self._language

    def text(self, key: str, **values: object) -> str:
        with self._lock:
            language = self._language
        template = TRANSLATIONS.get(language, {}).get(
            key,
            TRANSLATIONS["en"].get(key, key),
        )
        return template.format(**values)

    __call__ = text


def language_options() -> tuple[LanguageOption, ...]:
    return tuple(LanguageOption(code, name) for code, name in LANGUAGES)
