# -*- coding: utf-8 -*-
"""鼠标注入（SendInput）。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

_user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

VK_F6 = 0x75          # 默认的开始/停止热键

BUTTONS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG),
                ("dy", wt.LONG),
                ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD),
                ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_void_p)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD),
                ("wScan", wt.WORD),
                ("dwFlags", wt.DWORD),
                ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_void_p)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD),
                ("wParamL", wt.WORD),
                ("wParamH", wt.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    # 64 位下必须是 40 字节（4 类型 + 4 对齐 + 32 联合体），否则 SendInput
    # 会以 ERROR_INVALID_PARAMETER 失败。
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


def _virtual_desktop() -> tuple[int, int, int, int]:
    g = _user32.GetSystemMetrics
    return (g(SM_XVIRTUALSCREEN), g(SM_YVIRTUALSCREEN),
            g(SM_CXVIRTUALSCREEN), g(SM_CYVIRTUALSCREEN))


def to_absolute(x: int, y: int) -> tuple[int, int]:
    """物理像素 → SendInput 需要的 0..65535 虚拟桌面归一化坐标。"""
    vx, vy, vw, vh = _virtual_desktop()
    nx = round((x - vx) * 65535 / max(1, vw - 1))
    ny = round((y - vy) * 65535 / max(1, vh - 1))
    return int(nx), int(ny)


def _send(events: list[INPUT]) -> int:
    if not events:
        return 0
    arr = (INPUT * len(events))(*events)
    return int(_user32.SendInput(len(events), ctypes.byref(arr),
                                 ctypes.sizeof(INPUT)))


def _mouse_event(flags: int, nx: int = 0, ny: int = 0) -> INPUT:
    ev = INPUT()
    ev.type = INPUT_MOUSE
    ev.mi = MOUSEINPUT(nx, ny, 0, flags, 0, None)
    return ev


def click(x: int | None = None, y: int | None = None, *,
          button: str = "left") -> int:
    """移动（可选）+ 按下 + 抬起，合成**一次** SendInput 调用。"""
    down, up = BUTTONS.get(button, BUTTONS["left"])
    events: list[INPUT] = []
    if x is not None and y is not None:
        nx, ny = to_absolute(x, y)
        events.append(_mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
                                   | MOUSEEVENTF_VIRTUALDESK, nx, ny))
    events.append(_mouse_event(down))
    events.append(_mouse_event(up))
    return _send(events)

