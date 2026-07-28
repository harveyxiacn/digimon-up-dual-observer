# DIGIMON UP // DUAL OBSERVER

一个面向 Windows、BlueStacks 与 LDPlayer（雷电模拟器）的双通道画面监控器。程序通过 ADB 直接取得安卓画面并发送点击，不依赖鼠标位置，因此两个模拟器可以并排、最小化或放在不同显示器上。

![像素风双通道监控界面](docs/ui-preview.png)

## 已实现

- 同时监控最多两个已勾选的 ADB 模拟器，并在桌面 UI 中显示实时缩略图。
- 启动和刷新时扫描 Windows 进程，识别 BlueStacks、雷电、夜神、MuMu、逍遥与 Genymotion；检测到模拟器但没有 ADB 时显示对应开启提示。
- 连续两帧确认右侧任务卡的荧光绿色完成框，然后点击任务卡。
- 领取后连续确认全屏蓝色“报酬/点击关闭”层，再自动点击关闭并回到新任务。
- 每次领取前先做繁体中文 OCR。遇到“抽取技能卡片”或“抽取支援型数码宝贝/數碼寶貝”时阻止点击，向 Discord 发送文字和当前截图。
- 同时确认“出售”和“装备”两个大按钮后才进入装备处理：
  - 绿色向上箭头：点击“装备”；
  - 装备后旧装备出现红色向下箭头：点击“出售”；
  - 初次就是红色向下箭头：直接点击“出售”；
  - 箭头不明确：保持不动并写入日志。
- OCR 识别“全像/全息投影券不足”后发送 Discord 截图通知，并有冷却时间避免刷屏。
- 自动保存发生点击或告警时的截图到 `captures/`，运行日志写入 `logs/monitor.log`。
- 可随时取消“启用自动点击”，切换为只识别、不操作的观察模式。

## 安装与运行

本机已有依赖时，直接运行：

```powershell
.\run.ps1
```

也可以直接双击 `启动监控器.bat`。

在新电脑上首次安装：

```powershell
.\install.ps1
.\run.ps1
```

还需要：

1. 在 BlueStacks 与雷电模拟器设置中开启 ADB/本地调试。
2. 启动两个模拟器和游戏。
3. 打开监控器并点“刷新 ADB”。
4. 把 `config.local.example.yaml` 复制为 `config.local.yaml`，填写本机 BlueStacks ADB 端口与设备别名。该文件不会进入 Git。雷电通常会以 `emulator-5554` 自动出现。
5. 只勾选需要监控的两个模拟器。Quest、手机等其他 ADB 设备默认不会被勾选。
6. 建议先关闭“启用自动点击”，观察识别日志几分钟；画面与样本一致后再开启。

程序通过无需管理员权限的 Windows Tool Help 进程快照读取主进程文件名，不会读取游戏账号、窗口标题、进程路径、命令行或模拟器内文件。BlueStacks 需要在“设置 → 高级”开启 Android Debug Bridge；雷电应选择“开启本地连接”，不要开启远程连接；MuMu 可在问题诊断/多开器查看 ADB 端口。

- BlueStacks ADB 官方说明：<https://support.bluestacks.com/hc/en-us/articles/23925869130381-How-to-enable-Android-Debug-Bridge-on-BlueStacks-5>
- 雷电 ADB 本地连接说明：<https://pre-prod-web-next.ldplayer.net/blog/introduction-to-version-4.0.37-and-3.102-features.html>
- MuMu ADB 官方开发说明：<https://www.mumuplayer.com/help/win/developers-essentials-manual.html>

### Discord Webhook 与隐私

Webhook 有两种设置方式：

1. 在软件界面的“Discord 通讯”密码输入框中粘贴，然后点击“发送测试信号”或启动监控；程序会保存到本机 `.env`。
2. 将 `.env.example` 复制为 `.env`，填写 `DIGIMON_DISCORD_WEBHOOK_URL`。

`.env`、`config.local.yaml`、`captures/` 与 `logs/` 都已被 `.gitignore` 排除。不要把 Webhook 写入 `config.yaml`、源代码、Issue、截图或提交记录。如果 Webhook 曾经公开，应立即在 Discord 中删除并重新生成。

## 识别安全边界

- ADB 点击使用截图内的坐标，不会控制 Windows 鼠标。
- 任务领取需要“绿色边框 + OCR 有文字 + 连续两帧”三项同时成立。
- 奖励关闭需要蓝色遮罩覆盖屏幕中段绝大部分宽度并连续两帧成立；装备比较弹窗不会满足这个条件。
- 特殊任务优先级高于自动领取；只要 OCR 分类为特殊抽卡任务，就不点击。
- 装备动作必须先识别到成对的大号粉色/蓝色按钮，不会仅凭战斗画面里的箭头或血条点击。
- 未知装备状态默认不操作，而不是猜测。
- 两次动作之间默认至少间隔 2.5 秒；Discord 也有事件去重和冷却。

阈值、轮询时间与冷却时间都在 [config.yaml](config.yaml) 中。游戏更新 UI、改变语言或改变纵横比后，应先回到观察模式并重新校准。

## 离线验证

运行单元测试：

```powershell
python -m pytest
```

使用最初提供的六张截图做完整视觉/OCR 回归：

```powershell
python tools\analyze_samples.py "截图所在目录"
```

预期结果是两个已完成任务、一个特殊抽卡任务、两个更好装备和一个更差装备全部匹配。

## UI 视觉与字体

界面以 01–04 代数码终端的共同视觉语言重新设计：深蓝数字世界底色、青色电路网格、D-3 式多彩状态信号、D-Ark 式卡片边框，以及 D-Scanner 的红蓝警示分区。没有复制动画 Logo、角色图或游戏贴图。

繁体中文 UI 使用 **Fusion Pixel 12px Proportional zh_hant**。字体文件位于 `assets/fonts/`，依据同目录 `OFL.txt` 中的 SIL Open Font License 1.1 分发。

- 字体项目与授权：<https://github.com/TakWolf/fusion-pixel-font>
- Bandai D-Scanner 商品视觉参考：<https://www.bandai.co.jp/catalog/item.php?jan_cd=4543112120243000>
- Bandai D-Scanner 红/蓝版本资料：<https://www.atpress.ne.jp/news/328455>

## 项目结构

```text
digimon_monitor/
  adb.py                 ADB 设备、截图与点击
  vision.py              任务框和装备弹窗视觉识别
  ocr.py                 繁体中文任务/弹窗 OCR
  monitor.py             双设备循环、稳定帧、冷却与安全规则
  discord_notifier.py    Discord Webhook 与截图附件
  ui.py / theme.py       PySide6 像素风桌面 UI
tools/analyze_samples.py 六张参考图回归工具
tests/test_vision.py     核心分类与视觉单元测试
```
