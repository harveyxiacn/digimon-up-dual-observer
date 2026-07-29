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
    QComboBox,
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
from .config import (
    AppConfig,
    load_config,
    save_ui_language,
    save_webhook,
)
from .discord_notifier import DiscordNotifier
from .discovery import detect_running_emulators
from .i18n import Translator, language_options
from .monitor import MonitorController
from .theme import (
    COLORS,
    DigitalBackdrop,
    apply_pixel_font,
    install_pixel_fonts,
)


class EventBus(QObject):
    log = Signal(str, str)
    frame = Signal(str, object)
    status = Signal(str, str)
    discord_test = Signal(bool, str)


def normalized_selected_serials(
    devices: list[AdbDevice],
    selected: set[str],
    *,
    allow_multiple: bool,
) -> list[str]:
    """Keep valid selections in ADB order and choose one safe default."""
    online = [device for device in devices if device.state == "device"]
    ordered = [device.serial for device in online if device.serial in selected]
    if not ordered:
        ordered = [
            device.serial for device in online if device.is_safe_default
        ][:1]
    limit = 2 if allow_multiple else 1
    return ordered[:limit]


class PreviewCard(QFrame):
    def __init__(self, index: int, translator: Translator):
        super().__init__()
        self.index = index
        self.tr = translator
        self.serial = ""
        self.has_frame = False
        self.current_status = "OFFLINE"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.name_label = QLabel()
        self.name_label.setObjectName("Muted")
        self.status_label = QLabel()
        self.status_label.setObjectName("StatusOffline")
        header.addWidget(self.name_label)
        header.addStretch()
        header.addWidget(self.status_label)
        self.preview = QLabel()
        self.preview.setObjectName("Preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(250, 330)
        layout.addLayout(header)
        layout.addWidget(self.preview, 1)
        self.retranslate()

    def assign(self, device: AdbDevice, alias: str = "") -> None:
        self.serial = device.serial
        self.has_frame = False
        model = device.model.replace("_", " ") or "ANDROID"
        label = alias or model
        self.name_label.setText(f"{label.upper()} // {device.serial}")
        self.set_status("LINKING")

    def clear(self) -> None:
        self.serial = ""
        self.has_frame = False
        self.name_label.setText(
            self.tr("preview.link_waiting", index=self.index)
        )
        self.preview.clear()
        self.preview.setText(self.tr("preview.waiting"))
        self.set_status("OFFLINE")

    def set_status(self, status: str) -> None:
        self.current_status = status
        self.status_label.setText(self.tr(f"status.{status.lower()}"))
        if status == "ONLINE":
            self.status_label.setObjectName("StatusOnline")
        elif status in ("LINKING", "RETRYING"):
            self.status_label.setObjectName("StatusLinking")
        else:
            self.status_label.setObjectName("StatusOffline")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def retranslate(self) -> None:
        if not self.serial:
            self.name_label.setText(
                self.tr("preview.link_waiting", index=self.index)
            )
        if not self.has_frame:
            self.preview.setText(self.tr("preview.waiting"))
        self.set_status(self.current_status)

    def show_frame(self, frame) -> None:
        self.has_frame = True
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
    def __init__(
        self,
        config: AppConfig,
        font_families: dict[str, str] | None = None,
    ):
        super().__init__()
        self.config = config
        self.tr = Translator(config.ui.language)
        self.config.ui.language = self.tr.language
        self.font_families = font_families or {}
        self.bus = EventBus()
        self.adb = AdbClient(
            config.adb.executable,
            config.adb.command_timeout_seconds,
            self.tr,
        )
        self.notifier = DiscordNotifier(
            config.webhook_url,
            translator=self.tr,
        )
        self.controller = MonitorController(
            config=config,
            adb=self.adb,
            notifier=self.notifier,
            log_callback=self.bus.log.emit,
            frame_callback=self.bus.frame.emit,
            status_callback=self.bus.status.emit,
            translator=self.tr,
        )
        self.devices: list[AdbDevice] = []
        self._updating_device_checks = False
        self.preview_cards = [
            PreviewCard(1, self.tr),
            PreviewCard(2, self.tr),
        ]
        self.setWindowTitle("DIGIMON UP // OBSERVER")
        self.resize(1180, 820)
        self.setMinimumSize(980, 700)
        self._build_ui()
        self._connect_signals()
        self.retranslate_ui()
        self.refresh_devices()

    def _build_ui(self) -> None:
        root = DigitalBackdrop()
        root.setObjectName("Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(22, 18, 22, 18)
        root_layout.setSpacing(12)

        header = QHBoxLayout()
        title_column = QVBoxLayout()
        self.title = QLabel("DIGIMON UP // OBSERVER")
        self.title.setObjectName("Title")
        self.title.setMinimumHeight(36)
        self.subtitle = QLabel()
        self.subtitle.setObjectName("Subtitle")
        self.subtitle.setMinimumHeight(16)
        title_column.addWidget(self.title)
        title_column.addWidget(self.subtitle)
        header.addLayout(title_column)
        header.addStretch()
        self.language_label = QLabel()
        self.language_label.setObjectName("Muted")
        self.language_combo = QComboBox()
        for option in language_options():
            self.language_combo.addItem(option.name, option.code)
        language_index = self.language_combo.findData(self.tr.language)
        self.language_combo.setCurrentIndex(max(0, language_index))
        header.addWidget(self.language_label)
        header.addWidget(self.language_combo)
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

        self.devices_group = QGroupBox()
        devices_layout = QVBoxLayout(self.devices_group)
        self.multi_device_mode = QCheckBox()
        self.multi_device_mode.setChecked(False)
        devices_layout.addWidget(self.multi_device_mode)
        self.device_list = QListWidget()
        self.device_list.setMinimumHeight(140)
        devices_layout.addWidget(self.device_list)
        self.discovery_label = QLabel()
        self.discovery_label.setObjectName("Muted")
        self.discovery_label.setWordWrap(True)
        devices_layout.addWidget(self.discovery_label)
        device_buttons = QHBoxLayout()
        self.refresh_button = QPushButton()
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("127.0.0.1:5555")
        self.connect_button = QPushButton()
        device_buttons.addWidget(self.refresh_button)
        devices_layout.addLayout(device_buttons)
        connect_row = QHBoxLayout()
        connect_row.addWidget(self.address_edit, 1)
        connect_row.addWidget(self.connect_button)
        devices_layout.addLayout(connect_row)
        layout.addWidget(self.devices_group)

        self.webhook_group = QGroupBox()
        webhook_layout = QVBoxLayout(self.webhook_group)
        self.webhook_edit = QLineEdit(self.config.webhook_url)
        self.webhook_edit.setEchoMode(QLineEdit.Password)
        self.webhook_edit.setPlaceholderText("Discord Webhook URL")
        self.test_button = QPushButton()
        webhook_layout.addWidget(self.webhook_edit)
        webhook_layout.addWidget(self.test_button)
        layout.addWidget(self.webhook_group)

        self.protocol_group = QGroupBox()
        protocol_layout = QVBoxLayout(self.protocol_group)
        self.auto_click = QCheckBox()
        self.auto_click.setChecked(self.config.monitor.automation_enabled)
        protocol_layout.addWidget(self.auto_click)
        self.protocol_text = QLabel()
        self.protocol_text.setObjectName("Muted")
        self.protocol_text.setWordWrap(True)
        protocol_layout.addWidget(self.protocol_text)
        layout.addWidget(self.protocol_group)

        actions = QHBoxLayout()
        self.start_button = QPushButton()
        self.start_button.setObjectName("Primary")
        self.stop_button = QPushButton()
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

        self.preview_group = QGroupBox()
        preview_layout = QHBoxLayout(self.preview_group)
        for card in self.preview_cards:
            preview_layout.addWidget(card, 1)
        self.preview_cards[1].setVisible(False)
        layout.addWidget(self.preview_group, 3)

        self.log_group = QGroupBox()
        log_layout = QVBoxLayout(self.log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(800)
        self.log_view.setMinimumHeight(150)
        log_layout.addWidget(self.log_view)
        layout.addWidget(self.log_group, 2)
        return panel

    def _connect_signals(self) -> None:
        self.language_combo.currentIndexChanged.connect(
            self.on_language_changed
        )
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.multi_device_mode.toggled.connect(self.on_monitor_mode_changed)
        self.device_list.itemChanged.connect(self.on_device_check_changed)
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

    def retranslate_ui(self) -> None:
        self.subtitle.setText(self.tr("app.subtitle"))
        self.language_label.setText(self.tr("language.label"))
        self.devices_group.setTitle(self.tr("group.devices"))
        self.multi_device_mode.setText(self.tr("devices.multi"))
        if not self.discovery_label.text():
            self.discovery_label.setText(self.tr("devices.scanning"))
        self.refresh_button.setText(self.tr("devices.refresh"))
        self.connect_button.setText(self.tr("devices.connect"))
        self.webhook_group.setTitle(self.tr("group.discord"))
        self.test_button.setText(self.tr("discord.test"))
        self.protocol_group.setTitle(self.tr("group.protocol"))
        self.auto_click.setText(self.tr("automation.enable"))
        self.protocol_text.setText(self.tr("protocol.text"))
        self.start_button.setText(self.tr("action.start"))
        self.stop_button.setText(self.tr("action.stop"))
        self.preview_group.setTitle(
            self.tr(
                "preview.multi"
                if self.multi_device_mode.isChecked()
                else "preview.single"
            )
        )
        self.log_group.setTitle(self.tr("group.events"))
        for card in self.preview_cards:
            card.retranslate()

    @Slot(int)
    def on_language_changed(self, index: int) -> None:
        language = self.language_combo.itemData(index)
        if not language or language == self.tr.language:
            return
        self.tr.set_language(language)
        self.config.ui.language = self.tr.language
        save_ui_language(self.config.project_dir, self.tr.language)
        app = QApplication.instance()
        if app is not None:
            apply_pixel_font(app, self.font_families, self.tr.language)
        self.retranslate_ui()
        self.refresh_devices()
        self.append_log(
            "info",
            self.tr(
                "language.changed",
                language=self.language_combo.currentText(),
            ),
        )

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
        normalized = normalized_selected_serials(
            self.devices,
            selected,
            allow_multiple=self.multi_device_mode.isChecked(),
        )
        self._updating_device_checks = True
        self.device_list.clear()
        for device in self.devices:
            alias = self.config.adb.device_aliases.get(device.serial, "")
            suffix = (
                ""
                if device.is_safe_default
                else self.tr("device.default_excluded")
            )
            model = (
                device.model.replace("_", " ").strip()
                or self.tr("device.android")
            )
            device_name = f"{model} · {device.serial}"
            display_name = (
                f"{alias} · {device_name}" if alias else device_name
            )
            item = QListWidgetItem(display_name + suffix)
            item.setData(Qt.UserRole, device.serial)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            checked = device.serial in normalized
            if device.state != "device":
                checked = False
                item.setText(item.text() + f"  [{device.state}]")
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.device_list.addItem(item)
        self._updating_device_checks = False
        running_emulators = detect_running_emulators()
        connected_emulators = [
            device
            for device in self.devices
            if device.state == "device" and device.is_safe_default
        ]
        if running_emulators:
            separator = "、" if self.tr.language != "en" else ", "
            names = separator.join(
                self.tr(f"emulator.{item.key}.name")
                for item in running_emulators
            )
            if connected_emulators:
                self.discovery_label.setText(
                    self.tr(
                        "discovery.process_scan",
                        names=names,
                        count=len(connected_emulators),
                    )
                )
            else:
                hints = "\n".join(
                    "• "
                    + self.tr(f"emulator.{item.key}.name")
                    + ": "
                    + self.tr(f"emulator.{item.key}.hint")
                    for item in running_emulators
                )
                self.discovery_label.setText(
                    self.tr(
                        "discovery.detected_no_adb",
                        hints=hints,
                    )
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
                self.tr(
                    "discovery.connected",
                    count=len(connected_emulators),
                )
            )
        else:
            self.discovery_label.setText(self.tr("discovery.none"))
        self.append_log(
            "info",
            self.tr("log.adb_found", count=len(self.devices)),
        )

    @Slot(bool)
    def on_monitor_mode_changed(self, allow_multiple: bool) -> None:
        selected = {
            self.device_list.item(index).data(Qt.UserRole)
            for index in range(self.device_list.count())
            if self.device_list.item(index).checkState() == Qt.Checked
        }
        normalized = set(
            normalized_selected_serials(
                self.devices,
                selected,
                allow_multiple=allow_multiple,
            )
        )
        self._updating_device_checks = True
        for index in range(self.device_list.count()):
            item = self.device_list.item(index)
            item.setCheckState(
                Qt.Checked
                if item.data(Qt.UserRole) in normalized
                else Qt.Unchecked
            )
        self._updating_device_checks = False
        self.preview_cards[1].setVisible(allow_multiple)
        self.preview_group.setTitle(
            self.tr("preview.multi" if allow_multiple else "preview.single")
        )
        mode = self.tr("mode.multi" if allow_multiple else "mode.single")
        self.append_log(
            "info",
            self.tr("log.mode_changed", mode=mode),
        )

    @Slot(QListWidgetItem)
    def on_device_check_changed(self, changed_item: QListWidgetItem) -> None:
        if self._updating_device_checks or changed_item.checkState() != Qt.Checked:
            return
        if self.multi_device_mode.isChecked():
            checked_count = sum(
                self.device_list.item(index).checkState() == Qt.Checked
                for index in range(self.device_list.count())
            )
            if checked_count > 2:
                self._updating_device_checks = True
                changed_item.setCheckState(Qt.Unchecked)
                self._updating_device_checks = False
                self.append_log(
                    "warning",
                    self.tr("log.max_two"),
                )
            return
        self._updating_device_checks = True
        for index in range(self.device_list.count()):
            item = self.device_list.item(index)
            if item is not changed_item:
                item.setCheckState(Qt.Unchecked)
        self._updating_device_checks = False

    @Slot()
    def connect_address(self) -> None:
        try:
            result = self.adb.connect(self.address_edit.text())
            self.append_log("info", f"[ADB] {result}")
            self.refresh_devices()
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.tr("dialog.adb_connect_failed"),
                str(exc),
            )

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
            QMessageBox.information(
                self,
                self.tr("dialog.select_device_title"),
                self.tr("dialog.select_device_body"),
            )
            return
        if not self.multi_device_mode.isChecked() and len(devices) > 1:
            devices = devices[:1]
        if len(devices) > 2:
            QMessageBox.information(
                self,
                self.tr("dialog.max_two_title"),
                self.tr("dialog.max_two_body"),
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
        self.multi_device_mode.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.connect_button.setEnabled(False)
        mode = self.tr(
            "mode.automation"
            if self.auto_click.isChecked()
            else "mode.observation"
        )
        self.append_log(
            "info",
            self.tr(
                "log.links_started",
                count=len(devices),
                mode=mode,
            ),
        )

    @Slot()
    def stop_monitoring(self) -> None:
        self.controller.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.device_list.setEnabled(True)
        self.multi_device_mode.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.connect_button.setEnabled(True)
        self.append_log("info", self.tr("log.links_stopped"))

    @Slot()
    def test_discord(self) -> None:
        webhook = self.webhook_edit.text().strip()
        self.notifier.set_webhook(webhook)
        if webhook:
            save_webhook(self.config.project_dir, webhook)
        self.test_button.setEnabled(False)

        def send() -> None:
            try:
                self.notifier.send(self.tr("discord.test_message"))
                self.bus.discord_test.emit(
                    True,
                    self.tr("discord.test_success"),
                )
            except Exception as exc:
                self.bus.discord_test.emit(False, str(exc))

        threading.Thread(target=send, daemon=True).start()

    @Slot(bool, str)
    def on_discord_test(self, success: bool, message: str) -> None:
        self.test_button.setEnabled(True)
        if success:
            self.append_log("info", f"[DISCORD] {message}")
        else:
            QMessageBox.warning(
                self,
                self.tr("discord.test_failed"),
                message,
            )

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
    translator = Translator(config.ui.language)
    config.ui.language = translator.language
    font_families = install_pixel_fonts(app, config.project_dir)
    apply_pixel_font(app, font_families, translator.language)
    window = MainWindow(config, font_families)
    window.show()
    return app.exec()
