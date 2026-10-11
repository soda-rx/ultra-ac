# -*- coding: utf-8 -*-
"""系统环境读取。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

# “辅助功能 → 视觉效果 → 动画效果”
SPI_GETCLIENTAREAANIMATION = 0x1042


def system_prefers_dark() -> bool:
    """读取 Windows 的应用配色偏好。"""
    try:
        import winreg
        path = (r"Software\Microsoft\Windows\CurrentVersion\Themes"
                r"\Personalize")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
    except (ImportError, OSError, ValueError, TypeError):
        return False


def system_animations_enabled() -> bool:
    """Windows 的“显示动画效果”开着吗。读不到就当开着。"""
    value = wt.BOOL()
    try:
        ok = ctypes.WinDLL("user32").SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(value), 0)
    except (AttributeError, OSError):
        return True
    return bool(value.value) if ok else True
