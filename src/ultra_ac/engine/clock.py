# -*- coding: utf-8 -*-
"""高精度定时。"""

from __future__ import annotations

import ctypes
import threading
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
    def wait_until(target: float, cancel: threading.Event | None = None) -> bool:
        """等到 `perf_counter()` 到达 target。

        `cancel` 被置位时立刻返回 False —— 点击引擎要靠它做到"一按停止
        就真的停下"，而不是等完当前这一拍。睡眠阶段直接等事件唤醒，
        自旋阶段（最多约 3ms）不再逐个循环检查，避免在 10000 CPS 下
        白添开销：那点延迟人眼根本分辨不出。
        返回 True 表示等到了，False 表示被取消。
        """
        while True:
            if cancel is not None and cancel.is_set():
                return False
            remain = target - perf_counter()
            if remain <= 0.0:
                return True
            if remain > SPIN_WINDOW + SLEEP_SLACK:
                nap = remain - SPIN_WINDOW
                if cancel is not None:
                    if cancel.wait(nap):
                        return False
                else:
                    time.sleep(nap)
            else:
                while perf_counter() < target:
                    pass
                return True

