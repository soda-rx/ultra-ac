# -*- coding: utf-8 -*-
"""高精度定时。"""

from __future__ import annotations

import ctypes
import time
from time import perf_counter

_winmm = ctypes.WinDLL("winmm")

# 自旋窗口（秒）。剩余时间小于它就纯自旋，不再 sleep。
SPIN_WINDOW = 0.0015
# Sleep 的向上取整余量：Windows 的 Sleep 会比请求值多睡一点，这里预留出来
SLEEP_SLACK = 0.0012


class Clock:
    """进程级定时器粒度管理 + 精确等待。"""

    def __init__(self) -> None:
        self._raised = False

    def raise_resolution(self) -> bool:
        """把定时器粒度提到 1ms。返回是否成功。"""
        if self._raised:
            return True
        ok = _winmm.timeBeginPeriod(1) == 0
        self._raised = ok
        return ok

    def restore_resolution(self) -> None:
        if self._raised:
            _winmm.timeEndPeriod(1)
            self._raised = False

    @staticmethod
    def wait_until(target: float) -> None:
        """等到 `perf_counter()` 到达 target。"""
        while True:
            remain = target - perf_counter()
            if remain <= 0.0:
                return
            if remain > SPIN_WINDOW + SLEEP_SLACK:
                time.sleep(remain - SPIN_WINDOW)
            else:
                while perf_counter() < target:
                    pass
                return

