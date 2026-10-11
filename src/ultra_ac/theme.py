# -*- coding: utf-8 -*-
"""Material Design 3 设计 token：字体阶、形状阶、运动规格、主题管理。"""

from __future__ import annotations


from PySide6.QtCore import QEasingCurve, QObject, QPointF, Signal

from .md3 import DARK, LIGHT, Scheme

# 字体

# Roboto 优先；系统没装就退回 Segoe UI Variable / 微软雅黑
FONT_STACK = ["Roboto", "Segoe UI Variable", "Microsoft YaHei UI", "Segoe UI"]

WEIGHT_REGULAR = 400
WEIGHT_MEDIUM = 500

# MD3 字体阶：(字号, 字重, 字距)
TYPE_SCALE: dict[str, tuple[float, int, float]] = {
    "display_large": (57, WEIGHT_REGULAR, -0.25),
    "display_medium": (45, WEIGHT_REGULAR, 0.0),
    "display_small": (36, WEIGHT_REGULAR, 0.0),
    "headline_large": (32, WEIGHT_REGULAR, 0.0),
    "headline_medium": (28, WEIGHT_REGULAR, 0.0),
    "headline_small": (24, WEIGHT_REGULAR, 0.0),
    "title_large": (22, WEIGHT_REGULAR, 0.0),
    "title_medium": (16, WEIGHT_MEDIUM, 0.15),
    "title_small": (14, WEIGHT_MEDIUM, 0.1),
    "body_large": (16, WEIGHT_REGULAR, 0.5),
    "body_medium": (14, WEIGHT_REGULAR, 0.25),
    "body_small": (12, WEIGHT_REGULAR, 0.4),
    "label_large": (14, WEIGHT_MEDIUM, 0.1),
    "label_medium": (12, WEIGHT_MEDIUM, 0.5),
    "label_small": (11, WEIGHT_MEDIUM, 0.5),
}


# 形状与间距

class Shape:
    NONE = 0.0
    XS = 4.0
    S = 8.0
    M = 12.0
    L = 16.0
    XL = 28.0
    FULL = 999.0
    # 窗口本身的圆角
    WINDOW = 24.0


class Space:
    """MD3 的 4dp 网格。"""

    XS = 4
    S = 8
    M = 12
    L = 16
    XL = 24
    XXL = 32


# 运动规格

class Dur:
    """MD3 时长分档（毫秒）。"""

    SHORT1 = 50
    SHORT2 = 100
    SHORT3 = 150
    SHORT4 = 200
    MEDIUM1 = 250
    MEDIUM2 = 300
    MEDIUM3 = 350
    MEDIUM4 = 400
    LONG1 = 450
    LONG2 = 500
    LONG3 = 550
    LONG4 = 600


# 动效开关，跟随 Windows 的“显示动画效果”。关掉之后所有过渡一帧到位，
# 状态（选中、按下、开关位置）依旧正确，只是不再有过程。
_motion = True


def motion_enabled() -> bool:
    return _motion


def set_motion_enabled(on: bool) -> None:
    global _motion
    _motion = bool(on)


def motion_duration(ms: int) -> int:
    """动画时长。系统关了动画效果就返回 0，动画直接落到终点。"""
    return int(ms) if _motion else 0


def _bezier(x1: float, y1: float, x2: float, y2: float) -> QEasingCurve:
    curve = QEasingCurve()
    curve.setType(QEasingCurve.BezierSpline)
    curve.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2),
                                QPointF(1.0, 1.0))
    return curve


def emphasized_decelerate() -> QEasingCurve:
    return _bezier(0.05, 0.7, 0.1, 1.0)


def standard() -> QEasingCurve:
    return _bezier(0.2, 0.0, 0.0, 1.0)


def expressive_spring() -> QEasingCurve:
    """MD3 Expressive 的弹性手感：轻微过冲后回落。"""
    curve = QEasingCurve(QEasingCurve.OutBack)
    curve.setOvershoot(1.12)
    return curve


def pop_spring() -> QEasingCurve:
    """窗口弹出用：只留一点点过冲。控件那档 1.12 放到窗口尺度上就太夸张了。"""
    curve = QEasingCurve(QEasingCurve.OutBack)
    curve.setOvershoot(1.02)
    return curve


# 高度（elevation）

# MD3 elevation level → 阴影参数 (y偏移, 模糊半径, 不透明度)
ELEVATION = {
    0: (0.0, 0.0, 0.0),
    1: (1.0, 3.0, 0.15),
    2: (1.0, 6.0, 0.15),
    3: (2.0, 10.0, 0.16),
    4: (3.0, 14.0, 0.16),
    5: (4.0, 18.0, 0.18),
}


# 主题管理

class ThemeManager(QObject):
    """全局主题。控件订阅 changed 后重绘即可换肤。"""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._scheme: Scheme = LIGHT

    @property
    def s(self) -> Scheme:
        """当前颜色角色表。"""
        return self._scheme

    @property
    def dark(self) -> bool:
        return self._scheme.dark

    def set_dark(self, dark: bool) -> None:
        target = DARK if dark else LIGHT
        if target is not self._scheme:
            self._scheme = target
            self.changed.emit()

    def toggle(self) -> None:
        self.set_dark(not self._scheme.dark)


THEME = ThemeManager()
