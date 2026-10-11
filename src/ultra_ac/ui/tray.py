# -*- coding: utf-8 -*-
"""系统托盘图标与菜单。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..theme import THEME
from ..widgets.icons import app_icon_qicon


def _menu_qss(s) -> str:
    """给原生菜单套一层 MD3 皮肤，避免和自绘界面割裂。"""
    return f"""
QMenu {{
    background: {s.surface_container};
    color: {s.on_surface};
    border: 1px solid {s.outline_variant};
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 26px 8px 16px;
    border-radius: 8px;
    min-width: 132px;
}}
QMenu::item:selected {{
    background: {s.secondary_container};
    color: {s.on_secondary_container};
}}
QMenu::item:disabled {{ color: {s.outline}; }}
QMenu::separator {{
    height: 1px;
    background: {s.outline_variant};
    margin: 6px 10px;
}}
"""


class Tray(QObject):
    showRequested = Signal()
    quitRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._icon = QSystemTrayIcon(self)
        self._menu = QMenu()

        # 菜单只留"退出"：打开主窗口用点图标（更顺手），开始/停止有全局热键，
        # 悬浮窗开关在设置里 —— 这些在菜单里再放一遍都是冗余。
        self._act_quit = QAction("退出", self)
        self._act_quit.triggered.connect(self.quitRequested)
        self._menu.addAction(self._act_quit)

        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(self._on_activated)
        self._apply_theme()
        THEME.changed.connect(self._apply_theme)

    def available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self) -> None:
        if self.available():
            self._icon.show()

    def hide(self) -> None:
        self._icon.hide()

    def _apply_theme(self) -> None:
        # logo 用固定配色（白底黑线），不跟随深浅色
        from ..widgets.icons import LOGO_BG, LOGO_FG
        self._icon.setIcon(app_icon_qicon(LOGO_BG, LOGO_FG))
        self._menu.setStyleSheet(_menu_qss(THEME.s))

    def set_running(self, running: bool) -> None:
        self.set_tooltip("运行中" if running else "待机")

    def set_tooltip(self, state: str) -> None:
        self._icon.setToolTip(f"Ultra AC · {state}")

    def show_message(self, title: str, body: str) -> None:
        if self.available():
            self._icon.showMessage(title, body, QSystemTrayIcon.Information, 3000)

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.showRequested.emit()
