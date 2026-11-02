import sys
import os
import platform
import socket
import shutil
import time
from collections import deque

import psutil
from PySide6.QtCore import Qt, QTimer, QPointF, QSettings
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QProgressBar, QFrame,
    QStackedWidget, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QComboBox, QAbstractItemView, QFormLayout, QFileDialog, QMessageBox
)

BG = "#0c0e14"
PANEL = "#151925"
BORDER = "#2a3042"
TEXT = "#f1f2fa"
MUTED = "#969eb4"
PURPLE = "#a78bfa"
BLUE = "#60a5fa"
GREEN = "#34d399"
YELLOW = "#fbbf24"


def human_bytes(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024


def card_style():
    return f"""
        QFrame#card {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 12px;
        }}
        QLabel {{ background: transparent; border: none; }}
    """


class InfoCard(QFrame):
    def __init__(self, title, value="--", accent=PURPLE):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(card_style())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        label = QLabel(title.upper())
        label.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; font-weight: bold;"
        )
        self.value = QLabel(value)
        self.value.setWordWrap(True)
        self.value.setStyleSheet(
            f"color: {accent}; font-size: 22px; font-weight: bold;"
        )
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        layout.addWidget(label)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)


class LineChart(QWidget):
    def __init__(self, title, color):
        super().__init__()
        self.title = title
        self.color = QColor(color)
        self.values = deque(maxlen=60)
        self.setMinimumHeight(210)

    def add_value(self, value):
        self.values.append(value)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(PANEL))
        p.setPen(QColor(TEXT))
        p.drawText(16, 25, self.title)
        current = self.values[-1] if self.values else 0
        p.setPen(self.color)
        p.drawText(self.width() - 72, 25, f"{current:.1f}%")

        left, right, top, bottom = 42, self.width() - 15, 48, self.height() - 25
        h = bottom - top
        w = right - left
        for tick in range(0, 101, 25):
            y = bottom - h * tick / 100
            p.setPen(QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine))
            p.drawLine(left, int(y), right, int(y))
            p.setPen(QColor(MUTED))
            p.drawText(3, int(y) + 4, f"{tick}%")

        if len(self.values) < 2 or w <= 0 or h <= 0:
            p.setPen(QColor(MUTED))
            p.drawText(left, top + 35, "Collecting history...")
            return

        points = [
            QPointF(left + i * w / (len(self.values) - 1),
                    bottom - max(0, min(100, v)) * h / 100)
            for i, v in enumerate(self.values)
        ]
        path = QPainterPath()
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)

        area = QPainterPath(path)
        area.lineTo(points[-1].x(), bottom)
        area.lineTo(points[0].x(), bottom)
        area.closeSubpath()
        fill = QColor(self.color)
        fill.setAlpha(28)
        p.fillPath(area, fill)
        p.setPen(QPen(self.color, 2))
        p.drawPath(path)



class CoreUsageWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.setStyleSheet(card_style())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title = QLabel("CPU CORE UTILIZATION")
        title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(title)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        layout.addLayout(self.grid)

        self.labels = []
        self.bars = []
        count = psutil.cpu_count(logical=True) or 1

        for i in range(count):
            item = QWidget()
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(2, 2, 2, 2)
            item_layout.setSpacing(4)

            label = QLabel(f"CPU {i}  •  0%")
            label.setStyleSheet(f"color: {TEXT}; font-size: 10px;")

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {BORDER};
                    border: none;
                    border-radius: 4px;
                    height: 7px;
                }}
                QProgressBar::chunk {{
                    background: {PURPLE};
                    border-radius: 4px;
                }}
            """)

            item_layout.addWidget(label)
            item_layout.addWidget(bar)
            self.grid.addWidget(item, i // 4, i % 4)
            self.labels.append(label)
            self.bars.append(bar)

    def update_values(self, values):
        for i, value in enumerate(values):
            if i >= len(self.bars):
                break
            value = max(0, min(100, value))
            self.labels[i].setText(f"CPU {i}  •  {value:.0f}%")
            self.bars[i].setValue(int(value))


class DiskIOChart(QWidget):
    def __init__(self):
        super().__init__()
        self.read_values = deque(maxlen=60)
        self.write_values = deque(maxlen=60)
        self.setMinimumHeight(205)

    def add_values(self, read_rate, write_rate):
        self.read_values.append(read_rate / (1024 ** 2))
        self.write_values.append(write_rate / (1024 ** 2))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(PANEL))

        p.setPen(QColor(TEXT))
        p.drawText(16, 25, "DISK READ / WRITE")

        p.setPen(QColor(BLUE))
        p.drawText(190, 25, "● Read")
        p.setPen(QColor(YELLOW))
        p.drawText(260, 25, "● Write")

        left, right = 48, self.width() - 18
        top, bottom = 48, self.height() - 25
        width, height = right - left, bottom - top

        if width <= 0 or height <= 0:
            return

        read = list(self.read_values)
        write = list(self.write_values)
        maximum = max(read + write + [1.0]) * 1.15

        for tick in range(5):
            value = maximum * tick / 4
            y = bottom - height * tick / 4
            p.setPen(QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine))
            p.drawLine(left, int(y), right, int(y))
            p.setPen(QColor(MUTED))
            p.drawText(2, int(y) + 4, f"{value:.1f}")

        def draw_series(values, color):
            if len(values) < 2:
                return
            points = [
                QPointF(
                    left + i * width / (len(values) - 1),
                    bottom - min(v, maximum) * height / maximum
                )
                for i, v in enumerate(values)
            ]
            path = QPainterPath()
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
            p.setPen(QPen(QColor(color), 2))
            p.drawPath(path)

        draw_series(read, BLUE)
        draw_series(write, YELLOW)

        p.setPen(QColor(MUTED))
        p.drawText(right - 64, self.height() - 5, "MB/s")


class SystemPulse(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SystemPulse")
        self.resize(1200, 800)
        self.setMinimumSize(850, 600)

        self.settings_store = QSettings("SystemPulse", "SystemPulse")
        self.temperature_enabled = self.settings_store.value(
            "show_temperature", True, type=bool
        )
        self.start_minimized_enabled = self.settings_store.value(
            "start_minimized", False, type=bool
        )
        self.always_on_top_enabled = self.settings_store.value(
            "always_on_top", False, type=bool
        )
        self.saved_refresh_interval = self.settings_store.value(
            "refresh_interval", 1000, type=int
        )

        self.processes = []
        self.previous_net = psutil.net_io_counters()
        self.last_net_time = time.monotonic()
        self.previous_disk = psutil.disk_io_counters()
        self.last_disk_time = time.monotonic()
        self.cpu_history = deque(maxlen=60)
        self.ram_history = deque(maxlen=60)

        self.build_ui()
        if self.always_on_top_enabled:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        psutil.cpu_percent(interval=None)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start(self.saved_refresh_interval)

        self.refresh_all()
        self.refresh_processes()
        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self.refresh_processes)
        self.process_timer.start(3000)

    def scroll_area(self, widget, horizontal=False):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if horizontal else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background: #0c0e14;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: #0c0e14;
            }
        """)
        widget.setStyleSheet(
            widget.styleSheet() + " QWidget { background-color: #0c0e14; }"
        )
        scroll.setWidget(widget)
        return scroll

    def build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sidebar with its own vertical scrollbar
        sidebar_content = QWidget()
        sidebar_content.setStyleSheet("background: #10131c;")
        side = QVBoxLayout(sidebar_content)
        side.setContentsMargins(14, 22, 14, 16)
        side.setSpacing(7)

        brand = QLabel("◈  SystemPulse")
        brand.setStyleSheet(
            f"color: {TEXT}; font-size: 19px; font-weight: bold; padding: 8px;"
        )
        side.addWidget(brand)

        category = QLabel("MONITOR")
        category.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; padding: 10px 8px 3px;"
        )
        side.addWidget(category)

        nav_items = [
            ("Overview", "◫"),
            ("Processes", "≋"),
            ("Hardware", "▣"),
            ("Storage", "▤"),
            ("Network", "⌁"),
            ("Settings", "⚙"),
        ]
        self.nav_buttons = []
        for i, (name, icon) in enumerate(nav_items):
            btn = QPushButton(f"  {icon}    {name}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, index=i: self.switch_page(index))
            self.nav_buttons.append(btn)
            side.addWidget(btn)

        side.addStretch()
        side.addWidget(QLabel("SYSTEMPULSE\nVersion 0.3.0\nLocal monitoring"))

        self.sidebar = self.scroll_area(sidebar_content)
        self.sidebar.setFixedWidth(225)
        outer.addWidget(self.sidebar)

        content = QWidget()
        content.setObjectName("content")
        col = QVBoxLayout(content)
        col.setContentsMargins(25, 22, 25, 16)
        col.setSpacing(10)

        self.page_title = QLabel("Overview")
        self.page_title.setStyleSheet(
            f"color: {TEXT}; font-size: 26px; font-weight: bold;"
        )
        self.page_subtitle = QLabel("Your computer, at a glance.")
        self.page_subtitle.setStyleSheet(f"color: {MUTED};")
        col.addWidget(self.page_title)
        col.addWidget(self.page_subtitle)

        self.pages = QStackedWidget()
        # Give every page its own scroll area.
        for page in (
            self.make_overview(),
            self.make_process_page(),
            self.make_hardware_page(),
            self.make_storage_page(),
            self.make_network_page(),
            self.make_settings_page(),
        ):
            page.setMinimumWidth(0)
            self.pages.addWidget(self.scroll_area(page))

        col.addWidget(self.pages, 1)
        self.status = QLabel("Monitoring initialized")
        self.status.setStyleSheet(f"color: {GREEN}; font-size: 11px;")
        col.addWidget(self.status)
        outer.addWidget(content, 1)

        self.setStyleSheet(f"""
            QWidget#root, QWidget#content {{
                background: {BG}; color: {TEXT};
            }}
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {BG}; width: 11px; margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: #424960; border-radius: 5px; min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {PURPLE}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QPushButton {{
                color: {MUTED}; background: transparent;
                border: 1px solid transparent; border-radius: 8px;
                padding: 12px 8px; text-align: left;
            }}
            QPushButton:hover {{ background: #202434; color: {TEXT}; }}
            QPushButton:checked {{
                background: #2b2443; color: #c4b5fd;
                border: 1px solid #453763; font-weight: bold;
            }}
            QLineEdit, QComboBox {{
                background: {PANEL}; color: {TEXT};
                border: 1px solid {BORDER}; border-radius: 7px;
                padding: 9px;
            }}
            QTableWidget {{
                background: {PANEL}; alternate-background-color: #1b1f2c;
                color: {TEXT}; border: 1px solid {BORDER};
                gridline-color: {BORDER}; selection-background-color: #40345f;
            }}
            QHeaderView::section {{
                background: #202434; color: {MUTED};
                padding: 9px; border: none;
            }}
            QProgressBar {{
                background: {BORDER}; border: none; border-radius: 4px;
                height: 8px;
            }}
            QProgressBar::chunk {{ background: {PURPLE}; border-radius: 4px; }}
        """)
        self.switch_page(0)

    def make_overview(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.cpu_card = InfoCard("CPU usage", "0%", PURPLE)
        self.ram_card = InfoCard("Memory usage", "0%", BLUE)
        self.disk_card = InfoCard("Disk usage", "0%", GREEN)
        self.net_card = InfoCard("Download speed", "0 B/s", YELLOW)

        for i, card in enumerate([
            self.cpu_card, self.ram_card, self.disk_card, self.net_card
        ]):
            grid.addWidget(card, i // 2, i % 2)
        layout.addLayout(grid)

        charts = QGridLayout()
        charts.setSpacing(12)
        self.cpu_chart = LineChart("CPU UTILIZATION", PURPLE)
        self.ram_chart = LineChart("MEMORY UTILIZATION", BLUE)
        charts.addWidget(self.cpu_chart, 0, 0)
        charts.addWidget(self.ram_chart, 0, 1)
        layout.addLayout(charts)

        disk_cards = QGridLayout()
        disk_cards.setSpacing(12)
        self.disk_read_card = InfoCard("Disk read speed", "0 MB/s", BLUE)
        self.disk_write_card = InfoCard("Disk write speed", "0 MB/s", YELLOW)
        disk_cards.addWidget(self.disk_read_card, 0, 0)
        disk_cards.addWidget(self.disk_write_card, 0, 1)
        layout.addLayout(disk_cards)

        self.disk_chart = DiskIOChart()
        layout.addWidget(self.disk_chart)

        core_title = QLabel("PROCESSOR CORES")
        core_title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(core_title)
        self.core_usage = CoreUsageWidget()
        layout.addWidget(self.core_usage)

        summary_title = QLabel("SYSTEM SUMMARY")
        summary_title.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(summary_title)

        summary_grid = QGridLayout()
        summary_grid.setSpacing(10)
        self.summary_os = InfoCard("Operating system", platform.system(), PURPLE)
        self.summary_cpu = InfoCard("Logical CPUs", str(psutil.cpu_count()), BLUE)
        self.summary_ram = InfoCard(
            "Installed RAM", human_bytes(psutil.virtual_memory().total), GREEN
        )
        self.summary_uptime = InfoCard("System uptime", self.uptime(), YELLOW)

        for card in [
            self.summary_os, self.summary_cpu,
            self.summary_ram, self.summary_uptime
        ]:
            card.setMaximumHeight(105)

        for i, card in enumerate([
            self.summary_os, self.summary_cpu,
            self.summary_ram, self.summary_uptime
        ]):
            summary_grid.addWidget(card, i // 2, i % 2)

        layout.addLayout(summary_grid)
        layout.addStretch()
        return page

    def make_process_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 8, 8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search process name or PID...")
        self.search.textChanged.connect(self.populate_processes)
        self.sort = QComboBox()
        self.sort.addItems(["Memory: highest first", "CPU: highest first", "Name: A–Z"])
        self.sort.currentIndexChanged.connect(self.populate_processes)
        row = QHBoxLayout()
        row.addWidget(self.search, 1)
        row.addWidget(self.sort)
        layout.addLayout(row)

        self.process_table = QTableWidget(0, 4)
        self.process_table.setHorizontalHeaderLabels(["Process", "PID", "CPU", "Memory"])
        self.process_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for c in range(1, 4):
            self.process_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )
        self.process_table.verticalHeader().setVisible(False)
        self.process_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.process_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.process_table.cellDoubleClicked.connect(self.show_process_details)
        self.process_table.setMinimumHeight(430)
        layout.addWidget(self.process_table)
        self.process_count = QLabel("Processes are read-only.")
        layout.addWidget(self.process_count)
        return page

    def make_hardware_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 8, 8)
        intro = QLabel("PC CONFIGURATION")
        intro.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: bold;")
        layout.addWidget(intro)

        self.hardware_cards = {}
        specs = [
            ("Operating system", "os"),
            ("Linux kernel", "kernel"),
            ("Processor model", "cpu"),
            ("Logical CPUs", "cores"),
            ("Total RAM", "ram"),
            ("Architecture", "arch"),
            ("Hostname", "host"),
            ("Machine uptime", "uptime"),
            ("Root disk", "disk"),
            ("CPU temperature", "temp"),
            ("Network interfaces", "interfaces"),
            ("Python version", "python"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (label, key) in enumerate(specs):
            card = InfoCard(label, "Detecting...")
            self.hardware_cards[key] = card
            grid.addWidget(card, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addStretch()
        return page

    def make_storage_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.addWidget(QLabel("Mounted filesystems and available space"))
        self.storage_table = QTableWidget(0, 4)
        self.storage_table.setHorizontalHeaderLabels(
            ["Mount point", "Total", "Used", "Free"]
        )
        self.storage_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for c in range(1, 4):
            self.storage_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeMode.ResizeToContents
            )
        self.storage_table.setMinimumHeight(300)
        self.storage_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.storage_table)
        layout.addStretch()
        return page

    def make_network_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 8, 8)
        grid = QGridLayout()
        self.net_download_card = InfoCard("Download rate", "0 B/s", BLUE)
        self.net_upload_card = InfoCard("Upload rate", "0 B/s", PURPLE)
        self.net_total_card = InfoCard("Bytes received", "0 B", GREEN)
        self.net_sent_card = InfoCard("Bytes sent", "0 B", YELLOW)
        for i, card in enumerate([
            self.net_download_card, self.net_upload_card,
            self.net_total_card, self.net_sent_card
        ]):
            grid.addWidget(card, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addWidget(QLabel("Network interfaces"))
        self.interface_table = QTableWidget(0, 3)
        self.interface_table.setHorizontalHeaderLabels(
            ["Interface", "Address", "Netmask"]
        )
        self.interface_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.interface_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.interface_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.interface_table.setMinimumHeight(300)
        self.interface_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.interface_table)
        return page

    def make_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.setSpacing(15)

        panel = QFrame()
        panel.setObjectName("card")
        panel.setStyleSheet(card_style())
        form = QFormLayout(panel)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(16)

        self.refresh_interval = QComboBox()
        for label, value in [
            ("1 second", 1000), ("2 seconds", 2000),
            ("3 seconds", 3000), ("5 seconds", 5000),
            ("10 seconds", 10000),
        ]:
            self.refresh_interval.addItem(label, value)

        saved_index = self.refresh_interval.findData(
            self.saved_refresh_interval
        )
        if saved_index >= 0:
            self.refresh_interval.setCurrentIndex(saved_index)
        self.refresh_interval.currentIndexChanged.connect(
            self.change_refresh_rate
        )

        self.always_on_top = QComboBox()
        self.always_on_top.addItems(["Disabled", "Enabled"])
        self.always_on_top.setCurrentIndex(
            1 if self.always_on_top_enabled else 0
        )
        self.always_on_top.currentIndexChanged.connect(
            self.change_always_on_top
        )

        self.start_minimized = QComboBox()
        self.start_minimized.addItems(["Disabled", "Enabled"])
        self.start_minimized.setCurrentIndex(
            1 if self.start_minimized_enabled else 0
        )
        self.start_minimized.currentIndexChanged.connect(
            self.change_start_minimized
        )

        self.autostart = QComboBox()
        self.autostart.addItems(["No action", "Enable", "Disable"])
        self.autostart.currentIndexChanged.connect(self.change_autostart)

        self.show_temp = QComboBox()
        self.show_temp.addItems(["Show when available", "Do not show"])
        self.show_temp.setCurrentIndex(
            0 if self.temperature_enabled else 1
        )
        self.show_temp.currentIndexChanged.connect(
            self.change_temperature_display
        )

        self.settings_note = QLabel(
            "Preferences are saved on this computer. "
            "Startup integration uses your Linux user account."
        )
        self.settings_note.setWordWrap(True)
        self.settings_note.setStyleSheet(f"color: {MUTED};")

        form.addRow("Metrics refresh interval", self.refresh_interval)
        form.addRow("Keep window on top", self.always_on_top)
        form.addRow("Start minimized", self.start_minimized)
        form.addRow("Launch with Linux login", self.autostart)
        form.addRow("Temperature display", self.show_temp)
        form.addRow("Information", self.settings_note)
        layout.addWidget(panel)

        export_button = QPushButton("Export system diagnostics")
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.clicked.connect(self.export_diagnostics)
        layout.addWidget(export_button)

        about = InfoCard(
            "About SystemPulse",
            "Local system monitoring built with Python, PySide6 and psutil.",
            PURPLE
        )
        about.setMaximumHeight(115)
        layout.addWidget(about)
        layout.addStretch()
        return page

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        titles = [
            ("Overview", "Your computer, at a glance."),
            ("Processes", "Search and inspect running processes."),
            ("Hardware", "Specifications detected from your PC."),
            ("Storage", "Disk space and mounted filesystems."),
            ("Network", "Traffic rates and available interfaces."),
            ("Settings", "Configure SystemPulse behavior."),
        ]
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        if index == 2:
            self.update_hardware()
        elif index == 3:
            self.update_storage()
        elif index == 4:
            self.update_network_interfaces()

    def change_refresh_rate(self):
        interval = int(self.refresh_interval.currentData())
        self.settings_store.setValue("refresh_interval", interval)
        if hasattr(self, "timer"):
            self.timer.setInterval(interval)

    def change_always_on_top(self, index):
        self.always_on_top_enabled = (index == 1)
        self.settings_store.setValue("always_on_top", self.always_on_top_enabled)
        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint,
            self.always_on_top_enabled
        )
        self.show()

    def change_temperature_display(self, index):
        self.temperature_enabled = (index == 0)
        self.settings_store.setValue("show_temperature", self.temperature_enabled)
        if hasattr(self, "hardware_cards"):
            self.update_hardware()

    def change_start_minimized(self, index):
        self.start_minimized_enabled = (index == 1)
        self.settings_store.setValue(
            "start_minimized", self.start_minimized_enabled
        )

    def change_autostart(self, index):
        if index == 0:
            return

        from pathlib import Path
        import os

        autostart_dir = Path.home() / ".config" / "autostart"
        entry = autostart_dir / "systempulse.desktop"

        try:
            if index == 1:
                autostart_dir.mkdir(parents=True, exist_ok=True)
                app_path = Path(__file__).resolve()
                python_path = Path(sys.executable).resolve()
                entry.write_text(
                    "[Desktop Entry]\\n"
                    "Type=Application\\n"
                    "Name=SystemPulse\\n"
                    f"Exec={python_path} {app_path}\\n"
                    "Terminal=false\\n"
                    "X-GNOME-Autostart-enabled=true\\n"
                )
                self.settings_note.setText(
                    "Autostart enabled. SystemPulse will launch at login."
                )
            else:
                if entry.exists():
                    entry.unlink()
                self.settings_note.setText("Autostart disabled.")
        except OSError as error:
            self.settings_note.setText(f"Could not update autostart: {error}")

        self.autostart.blockSignals(True)
        self.autostart.setCurrentIndex(0)
        self.autostart.blockSignals(False)

    def read_temperature(self):
        try:
            sensors = psutil.sensors_temperatures()
            values = [
                (entry.label or name, entry.current)
                for name, entries in sensors.items()
                for entry in entries
                if entry.current is not None
            ]
            if values:
                label, temp = max(values, key=lambda x: x[1])
                return f"{label}: {temp:.1f} °C"
        except (AttributeError, OSError, RuntimeError):
            pass
        return "Not available"

    def refresh_all(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_io_counters()

            disk_io = psutil.disk_io_counters()
            disk_now = time.monotonic()
            disk_elapsed = max(disk_now - self.last_disk_time, 0.001)

            if disk_io is not None and self.previous_disk is not None:
                read_rate = max(
                    0, disk_io.read_bytes - self.previous_disk.read_bytes
                ) / disk_elapsed
                write_rate = max(
                    0, disk_io.write_bytes - self.previous_disk.write_bytes
                ) / disk_elapsed
            else:
                read_rate = write_rate = 0

            self.previous_disk = disk_io
            self.last_disk_time = disk_now
            now = time.monotonic()
            elapsed = max(now - self.last_net_time, 0.001)
            down = max(0, net.bytes_recv - self.previous_net.bytes_recv) / elapsed
            up = max(0, net.bytes_sent - self.previous_net.bytes_sent) / elapsed
            self.previous_net = net
            self.last_net_time = now

            self.cpu_card.value.setText(f"{cpu:.1f}%")
            self.cpu_card.detail.setText("Current processor usage")
            self.ram_card.value.setText(f"{mem.percent:.1f}%")
            self.ram_card.detail.setText(
                f"{human_bytes(mem.used)} of {human_bytes(mem.total)}"
            )
            self.disk_card.value.setText(f"{disk.percent:.1f}%")
            self.disk_card.detail.setText(
                f"{human_bytes(disk.free)} available on /"
            )
            self.net_card.value.setText(f"{human_bytes(down)}/s")
            self.net_card.detail.setText(f"Upload: {human_bytes(up)}/s")

            self.disk_read_card.value.setText(
                f"{read_rate / (1024 ** 2):.2f} MB/s"
            )
            self.disk_write_card.value.setText(
                f"{write_rate / (1024 ** 2):.2f} MB/s"
            )
            self.disk_chart.add_values(read_rate, write_rate)
            self.core_usage.update_values(
                psutil.cpu_percent(percpu=True, interval=None)
            )

            self.cpu_chart.add_value(cpu)
            self.ram_chart.add_value(mem.percent)
            self.summary_os.value.setText(
                f"{platform.system()} {platform.release()}"
            )
            self.summary_cpu.value.setText(
                str(psutil.cpu_count(logical=True) or "N/A")
            )
            self.summary_ram.value.setText(human_bytes(mem.total))
            self.summary_uptime.value.setText(self.uptime())

            self.net_download_card.value.setText(f"{human_bytes(down)}/s")
            self.net_upload_card.value.setText(f"{human_bytes(up)}/s")
            self.net_total_card.value.setText(human_bytes(net.bytes_recv))
            self.net_sent_card.value.setText(human_bytes(net.bytes_sent))
            self.status.setText("●  Monitoring active")
        except (OSError, ValueError, RuntimeError) as error:
            self.status.setText(f"Monitoring error: {error}")

    def uptime(self):
        seconds = int(time.time() - psutil.boot_time())
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes = seconds // 60
        return f"{days}d {hours}h {minutes}m"

    def refresh_processes(self):
        items = []
        for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
            try:
                info = proc.info
                mem = info["memory_info"].rss if info["memory_info"] else 0
                items.append({
                    "name": info["name"] or "Unknown",
                    "pid": info["pid"],
                    "cpu": info["cpu_percent"] or 0,
                    "memory": mem,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.processes = items
        self.populate_processes()

    def populate_processes(self, *args):
        if not hasattr(self, "process_table"):
            return
        query = self.search.text().lower().strip()
        items = [
            p for p in self.processes
            if query in p["name"].lower() or query in str(p["pid"])
        ]
        mode = self.sort.currentIndex()
        if mode == 0:
            items.sort(key=lambda p: p["memory"], reverse=True)
        elif mode == 1:
            items.sort(key=lambda p: p["cpu"], reverse=True)
        else:
            items.sort(key=lambda p: p["name"].lower())

        self.process_table.setRowCount(len(items))
        for row, p in enumerate(items):
            values = [
                p["name"], str(p["pid"]),
                f"{p['cpu']:.1f}%", human_bytes(p["memory"])
            ]
            for col, value in enumerate(values):
                self.process_table.setItem(row, col, QTableWidgetItem(value))
        self.process_count.setText(f"{len(items)} matching processes • Read-only")


    def show_process_details(self, row, column):
        try:
            pid_item = self.process_table.item(row, 1)
            if pid_item is None:
                return

            pid = int(pid_item.text())
            process = psutil.Process(pid)

            with process.oneshot():
                name = process.name()
                status = process.status()
                memory = process.memory_info().rss
                threads = process.num_threads()

                try:
                    username = process.username()
                except (psutil.AccessDenied, OSError):
                    username = "Access denied"

                try:
                    executable = process.exe() or "Not available"
                except (psutil.AccessDenied, OSError):
                    executable = "Access denied"

            cpu_item = self.process_table.item(row, 2)
            cpu_text = cpu_item.text() if cpu_item else "Not available"

            details = (
                f"Name: {name}\n"
                f"PID: {pid}\n"
                f"Status: {status}\n"
                f"CPU: {cpu_text}\n"
                f"Memory: {human_bytes(memory)}\n"
                f"Threads: {threads}\n"
                f"User: {username}\n"
                f"Executable: {executable}"
            )

            QMessageBox.information(
                self, f"Process details — {name}", details
            )

        except (psutil.Error, OSError, ValueError) as error:
            QMessageBox.warning(
                self,
                "Process unavailable",
                f"The process may have exited or access may be restricted.\n\n{error}"
            )

    def export_diagnostics(self):
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export SystemPulse diagnostics",
            str(Path.home() / "systempulse-diagnostics.txt"),
            "Text files (*.txt)"
        )

        if not destination:
            return

        try:
            memory = psutil.virtual_memory()
            root_disk = psutil.disk_usage("/")
            disk_io = psutil.disk_io_counters()
            cpu_per_core = psutil.cpu_percent(
                interval=0.2, percpu=True
            )

            cpu_name = "Not reported"
            try:
                with open("/proc/cpuinfo", encoding="utf-8") as cpu_file:
                    for line in cpu_file:
                        if line.lower().startswith("model name"):
                            cpu_name = line.split(":", 1)[1].strip()
                            break
            except OSError:
                cpu_name = platform.processor() or "Not reported"

            partitions = []
            seen_mounts = set()

            for part in psutil.disk_partitions(all=False):
                if part.mountpoint in seen_mounts:
                    continue
                seen_mounts.add(part.mountpoint)

                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append(
                        f"  {part.mountpoint}: "
                        f"{human_bytes(usage.used)} used / "
                        f"{human_bytes(usage.total)} total"
                    )
                except (PermissionError, OSError):
                    partitions.append(
                        f"  {part.mountpoint}: access unavailable"
                    )

            temperatures = []
            try:
                sensor_data = psutil.sensors_temperatures()
                for sensor_name, entries in sensor_data.items():
                    for entry in entries:
                        if entry.current is not None:
                            label = entry.label or sensor_name
                            temperatures.append(
                                f"  {label}: {entry.current:.1f} C"
                            )
            except (AttributeError, OSError, RuntimeError):
                pass

            interfaces = list(psutil.net_if_addrs().keys())

            report = [
                "SYSTEMPULSE DIAGNOSTICS",
                "=" * 42,
                f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "Application: SystemPulse 0.5 Beta",
                "",
                "OPERATING SYSTEM",
                f"  OS: {platform.system()} {platform.release()}",
                f"  Kernel: {platform.version()}",
                f"  Architecture: {platform.machine()}",
                f"  Python: {platform.python_version()}",
                f"  Uptime: {self.uptime()}",
                "",
                "PROCESSOR",
                f"  Model: {cpu_name}",
                f"  Physical cores: {psutil.cpu_count(logical=False)}",
                f"  Logical CPUs: {psutil.cpu_count(logical=True)}",
                f"  Overall usage: {psutil.cpu_percent(interval=None):.1f}%",
                "  Per-core usage: " + ", ".join(
                    f"{value:.1f}%" for value in cpu_per_core
                ),
                "",
                "MEMORY",
                f"  Total: {human_bytes(memory.total)}",
                f"  Used: {human_bytes(memory.used)}",
                f"  Available: {human_bytes(memory.available)}",
                f"  Usage: {memory.percent:.1f}%",
                "",
                "ROOT FILESYSTEM",
                f"  Total: {human_bytes(root_disk.total)}",
                f"  Used: {human_bytes(root_disk.used)}",
                f"  Free: {human_bytes(root_disk.free)}",
                "",
                "MOUNTED FILESYSTEMS",
                *(partitions or ["  No filesystem data available"]),
                "",
                "DISK I/O (CUMULATIVE)",
                (
                    f"  Read: {human_bytes(disk_io.read_bytes)}"
                    if disk_io else "  Read: unavailable"
                ),
                (
                    f"  Written: {human_bytes(disk_io.write_bytes)}"
                    if disk_io else "  Written: unavailable"
                ),
                "",
                "TEMPERATURE SENSORS",
                *(temperatures or ["  No readable sensors detected"]),
                "",
                "NETWORK INTERFACES",
                *[f"  {name}" for name in interfaces],
                "",
                "PRIVACY",
                "  This report omits IP addresses, hostnames, usernames,",
                "  and the list of running processes.",
            ]

            with open(destination, "w", encoding="utf-8") as report_file:
                report_file.write("\n".join(report) + "\n")

            QMessageBox.information(
                self,
                "Diagnostics exported",
                f"Report saved successfully:\n{destination}"
            )

        except (OSError, psutil.Error, ValueError) as error:
            QMessageBox.critical(
                self,
                "Export failed",
                f"Could not create the report:\n{error}"
            )

    def update_hardware(self):
        mem = psutil.virtual_memory()
        root = shutil.disk_usage("/")
        try:
            cpu_name = ""
            with open("/proc/cpuinfo", encoding="utf-8") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        cpu_name = line.split(":", 1)[1].strip()
                        break
            if not cpu_name:
                cpu_name = platform.processor() or "Not reported"
        except OSError:
            cpu_name = platform.processor() or "Not reported"

        interfaces = ", ".join(psutil.net_if_addrs().keys()) or "None detected"
        values = {
            "os": f"{platform.system()} {platform.release()}",
            "kernel": platform.version(),
            "cpu": cpu_name,
            "cores": f"{psutil.cpu_count(logical=False) or '?'} physical / "
                     f"{psutil.cpu_count(logical=True) or '?'} logical",
            "ram": f"{human_bytes(mem.total)} total",
            "arch": f"{platform.machine()} • {platform.architecture()[0]}",
            "host": socket.gethostname(),
            "uptime": self.uptime(),
            "disk": f"{human_bytes(root.total)} total • "
                    f"{human_bytes(root.free)} free",
            "temp": self.read_temperature() if getattr(self, "temperature_enabled", True) else "Hidden in settings",
            "interfaces": interfaces,
            "python": platform.python_version(),
        }
        for key, value in values.items():
            self.hardware_cards[key].value.setText(value)

    def update_storage(self):
        rows = []
        seen = set()
        for part in psutil.disk_partitions(all=False):
            if part.mountpoint in seen:
                continue
            seen.add(part.mountpoint)
            try:
                usage = psutil.disk_usage(part.mountpoint)
                rows.append((
                    part.mountpoint, human_bytes(usage.total),
                    human_bytes(usage.used), human_bytes(usage.free)
                ))
            except (PermissionError, OSError):
                continue
        self.storage_table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, value in enumerate(values):
                self.storage_table.setItem(r, c, QTableWidgetItem(value))

    def update_network_interfaces(self):
        rows = []
        for name, addresses in psutil.net_if_addrs().items():
            for address in addresses:
                if address.family == socket.AF_INET:
                    rows.append((name, address.address, address.netmask or "—"))
        self.interface_table.setRowCount(len(rows))
        for r, values in enumerate(rows):
            for c, value in enumerate(values):
                self.interface_table.setItem(r, c, QTableWidgetItem(value))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SystemPulse")
    app.setStyle("Fusion")
    window = SystemPulse()
    window.show()
    if window.start_minimized_enabled:
        window.showMinimized()
    sys.exit(app.exec())
