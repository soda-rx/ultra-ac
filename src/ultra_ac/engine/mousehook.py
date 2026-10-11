# -*- coding: utf-8 -*-
"""跟踪**物理**鼠标按键状态（低级鼠标钩子 WH_MOUSE_LL）。"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading

_user32 = ctypes.WinDLL("user32", use_last_error=True)

WH_MOUSE_LL = 14
HC_ACTION = 0
LLMHF_INJECTED = 0x00000001
WM_QUIT = 0x0012

WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
WM_MBUTTONDOWN, WM_MBUTTONUP = 0x0207, 0x0208

_BUTTONS = ("left", "right", "middle")
_DOWN = {"left": WM_LBUTTONDOWN, "right": WM_RBUTTONDOWN, "middle": WM_MBUTTONDOWN}
_UP = {"left": WM_LBUTTONUP, "right": WM_RBUTTONUP, "middle": WM_MBUTTONUP}

# 回调签名。返回值和句柄都用 ssize_t / c_void_p —— 用 c_int 会在 64 位进程里截断。
_HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                               wt.WPARAM, wt.LPARAM)

_user32.SetWindowsHookExW.restype = ctypes.c_void_p
_user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _HOOKPROC,
                                      ctypes.c_void_p, wt.DWORD]
_user32.CallNextHookEx.restype = ctypes.c_ssize_t
_user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                   wt.WPARAM, wt.LPARAM]
_user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
_user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), ctypes.c_void_p,
                                ctypes.c_uint, ctypes.c_uint]
_user32.PostThreadMessageW.argtypes = [wt.DWORD, ctypes.c_uint,
                                       wt.WPARAM, wt.LPARAM]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT),
                ("mouseData", wt.DWORD),
                ("flags", wt.DWORD),
                ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_void_p)]


class MouseHold:
    """只反映物理按键的按下状态。"""

    def __init__(self) -> None:
        self._down = dict.fromkeys(_BUTTONS, False)
        self._hook = None
        self._proc = None    # 必须持有回调引用：被 GC 回收后回调变野指针，进程直接崩
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()

    def down(self, button: str = "left") -> bool:
        return self._down.get(button, False)

    def _apply(self, msg: int, injected: bool) -> None:
        """喂一条鼠标消息。注入事件直接忽略 —— 这正是本模块存在的理由。"""
        if injected:
            return
        for name in _BUTTONS:
            if msg == _DOWN[name]:
                self._down[name] = True
            elif msg == _UP[name]:
                self._down[name] = False

    def _callback(self, code, wparam, lparam):
        if code == HC_ACTION:
            info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            self._apply(int(wparam), bool(info.flags & LLMHF_INJECTED))
        return _user32.CallNextHookEx(None, code, wparam, lparam)

    def _pump(self) -> None:
        """专用线程：装钩子，然后一直跑消息循环 —— 钩子回调就在这个线程执行。"""
        self._thread_id = int(ctypes.windll.kernel32.GetCurrentThreadId())
        self._proc = _HOOKPROC(self._callback)
        self._hook = _user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, None, 0)
        self._ready.set()
        if not self._hook:
            return
        msg = wt.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    def install(self) -> bool:
        if self._hook:
            return True
        self._ready.clear()
        self._thread = threading.Thread(target=self._pump, name="ultra-ac-mousehook",
                                        daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)
        return bool(self._hook)

    def remove(self) -> None:
        if self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        if self._hook:
            _user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
        self._proc = None
        self._thread = None
        self._thread_id = 0
        for name in _BUTTONS:
            self._down[name] = False
