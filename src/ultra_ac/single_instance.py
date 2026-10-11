# -*- coding: utf-8 -*-
"""单实例：第二次启动时把已经在跑的那个唤到前面来。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

from PySide6.QtCore import (QAbstractNativeEventFilter, QCoreApplication,
                            QObject, Signal)

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)

# 句柄一律按 void* 声明，默认的 c_int 会在 64 位上截断
_kernel32.CreateMutexW.restype = ctypes.c_void_p
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
_user32.FindWindowW.restype = ctypes.c_void_p
_user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
_user32.RegisterWindowMessageW.restype = ctypes.c_uint
_user32.RegisterWindowMessageW.argtypes = [ctypes.c_wchar_p]
_user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                 ctypes.c_size_t, ctypes.c_ssize_t]

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Ultra AC.SingleInstance"
WAKE_MESSAGE = "Ultra AC.WakeUp"
WINDOW_TITLE = "Ultra AC"


class SingleInstance:
    """靠一个命名互斥体判断自己是不是头一个。"""

    def __init__(self, name: str = MUTEX_NAME) -> None:
        self._name = name
        self._handle = None

    def acquire(self) -> bool:
        handle = _kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            return True                      # 系统不给就算能跑，别误伤
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            _kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle:
            _kernel32.CloseHandle(self._handle)
            self._handle = None


def wake_existing() -> bool:
    """给已经在跑的那个实例投一条唤醒消息。"""
    hwnd = _user32.FindWindowW(None, WINDOW_TITLE)
    if not hwnd:
        return False
    message = _user32.RegisterWindowMessageW(WAKE_MESSAGE)
    if not message:
        return False
    return bool(_user32.PostMessageW(hwnd, message, 0, 0))


class WakeListener(QObject, QAbstractNativeEventFilter):
    """接住唤醒消息。窗口建好之后才能装。"""

    activated = Signal()

    def __init__(self, window) -> None:
        QObject.__init__(self, window)
        QAbstractNativeEventFilter.__init__(self)
        self._message = int(_user32.RegisterWindowMessageW(WAKE_MESSAGE))
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self)

    def nativeEventFilter(self, _event_type, message):  # noqa: N802
        try:
            msg = ctypes.cast(int(message), ctypes.POINTER(wt.MSG)).contents
        except (TypeError, ValueError):
            return False, 0
        if msg.message == self._message:
            self.activated.emit()
            return True, 0
        return False, 0

    def detach(self) -> None:
        """摘掉事件过滤器，别留到解释器收尾。"""
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self)
