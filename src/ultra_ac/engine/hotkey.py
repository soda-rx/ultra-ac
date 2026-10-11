# -*- coding: utf-8 -*-
"""全局热键（RegisterHotKey）。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

_user32 = ctypes.WinDLL("user32", use_last_error=True)

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0001, 0x0002, 0x0004, 0x4000

ERROR_HOTKEY_ALREADY_REGISTERED = 1409


class HotkeyManager(QObject, QAbstractNativeEventFilter):
    """在主窗口上注册全局热键，通过 Qt 原生事件过滤器接收 WM_HOTKEY。"""

    triggered = Signal(str)

    def __init__(self, window) -> None:
        QObject.__init__(self, window)
        QAbstractNativeEventFilter.__init__(self)
        self._hwnd = int(window.winId())
        self._names: dict[int, str] = {}
        self._failed: dict[str, str] = {}
        self._next_id = 0xA000
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self)

    def register(self, name: str, vk: int, mods: int = 0) -> bool:
        """注册一个热键。失败时记录原因，不抛异常。"""
        hk_id = self._next_id
        self._next_id += 1
        if _user32.RegisterHotKey(wt.HWND(self._hwnd), hk_id,
                                  mods | MOD_NOREPEAT, vk):
            self._names[hk_id] = name
            self._failed.pop(name, None)
            return True
        err = ctypes.get_last_error()
        self._failed[name] = ("已被其它程序占用" if err ==
                              ERROR_HOTKEY_ALREADY_REGISTERED
                              else f"注册失败（错误 {err}）")
        return False

    def failures(self) -> dict[str, str]:
        return dict(self._failed)

    def unregister_all(self) -> None:
        for hk_id in list(self._names):
            _user32.UnregisterHotKey(wt.HWND(self._hwnd), hk_id)
        self._names.clear()

    def detach(self) -> None:
        """摘掉事件过滤器。留着的话解释器收尾时 Qt 还会回调，必然报错。"""
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self)

    def nativeEventFilter(self, _event_type, message):  # noqa: N802
        try:
            msg = ctypes.cast(int(message), ctypes.POINTER(wt.MSG)).contents
        except (TypeError, ValueError):
            return False, 0
        if msg.message == WM_HOTKEY:
            name = self._names.get(int(msg.wParam))
            if name:
                self.triggered.emit(name)
                return True, 0
        return False, 0
