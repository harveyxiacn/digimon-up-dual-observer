from __future__ import annotations

from datetime import datetime
import sys
import threading

import cv2
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor, QImage, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .adb import AdbClient, AdbDevice
from .config import AppConfig, load_config, save_webhook
from .discord_notifier import DiscordNotifier
from .discovery import detect_running_emulators
from .monitor import MonitorController
from .theme import COLORS, DigitalBackdrop, install_pixel_font, stylesheet


class EventBus(QObject):
    log = Signal(str, str)
    frame = Signal(str, object)
    status = Signal(str, str)
    discord_test = Signal(bool, str)


class PreviewCard(QFrame):
    def __init__(self, index: int):
        super().__init__()
        self.serial = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.name_label = QLabel(f"LINK {index} // WAITING")
        self.name_label.setObjectName("Muted")
        self.status_label = QLabel("OFFLINE")
        self.status_label.setObjectName("StatusOffline")
        header.addWidget(self.name_label)
        header.addStretch()
        header.addWidget(self.status_label)
        self.preview = QLabel("等待模拟器画面\n\nADB SCREEN CHANNEL")
        self.preview.setObjectName("Preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(250, 330)
        layout.addLayout(header)
        layout.addWidget(self.preview, 1)

    def assign(self, device: AdbDevice, alias: str = "") -> None:
        self.serial = device.serial
        model = device.model.replace("_", " ") or "ANDROID"
        label = alias or model
        self.name_label.setText(f"{label.upper()} // {device.serial}")
        self.set_status("LINKING")

    def clear(self) -> None:
        self.serial = ""
        self.name_label.setText("LINK // WAITING")
        self.preview.clear()
        self.preview.setText("等待模拟器画面\n\nADB SCREEN CHANNEL")
        self.set_status("OFFLINE")

    def set_status(self, status: str) -> None:
        self.status_label.setText(status)
        if status == "ONLINE":
            self.status_label.setObjectName("StatusOnline")
        elif status in ("LINKING", "RETRYING"):
            self.status_label.setObjectName("StatusLinking")
        else:
            self.status_label.setObjectName("StatusOffline")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def show_frame(self, frame) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, channels = rgb.shape
        image = QImage(
            rgb.data,
            w,
            h,
            channels * w,
            QImage.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview.setPixmap(pixmap)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.bus = EventBus()
        self.adb = AdbClient(
            config.adb.executable,
            config.adb.command_timeout_seconds,
        )
        self.notifier = DiscordNotifier(config.webhook_url)
        self.controller = MonitorController(
            config=config,
            adb=self.adb,
            notifier=self.notifier,
            log_callback=self.bus.log.emit,
            frame_callback=self.bus.frame.emit,
            status_callback=self.bus.status.emit,
        )
        self.devices: list[AdbDevice] = []
        self.preview_cards = [PreviewCard(1), PreviewCard(2)]
        self.setWindowTitle("DIGIMON UP // DUAL OBSERVER")
        self.resize(1180, 820)
        self.setMinimumSize(980, 700)
        self._build_ui()
        self._connect_signals()
        self.refresh_devices()

    def _build_ui(self) -> None:
        root = DigitalBackdrop()
        root.setObjectName("Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 18, 22, 18)
        root_layout.setSpacing(12)

        header = QHBoxLayout()
        title_column = QVBoxLayout()
        title = QLabel("DIGIMON UP // DUAL OBSERVER")
        title.setObjectName("Title")
        subtitle = QLabel(
            "DIGITAL WORLD LINK  •  TASK WATCH  •  EQUIPMENT PROTOCOL"
        )
        subtitle.setObjectName("Subtitle")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        header.addLayout(title_column)
        header.addStretch()
        chip = QLabel("D-3  /  D-ARK  /  D-SCANNER")
        chip.setObjectName("Chip")
        header.addWidget(chip)
        root_layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        controls = self._build_controls()
        monitor = self._build_monitor_area()
        splitter.addWidget(controls)
        splitter.addWidget(monitor)
        splitter.setSizes([365, 760])
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumWidth(430)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        devices_group = QGroupBox("01 // 模拟器链路")
        devices_layout = QVBoxLayout(devices_group)
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(140)
        devices_layout.addWidget(self.device_list)
        self.discovery_label = QLabel("正在扫描模拟器进程…")
        self.discovery_label.setObjectName("Muted")
        self.discovery_label.setWordWrap(True)
        devices_layout.addWidget(self.discovery_label)
        device_buttons = QHBoxLayout()
        self.refresh_button = QPushButton("刷新 ADB")
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("127.0.0.1:5555")
        self.connect_button = QPushButton("连接")
        device_buttons.addWidget(self.refresh_button)
        devices_layout.addLayout(device_buttons)
        connect_row = QHBoxLayout()
        connect_row.addWidget(self.address_edit, 1)
        connect_row.addWidget(self.connect_button)
        devices_layout.addLayout(connect_row)
        layout.addWidget(devices_group)

        webhook_group = QGroupBox("02 // Discord 通讯")
        webhook_layout = QVBoxLayout(webhook_group)
        self.webhook_edit = QLineEdit(self.config.webhook_url)
        self.webhook_edit.setEchoMode(QLineEdit.Password)
        self.webhook_edit.setPlaceholderText("Discord Webhook URL")
        self.test_button = QPushButton("发送测试信号")
        webhook_layout.addWidget(self.webhook_edit)
        webhook_layout.addWidget(self.test_button)
        layout.addWidget(webhook_group)

        protocol_group = QGroupBox("03 // 自动处理协议")
        protocol_layout = QVBoxLayout(protocol_group)
        self.auto_click = QCheckBox("启用自动点击")
        self.auto_click.setChecked(self.config.monitor.automation_enabled)
        protocol_layout.addWidget(self.auto_click)
        protocol_text = QLabel(
            "[OK] 绿色任务框 → 领取\n"
            "[OK] 绿色上箭头 → 装备后出售旧件\n"
            "[OK] 红色下箭头 → 出售\n"
            "[!] 特殊抽卡 / 投影券不足 → Discord"
        )
        protocol_text.setObjectName("Muted")
        protocol_text.setWordWrap(True)
        protocol_layout.addWidget(protocol_text)
        layout.addWidget(protocol_group)

        actions = QHBoxLayout()
        self.start_button = QPushButton("START LINK")
        self.start_button.setObjectName("Primary")
        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("Stop")
        self.stop_button.setEnabled(False)
        actions.addWidget(self.start_button, 2)
        actions.addWidget(self.stop_button, 1)
        layout.addLayout(actions)
        layout.addStretch()
        return panel

    def _build_monitor_area(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(10)

        preview_group = QGroupBox("LIVE // 双通道画面")
        preview_layout = QHBoxLayout(preview_group)
        for card in self.preview_cards:
            preview_layout.addWidget(card, 1)
        layout.addWidget(preview_group, 3)

        log_group = QGroupBox("EVENT STREAM // 事件日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(800)
        self.log_view.setMinimumHeight(150)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group, 2)
        return panel

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.connect_button.clicked.connect(self.connect_address)
        self.address_edit.returnPressed.connect(self.connect_address)
        self.test_button.clicked.connect(self.test_discord)
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.auto_click.toggled.connect(
            self.controller.set_automation_enabled
        )
        self.bus.log.connect(self.append_log)
        self.bus.frame.connect(self.on_frame)
        self.bus.status.connect(self.on_status)
        self.bus.discord_test.connect(self.on_discord_test)

    @Slot()
    def refresh_devices(self) -> None:
        selected = {
            item.data(Qt.UserRole)
            for index in range(self.device_list.count())
            if (item := self.device_list.item(index)).checkState()
            == Qt.Checked
        }
        for address in self.config.adb.connect_addresses:
            try:
                self.adb.connect(address)
            except Exception:
                # It is normal for a configured emulator to be closed.
                pass
        try:
            self.devices = self.adb.list_devices()
        except Exception as exc:
            QMessageBox.warning(self, "ADB", str(exc))
            return
        self.device_list.clear()
        for device in self.devices:
            alias = self.config.adb.device_aliases.get(device.serial, "")
            suffix = "" if device.is_safe_default else "  [默认不勾选]"
            display_name = (
                f"{alias} · {device.display_name}" if alias else device.display_name
            )
            item = QListWidgetItem(display_name + suffix)
            item.setData(Qt.UserRole, device.serial)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            checked = (
                device.serial in selected
                or (not selected and device.is_safe_default)
            )
            if device.state != "device":
                checked = False
                item.setText(item.text() + f"  [{device.state}]")
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.device_list.addItem(item)
        running_emulators = detect_running_emulators()
        connected_emulators = [
            device
            for device in self.devices
            if device.state == "device" and device.is_safe_default
        ]
        if running_emulators:
            names = "、".join(item.name for item in running_emulators)
            if connected_emulators:
                self.discovery_label.setText(
                    f"进程扫描：{names}\n"
                    f"ADB 已连接 {len(connected_emulators)} 台模拟器，可勾选后启动。"
                )
            else:
                hints = "\n".join(
                    f"• {item.name}：{item.adb_hint}"
                    for item in running_emulators
                )
                self.discovery_label.setText(
                    f"检测到模拟器进程，但没有可用 ADB 设备：\n{hints}"
                )
                suggested = next(
                    (
                        item.suggested_address
                        for item in running_emulators
                        if item.suggested_address
                    ),
                    "",
                )
                if suggested and not self.address_edit.text().strip():
                    self.address_edit.setPlaceholderText(suggested)
        elif connected_emulators:
            self.discovery_label.setText(
                f"ADB 已连接 {len(connected_emulators)} 台模拟器，可勾选后启动。"
            )
        else:
            self.discovery_label.setText(
                "未发现常见模拟器进程或 ADB 设备。请先启动模拟器，"
                "并在其设置中开启 ADB/本地连接。"
            )
        self.append_log("info", f"[SYSTEM] ADB 发现 {len(self.devices)} 个设备")

    @Slot()
    def connect_address(self) -> None:
        try:
            result = self.adb.connect(self.address_edit.text())
            self.append_log("info", f"[ADB] {result}")
            self.refresh_devices()
        except Exception as exc:
            QMessageBox.warning(self, "ADB 连接失败", str(exc))

    def _selected_devices(self) -> list[AdbDevice]:
        serials = {
            self.device_list.item(index).data(Qt.UserRole)
            for index in range(self.device_list.count())
            if self.device_list.item(index).checkState() == Qt.Checked
        }
        return [
            device
            for device in self.devices
            if device.serial in serials and device.state == "device"
        ]

    @Slot()
    def start_monitoring(self) -> None:
        devices = self._selected_devices()
        if not devices:
            QMessageBox.information(self, "请选择模拟器", "至少勾选一个在线模拟器。")
            return
        if len(devices) > 2:
            QMessageBox.information(
                self,
                "最多两个通道",
                "本版本同时监控最多两个模拟器，请取消多余勾选。",
            )
            return
        webhook = self.webhook_edit.text().strip()
        self.notifier.set_webhook(webhook)
        if webhook:
            save_webhook(self.config.project_dir, webhook)
        for card in self.preview_cards:
            card.clear()
        for card, device in zip(self.preview_cards, devices[:2]):
            card.assign(
                device,
                self.config.adb.device_aliases.get(device.serial, ""),
            )
        self.controller.start(devices)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.device_list.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.connect_button.setEnabled(False)
        mode = "AUTO" if self.auto_click.isChecked() else "OBSERVE"
        self.append_log(
            "info",
            f"[SYSTEM] {len(devices)} 条链路启动 // MODE={mode}",
        )

    @Slot()
    def stop_monitoring(self) -> None:
        self.controller.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.device_list.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.connect_button.setEnabled(True)
        self.append_log("info", "[SYSTEM] 所有监控链路已停止")

    @Slot()
    def test_discord(self) -> None:
        webhook = self.webhook_edit.text().strip()
        self.notifier.set_webhook(webhook)
        if webhook:
            save_webhook(self.config.project_dir, webhook)
        self.test_button.setEnabled(False)

        def send() -> None:
            try:
                self.notifier.send(
                    "🟦 DIGIMON UP // DUAL OBSERVER 测试信号已连接。"
                )
                self.bus.discord_test.emit(True, "Discord 测试信号发送成功")
            except Exception as exc:
                self.bus.discord_test.emit(False, str(exc))

        threading.Thread(target=send, daemon=True).start()

    @Slot(bool, str)
    def on_discord_test(self, success: bool, message: str) -> None:
        self.test_button.setEnabled(True)
        if success:
            self.append_log("info", f"[DISCORD] {message}")
        else:
            QMessageBox.warning(self, "Discord 测试失败", message)

    @Slot(str, str)
    def append_log(self, level: str, message: str) -> None:
        color = {
            "error": COLORS["red"],
            "warning": COLORS["yellow"],
            "info": COLORS["cyan"],
        }.get(level.lower(), COLORS["text"])
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        stamp = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"{stamp}  {message}\n", fmt)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    @Slot(str, object)
    def on_frame(self, serial: str, frame) -> None:
        for card in self.preview_cards:
            if card.serial == serial:
                card.show_frame(frame)
                break

    @Slot(str, str)
    def on_status(self, serial: str, status: str) -> None:
        for card in self.preview_cards:
            if card.serial == serial:
                card.set_status(status)
                break

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.controller.stop()
        event.accept()


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    config = load_config()
    font_family = install_pixel_font(app, config.project_dir)
    app.setStyleSheet(stylesheet(font_family))
    window = MainWindow(config)
    window.show()
    return app.exec()
