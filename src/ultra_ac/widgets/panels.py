# -*- coding: utf-8 -*-
"""MD3 面板级组件：顶部应用栏、底部面板、状态行、列表项、卡片。"""

from __future__ import annotations

from PySide6.QtCore import (QPointF, QRectF, Qt, QVariantAnimation,
                            Signal)
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..theme import (Dur, Shape, Space, THEME, emphasized_decelerate,
                     expressive_spring, motion_duration, standard)
from .controls import MdIconButton
from .icons import LOGO_BG, LOGO_FG, draw_app_icon, draw_icon
from .primitives import (MdInteractive, ThemedWidget, anim_float, draw_shape,
                         md_font, qc, rounded_path, soft_shadow)

APP_BAR_H = 64
SHEET_RADIUS = 28
# 面板顶部（把手 + 标题）高度
SHEET_HEADER = 64


# 顶部应用栏

class TopAppBar(ThemedWidget):
    """MD3 小号顶部应用栏（64dp）：应用图标 + 标题 + 尾部图标按钮，可拖动移动窗口。"""

    minimizeRequested = Signal()
    closeRequested = Signal()
    themeToggleRequested = Signal()
    pinToggled = Signal(bool)

    ICON = 26.0

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self.setFixedHeight(APP_BAR_H)

        self._pinned = False
        self.btn_theme = MdIconButton("contrast", parent=self)
        self.btn_pin = MdIconButton("push_pin", variant="toggle", parent=self)
        self.btn_min = MdIconButton("remove", parent=self)
        self.btn_close = MdIconButton("close", parent=self)
        self.btn_theme.clicked.connect(self.themeToggleRequested)
        self.btn_pin.clicked.connect(self._on_pin)
        self.btn_min.clicked.connect(self.minimizeRequested)
        self.btn_close.clicked.connect(self.closeRequested)

    def _on_pin(self) -> None:
        self._pinned = not self._pinned
        self.btn_pin.set_selected(self._pinned)
        self.pinToggled.emit(self._pinned)

    def is_pinned(self) -> bool:
        return self._pinned

    def set_pinned(self, on: bool) -> None:
        """直接设值、不发信号 —— 从配置文件恢复时用。"""
        self._pinned = bool(on)
        self.btn_pin.set_selected(self._pinned)

    def resizeEvent(self, _e) -> None:  # noqa: N802
        size = 40
        y = (APP_BAR_H - size) // 2
        x = self.width() - Space.XS - size
        # 从右往左：关闭、最小化、置顶、主题
        for btn in (self.btn_close, self.btn_min, self.btn_pin, self.btn_theme):
            btn.move(x, y)
            x -= size

    def _hit_button(self, pos) -> bool:
        for btn in (self.btn_theme, self.btn_pin, self.btn_min, self.btn_close):
            if btn.geometry().contains(pos.toPoint()):
                return True
        return False

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() != Qt.LeftButton or self._hit_button(e.position()):
            return
        handle = self.window().windowHandle()
        if handle is not None:
            handle.startSystemMove()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s = THEME.s
        icon = self.ICON
        draw_app_icon(p, QRectF(Space.L, (APP_BAR_H - icon) / 2, icon, icon),
                      bg=LOGO_BG, fg=LOGO_FG)
        p.setFont(md_font("title_large"))
        p.setPen(qc(s.on_surface))
        p.drawText(QRectF(Space.L + icon + Space.S, 0, 220, APP_BAR_H),
                   Qt.AlignLeft | Qt.AlignVCenter, self._title)


# 状态行

class StatusRow(ThemedWidget):
    """状态行：状态点 + 当前快捷键（或提示语）+ 右侧提示。

    左边那截"快捷键 X"是可以点的，点了直接去设置里改键。
    """

    hotkeyClicked = Signal()

    LABEL_W = 132

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._running = False
        self._notice = ""
        self._hotkey = "—"
        self._hint = ""
        self._hovered = False
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)
        self.setFixedHeight(40)

    def set_hotkey(self, name: str) -> None:
        if name != self._hotkey:
            self._hotkey = name
            self.update()

    def set_hint(self, text: str) -> None:
        """非空时顶替左侧的快捷键 —— 按住模式下那里要说明怎么触发。"""
        if text != self._hint:
            self._hint = text
            self.update()

    def set_notice(self, text: str) -> None:
        """提示占中段位置，长文本向左回退，别压到快捷键上。"""
        if text != self._notice:
            self._notice = text
            self.update()

    def set_running(self, running: bool) -> None:
        self._running = running
        self.update()

    def _clickable(self) -> bool:
        """提示语顶替了快捷键（按住模式）时不响应点击。"""
        return not self._hint

    def _in_label(self, x: float) -> bool:
        return self._clickable() and 0.0 <= x <= self.LABEL_W

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton and self._in_label(e.position().x()):
            self.hotkeyClicked.emit()

    def mouseMoveEvent(self, e):  # noqa: N802
        inside = self._in_label(e.position().x())
        if inside != self._hovered:
            self._hovered = inside
            self.setCursor(Qt.PointingHandCursor if inside else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, e):  # noqa: N802
        self._hovered = False
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s = THEME.s
        cy = self.height() / 2
        color = s.success if self._running else s.outline

        p.setPen(Qt.NoPen)
        p.setBrush(qc(color))
        p.drawEllipse(QPointF(6, cy), 5.0, 5.0)

        p.setFont(md_font("label_large"))
        p.setPen(qc(s.primary if self._hovered
                    else s.on_surface_variant))
        p.drawText(QRectF(18, 0, self.LABEL_W - 18, self.height()),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   self._hint or f"快捷键 {self._hotkey}")

        if self._notice:
            p.setFont(md_font("body_medium"))
            p.setPen(qc(s.error))
            p.drawText(QRectF(150, 0, self.width() - 150, self.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, self._notice)


# 列表项 / 卡片 / 辅助文字

class ListItem(ThemedWidget):
    """MD3 列表项：左侧标签，右侧控件。"""

    HEIGHT = 44

    def __init__(self, label: str, controls: list[QWidget], *,
                 supporting: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._supporting = supporting
        self.setFixedHeight(self.HEIGHT if not supporting else self.HEIGHT + 8)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(Space.S)
        lay.addStretch(1)
        for w in controls:
            lay.addWidget(w, 0, Qt.AlignVCenter)

    def set_supporting(self, text: str) -> None:
        if text != self._supporting:
            self._supporting = text
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        s = THEME.s
        p.setFont(md_font("body_large"))
        p.setPen(qc(s.on_surface))
        top = 0 if not self._supporting else 6
        p.drawText(QRectF(0, top, self.width(), 22 if self._supporting
                          else self.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self._label)
        if self._supporting:
            p.setFont(md_font("body_small"))
            p.setPen(qc(s.on_surface_variant))
            p.drawText(QRectF(0, top + 22, self.width(), 18),
                       Qt.AlignLeft | Qt.AlignVCenter, self._supporting)


class SectionHeader(ThemedWidget):
    """面板里的小节标题。"""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(32)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(md_font("label_large"))
        p.setPen(qc(THEME.s.primary))
        p.drawText(QRectF(0, 0, self.width(), self.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self._text)


class Caption(ThemedWidget):
    """辅助文字。role 决定字号，color_role 决定颜色角色。"""

    def __init__(self, text: str, *, role: str = "label_medium",
                 color_role: str = "on_surface_variant",
                 align: Qt.AlignmentFlag = Qt.AlignLeft,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._role = role
        self._color_role = color_role
        self._align = align
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def setText(self, value: str) -> None:  # noqa: N802
        if value != self._text:
            self._text = value
            self.update()

    def text(self) -> str:
        return self._text

    def sizeHint(self):  # noqa: N802
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QFontMetricsF as _FM
        fm = _FM(md_font(self._role))
        # 字距作用在最后一个字符之后，留窄了会把结尾裁掉
        return QSize(round(fm.horizontalAdvance(self._text)) + 12,
                     round(fm.height()) + 4)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(md_font(self._role))
        p.setPen(qc(getattr(THEME.s, self._color_role)))
        p.drawText(QRectF(0, 0, self.width(), self.height()),
                   self._align | Qt.AlignVCenter, self._text)


class Card(ThemedWidget):
    """MD3 卡片容器。内容由内部布局摆放，这里只负责底板。"""

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_shape(p, QRectF(self.rect()), Shape.M,
                   fill=THEME.s.surface_container_low)


class WarningBar(ThemedWidget):
    """卡片里的一条警示：error_container 底 + 警示图标 + 一句话。

    上下各留 GAP 的空隙，隐藏时整条（含空隙）都不占高度。
    """

    GAP = 8
    BODY = 34
    HEIGHT = BODY + GAP * 2
    ICON = 18.0

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(self.HEIGHT)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s = THEME.s
        body = QRectF(self.rect()).adjusted(0, self.GAP, 0, -self.GAP)
        draw_shape(p, body, Shape.S, fill=s.error_container)
        draw_icon(p, "warning",
                  QRectF(Space.M, body.center().y() - self.ICON / 2,
                         self.ICON, self.ICON), s.error)
        p.setFont(md_font("body_small"))
        p.setPen(qc(s.on_error_container))
        p.drawText(QRectF(Space.M + self.ICON + Space.S, body.top(),
                          body.width() - Space.M * 2 - self.ICON - Space.S,
                          body.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self._text)


class ActionRow(MdInteractive):
    """可点击的列表项：左侧标签（可带副标题），右侧图标。"""

    HEIGHT = 56
    TWO_LINE_HEIGHT = 68

    def __init__(self, label: str, *, supporting: str = "",
                 icon: str = "expand_more", border_role: str | None = None,
                 color_role: str | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._supporting = supporting
        self._icon = icon
        self._border_role = border_role
        self._color_role = color_role
        self.setFixedHeight(self.TWO_LINE_HEIGHT if supporting else self.HEIGHT)

    def _accent(self) -> str:
        """标签与图标的颜色。给了 color_role 就按它走（破坏性操作会传 error）。"""
        if self._color_role:
            return getattr(THEME.s, self._color_role, THEME.s.on_surface)
        return THEME.s.on_surface

    def corner_radius(self) -> float:
        return Shape.FULL

    def surface_border(self) -> str | None:
        if not self._border_role:
            return None
        return getattr(THEME.s, self._border_role, THEME.s.outline_variant)

    def surface_fill(self) -> str | None:
        # 椭圆按钮给一层极淡的底，免得描边显得空
        return THEME.s.surface_container_low if self._border_role else None

    def layer_role(self) -> str:
        return self._accent()

    def content_color(self) -> str:
        return self._accent()

    def paint_content(self, p: QPainter, rect: QRectF) -> None:
        s = THEME.s
        pad = Space.XL if self._border_role else Space.L
        size = 24.0
        text_w = rect.width() - pad * 2 - size - Space.S
        if self._supporting:
            p.setFont(md_font("body_large"))
            p.setPen(qc(self._accent()))
            p.drawText(QRectF(pad, 12, text_w, 22),
                       Qt.AlignLeft | Qt.AlignVCenter, self._label)
            p.setFont(md_font("body_small"))
            p.setPen(qc(s.on_surface_variant))
            p.drawText(QRectF(pad, 34, text_w, 18),
                       Qt.AlignLeft | Qt.AlignVCenter, self._supporting)
        else:
            p.setFont(md_font("body_large"))
            p.setPen(qc(self._accent()))
            p.drawText(QRectF(pad, 0, text_w, rect.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, self._label)
        icon_color = (self._accent() if self._color_role
                      else s.primary if self._border_role
                      else s.on_surface_variant)
        draw_icon(p, self._icon,
                  QRectF(rect.right() - pad - size,
                         rect.center().y() - size / 2, size, size),
                  icon_color)


# 底部面板

class ModalBottomSheet(QWidget):
    """MD3 模态底部面板，带两档高度（半展开 / 全展开）。"""

    # 顶部拖拽把手区高度
    GRAB_HEIGHT = 64
    # 半展开占窗口高度的比例
    HALF_RATIO = 0.52
    # 相对半展开高度再往下拖这个比例就关闭
    DISMISS_RATIO = 0.42

    def __init__(self, title: str, content: QWidget,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._h = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(motion_duration(Dur.MEDIUM4))
        self._anim.setEasingCurve(emphasized_decelerate())
        self._anim.valueChanged.connect(self._on_h)
        self._anim.finished.connect(self._on_finished)

        self._drag_from: float | None = None
        self._drag_h0 = 0.0
        self._close_on_release = False
        self._scroll = 0.0

        self._shadow = None
        self._shadow_key = None
        self._shadow_margin = 48

        # 内容放进取景框，滚动时不会画到把手和标题上
        self._viewport = QWidget(self)
        self._content = content
        self._content.setParent(self._viewport)

        # 标题栏右端的上/下箭头：不想拖把手时也能在半展开与全展开之间切换
        self.btn_expand = MdIconButton("expand_less", parent=self)
        self.btn_expand.setToolTip("展开 / 收起")
        self.btn_expand.clicked.connect(self.toggle_expanded)
        self.btn_expand.raise_()
        self.hide()

    def content_height(self) -> int:
        return self._content.sizeHint().height()

    def max_height(self) -> int:
        """全展开高度。减掉 APP_BAR_H 就是为了不遮挡标题栏按钮。"""
        return max(SHEET_HEADER + 80, self.height() - APP_BAR_H)

    def detents(self) -> tuple[float, float]:
        """两档高度：(半展开, 全展开)。"""
        full = min(float(self.max_height()),
                   SHEET_HEADER + self.content_height() + Space.L)
        half = min(full, self.height() * self.HALF_RATIO)
        return half, full

    def _scroll_max(self) -> float:
        view = max(0.0, self._h - SHEET_HEADER)
        return max(0.0, self.content_height() + Space.L - view)

    def _relayout(self) -> None:
        top = self.height() - self._h
        self._scroll = max(0.0, min(self._scroll, self._scroll_max()))
        self._viewport.setGeometry(0, round(top + SHEET_HEADER), self.width(),
                                   max(0, round(self._h - SHEET_HEADER)))
        self._content.setGeometry(Space.L, round(-self._scroll),
                                  self.width() - Space.L * 2,
                                  self.content_height())
        size = self.btn_expand.height()
        self.btn_expand.move(self.width() - Space.S - self.btn_expand.width(),
                             round(top + (SHEET_HEADER - size) / 2))

    def resizeEvent(self, _e) -> None:  # noqa: N802
        self._relayout()

    def open(self) -> None:
        self._scroll = 0.0
        self._relayout()
        self._sync_expand_icon()
        self.show()
        self.btn_expand.raise_()
        self.raise_()
        half, _full = self.detents()
        self._animate_to(half)

    def close_sheet(self) -> None:
        self._animate_to(0.0)

    def toggle_expanded(self) -> None:
        """半展开 ⇄ 全展开。"""
        if not self.is_open():
            return
        half, full = self.detents()
        self._animate_to(half if self._h >= full - 1.0 else full)

    def _animate_to(self, target: float) -> None:
        target = float(target)
        if abs(target - self._h) < 0.5:
            # 端点相同的退化动画没有意义：它在停止状态下重设起始值时会吐出
            # 一个无效变体，槽函数一旦抛异常，面板就再也动不了了
            self._h = target
            self._sync_expand_icon()
            self._relayout()
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(float(self._h))
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_h(self, v) -> None:
        self._h = anim_float(v, self._h)
        self._sync_expand_icon()
        self._relayout()
        self.update()

    def _sync_expand_icon(self) -> None:
        half, full = self.detents()
        # 只有一档高度（内容本来就装得下）就不必给展开按钮
        self.btn_expand.setVisible(full - half > 1.0)
        self.btn_expand.set_icon("expand_less"
                                 if self._h < (half + full) / 2
                                 else "expand_more")

    def _on_finished(self) -> None:
        if self._h <= 1.0:
            self.hide()

    def is_open(self) -> bool:
        return self.isVisible() and self._h > 1.0

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() != Qt.LeftButton:
            return
        y = e.position().y()
        top = self.height() - self._h
        if y < top:
            self._close_on_release = True
            return
        if y <= top + self.GRAB_HEIGHT:
            self._drag_from = y
            self._drag_h0 = self._h
            self._anim.stop()

    def mouseMoveEvent(self, e):  # noqa: N802
        if self._drag_from is None:
            return
        _half, full = self.detents()
        dy = e.position().y() - self._drag_from
        self._h = max(0.0, min(full, self._drag_h0 - dy))
        self._relayout()
        self.update()

    def mouseReleaseEvent(self, e):  # noqa: N802
        if self._close_on_release:
            self._close_on_release = False
            self.close_sheet()
            return
        if self._drag_from is None:
            return
        self._drag_from = None
        half, full = self.detents()
        if self._h < half * (1.0 - self.DISMISS_RATIO):
            self.close_sheet()
            return
        # 吸附到最近的一档
        target = half if abs(self._h - half) <= abs(self._h - full) else full
        self._animate_to(target)

    def wheelEvent(self, e):  # noqa: N802
        if self._scroll_max() <= 0.0:
            return
        self._scroll -= e.angleDelta().y() / 120.0 * 52.0
        self._relayout()
        self.update()
        e.accept()

    def _shadow_pixmap(self):
        """阴影按全展开高度缓存一份：面板底边在窗口外，只有顶边和两侧可见。"""
        h = self.max_height()
        key = (self.width(), h, THEME.s.name)
        if self._shadow is None or key != self._shadow_key:
            m = self._shadow_margin
            pm = QPixmap(self.width() + m * 2, h + m * 2)
            pm.fill(Qt.transparent)
            sp = QPainter(pm)
            sp.setRenderHint(QPainter.Antialiasing)
            soft_shadow(sp, QRectF(m, m, self.width(), h), SHEET_RADIUS, 3,
                        THEME.s.shadow)
            sp.end()
            self._shadow = pm
            self._shadow_key = key
        return self._shadow

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        p.setClipPath(rounded_path(QRectF(self.rect()), Shape.WINDOW))

        s = THEME.s
        h = self._h
        if h <= 0.5:
            return
        y = self.height() - h
        cover = min(1.0, h / max(1.0, self.max_height()))

        p.setPen(Qt.NoPen)
        p.setBrush(qc(s.scrim, 0.32 * cover))
        p.drawRect(self.rect())

        m = self._shadow_margin
        p.drawPixmap(QPointF(-m, y - m), self._shadow_pixmap())

        draw_shape(p, QRectF(0, y, self.width(), h + SHEET_RADIUS),
                   SHEET_RADIUS, fill=s.surface_container_low)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(s.surface_container_low))
        p.drawRect(QRectF(0, y + SHEET_RADIUS, self.width(), h))

        # 拖拽把手
        p.setBrush(qc(s.on_surface_variant, 0.5))
        p.drawRoundedRect(QRectF(self.width() / 2 - 16, y + 12, 32, 4), 2, 2)

        p.setFont(md_font("title_large"))
        p.setPen(qc(s.on_surface))
        p.drawText(QRectF(Space.L, y + 26, self.width() - Space.L * 2, 32),
                   Qt.AlignLeft | Qt.AlignVCenter, self._title)
