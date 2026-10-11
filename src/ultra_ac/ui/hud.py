# -*- coding: utf-8 -*-
"""迷你悬浮窗：置顶显示运行状态与实际 CPS。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication

from ..theme import (Dur, THEME, emphasized_decelerate,
                     expressive_spring, motion_duration)
from ..widgets.primitives import (ThemedWidget, anim_float, draw_shape, md_font,
                                  qc, rounded_path)

WIDTH = 124
HEIGHT = 40
DOCK_W = 30        # 吸附后只留状态点的宽度
SNAP = 30          # 距边缘多少像素内触发吸附
MARGIN = 18
TEXT_FADE_FROM = 48  # 宽度小于此值就不画文字
SLIDE = 10.0       # 入场/退场时相对静止位置的位移


class Hud(ThemedWidget):
    """置顶小胶囊。可拖动；贴到左右边缘会吸附成圆点。"""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(WIDTH, HEIGHT)
        self.setCursor(Qt.SizeAllCursor)

        self._running = False
        self._actual: float | None = None
        self._shown_once = False

        self._dock = 0                 # -1 左 / 0 自由 / 1 右
        self._hovered = False
        self._drag_origin: QPointF | None = None
        self._from = (0, WIDTH)
        self._to = (0, WIDTH)
        self._y = 0
        # 静止位置。淡入淡出只改窗口的实际坐标，绝不动这个锚点 ——
        # 之前是用"当前 y"当地基，动画被中途打断一次就永久上移 10px，
        # 反复开关几次悬浮窗就一路爬出屏幕。
        self._anchor = QPoint(0, 0)
        self._fade_offset = 0

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(motion_duration(Dur.MEDIUM3))
        self._anim.setEasingCurve(expressive_spring())
        self._anim.valueChanged.connect(self._on_geometry)

        # 入场/退场：淡入淡出 + 轻微上浮
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(motion_duration(Dur.MEDIUM2))
        self._fade.setEasingCurve(emphasized_decelerate())
        self._fade.valueChanged.connect(self._on_fade)
        self._fade.finished.connect(self._on_fade_done)
        self._fade_hiding = False

    def set_state(self, running: bool, actual: float | None) -> None:
        if (running, actual) == (self._running, self._actual):
            return
        self._running, self._actual = running, actual
        self.update()

    def show_hud(self) -> None:
        if not self._shown_once:
            self._shown_once = True
            self.move_to_default()
        self._fade.stop()
        self._fade_hiding = False
        self._fade_offset = round(SLIDE)
        self._apply_offset()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def hide_hud(self) -> None:
        if not self.isVisible():
            return
        self._fade.stop()
        self._fade_hiding = True
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _on_fade(self, v) -> None:
        t = anim_float(v, 1.0)
        self.setWindowOpacity(t)
        # 入场从下面浮上来，退场往上收，两边对称；锚点本身不动
        self._fade_offset = round(-SLIDE * (1.0 - t) if self._fade_hiding
                                  else SLIDE * (1.0 - t))
        self._apply_offset()

    def _on_fade_done(self) -> None:
        if self._fade_hiding:
            self._fade_offset = 0
            self._apply_offset()
            self.hide()
            self.setWindowOpacity(1.0)

    def _apply_offset(self) -> None:
        self.move(self._anchor.x(), self._anchor.y() + self._fade_offset)

    def _set_pos(self, x: int, y: int) -> None:
        """所有位移都从这里走，保证锚点与实际位置不会脱节。"""
        self._anchor = QPoint(int(x), int(y))
        self._apply_offset()

    def _screen(self):
        return (self.screen() or QApplication.primaryScreen())

    def _clamp(self, x: int, y: int) -> tuple[int, int]:
        g = self._screen().availableGeometry()
        x = max(g.left(), min(x, g.right() - self.width() + 1))
        y = max(g.top(), min(y, g.bottom() - self.height() + 1))
        return x, y

    def move_to_default(self) -> None:
        """默认贴主屏右上角，但保持在屏幕内。"""
        g = self._screen().availableGeometry()
        self._set_pos(*self._clamp(g.right() - WIDTH - MARGIN, g.top() + MARGIN))

    # 吸附
    def _animate_to(self, x: int, width: int, dock: int, y: int) -> None:
        self._dock = dock
        self._from = (self._anchor.x(), self.width())
        self._to = (x, width)
        self._y = y
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _on_geometry(self, v) -> None:
        x0, w0 = self._from
        x1, w1 = self._to
        t = anim_float(v, 1.0)
        self.setFixedWidth(max(DOCK_W, round(w0 + (w1 - w0) * t)))
        self._set_pos(round(x0 + (x1 - x0) * t), self._y)
        self.update()

    def _expanded_x(self) -> int:
        """展开成完整宽度时的 x —— 吸附在哪边就贴住哪边不动。"""
        g = self._screen().availableGeometry()
        if self._dock > 0:
            return max(g.left(), g.right() - WIDTH + 1)
        return g.left()

    def _docked_x(self) -> int:
        g = self._screen().availableGeometry()
        return g.left() if self._dock < 0 else g.right() - DOCK_W + 1

    def _settle(self) -> None:
        """按当前吸附状态摆到位。鼠标还在上面就保持展开，离开了才收成点。"""
        g = self._screen().availableGeometry()
        y = max(g.top(), min(self._anchor.y(), g.bottom() - HEIGHT + 1))
        if not self._dock:
            cx, cy = self._clamp(self._anchor.x(), y)
            self._animate_to(cx, WIDTH, 0, cy)
        elif self._hovered or self._drag_origin is not None:
            self._animate_to(self._expanded_x(), WIDTH, self._dock, y)
        else:
            self._animate_to(self._docked_x(), DOCK_W, self._dock, y)

    def _snap(self) -> None:
        """松手后判定吸附：贴边就吸附，否则回到完整胶囊并钳进屏幕。"""
        g = self._screen().availableGeometry()
        x = self._anchor.x()
        if x <= g.left() + SNAP:
            self._dock = -1
        elif x + self.width() >= g.right() - SNAP:
            self._dock = 1
        else:
            self._dock = 0
        self._settle()

    # 拖动（自己实现而不用 startSystemMove，因为需要在松手时做吸附判定）
    def enterEvent(self, event):  # noqa: N802
        # 收成点之后，鼠标一碰就展开（带动画）
        self._hovered = True
        if self._dock:
            self._settle()

    def leaveEvent(self, event):  # noqa: N802
        self._hovered = False
        if self._dock and self._drag_origin is None:
            self._settle()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        self._anim.stop()
        # 淡入淡出没走完就上手拖：先落到锚点上，免得拖拽基准带着偏移
        self._fade.stop()
        self._fade_offset = 0
        self.setWindowOpacity(1.0)
        self._apply_offset()
        if self._dock and self.width() < WIDTH:
            # 点一下先展开，但**不脱离吸附** —— 只有真的拖动了才脱离
            self.setFixedWidth(WIDTH)
            self._set_pos(self._expanded_x(), self._anchor.y())
        self._drag_origin = (event.globalPosition().toPoint() - self.pos())

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_origin is None:
            return
        if self._dock:
            # 真的动了才脱离吸附，否则单纯点一下不该把它从边上拽下来
            self._dock = 0
            self._drag_origin = (event.globalPosition().toPoint() - self.pos())
        target = event.globalPosition().toPoint() - self._drag_origin
        self._set_pos(*self._clamp(target.x(), target.y()))

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() != Qt.LeftButton or self._drag_origin is None:
            return
        self._drag_origin = None
        self._snap()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s = THEME.s
        w = self.width()

        # 一层平底就够：以前是阴影 + 描边 + 底色三层叠在一枚 40px 高的胶囊里，
        # 边缘糊成一圈同心线，既不干净也不像 MD3。
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setClipPath(rounded_path(QRectF(self.rect()), HEIGHT / 2))
        draw_shape(p, body, HEIGHT / 2, fill=s.surface_container_high)

        # 收窄时状态点自然居中：19 是完整胶囊里的位置，min 之后会向中心靠
        dot_x = min(19.0, w / 2)
        cy = self.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(qc(s.success if self._running else s.outline))
        p.drawEllipse(QPointF(dot_x, cy), 5.5, 5.5)

        # 文字随宽度淡出，收成圆点时就完全看不见
        fade = max(0.0, min(1.0, (w - TEXT_FADE_FROM) / (WIDTH - TEXT_FADE_FROM)))
        if fade > 0.01:
            p.setOpacity(fade)
            text = "—" if self._actual is None else f"{self._actual:.1f}"
            p.setFont(md_font("title_medium"))
            p.setPen(qc(s.on_surface if self._actual is not None
                        else s.on_surface_variant))
            p.drawText(QRectF(dot_x + 13, 0, 50, self.height()),
                       Qt.AlignRight | Qt.AlignVCenter, text)
            p.setFont(md_font("label_small"))
            p.setPen(qc(s.on_surface_variant))
            p.drawText(QRectF(w - 38, 0, 32, self.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, "CPS")
            p.setOpacity(1.0)
