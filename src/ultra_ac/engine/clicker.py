# -*- coding: utf-8 -*-
"""点击引擎。"""

from __future__ import annotations

import random
import threading
from collections import deque
from enum import Enum
from time import perf_counter

from PySide6.QtCore import QObject, Signal

from .clock import Clock
from .input_win32 import click
from .mousehook import MouseHold
from .screen import cursor_pos

# 空闲轮询间隔
IDLE_POLL = 0.008
# 按住超过这么久才算连点，更短的一律当普通单击
HOLD_DELAY = 0.18

# 拟人化：点多久歇一次、每次歇多久（秒）
HUMAN_WORK = (6.0, 15.0)
HUMAN_REST = (0.25, 0.9)
# 间隔的随机浮动比例
HUMAN_JITTER = 0.12
# 状态上报间隔，太密会淹掉事件循环
STATS_INTERVAL = 0.2
# 晃动检测的采样间隔，要远高于点击频率
SHAKE_SAMPLE = 0.008

DEFAULT_REASON = "已停止"
SHAKE_REASON = "检测到鼠标剧烈晃动，已停止"


class ShakeDetector:
    """识别光标被快速来回甩动。"""

    WINDOW = 1.3           # 拐点的有效时间窗
    REVERSALS = 10         # 至少这么多次反向
    MIN_SPAN = 0.6         # 这些反向必须持续这么久
    MAX_INTERVAL = 0.10    # 平均每次反向不超过这么久（约 10 次/秒）
    MIN_SWING = 28.0       # 单次摆幅下限，小于它不算"甩"

    def __init__(self) -> None:
        self._turns: deque[float] = deque()
        self._extreme: float | None = None
        self._dir = 0

    def reset(self) -> None:
        self._turns.clear()
        self._extreme = None
        self._dir = 0

    def feed(self, x: float) -> bool:
        """喂一个横向坐标；返回 True 表示判定为"在剧烈甩鼠标"。"""
        now = perf_counter()
        while self._turns and now - self._turns[0] > self.WINDOW:
            self._turns.popleft()

        if self._extreme is None:
            self._extreme = x
            return False

        delta = x - self._extreme
        if self._dir == 0:
            # 先走够一个摆幅，才确定当前朝向
            if abs(delta) >= self.MIN_SWING:
                self._dir = 1 if delta > 0 else -1
                self._extreme = x
            return False

        if (self._dir > 0 and delta > 0) or (self._dir < 0 and delta < 0):
            self._extreme = x          # 同向继续，刷新极值
            return False

        if abs(delta) < self.MIN_SWING:
            return False               # 反向但幅度不够，还谈不上甩

        self._dir = -self._dir
        self._extreme = x
        self._turns.append(now)

        if len(self._turns) < self.REVERSALS:
            return False
        span = self._turns[-1] - self._turns[0]
        if span < self.MIN_SPAN:
            return False
        return span / (len(self._turns) - 1) <= self.MAX_INTERVAL


class TriggerMode(Enum):
    """怎么开始、怎么停。"""

    TOGGLE = "toggle"     # 热键或按钮切换
    HOLD = "hold"         # 按住鼠标键期间连点，松开即停


class ClickEngine(QObject):
    started = Signal()
    stopped = Signal(str)
    stats = Signal(int, float)     # 累计点击次数, 实测 CPS

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._clock = Clock()
        self._quit = threading.Event()
        # 停止请求。置位后所有等待立刻放弃，没有"还没点完的点击"再被送出去。
        self._stop = threading.Event()
        self._stop_reason = DEFAULT_REASON
        self._thread: threading.Thread | None = None

        self._mode: TriggerMode = TriggerMode.TOGGLE
        self._cps: float = 100.0
        self._want: bool = False
        self._button: str = "left"
        self._shake_on = True
        self._shake = ShakeDetector()
        # 物理按键状态（低级鼠标钩子，只有按住模式才装）
        self._hold = MouseHold()
        # 按下时刻，0 = 未按下
        self._hold_since = 0.0
        # 拟人化间隔
        self._human = False
        self._rest_at = 0.0        # 下次开始"歇手"的时刻
        self._rest_until = 0.0     # 这次"歇手"结束的时刻
        # 随机坐标抖动：半径（px），0 = 关闭。anchor 是这一轮点击的基准点
        self._jitter = 0
        self._anchor = None

    # 参数（由 UI 线程写入）
    def configure(self, *, mode: TriggerMode | None = None,
                  cps: float | None = None,
                  button: str | None = None,
                  shake: bool | None = None,
                  human: bool | None = None,
                  jitter: int | None = None) -> None:
        if mode is not None and mode is not self._mode:
            self._mode = mode
            # 换模式时把上一轮的停止请求和按住计时清掉，别让它跨模式生效
            self._want = False
            self._stop.clear()
            self._stop_reason = DEFAULT_REASON
            self._hold_since = 0.0
            if mode is TriggerMode.HOLD:
                self._hold.install()
            else:
                # 只有按住模式需要全局低级鼠标钩子。切换模式用不上它，
                # 挂着反而会在高 CPS 下把每个注入事件都绕一圈 Python 回调，
                # 拖慢系统输入分发 —— 停止热键也会跟着变慢。
                self._hold.remove()
        if cps is not None:
            self._cps = float(cps)
        if button is not None:
            self._button = button
        if shake is not None:
            self._shake_on = bool(shake)
        if human is not None:
            self._human = bool(human)
        if jitter is not None:
            self._jitter = max(0, int(jitter))

    # 生命周期
    def start(self) -> None:
        self._stop_reason = DEFAULT_REASON
        self._stop.clear()
        self._want = True

    def stop(self, reason: str = DEFAULT_REASON) -> None:
        """请求停止。真正的停止确认由工作线程发出（stopped 信号）。

        这样 UI 上的"已停止"就代表真的不再注入点击了，而不是"已经请求了"。
        """
        self._stop_reason = reason
        self._want = False
        self._stop.set()

    def shutdown(self) -> None:
        self._want = False
        self._stop.set()
        self._quit.set()
        self._hold.wake_all()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._hold.remove()

    def ensure_running(self) -> None:
        """启动常驻工作线程（按住模式需要它一直在监听）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._shake.reset()          # 启动前甩过的不算
        if self._mode is TriggerMode.HOLD:
            # 按住判定依赖物理按键钩子；正常情况下 configure 已经装过，
            # 这里补一次保证直接调用引擎时也能工作。
            self._hold.install()
        self._quit.clear()
        self._thread = threading.Thread(target=self._loop, name="ultra-ac-engine",
                                        daemon=True)
        self._thread.start()

    # 按住判定
    def _holding(self) -> bool:
        """按住模式：必须按够 `HOLD_DELAY` 才开始连点。"""
        # 用钩子读：GetAsyncKeyState 会把自己注入的抬起也算上，导致误判松手
        if not self._hold.down(self._button):
            self._hold_since = 0.0
            return False
        now = perf_counter()
        if self._hold_since == 0.0:
            self._hold_since = now
            return False          # 先等一等，可能只是单击
        return now - self._hold_since >= HOLD_DELAY

    def _wake_event(self) -> threading.Event:
        """当前模式下"应该立刻醒来"的信号。"""
        if self._mode is TriggerMode.HOLD:
            # 松手就该停：按住模式用物理抬起事件打断等待
            return self._hold.up_event(self._button)
        return self._stop

    def _click_point(self) -> tuple[int, int] | None:
        """抖动开启时给出本次落点；关闭时返回 None，表示原地点击。"""
        if self._jitter <= 0:
            return None
        now = cursor_pos()
        if (self._anchor is None
                or abs(now.x() - self._anchor.x()) > self._jitter
                or abs(now.y() - self._anchor.y()) > self._jitter):
            self._anchor = now          # 光标跑到抖动范围外：用户自己挪了鼠标
        return (self._anchor.x() + random.randint(-self._jitter, self._jitter),
                self._anchor.y() + random.randint(-self._jitter, self._jitter))

    # 工作线程
    def _loop(self) -> None:
        clock = self._clock
        clock.raise_resolution()
        clicks = 0
        window_start = perf_counter()
        window_count = 0
        last_stats = window_start
        next_tick = 0.0
        running = False

        try:
            while not self._quit.is_set():
                mode = self._mode
                wake = self._wake_event()

                if mode is TriggerMode.HOLD:
                    active = self._holding()
                else:
                    active = self._want and not self._stop.is_set()

                if not active:
                    if running:
                        running = False
                        reason = (self._stop_reason if mode is TriggerMode.TOGGLE
                                  else DEFAULT_REASON)
                        self._stop_reason = DEFAULT_REASON
                        # 到这儿才发停止信号：此刻起不会再有新的点击注入
                        self.stopped.emit(reason)
                    next_tick = 0.0
                    self._quit.wait(IDLE_POLL)
                    continue

                # 按住模式下停止由松手决定，所以只对切换模式生效
                if (self._shake_on and mode is TriggerMode.TOGGLE
                        and self._shake.feed(cursor_pos().x())):
                    self._want = False
                    self._stop_reason = SHAKE_REASON
                    self._stop.set()
                    # 交给循环顶部统一收尾，那里才会真正发 stopped
                    continue

                if not running:
                    running = True
                    clicks = 0
                    window_start = perf_counter()
                    window_count = 0
                    last_stats = window_start
                    next_tick = 0.0
                    self._anchor = None
                    self._rest_until = 0.0
                    self._rest_at = perf_counter() + random.uniform(*HUMAN_WORK)
                    self._shake.reset()
                    self.started.emit()

                now = perf_counter()
                if self._human:
                    if now < self._rest_until:
                        # 歇手期间不点击，循环照跑以便随时能停
                        clock.wait_until(min(self._rest_until,
                                             now + IDLE_POLL), wake)
                        continue
                    if now >= self._rest_at:
                        self._rest_until = now + random.uniform(*HUMAN_REST)
                        self._rest_at = (self._rest_until
                                         + random.uniform(*HUMAN_WORK))
                        continue

                interval = 1.0 / max(1.0, self._cps)
                if self._human:
                    # 平均值不变，只是不再等间距
                    interval *= 1.0 + random.uniform(-HUMAN_JITTER, HUMAN_JITTER)
                if next_tick == 0.0:
                    next_tick = now
                if now >= next_tick:
                    if now - next_tick > interval:
                        # 已经错过一整拍以上（比如注入接口被系统卡住）：
                        # 这一拍直接作废，重新对齐。绝不把欠下的点击补回来，
                        # 否则停止时还会有一串"迟到"的点击排队执行。
                        next_tick = now + interval
                    else:
                        # 停止请求可能刚好在等待期间到达：发起点之前再确认一次
                        if mode is TriggerMode.TOGGLE and not self._want:
                            continue
                        point = self._click_point()
                        if point is None:
                            click(button=self._button)
                        else:
                            click(point[0], point[1], button=self._button)
                        clicks += 1
                        window_count += 1
                        next_tick += interval
                        if next_tick <= now:      # 落后太多就重新对齐，不追债
                            next_tick = now + interval
                # 晃动检测独立于点击频率采样
                target = next_tick
                if self._shake_on and mode is TriggerMode.TOGGLE:
                    target = min(target, perf_counter() + SHAKE_SAMPLE)
                # 等到下一拍；停止请求 / 按住模式松手都会立刻打断
                if not clock.wait_until(target, wake):
                    continue

                stamp = perf_counter()
                if stamp - last_stats >= STATS_INTERVAL:
                    elapsed = stamp - window_start
                    actual = window_count / elapsed if elapsed > 0 else 0.0
                    self.stats.emit(clicks, actual)
                    window_start = stamp
                    window_count = 0
                    last_stats = stamp
        finally:
            clock.restore_resolution()
