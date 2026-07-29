from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QApplication, QWidget


COLORS = {
    "ink": "#040B1C",
    "navy": "#061A38",
    "panel": "#082954",
    "panel_hi": "#0C3D70",
    "cyan": "#35E8FF",
    "blue": "#168DFF",
    "yellow": "#FFD83D",
    "green": "#53F58A",
    "magenta": "#F34BD2",
    "red": "#FF5D5D",
    "text": "#EAFBFF",
    "muted": "#8CB7CB",
}


class DigitalBackdrop(QWidget):
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#071B3A"))
        gradient.setColorAt(0.55, QColor("#04152D"))
        gradient.setColorAt(1, QColor("#020817"))
        painter.fillRect(self.rect(), gradient)

        grid_pen = QPen(QColor(27, 113, 166, 38), 1)
        painter.setPen(grid_pen)
        step = 24
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)

        circuit_pen = QPen(QColor(53, 232, 255, 42), 2)
        painter.setPen(circuit_pen)
        w, h = self.width(), self.height()
        for offset in (0, 110, 260):
            points = [
                QPointF(0, 90 + offset),
                QPointF(w * 0.18, 90 + offset),
                QPointF(w * 0.24, 135 + offset),
                QPointF(w * 0.52, 135 + offset),
            ]
            painter.drawPolyline(QPolygonF(points))
            painter.fillRect(
                QRectF(w * 0.52, 131 + offset, 8, 8),
                QColor(COLORS["yellow"]),
            )
        painter.end()
        super().paintEvent(event)


FONT_FILES = {
    "zh_CN": "fusion-pixel-12px-proportional-zh_hans.ttf",
    "zh_TW": "fusion-pixel-12px-proportional-zh_hant.ttf",
    "en": "fusion-pixel-12px-proportional-latin.ttf",
    "ja": "fusion-pixel-12px-proportional-ja.ttf",
}

SYSTEM_FONT_FALLBACKS = {
    "zh_CN": "Microsoft YaHei UI",
    "zh_TW": "Microsoft JhengHei UI",
    "en": "Segoe UI",
    "ja": "Yu Gothic UI",
}


def install_pixel_fonts(
    app: QApplication,
    project_dir: Path,
) -> dict[str, str]:
    font_dir = project_dir / "assets" / "fonts"
    installed: dict[str, str] = {}
    for language, filename in FONT_FILES.items():
        font_path = font_dir / filename
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            installed[language] = families[0]
    return installed


def apply_pixel_font(
    app: QApplication,
    font_families: dict[str, str],
    language: str,
) -> str:
    family = font_families.get(
        language,
        SYSTEM_FONT_FALLBACKS.get(language, "Segoe UI"),
    )
    font = QFont(family, 11)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)
    app.setStyleSheet(stylesheet(family))
    return family


def stylesheet(font_family: str) -> str:
    c = COLORS
    return f"""
    * {{
        font-family: "{font_family}";
        color: {c["text"]};
    }}
    QMainWindow, QWidget#Root {{
        background: transparent;
    }}
    QLabel#Title {{
        color: {c["cyan"]};
        font-size: 25px;
        letter-spacing: 2px;
    }}
    QLabel#Subtitle, QLabel#Muted {{
        color: {c["muted"]};
        font-size: 12px;
    }}
    QLabel#Chip {{
        background: {c["yellow"]};
        color: {c["ink"]};
        border: 2px solid #FFF3A0;
        padding: 5px 10px;
        font-size: 12px;
    }}
    QGroupBox {{
        background-color: rgba(5, 29, 61, 225);
        border: 2px solid {c["panel_hi"]};
        border-top-color: {c["cyan"]};
        margin-top: 14px;
        padding: 16px 12px 12px 12px;
        font-size: 13px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        color: {c["yellow"]};
        background: {c["navy"]};
    }}
    QListWidget, QPlainTextEdit, QLineEdit, QComboBox {{
        background: rgba(1, 12, 29, 235);
        border: 2px solid {c["panel_hi"]};
        selection-background-color: {c["blue"]};
        padding: 7px;
    }}
    QLineEdit:focus, QListWidget:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border-color: {c["cyan"]};
    }}
    QComboBox QAbstractItemView {{
        background: {c["navy"]};
        border: 2px solid {c["cyan"]};
        selection-background-color: {c["blue"]};
    }}
    QListWidget::item {{
        min-height: 30px;
        border-bottom: 1px solid #174B72;
        padding: 4px;
    }}
    QListWidget::indicator, QCheckBox::indicator {{
        width: 18px;
        height: 18px;
    }}
    QCheckBox {{
        spacing: 8px;
        color: {c["text"]};
    }}
    QPushButton {{
        background: {c["panel_hi"]};
        border: 2px solid {c["blue"]};
        border-bottom-color: #064A91;
        padding: 8px 14px;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background: #0E5793;
        border-color: {c["cyan"]};
    }}
    QPushButton:pressed {{
        background: #06213F;
        padding-top: 10px;
        padding-bottom: 6px;
    }}
    QPushButton:disabled {{
        color: #527286;
        border-color: #27445A;
        background: #102238;
    }}
    QPushButton#Primary {{
        color: {c["ink"]};
        background: {c["cyan"]};
        border-color: #B9F8FF;
        font-size: 14px;
    }}
    QPushButton#Stop {{
        background: {c["magenta"]};
        color: white;
        border-color: #FFB5F0;
    }}
    QLabel#Preview {{
        background: rgba(1, 8, 22, 235);
        border: 2px solid {c["panel_hi"]};
        color: {c["muted"]};
    }}
    QLabel#StatusOnline {{
        color: {c["green"]};
        background: #062A23;
        border: 1px solid {c["green"]};
        padding: 3px 7px;
    }}
    QLabel#StatusLinking {{
        color: {c["yellow"]};
        background: #2D260A;
        border: 1px solid {c["yellow"]};
        padding: 3px 7px;
    }}
    QLabel#StatusOffline {{
        color: {c["muted"]};
        background: #101B2A;
        border: 1px solid #35506A;
        padding: 3px 7px;
    }}
    QScrollBar:vertical {{
        width: 12px;
        background: #06172D;
    }}
    QScrollBar::handle:vertical {{
        background: {c["blue"]};
        min-height: 25px;
    }}
    """
