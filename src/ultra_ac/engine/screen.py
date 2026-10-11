# -*- coding: utf-8 -*-
"""屏幕坐标工具。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

from PySide6.QtCore import QPoint


_user32 = ctypes.WinDLL("user32", use_last_error=True)


class _POINT(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG)]


def cursor_pos() -> QPoint:
    """当前光标位置（物理像素）。"""
    pt = _POINT()
    if not _user32.GetCursorPos(ctypes.byref(pt)):
        return QPoint(0, 0)
    return QPoint(int(pt.x), int(pt.y))


