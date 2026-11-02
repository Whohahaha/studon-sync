"""PySide6 desktop UI: account, courses, sync/schedule, plus a tray icon that runs scheduled syncs."""

import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import courses, credentials, paths, runner, schedule
from ..core import settings as settings_mod
from ..core.fau_login import LoginError
from ..core.settings import Course
from ..i18n import set_language, t
from . import autostart


def _icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#04316A"))  # FAU blue
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 12, 12)
    p.setPen(QColor("white"))
    p.setFont(QFont("Helvetica", 30, QFont.Bold))
    p.drawText(pix.rect(), Qt.AlignCenter, "S")
    p.end()
    return QIcon(pix)


class Bridge(QObject):
    """Carries results from worker threads back to the Qt thread."""

    call = Signal(object)


def run_in_thread(bridge: Bridge, work: Callable[[], object], done: Callable[[object], None]) -> None:
    def target() -> None:
        try:
            result: object = work()
        except Exception as e:  # handed to `done`, which shows it
            result = e
        bridge.call.emit(lambda: done(result))

    threading.Thread(target=target, daemon=True).start()


class AccountTab(QWidget):
    def __init__(self, bridge: Bridge) -> None:
        super().__init__()
        self.bridge = bridge
        layout = QVBoxLayout(self)
        intro = QLabel(t("acc.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.username = QLineEdit(credentials.stored_username())
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.Password)
        self.secret.setPlaceholderText(t("acc.secret_placeholder"))
        self.secret.textChanged.connect(self.update_code)
        form.addRow(t("acc.username"), self.username)
        form.addRow(t("acc.password"), self.password)
        form.addRow(t("acc.secret"), self.secret)
        layout.addLayout(form)
        self.refresh_placeholders()

        buttons = QHBoxLayout()
        save = QPushButton(t("acc.save"))
        save.clicked.connect(self.save)
        self.test_btn = QPushButton(t("acc.test"))
        self.test_btn.clicked.connect(self.test_login)
        buttons.addWidget(save)
        buttons.addWidget(self.test_btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

        layout.addSpacing(16)
        layout.addWidget(QLabel(f"<b>{t('acc.code_title')}</b>"))
        help_ = QLabel(t("acc.code_help"))
        help_.setWordWrap(True)
        layout.addWidget(help_)
        self.code = QLabel()
        self.code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.code.setFont(QFont("Menlo", 28, QFont.Bold))
        self.code_left = QLabel()
        layout.addWidget(self.code)
        layout.addWidget(self.code_left)
        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_code)
        self.timer.start(1000)
        self.update_code()

    def refresh_placeholders(self) -> None:
        self.password.setPlaceholderText(t("acc.saved_placeholder") if credentials.has_password() else "")
        if credentials.has_totp_secret():
            self.secret.setPlaceholderText(t("acc.saved_placeholder"))

    def update_code(self) -> None:
        typed = self.secret.text().strip()
        try:
            if typed or credentials.has_totp_secret():
                code, left = credentials.current_code(typed or None)
                self.code.setText(f"{code[:3]} {code[3:]}")
                self.code_left.setText(t("acc.code_left", s=left))
                return
        except ValueError:
            pass
        self.code.setText("— — —")
        self.code_left.setText(t("acc.code_none") if not typed else t("acc.bad_secret"))

    def save(self) -> None:
        try:
            credentials.save(self.username.text(), self.password.text(), self.secret.text())
        except ValueError:
            self.status.setText(t("acc.bad_secret"))
            return
        self.password.clear()
        self.secret.clear()
        self.refresh_placeholders()
        self.status.setText(t("acc.saved"))

    def test_login(self) -> None:
        self.test_btn.setEnabled(False)
        self.status.setText(t("acc.testing"))

        def done(result: object) -> None:
            self.test_btn.setEnabled(True)
            if result is True:
                self.status.setText(t("acc.test_ok"))
            else:
                err = str(result) if isinstance(result, (LoginError, Exception)) else "StudOn"
                self.status.setText(t("acc.test_fail", err=err))

        run_in_thread(self.bridge, runner.test_login, done)


class CoursesTab(QWidget):
    def __init__(self, bridge: Bridge) -> None:
        super().__init__()
        self.bridge = bridge
        layout = QVBoxLayout(self)
        intro = QLabel(t("crs.intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        row = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText(t("crs.url_placeholder"))
        self.url.returnPressed.connect(self.add)
        self.add_btn = QPushButton(t("crs.add"))
        self.add_btn.clicked.connect(self.add)
        row.addWidget(self.url)
        row.addWidget(self.add_btn)
        layout.addLayout(row)
        self.status = QLabel()
        layout.addWidget(self.status)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([t("crs.col_enabled"), t("crs.col_title"), t("crs.col_target")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemChanged.connect(self.item_changed)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        for key, slot in (("crs.change_target", self.change_target), ("crs.open", self.open_folder), ("crs.remove", self.remove)):
            btn = QPushButton(t(key))
            btn.clicked.connect(slot)
            actions.addWidget(btn)
        actions.addStretch()
        layout.addLayout(actions)

        default = QHBoxLayout()
        default.addWidget(QLabel(t("crs.default_dir")))
        self.default_dir = QLabel()
        default.addWidget(self.default_dir, 1)
        choose = QPushButton(t("crs.choose"))
        choose.clicked.connect(self.choose_default)
        default.addWidget(choose)
        layout.addLayout(default)
        self.reload()

    def reload(self) -> None:
        s = settings_mod.load()
        self.default_dir.setText(s.default_target_dir)
        self.table.blockSignals(True)
        self.table.setRowCount(len(s.courses))
        for i, c in enumerate(s.courses):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            check.setCheckState(Qt.Checked if c.enabled else Qt.Unchecked)
            check.setData(Qt.UserRole, c.ref_id)
            self.table.setItem(i, 0, check)
            self.table.setItem(i, 1, QTableWidgetItem(c.title))
            self.table.setItem(i, 2, QTableWidgetItem(c.target_dir))
        self.table.blockSignals(False)

    def selected(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(Qt.UserRole) if rows else None

    def item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        s = settings_mod.load()
        if c := s.course(item.data(Qt.UserRole)):
            c.enabled = item.checkState() == Qt.Checked
            settings_mod.save(s)

    def add(self) -> None:
        ref_id = courses.parse_ref_id(self.url.text())
        if not ref_id:
            self.status.setText(t("crs.bad_url"))
            return
        if settings_mod.load().course(ref_id):
            self.status.setText(t("crs.exists"))
            return
        self.add_btn.setEnabled(False)
        self.status.setText(t("crs.adding"))

        def done(title: object) -> None:
            self.add_btn.setEnabled(True)
            self.status.clear()
            if not isinstance(title, str):
                title, ok = QInputDialog.getText(self, t("app.title"), t("crs.no_title"), text=f"StudOn-{ref_id}")
                if not ok or not title.strip():
                    return
            s = settings_mod.load()
            target = courses.default_target(title, s.default_target_dir, {c.target_dir for c in s.courses})
            s.courses.append(Course(ref_id=ref_id, title=title.strip(), target_dir=target))
            settings_mod.save(s)
            self.url.clear()
            self.reload()

        run_in_thread(self.bridge, lambda: courses.fetch_title(ref_id), done)

    def change_target(self) -> None:
        ref_id = self.selected()
        if not ref_id:
            return
        s = settings_mod.load()
        c = s.course(ref_id)
        folder = QFileDialog.getExistingDirectory(self, t("crs.change_target"), str(Path(c.target_dir).expanduser().parent))
        if folder:
            c.target_dir = folder
            settings_mod.save(s)
            self.reload()

    def open_folder(self) -> None:
        ref_id = self.selected()
        if ref_id and (c := settings_mod.load().course(ref_id)):
            path = Path(c.target_dir).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def remove(self) -> None:
        ref_id = self.selected()
        if not ref_id:
            return
        s = settings_mod.load()
        s.courses = [c for c in s.courses if c.ref_id != ref_id]  # downloaded files are kept
        settings_mod.save(s)
        self.reload()

    def choose_default(self) -> None:
        s = settings_mod.load()
        folder = QFileDialog.getExistingDirectory(self, t("crs.default_dir"), s.default_target_dir)
        if folder:
            s.default_target_dir = folder
            settings_mod.save(s)
            self.reload()


class SyncTab(QWidget):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self.window_ = window
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self.sync_btn = QPushButton(t("sync.now"))
        self.sync_btn.clicked.connect(window.start_sync)
        row.addWidget(self.sync_btn)
        self.last = QLabel()
        row.addWidget(self.last, 1)
        logs = QPushButton(t("sync.open_logs"))
        logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.log_dir()))))
        row.addWidget(logs)
        layout.addLayout(row)

        s = settings_mod.load()
        sched = QHBoxLayout()
        sched.addWidget(QLabel(t("sync.schedule")))
        self.mode = QComboBox()
        for mode in ("off", "daily", "interval"):
            self.mode.addItem(t(f"sync.mode_{mode}"), mode)
        self.mode.setCurrentIndex(["off", "daily", "interval"].index(s.schedule.mode))
        self.time = QTimeEdit()
        self.time.setDisplayFormat("HH:mm")
        hour, minute = (int(x) for x in s.schedule.time.split(":"))
        self.time.setTime(self.time.time().fromString(f"{hour:02d}:{minute:02d}", "HH:mm"))
        self.hours = QSpinBox()
        self.hours.setRange(1, 168)
        self.hours.setValue(s.schedule.hours)
        self.hours_label = QLabel(t("sync.hours"))
        for w in (self.mode, self.time, self.hours, self.hours_label):
            sched.addWidget(w)
        sched.addStretch()
        layout.addLayout(sched)
        self.mode.currentIndexChanged.connect(self.save_schedule)
        self.time.timeChanged.connect(self.save_schedule)
        self.hours.valueChanged.connect(self.save_schedule)

        self.autostart = QCheckBox(t("sync.start_at_login"))
        self.autostart.setChecked(s.start_at_login)
        self.autostart.toggled.connect(self.save_autostart)
        layout.addWidget(self.autostart)
        note = QLabel(t("sync.note"))
        note.setWordWrap(True)
        note.setStyleSheet("color: gray")
        layout.addWidget(note)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Menlo", 11))
        self.log.setMaximumBlockCount(5000)
        layout.addWidget(self.log, 1)
        self.update_visibility()
        self.refresh_last()

    def update_visibility(self) -> None:
        mode = self.mode.currentData()
        self.time.setVisible(mode == "daily")
        self.hours.setVisible(mode == "interval")
        self.hours_label.setVisible(mode == "interval")

    def save_schedule(self) -> None:
        s = settings_mod.load()
        s.schedule.mode = self.mode.currentData()
        s.schedule.time = self.time.time().toString("HH:mm")
        s.schedule.hours = self.hours.value()
        settings_mod.save(s)
        self.update_visibility()

    def save_autostart(self, enabled: bool) -> None:
        s = settings_mod.load()
        s.start_at_login = enabled
        settings_mod.save(s)
        autostart.set_enabled(enabled)

    def refresh_last(self) -> None:
        s = settings_mod.load()
        if s.last_sync:
            when = datetime.fromisoformat(s.last_sync).strftime("%Y-%m-%d %H:%M")
            self.last.setText(t("sync.last", when=when, result=t("sync.ok" if s.last_sync_ok else "sync.failed")))
        else:
            self.last.setText(t("sync.never"))

    def set_running(self, running: bool) -> None:
        self.sync_btn.setEnabled(not running)
        self.sync_btn.setText(t("sync.running" if running else "sync.now"))


class MainWindow(QMainWindow):
    line = Signal(str)

    def __init__(self, tray: QSystemTrayIcon) -> None:
        super().__init__()
        self.tray = tray
        self.bridge = Bridge()
        self.bridge.call.connect(lambda fn: fn())
        self.syncing = False
        self.setWindowTitle(t("app.title"))
        self.setWindowIcon(_icon())
        self.resize(820, 600)

        tabs = QTabWidget()
        self.account = AccountTab(self.bridge)
        self.courses = CoursesTab(self.bridge)
        self.sync = SyncTab(self)
        tabs.addTab(self.account, t("tab.account"))
        tabs.addTab(self.courses, t("tab.courses"))
        tabs.addTab(self.sync, t("tab.sync"))
        self.tabs = tabs
        self.setCentralWidget(tabs)
        self.line.connect(self.sync.log.appendPlainText)

        self.scheduler = QTimer(self)
        self.scheduler.timeout.connect(self.check_schedule)
        self.scheduler.start(60_000)
        QTimer.singleShot(5_000, self.check_schedule)

    def check_schedule(self) -> None:
        if not self.syncing and schedule.is_due(settings_mod.load()) and not runner.is_running():
            self.start_sync()

    def start_sync(self) -> None:
        if self.syncing:
            return
        self.syncing = True
        self.sync.set_running(True)
        self.sync.log.clear()

        def done(result: object) -> None:
            self.syncing = False
            self.sync.set_running(False)
            self.sync.refresh_last()
            if isinstance(result, Exception):
                self.sync.log.appendPlainText(str(result))
                self.tray.showMessage(t("app.title"), t("notify.failed"))
            elif not result.ok:
                if result.error:
                    self.sync.log.appendPlainText(result.error)
                self.tray.showMessage(t("app.title"), t("notify.failed"))
            elif result.added or result.changed:
                self.tray.showMessage(t("app.title"), t("notify.new", added=result.added, changed=result.changed))

        run_in_thread(self.bridge, lambda: runner.run_sync(self.line.emit), done)

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.ignore()
        self.hide()  # keeps running in the tray for scheduled syncs


def run(background: bool = False) -> int:
    set_language(settings_mod.load().language)
    app = QApplication(sys.argv)
    app.setApplicationName(t("app.title"))
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(_icon())

    tray = QSystemTrayIcon(_icon())
    window = MainWindow(tray)
    menu = QMenu()
    for key, slot in (("tray.open", window.show_window), ("tray.sync", window.start_sync), ("tray.quit", app.quit)):
        action = QAction(t(key), menu)
        action.triggered.connect(slot)
        menu.addAction(action)
    tray.setContextMenu(menu)
    tray.setToolTip(t("app.title"))
    tray.show()

    if not background:
        window.show_window()
    return app.exec()
