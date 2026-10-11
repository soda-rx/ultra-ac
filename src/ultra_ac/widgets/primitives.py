# -*- coding: utf-8 -*-
"""MD3 绘制原语：字体、形状、状态层、水波纹、高度阴影、按压形变。"""

from __future__ import annotations

import os

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation,
                            Signal)
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QPainter, QPainterPath,
                           QPen)
from PySide6.QtWidgets import QWidget

from ..theme import (Shape, THEME, TYPE_SCALE, Dur, expressive_spring,
                     motion_duration, motion_enabled, standard)
from ..theme import FONT_STACK

# 字体

_WIN_FONTS = ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf", "segoeuib.ttf")
_fonts_loaded = False


def ensure_fonts() -> None:
    """把项目自带字体和系统中文字体显式注册进来。"""
    global _fonts_loaded
    if _fonts_loaded:
        return
    _fonts_loaded = True

    bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "assets", "fonts")
    if os.path.isdir(bundled):
        for name in sorted(os.listdir(bundled)):
            if name.lower().endswith((".ttf", ".otf", ".ttc")):
                QFontDatabase.addApplicationFont(os.path.join(bundled, name))

    windir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in _WIN_FONTS:
        path = os.path.join(windir, name)
        if os.path.exists(path):
            QFontDatabase.addApplicationFont(path)


def md_font(role: str, *, scale: float = 1.0) -> QFont:
    """按 MD3 字体阶角色取字体。"""
    size, weight, tracking = TYPE_SCALE[role]
    f = QFont()
    f.setFamilies(FONT_STACK)
    f.setPixelSize(max(1, round(size * scale)))
    f.setWeight(QFont.Weight(weight))
    if tracking:
        f.setLetterSpacing(QFont.AbsoluteSpacing, tracking)
    return f


def qc(hex_color: str, alpha: float = 1.0) -> QColor:
    c = QColor(hex_color)
    if alpha < 1.0:
        c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def anim_float(value, fallback: float = 0.0) -> float:
    """动画回调的取值口。

    QVariantAnimation 在停止状态下被改写端点的那一刻会吐出一个无效变体
    （Python 侧是 None）。直接 float() 会抛 TypeError，槽函数一崩，动画之后
    就再也不更新了 —— 面板卡在半空、点空白关不掉就是这么来的。
    """
    return float(value) if isinstance(value, (int, float)) else float(fallback)


# 形状与高度

def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    r = min(radius, rect.width() / 2, rect.height() / 2)
    path.addRoundedRect(rect, r, r)
    return path


def draw_shape(p: QPainter, rect: QRectF, radius: float, *,
               fill: str | None = None, fill_alpha: float = 1.0,
               border: str | None = None, border_width: float = 1.0) -> None:
    path = rounded_path(rect, radius)
    if fill is not None:
        p.setPen(Qt.NoPen)
        p.setBrush(qc(fill, fill_alpha))
        p.drawPath(path)
    if border is not None:
        p.setBrush(Qt.NoBrush)
        pen = QPen(qc(border), border_width)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        inset = border_width / 2
        p.drawPath(rounded_path(rect.adjusted(inset, inset, -inset, -inset),
                                radius - inset))


def soft_shadow(p: QPainter, rect: QRectF, radius: float, level: int,
                color: str) -> None:
    """MD3 高度阴影。用多层低透明度圆角矩形叠加近似高斯模糊。"""
    from ..theme import ELEVATION
    if level <= 0:
        return
    dy, blur, alpha = ELEVATION[level]
    steps = 18
    p.save()
    p.setPen(Qt.NoPen)
    for i in range(steps, 0, -1):
        f = i / steps
        grow = blur * f * 0.55
        a = alpha * (1.0 - f) * 0.55
        p.setBrush(qc(color, a))
        p.drawRoundedRect(
            rect.adjusted(-grow, -grow + dy, grow, grow + dy),
            radius + grow, radius + grow)
    p.restore()


# 状态层与水波纹

STATE_HOVER = 0.08
STATE_PRESS = 0.10


class Ripple:
    """单个水波纹。从触点扩散并淡出。"""

    __slots__ = ("center", "t", "anim")

    def __init__(self, center: QPointF, parent: QWidget, on_tick) -> None:
        self.center = center
        self.t = 0.0
        self.anim = QVariantAnimation(parent)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setDuration(motion_duration(450))
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(lambda v: (setattr(self, "t", float(v)),
                                                  on_tick()))
        self.anim.start()


# 可交互基类

class MdInteractive(QWidget):
    """MD3 可交互控件的公共基类。"""

    clicked = Signal()

    # 按下时的缩放比（MD3 Expressive 的按压反馈）
    PRESS_SCALE = 0.96

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hovered = False
        self._pressed = False
        self._layer = 0.0
        self._scale = 1.0
        self._ripples: list[Ripple] = []
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)

        self._layer_anim = QVariantAnimation(self)
        self._layer_anim.setDuration(motion_duration(Dur.SHORT4))
        self._layer_anim.setEasingCurve(standard())
        self._layer_anim.valueChanged.connect(self._on_layer)

        self._scale_anim = QVariantAnimation(self)
        self._scale_anim.valueChanged.connect(self._on_scale)

        THEME.changed.connect(self.update)

    def corner_radius(self) -> float:
        return Shape.FULL

    def container_rect(self) -> QRectF:
        return QRectF(self.rect())

    def layer_role(self) -> str:
        """状态层与波纹的颜色。**必须返回真实色值，不能返回角色名。**"""
        return THEME.s.on_surface

    def surface_fill(self) -> str | None:
        return None

    def surface_border(self) -> str | None:
        return None

    def border_width(self) -> float:
        return 1.0

    def content_color(self) -> str:
        return THEME.s.on_surface

    def paint_content(self, p: QPainter, rect: QRectF) -> None:
        """子类在这里画内容（文字、图标）。"""

    def _on_layer(self, value) -> None:
        self._layer = anim_float(value, self._layer)
        self.update()

    def _on_scale(self, value) -> None:
        self._scale = anim_float(value, self._scale)
        self.update()

    def _animate_layer(self, target: float) -> None:
        if abs(target - self._layer) < 1e-6:
            return
        self._layer_anim.stop()
        self._layer_anim.setStartValue(self._layer)
        self._layer_anim.setEndValue(target)
        self._layer_anim.start()

    def _animate_scale(self, target: float, *, spring: bool) -> None:
        if abs(target - self._scale) < 1e-6:
            return
        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._scale)
        self._scale_anim.setEndValue(target)
        if spring:
            self._scale_anim.setDuration(motion_duration(Dur.MEDIUM2))
            self._scale_anim.setEasingCurve(expressive_spring())
        else:
            self._scale_anim.setDuration(motion_duration(Dur.SHORT3))
            self._scale_anim.setEasingCurve(standard())
        self._scale_anim.start()

    def _push_ripple(self, pos: QPointF) -> None:
        if not motion_enabled():
            return                    # 关了动效就别铺一层静止的水波纹
        self._ripples = [r for r in self._ripples if r.anim.state() ==
                         QVariantAnimation.Running]
        self._ripples.append(Ripple(pos, self, self.update))

    def ripple_paint(self, p: QPainter, rect: QRectF, radius: float,
                     color: str) -> None:
        if not self._ripples:
            return
        path = rounded_path(rect, radius)
        p.save()
        p.setClipPath(path)
        reach = max(rect.width(), rect.height()) * 1.15
        for r in self._ripples:
            t = r.t
            # 半径快速铺满，透明度随后淡出
            rad = reach * (0.15 + 0.85 * t)
            alpha = 0.14 * (1.0 - t) ** 1.6
            if alpha <= 0.001:
                continue
            p.setPen(Qt.NoPen)
            p.setBrush(qc(color, alpha))
            p.drawEllipse(r.center, rad, rad)
        p.restore()

    def state_layer_paint(self, p: QPainter, rect: QRectF, radius: float) -> None:
        if self._layer <= 0.001:
            return
        path = rounded_path(rect, radius)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(self.layer_role(), self._layer))
        p.drawPath(path)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        if self.isEnabled():
            self._animate_layer(STATE_HOVER)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self._pressed = False
        self._animate_layer(0.0)
        self._animate_scale(1.0, spring=True)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton or not self.isEnabled():
            return
        self._pressed = True
        self._animate_layer(STATE_PRESS)
        self._animate_scale(self.PRESS_SCALE, spring=False)
        self._push_ripple(event.position())

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        was = self._pressed
        self._pressed = False
        self._animate_layer(STATE_HOVER if self._hovered else 0.0)
        self._animate_scale(1.0, spring=True)
        if was and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if not self.isEnabled():
            self._pressed = False
            self._animate_layer(0.0)
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setCursor(Qt.PointingHandCursor)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        if self._scale != 1.0:
            cx, cy = self.width() / 2, self.height() / 2
            p.translate(cx, cy)
            p.scale(self._scale, self._scale)
            p.translate(-cx, -cy)

        rect = self.container_rect()
        radius = self.corner_radius()
        fill = self.surface_fill()
        border = self.surface_border()

        if fill is not None:
            draw_shape(p, rect, radius, fill=fill)
        if border is not None:
            draw_shape(p, rect, radius, border=border,
                       border_width=self.border_width())
        self.state_layer_paint(p, rect, radius)
        self.ripple_paint(p, rect, radius,
                          self.content_color() if fill is None
                          else self.layer_role())
        self.paint_content(p, rect)


class ThemedWidget(QWidget):
    """非交互控件的基类，订阅主题变化。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        THEME.changed.connect(self._on_theme)

    def _on_theme(self) -> None:
        self.update()

    @property
    def s(self):
        return THEME.s
