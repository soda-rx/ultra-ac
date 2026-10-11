# -*- coding: utf-8 -*-
"""MD3 主窗口。"""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QRect, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from .. import config
from ..engine.clicker import ClickEngine, TriggerMode
from ..engine.hotkey import HotkeyManager
from ..engine.input_win32 import VK_F6
from ..theme import (Dur, Shape, Space, THEME, motion_duration, motion_enabled,
                     pop_spring, standard)
from ..widgets.controls import (FilterChip, KeyCaptureField, MdIconButton,
                                MdSlider, MdSwitch, MdTextField,
                                SegmentedButton, vk_name)
from ..widgets.loading import LoadingRing
from ..widgets.panels import (ActionRow, Caption, Card, ListItem,
                              ModalBottomSheet, SectionHeader, StatusRow,
                              TopAppBar, WarningBar)
from ..widgets.primitives import ThemedWidget, anim_float, draw_shape
from ..widgets.readout import RateDisplay
from .hud import Hud
from .tray import Tray

WIDTH = 420

MIN_CPS = 1.0
SLIDER_MAX = 1000.0   # 滑杆量程上限，再往上只能手输
MAX_CPS = 10000.0     # 手输上限

# 随机坐标抖动：默认 ±10px，上限 50px
JITTER_DEFAULT = 10
JITTER_MAX = 50

# 一行放得下，全部档位都挂在同一条量程上
PRESET_VALUES = ("10", "20", "50", "100", "500")
TRIGGERS = ["切换", "按住"]
MOUSE_LABELS = ["左键", "中键", "右键"]
MOUSE_KEYS = ["left", "middle", "right"]


def cps_from_t(t: float, lo: float, hi: float) -> float:
    """指数映射，保证低 CPS 区间在滑块上有足够行程。"""
    return lo * ((hi / lo) ** max(0.0, min(1.0, t)))


def t_from_cps(cps: float, lo: float, hi: float) -> float:
    cps = max(lo, min(hi, cps))
    return math.log(cps / lo) / math.log(hi / lo)


STOPS = [t_from_cps(c, MIN_CPS, SLIDER_MAX)
         for c in (10.0, 20.0, 50.0, 100.0, 500.0)]


class MainWindow(ThemedWidget):
    # 骨架阶段先占这个高度，和装好后的高度一致，加载完成时窗口不会跳一下
    SKELETON_HEIGHT = 642
    # 冷启动弹出的起始比例与时长
    POP_FROM = 0.88
    POP_MS = 200
    # 界面上的提示（检查更新、晃动急停…）挂多久自动消失
    NOTICE_MS = 5000

    def __init__(self) -> None:
        super().__init__()
        # 无边框窗口默认是 WS_POPUP，没有 WS_MINIMIZEBOX，Windows 不做最小化动画
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window
                            | Qt.WindowMinimizeButtonHint
                            | Qt.WindowSystemMenuHint)
        self.setWindowTitle("Ultra AC")
        self.setFixedWidth(WIDTH)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._notice = ""
        self._running = False
        self._loaded = False
        self._spinner: LoadingRing | None = None
        self._hotkeys: HotkeyManager | None = None
        self._really_quit = False
        self._shut = False
        # 清了配置后置位，退出时不再写回
        self._discard_config = False
        # 警示条状态与不含警示条的窗口基准高度
        self._warn_on = False
        self._base_height = 0
        # 抖动数值是否处于就地编辑状态
        self._editing_jitter = False
        # 拖动滑块会连续改值，保存需要节流
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_config)
        self._cfg = config.load()
        # 主题优先级：配置 > 命令行/系统。骨架就是按 THEME 画的，
        # 晚了会让等待页和装好后的配色对不上
        saved_theme = self._cfg.get("theme")
        if saved_theme in ("dark", "light"):
            THEME.set_dark(saved_theme == "dark")
        # 托盘提示只弹一次，弹过就记进配置
        self._tray_tipped = bool(self._cfg.get("tray_tip"))
        # 界面提示挂 5 秒自动消失
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.setInterval(self.NOTICE_MS)
        self._notice_timer.timeout.connect(self._clear_notice)

        self.engine = ClickEngine(self)
        self.engine.started.connect(self._on_engine_started)
        self.engine.stopped.connect(self._on_engine_stopped)
        self.engine.stats.connect(self._on_engine_stats)

        self.hud = Hud()

        # 关闭窗口的行为：0 = 收进托盘，1 = 直接退出（设置里可改）
        self._close_action = 0

        self.tray = Tray(self)
        self.tray.showRequested.connect(self.restore)
        self.tray.quitRequested.connect(self.request_quit)
        self.tray.set_running(False)
        self.tray.show()

        # 窗口自身的淡入淡出，时长取系统动画那一档
        self._window_hiding = False
        self._window_fade = QVariantAnimation(self)
        self._window_fade.setDuration(motion_duration(Dur.SHORT4))
        self._window_fade.setEasingCurve(standard())
        self._window_fade.valueChanged.connect(self._on_window_fade)
        self._window_fade.finished.connect(self._on_window_fade_done)

        # 先立骨架，界面留给 load()
        self._spinner = LoadingRing(self)
        self._center_spinner()
        self._spinner.start()
        # 存的值就超量程时，骨架直接按带警示条的高度立
        saved_cps = self._cfg.get("cps")
        over = isinstance(saved_cps, (int, float)) and saved_cps > SLIDER_MAX
        self.setFixedHeight(self.SKELETON_HEIGHT
                            + (WarningBar.HEIGHT if over else 0))

    def fade_in(self) -> None:
        """窗口出现时淡入。系统关了动画效果就直接到位。"""
        self._window_fade.stop()
        self._window_hiding = False
        if not motion_enabled():
            self.setWindowOpacity(1.0)
            return
        self._window_fade.setStartValue(0.0)
        self._window_fade.setEndValue(1.0)
        self._window_fade.start()

    def pop_in(self, done) -> None:
        """冷启动：窗口从中间由小变大弹出来，圈圈同时在转。

        界面装配（done）等弹完再做 —— 装配那几百毫秒是阻塞的，塞在动画中间
        会把动画卡住。
        """
        if not motion_enabled():
            self.setWindowOpacity(1.0)
            QTimer.singleShot(0, done)
            return
        target = self.geometry()
        w = max(1, round(target.width() * self.POP_FROM))
        h = max(1, round(target.height() * self.POP_FROM))
        start = QRect(target.center().x() - w // 2,
                      target.center().y() - h // 2, w, h)
        # 弹出期间要能改尺寸，先把固定尺寸松开
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.setGeometry(start)
        self.setWindowOpacity(0.0)
        self._pop = QVariantAnimation(self)
        self._pop.setDuration(motion_duration(self.POP_MS))
        self._pop.setEasingCurve(pop_spring())
        self._pop.valueChanged.connect(
            lambda v: self._on_pop(v, start, target))
        self._pop.finished.connect(lambda: self._finish_pop(target, done))
        self._pop.setStartValue(0.0)
        self._pop.setEndValue(1.0)
        self._pop.start()

    def _on_pop(self, value, start: QRect, target: QRect) -> None:
        t = anim_float(value, 1.0)
        self.setGeometry(
            round(start.x() + (target.x() - start.x()) * t),
            round(start.y() + (target.y() - start.y()) * t),
            max(1, round(start.width() + (target.width() - start.width()) * t)),
            max(1, round(start.height() + (target.height() - start.height()) * t)))
        self.setWindowOpacity(min(1.0, t * 1.6))

    def _finish_pop(self, target: QRect, done) -> None:
        self.setGeometry(target)
        self.setWindowOpacity(1.0)
        self.setFixedWidth(WIDTH)
        self.setFixedHeight(self.SKELETON_HEIGHT)
        done()

    def _hide_to_tray(self) -> None:
        """收进托盘：淡出再藏，和淡入对称。"""
        if not motion_enabled():
            self._finish_hide_to_tray()
            return
        self._window_fade.stop()
        self._window_hiding = True
        self._window_fade.setStartValue(self.windowOpacity())
        self._window_fade.setEndValue(0.0)
        self._window_fade.start()

    def _on_window_fade(self, v) -> None:
        self.setWindowOpacity(anim_float(v, self.windowOpacity()))

    def _on_window_fade_done(self) -> None:
        if not self._window_hiding:
            return
        self._window_hiding = False
        self.setWindowOpacity(1.0)
        self._finish_hide_to_tray()

    def _finish_hide_to_tray(self) -> None:
        self.hide()
        self._notify_tray_once()

    def load(self) -> None:
        """装真正的界面。调用方得先 show()，不然"秒开"就没意义了。"""
        if self._loaded or self._shut:
            return
        if self._spinner is not None:
            self._spinner.stop()
            self._spinner.deleteLater()
            self._spinner = None
        self._build()
        self.root.activate()
        self._loaded = True
        # 恢复设置放最后，盖掉上面的默认值
        self._apply_config()
        self._refresh()
        # 刚建出来的布局要跑完一轮事件才有真实高度，骨架期先顶着 SKELETON_HEIGHT
        QTimer.singleShot(0, self._sync_height)
        # 点界面空白处也要能结束编辑，所以挂在应用级
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        if self.isVisible():
            self._start_services()

    def _sync_height(self) -> None:
        height = self.sizeHint().height()
        if height <= 0:
            return
        # 警示条显示时 sizeHint 里已经含了它的高度，减掉才是基准高度
        self._base_height = height - (WarningBar.HEIGHT if self._warn_on else 0)
        self._apply_window_height()

    def _center_spinner(self) -> None:
        if self._spinner is None:
            return
        self._spinner.move((self.width() - self._spinner.width()) // 2,
                           (self.height() - self._spinner.height()) // 2)

    # 组装
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.root = outer

        self.app_bar = TopAppBar("Ultra AC", self)
        self.app_bar.minimizeRequested.connect(self.showMinimized)
        self.app_bar.closeRequested.connect(self.close)
        self.app_bar.themeToggleRequested.connect(self._on_theme_toggle)
        self.app_bar.pinToggled.connect(self._on_pin_toggled)
        outer.addWidget(self.app_bar)

        content = QWidget(self)
        outer.addWidget(content)
        col = QVBoxLayout(content)
        col.setContentsMargins(Space.L, 0, Space.L, Space.L)
        col.setSpacing(0)

        col.addWidget(self._build_rate_card(content))
        col.addSpacing(Space.L)
        col.addWidget(self._build_controls(content))
        col.addSpacing(Space.S)

        self.status = StatusRow(content)
        self.status.hotkeyClicked.connect(self.open_hotkey_settings)
        col.addWidget(self.status)

        # 设置与关于：椭圆描边按钮。设置用 MD3E 蓝，关于用中性描边
        self.row_settings = ActionRow("设置", icon="tune",
                                      border_role="primary", parent=content)
        self.row_settings.clicked.connect(self.open_settings)
        col.addWidget(self.row_settings)
        col.addSpacing(Space.S)

        self.row_about = ActionRow("关于", icon="info",
                                   border_role="outline_variant",
                                   parent=content)
        self.row_about.clicked.connect(self.open_about)
        col.addWidget(self.row_about)

        self._build_sheet()
        self._build_about()

    def _build_rate_card(self, parent: QWidget) -> QWidget:
        card = Card(parent)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(Space.L, Space.L, Space.L, Space.L)
        cl.setSpacing(0)

        self.readout = RateDisplay(100.0, minimum=MIN_CPS, maximum=MAX_CPS)
        self.readout.valueChanged.connect(self._sync_rate)
        cl.addWidget(self.readout)

        # 超出滑杆量程时的警示条。隐藏时连占位一起消失
        self.warn = WarningBar(
            f"超过 {SLIDER_MAX:.0f} CPS 可能达不到预期值，并伴随卡顿", card)
        self.warn.hide()
        cl.addWidget(self.warn)

        cl.addSpacing(2)

        # 滑杆量程 1–1000，再大的值只能手输；超出时轨道留空提示
        self.slider = MdSlider(
            minimum=0.0, maximum=1.0, stops=STOPS,
            formatter=lambda t: f"{cps_from_t(t, MIN_CPS, SLIDER_MAX):.0f}")
        self.slider.valueChanged.connect(
            lambda t: self._sync_rate(cps_from_t(t, MIN_CPS, SLIDER_MAX)))
        self.slider.released.connect(self._on_slider_released)
        cl.addWidget(self.slider)
        cl.addSpacing(Space.M)

        chip_row = QWidget(card)
        chl = QHBoxLayout(chip_row)
        chl.setContentsMargins(0, 0, 0, 0)
        chl.setSpacing(Space.S)
        self.chips: list[tuple[FilterChip, float]] = []
        for label in PRESET_VALUES:
            cps = float(label)
            chip = FilterChip(label, parent=chip_row)
            chip.clicked.connect(lambda _=False, c=cps: self._sync_rate(c))
            chl.addWidget(chip, 0, Qt.AlignVCenter)
            self.chips.append((chip, cps))
        chl.addStretch(1)
        cl.addWidget(chip_row)
        return card

    def _labelled(self, text: str, control: QWidget) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(Caption(text))
        lay.addSpacing(Space.XS)
        lay.addWidget(control)
        return box

    def _build_controls(self, parent: QWidget) -> QWidget:
        """触发方式与鼠标按键各占一行 —— 并排时每段太窄，点起来不踏实。"""
        box = QWidget(parent)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(Space.M)

        self.trigger = SegmentedButton(TRIGGERS)
        self.trigger.changed.connect(lambda _i: self._on_trigger_changed())
        lay.addWidget(self._labelled("触发方式", self.trigger))

        self.mouse_btn = SegmentedButton(MOUSE_LABELS)
        self.mouse_btn.changed.connect(lambda _i: self._refresh())
        lay.addWidget(self._labelled("鼠标按键", self.mouse_btn))
        return box

    def _build_sheet(self) -> None:
        settings = QWidget()
        sl = QVBoxLayout(settings)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        sl.addWidget(SectionHeader("快捷键"))
        self.k_toggle = KeyCaptureField(VK_F6)
        sl.addWidget(ListItem("开始 / 停止（仅切换模式可用）", [self.k_toggle]))
        self.k_toggle.changed.connect(lambda _vk: self._apply_hotkeys())

        sl.addWidget(SectionHeader("行为"))
        self.sw_hud = MdSwitch(False)
        sl.addWidget(ListItem("始终显示悬浮窗", [self.sw_hud]))
        self.sw_hud.toggled.connect(self._on_hud_toggle)

        self.seg_close = SegmentedButton(["最小化", "退出"])
        self.seg_close.set_index(self._close_action)
        self.seg_close.changed.connect(self._on_close_action)
        sl.addWidget(ListItem("关闭窗口时", [self.seg_close]))
        self.sw_shake = MdSwitch(True)
        sl.addWidget(ListItem("鼠标晃动急停", [self.sw_shake]))
        self.sw_shake.toggled.connect(lambda _on: self._refresh())

        # 拟人化只给开关，节奏由引擎掌握
        self.sw_human = MdSwitch(False)
        sl.addWidget(ListItem("拟人化间隔", [self.sw_human]))
        self.sw_human.toggled.connect(lambda _on: self._refresh())

        # 抖动：开关开启后行内出现铅笔，点它就地改 px
        self.sw_jitter = MdSwitch(False)
        self.f_jitter = MdTextField("", str(JITTER_DEFAULT), width=72)
        self.btn_jitter_edit = MdIconButton("edit", size=32)
        self.btn_jitter_edit.setToolTip("设置抖动范围")
        self.btn_jitter_edit.clicked.connect(self._begin_jitter_edit)
        self.row_jitter = ListItem(
            "随机坐标内抖动", [self.f_jitter, self.btn_jitter_edit,
                          self.sw_jitter],
            supporting=f"±{JITTER_DEFAULT} px")
        sl.addWidget(self.row_jitter)
        self.sw_jitter.toggled.connect(lambda _on: self._on_jitter_changed())
        self.f_jitter.valueChanged.connect(lambda _t: self._on_jitter_changed())
        self.f_jitter.editingFinished.connect(self._end_jitter_edit)

        sl.addWidget(SectionHeader("高级"))
        self.row_reset = ActionRow("清除配置并退出", icon="delete",
                                   border_role="outline_variant",
                                   color_role="error")
        self.row_reset.clicked.connect(self.clear_config_and_quit)
        sl.addWidget(self.row_reset)
        sl.addStretch(1)

        self.sheet = ModalBottomSheet("设置", settings, self)

    def _build_about(self) -> None:
        from .. import __version__

        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(Caption("Ultra AC", role="title_large",
                              color_role="on_surface"))
        lay.addSpacing(Space.XS)
        lay.addWidget(Caption(f"版本 {__version__}", role="body_medium"))
        lay.addSpacing(Space.M)

        self.row_update = ActionRow("检查更新",
                                    supporting="请手动前往 GitHub 下载新版本",
                                    icon="refresh", border_role="outline_variant")
        self.row_update.clicked.connect(
            lambda: self._about_notice("请手动前往 GitHub 下载新版本"))
        lay.addWidget(self.row_update)
        lay.addStretch(1)

        self.about_sheet = ModalBottomSheet("关于", box, self)

    def _set_notice(self, text: str) -> None:
        """设一条界面提示，5 秒后自动清掉。"""
        self._notice = text
        self._notice_timer.stop()
        if text:
            self._notice_timer.start()

    def _clear_notice(self) -> None:
        self._notice = ""
        self._refresh()

    def _about_notice(self, text: str) -> None:
        self._set_notice(text)
        self.about_sheet.close_sheet()
        self._refresh()

    def open_about(self) -> None:
        if self.sheet.is_open():
            self.sheet.close_sheet()
        self.about_sheet.setGeometry(self.rect())
        self.about_sheet.open()

    # 量程
    def _on_slider_released(self) -> None:
        """松手时若贴近某个预设档位就吸附过去。"""
        cps = self.readout.value()
        preset = min((p for _chip, p in self.chips), key=lambda p: abs(p - cps))
        if abs(preset - cps) <= max(0.6, preset * 0.02):
            self._sync_rate(preset)

    # 提示与状态
    def trigger_mode(self) -> TriggerMode:
        return TriggerMode.TOGGLE if self.trigger.index() == 0 else TriggerMode.HOLD

    def mouse_button(self) -> str:
        return MOUSE_KEYS[self.mouse_btn.index()]

    def _on_trigger_changed(self) -> None:
        self.engine.stop()
        self._set_notice("")
        self._refresh()

    def _on_pin_toggled(self, on: bool) -> None:
        """切换窗口置顶。"""
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()
        if on:
            self.raise_()
        self._touch_config()

    def _status_hint(self) -> str:
        """按住模式下左侧改说明触发方式 —— 那个快捷键此时根本用不上。"""
        if self.trigger_mode() is TriggerMode.HOLD:
            return f"按住{self.mouse_button_label()}即连点"
        return ""

    def mouse_button_label(self) -> str:
        return MOUSE_LABELS[self.mouse_btn.index()]

    def _refresh(self) -> None:
        self.engine.configure(mode=self.trigger_mode(),
                              cps=self.readout.value(),
                              button=self.mouse_button(),
                              shake=self.sw_shake.isChecked(),
                              human=self.sw_human.isChecked(),
                              jitter=self._jitter_radius())
        self.status.set_hint(self._status_hint())
        self.status.set_notice(self._notice)
        self._touch_config()

    @property
    def engine_running(self) -> bool:
        return self._running

    # 引擎回调
    def _on_engine_started(self) -> None:
        self._running = True
        self.status.set_running(True)
        self.hud.set_state(True, None)
        self.hud.show_hud()
        self.tray.set_running(True)
        self._refresh()

    def _on_engine_stopped(self, reason: str) -> None:
        self._running = False
        self.status.set_running(False)
        self.hud.set_state(False, None)
        self.tray.set_running(False)
        if not self.sw_hud.isChecked():
            self.hud.hide_hud()
        if reason and reason != "已停止":
            self._set_notice(reason)
        self._refresh()

    def _on_engine_stats(self, _clicks: int, actual: float) -> None:
        self.hud.set_state(True, actual)

    def _on_hud_toggle(self, on: bool) -> None:
        self._touch_config()
        if on or self.engine_running:
            self.hud.show_hud()
        else:
            self.hud.hide_hud()

    # 频率联动
    def _apply_rate(self, cps: float) -> None:
        cps = max(MIN_CPS, min(MAX_CPS, float(cps)))
        over = cps > SLIDER_MAX
        self.readout.set_value(cps)
        self.slider.set_overflow(over)
        self._show_warning(over)
        if not over:
            self.slider.set_value(t_from_cps(cps, MIN_CPS, SLIDER_MAX))
        for chip, preset in self.chips:
            chip.set_selected(abs(preset - cps) < 0.05)
        self.engine.configure(cps=cps)

    def _sync_rate(self, cps: float) -> None:
        self._apply_rate(cps)

    def _show_warning(self, on: bool) -> None:
        """超量程警示条。窗口是固定高度的，多出来的高度要一并给出去。"""
        if on == self._warn_on:
            return
        self._warn_on = on
        self.warn.setVisible(on)
        self._apply_window_height()

    def _apply_window_height(self) -> None:
        if not self._base_height:
            return
        self.setFixedHeight(self._base_height
                            + (WarningBar.HEIGHT if self._warn_on else 0))

    # 启动 / 停止（只由热键驱动）
    def toggle_running(self) -> None:
        if self.engine_running:
            self.engine.stop()
        else:
            self.begin()

    def begin(self) -> None:
        """开始连点。落点是当前光标位置，开了抖动就在它附近随机偏。"""
        self._set_notice("")
        if self.trigger_mode() is TriggerMode.HOLD:
            self._set_notice("按住模式下无需启动，按住鼠标键即可")
            self._refresh()
            return
        self.engine.configure(mode=self.trigger_mode(),
                              cps=self.readout.value(),
                              button=self.mouse_button(),
                              human=self.sw_human.isChecked(),
                              jitter=self._jitter_radius())
        self.engine.start()

    def set_preview(self, running: bool) -> None:
        """仅供截图校验：只改外观，绝不驱动引擎。"""
        self._running = running
        self.status.set_running(running)
        if running:
            self.hud.set_state(True, self.readout.value() * 0.973)
        else:
            self.hud.set_state(False, None)
        self._refresh()

    # 热键
    def _on_hotkey(self, name: str) -> None:
        # 只有一个热键：按一下开始，再按一下停止
        if name == "toggle":
            self.toggle_running()

    def _hotkey_notice(self) -> str:
        failed = self._hotkeys.failures() if self._hotkeys else {}
        if not failed:
            return ""
        return (f"{vk_name(self.k_toggle.vk())} "
                f"{failed.get('toggle', '')}，请在设置里换一个键")

    def _apply_hotkeys(self) -> None:
        if self._hotkeys is None:
            return
        self._hotkeys.unregister_all()
        self._hotkeys.register("toggle", self.k_toggle.vk())
        self.status.set_hotkey(vk_name(self.k_toggle.vk()))
        self._set_notice(self._hotkey_notice())
        self._refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._loaded:
            self._start_services()

    def _start_services(self) -> None:
        """热键和引擎线程要等界面装好才能起 —— 它们都要碰控件。"""
        if self._hotkeys is not None:
            return
        self._hotkeys = HotkeyManager(self)
        self._hotkeys.triggered.connect(self._on_hotkey)
        self._hotkeys.register("toggle", self.k_toggle.vk())
        self.status.set_hotkey(vk_name(self.k_toggle.vk()))
        self._set_notice(self._hotkey_notice())
        self.engine.ensure_running()
        self._refresh()

    def restore(self) -> None:
        """从托盘或另一个实例那里把窗口翻出来。刚才是藏着的就淡入。"""
        was_hidden = not self.isVisible() or self.isMinimized()
        self._window_fade.stop()
        self._window_hiding = False
        self.setWindowOpacity(1.0)
        if self.isMinimized():
            # 走原生还原，Windows 才有从任务栏弹回来的动画
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        if was_hidden and not self.isMinimized():
            self.fade_in()

    def shutdown(self) -> None:
        """收尾。closeEvent 和 aboutToQuit 都会走这里，重复调用无副作用。"""
        if self._shut:
            return
        self._shut = True
        self._window_fade.stop()
        self.setWindowOpacity(1.0)
        self._save_config()      # 退出时立即落盘，不等节流计时器
        self.engine.shutdown()
        self.hud.hide_hud()
        self.hud.close()
        if self._hotkeys is not None:
            self._hotkeys.unregister_all()
            self._hotkeys.detach()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.tray.hide()

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.MouseButtonPress:
            self._commit_editors(event)
        return super().eventFilter(obj, event)

    def _commit_editors(self, event) -> None:
        """点到编辑区之外（包括空白处）就结束编辑。
        只按坐标判断：鼠标事件会从被点的控件往父级冒泡，每冒一层过滤器就被叫一次，
        按事件接收者判断的话，点在输入框自己的内边距上也会被当成点了别处。"""
        pos = event.globalPosition().toPoint()
        editors = (getattr(self, "k_toggle", None), getattr(self, "f_jitter", None),
                   getattr(self, "readout", None))
        for editor in editors:
            if editor is None or not editor.is_editing():
                continue
            if not editor.rect().contains(editor.mapFromGlobal(pos)):
                editor.commit_edit()

    # 配置持久化
    def _config_dict(self) -> dict:
        return {
            "hotkey": self.k_toggle.vk(),
            "mode": "hold" if self.trigger_mode() is TriggerMode.HOLD else "toggle",
            "button": self.mouse_button(),
            "cps": round(self.readout.value(), 1),
            "shake": self.sw_shake.isChecked(),
            "human": self.sw_human.isChecked(),
            "jitter_on": self.sw_jitter.isChecked(),
            "jitter": self.f_jitter.text(),
            "hud": self.sw_hud.isChecked(),
            "close": self._close_action,
            "on_top": self.app_bar.is_pinned(),
            "theme": "dark" if THEME.dark else "light",
            "tray_tip": self._tray_tipped,
        }

    def _on_theme_toggle(self) -> None:
        THEME.toggle()
        self._touch_config()

    def _touch_config(self) -> None:
        """改了就重启保存计时器 —— 连续改动只有最后一次真正落盘。"""
        self._save_timer.start()

    def _save_config(self) -> None:
        if not self._loaded or self._discard_config:
            return          # 骨架阶段没控件可存；清了配置之后也不许再写回去
        config.save(self._config_dict())

    def clear_config_and_quit(self) -> None:
        """高级：删掉配置文件然后退出。退出流程不能再把它写回来。"""
        self._discard_config = True
        self._save_timer.stop()
        config.clear()
        self.request_quit()

    def _apply_config(self) -> None:
        """把存下来的设置灌进控件。"""
        c = self._cfg
        # 存过主题就用存的，没存过就保持启动时定下的（跟随系统）
        if c.get("theme") in ("dark", "light"):
            THEME.set_dark(c["theme"] == "dark")
        if isinstance(c.get("hotkey"), int):
            self.k_toggle.set_vk(c["hotkey"])
        if c.get("mode") == "hold":
            self.trigger.set_index(1)
        if c.get("button") in MOUSE_KEYS:
            self.mouse_btn.set_index(MOUSE_KEYS.index(c["button"]))
        self.sw_shake.setChecked(bool(c.get("shake", True)))
        self.sw_human.setChecked(bool(c.get("human", False)))
        self.sw_hud.setChecked(bool(c.get("hud", False)))
        self._close_action = 1 if c.get("close") == 1 else 0
        self.seg_close.set_index(self._close_action)
        self.sw_jitter.setChecked(bool(c.get("jitter_on", False)))
        self.f_jitter.setText(str(c.get("jitter", JITTER_DEFAULT)))
        self._sync_jitter_row()
        if c.get("on_top"):
            self.app_bar.set_pinned(True)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        cps = c.get("cps")
        # 没有配置就是全新安装，用 100 CPS 作为默认
        self._sync_rate(float(cps) if isinstance(cps, (int, float)) else 100.0)

    def _jitter_value(self) -> int:
        """输入框里的值，非法就回落到默认值。"""
        try:
            value = int(float(self.f_jitter.text()))
        except ValueError:
            value = JITTER_DEFAULT
        return max(1, min(JITTER_MAX, value))

    def _jitter_radius(self) -> int:
        return self._jitter_value() if self.sw_jitter.isChecked() else 0

    def _sync_jitter_row(self) -> None:
        """铅笔与就地输入框按状态互斥显示。"""
        on = self.sw_jitter.isChecked()
        self._editing_jitter = self._editing_jitter and on
        self.btn_jitter_edit.setVisible(on and not self._editing_jitter)
        self.f_jitter.setVisible(on and self._editing_jitter)
        self.row_jitter.set_supporting(f"±{self._jitter_value()} px")

    def _begin_jitter_edit(self) -> None:
        self._editing_jitter = True
        self._sync_jitter_row()
        self.f_jitter.focus_edit()

    def _end_jitter_edit(self) -> None:
        if not self._editing_jitter:
            return
        self._editing_jitter = False
        self.f_jitter.setText(str(self._jitter_value()))
        self._sync_jitter_row()
        self._refresh()

    def _on_jitter_changed(self) -> None:
        self._sync_jitter_row()
        self._refresh()

    def _notify_tray_once(self) -> None:
        """托盘提示一辈子只弹一次。

        弹过就立刻落盘，所以哪怕用户直接强杀进程，下次也不会再弹。
        """
        if self._tray_tipped:
            return
        self._tray_tipped = True
        self.tray.show_message("Ultra AC 仍在后台运行",
                               "双击托盘图标可以重新打开窗口")
        self._save_config()

    def _on_close_action(self, index: int) -> None:
        """0 = 关闭时收进托盘；1 = 直接退出。"""
        self._close_action = int(index)
        self._touch_config()

    def request_quit(self) -> None:
        self._really_quit = True
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        # 默认关窗口是收进托盘，可在设置里改成直接退出
        to_tray = (self._close_action == 0 and self.tray.available()
                   and not self._really_quit)
        if to_tray:
            event.ignore()
            self._hide_to_tray()
            return
        self.shutdown()
        super().closeEvent(event)
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def open_settings(self) -> None:
        if self.about_sheet.is_open():
            self.about_sheet.close_sheet()
        self.sheet.setGeometry(self.rect())
        self.sheet.open()

    def open_hotkey_settings(self) -> None:
        """点状态行上的快捷键，直接把设置面板打开并进入改键状态。"""
        self.open_settings()
        # 等面板滑上来再进捕获，否则抢不到焦点
        QTimer.singleShot(motion_duration(Dur.MEDIUM4),
                          self.k_toggle.begin_capture)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._center_spinner()
        for sheet in ("sheet", "about_sheet"):
            obj = getattr(self, sheet, None)
            if obj is not None:
                obj.setGeometry(self.rect())

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_shape(p, QRectF(self.rect()), Shape.WINDOW,
                   fill=THEME.s.surface, border=THEME.s.outline_variant)
