# DIGIMON UP // OBSERVER

**简体中文** | [繁體中文](README.zh-TW.md) | [English](README.md) | [日本語](README.ja.md)

一个面向 Windows 与主流安卓模拟器的 Digimon UP 画面监控与安全自动化工具。程序通过 ADB 截图并发送点击，不控制 Windows 鼠标，因此模拟器可以最小化或放在其他显示器上。默认监控一个模拟器；多模拟器模式最多支持两台。

![像素风模拟器监控界面](docs/ui-preview.png)

## 功能

- 默认选择并监控一台安全的 ADB 模拟器，只显示一个实时画面。
- 开启多模拟器模式后，可同时显示和监控最多两台实例。
- 无需管理员权限即可检测 BlueStacks、雷电、夜神、MuMu、逍遥和 Genymotion 进程。
- 只有连续两帧确认绿色任务框、当前完成数为绿色且没有红色当前进度时才领取任务；斜杠与要求完成数可以仍为白色。白色任务框、红色当前数值或 OCR 读到 `1/2` 等未完成比例都会阻止点击。
- 识别画面中央数码兽右上方的白底食物气泡，每次出现只点击一次，并在气泡消失后才重新待命。
- 领取后识别并关闭横跨屏幕的蓝色奖励画面。
- 遇到技能卡或支援型数码宝贝抽取任务时阻止自动领取，并向 Discord 发送截图。
- 装备流程必须同时确认大号“出售”和“装备”按钮：
  - 绿色上箭头：装备；
  - 替换后的旧装备变为红色下箭头：出售；
  - 初次弹窗就是红色下箭头：直接出售；
  - 箭头不明确：不操作并记录警告。
- OCR 识别全息/投影券不足后发送带冷却时间的 Discord 截图通知。
- 可随时关闭自动点击，切换为只识别、不操作的观察模式。
- UI、运行日志、弹窗、主要错误和 Discord 通知支持简体中文、繁体中文、英文和日文。

## 安装与运行

本机已有依赖时：

```powershell
.\run.ps1
```

也可以双击 `启动监控器.bat` 或 `start-monitor.bat`。

首次安装：

```powershell
.\install.ps1
.\run.ps1
```

然后：

1. 在模拟器设置中开启 ADB/本地调试。
2. 启动模拟器和 Digimon UP。
3. 打开监控器并点击“刷新 ADB”。
4. 把 `config.local.example.yaml` 复制为 `config.local.yaml`，填写本机 ADB 端口和可选设备别名。该文件不会进入 Git。
5. 单账号保持默认单模拟器模式；双开时启用多模拟器模式并选择第二台。
6. 游戏 UI 更新后，建议先使用观察模式运行几分钟，确认识别正常后再开启自动点击。

进程检测使用 Windows 原生 Tool Help 进程快照 API，只读取可执行文件名。它不需要管理员权限，也不会读取游戏账号、窗口标题、程序路径、命令行或模拟器内文件。

- [BlueStacks ADB 官方说明](https://support.bluestacks.com/hc/en-us/articles/23925869130381-How-to-enable-Android-Debug-Bridge-on-BlueStacks-5)
- [雷电 ADB 本地连接说明](https://pre-prod-web-next.ldplayer.net/blog/introduction-to-version-4.0.37-and-3.102-features.html)
- [MuMu 官方开发说明](https://www.mumuplayer.com/help/win/developers-essentials-manual.html)

## 语言选择

使用界面右上角的语言选择器，切换会立即生效，并在本机 `.env` 中保存为 `DIGIMON_UI_LANGUAGE`：

- `zh_CN` — 简体中文
- `zh_TW` — 繁体中文
- `en` — English
- `ja` — 日本語

内置 Fusion Pixel 字体会选择对应的拉丁、简体、繁体或日文字形；字体文件缺失时会回退到对应的 Windows UI 字体。

## 游戏 OCR 语言

默认 OCR 请求为 `chi_tra+chi_sim+jpn+eng`。程序会自动使用本机已安装的 Tesseract 语言包，并在日志中提示缺少的语言，不会因为缺少单个语言包而让整个 OCR 失败。

以下文本分类支持中文、英文和日文：

- 抽取技能卡片；
- 抽取支援型数码宝贝；
- 全息/投影券不足。

如需识别日文游戏画面，请安装 Tesseract 日文训练数据 `jpn`。软件 UI 语言和游戏 OCR 语言相互独立。

## Discord Webhook 与隐私

Webhook 有两种设置方式：

1. 粘贴到界面的 Discord 密码输入框，发送测试信号或启动监控。
2. 将 `.env.example` 复制为 `.env`，填写 `DIGIMON_DISCORD_WEBHOOK_URL`。

`.env`、`config.local.yaml`、`captures/` 与 `logs/` 已被 `.gitignore` 排除。不要把真实 Webhook 写入 `config.yaml`、源代码、Issue、截图或提交记录。如曾公开，应立即在 Discord 中删除并重新生成。

## 安全边界

- ADB 点击使用截图坐标，不会控制 Windows 鼠标。
- 任务领取需要绿色边框、当前完成数为绿色且没有红色当前进度、OCR 有文字、连续两帧同时成立；白色边框、红色当前值或未完成比例任一出现时都不点击。
- 食物气泡需连续两帧确认，每次出现只触发一次，并在连续两帧确认消失后重新待命。
- 奖励关闭需要蓝色遮罩覆盖屏幕中段绝大部分宽度，装备弹窗不会满足此条件。
- 特殊抽卡任务优先于自动领取。
- 装备动作必须识别到成对的粉色“出售”和蓝色“装备”按钮。
- 未知装备状态默认不操作。
- 两次动作默认至少间隔 2.5 秒；Discord 也有去重和冷却。

阈值与时间设置位于 [config.yaml](config.yaml)。游戏 UI、语言或纵横比大幅变化后，应回到观察模式重新校准。

## 验证

```powershell
python -m pytest
python tools\analyze_samples.py "截图所在目录"
```

## UI 与字体

界面使用深蓝数字世界底色、青色电路网格、D-3 状态色、D-Ark 卡片边框和 D-Scanner 红蓝警示区域，没有复制动画 Logo、角色图或游戏贴图。

项目依据 SIL Open Font License 1.1 打包 **Fusion Pixel 12px Proportional** 四种语言字形，上游许可说明位于 `assets/fonts/`。

- [Fusion Pixel Font 与许可](https://github.com/TakWolf/fusion-pixel-font)
- [Bandai D-Scanner 视觉参考](https://www.bandai.co.jp/catalog/item.php?jan_cd=4543112120243000)
- [Bandai D-Scanner 配色参考](https://www.atpress.ne.jp/news/328455)

## 项目结构

```text
digimon_monitor/
  i18n.py                四语言翻译与语言选择
  adb.py                 ADB 设备、截图与点击
  vision.py              任务、奖励与装备视觉识别
  ocr.py                 多语言 OCR 与已安装语言包回退
  monitor.py             稳定帧、冷却、通知与自动处理
  discord_notifier.py    私密 Discord Webhook 与截图附件
  ui.py / theme.py       PySide6 像素风 UI 与本地化字体
tools/analyze_samples.py 参考截图回归工具
tests/                   视觉、语言、配置与设备选择测试
```
