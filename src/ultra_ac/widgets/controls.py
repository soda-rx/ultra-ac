# -*- coding: utf-8 -*-
"""Material Design 3 组件库。"""

from __future__ import annotations


from PySide6.QtCore import (QPointF, QRectF, Qt, QVariantAnimation,
                            Signal)
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from ..md3 import mix
from ..theme import (Dur, Shape, Space, THEME, expressive_spring,
                     motion_duration, standard)
from .icons import draw_icon
from .primitives import (MdInteractive, ThemedWidget, anim_float, draw_shape,
                         md_font, qc, rounded_path)


def _center_text(p: QPainter, rect: QRectF, text: str, font, color: str) -> None:
    p.setFont(font)
    p.setPen(qc(color))
    p.drawText(rect, Qt.AlignCenter, text)


def _text_width(text: str, font) -> float:
    return QFontMetricsF(font).horizontalAdvance(text)


# 按钮

class MdIconButton(MdInteractive):
    """MD3 图标按钮。默认 40×40 圆形。"""

    def __init__(self, icon: str, *, size: int = 40, variant: str = "standard",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon = icon
        self._variant = variant
        self._selected = False
        self.setFixedSize(size, size)

    def set_selected(self, on: bool) -> None:
        self._selected = on
        self.update()

    def set_icon(self, icon: str) -> None:
        if icon != self._icon:
            self._icon = icon
            self.update()

    def corner_radius(self) -> float:
        return Shape.FULL

    def surface_fill(self) -> str | None:
        s = THEME.s
        if self._variant == "filled":
            return s.primary
        if self._variant == "tonal" or (self._variant == "toggle"
                                        and self._selected):
            return s.secondary_container
        return None

    def content_color(self) -> str:
        s = THEME.s
        if self._variant == "filled":
            return s.on_primary
        if self._variant == "tonal" or (self._variant == "toggle"
                                        and self._selected):
            return s.on_secondary_container
        return s.on_surface_variant

    def layer_role(self) -> str:
        return self.content_color()

    def paint_content(self, p: QPainter, rect: QRectF) -> None:
        size = min(rect.width(), rect.height()) * 0.5
        draw_icon(p, self._icon, QRectF(rect.center().x() - size / 2,
                                        rect.center().y() - size / 2,
                                        size, size), self.content_color())


# 芯片

class FilterChip(MdInteractive):
    """MD3 滤波芯片。未选中为描边，选中为 secondary_container 底 + 对勾。"""

    HEIGHT = 32

    def __init__(self, text: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._selected = False
        self.setFixedHeight(self.HEIGHT)

    def set_selected(self, on: bool) -> None:
        if on != self._selected:
            self._selected = on
            self.updateGeometry()
            self.update()

    def sizeHint(self):  # noqa: N802
        from PySide6.QtCore import QSize
        font = md_font("label_large")
        w = _text_width(self._text, font) + Space.L * 2
        if self._selected:
            w += 18 + Space.S
        return QSize(round(w), self.HEIGHT)

    def corner_radius(self) -> float:
        return Shape.S

    def surface_fill(self) -> str | None:
        return THEME.s.secondary_container if self._selected else None

    def surface_border(self) -> str | None:
        return None if self._selected else THEME.s.outline_variant

    def content_color(self) -> str:
        return (THEME.s.on_secondary_container if self._selected
                else THEME.s.on_surface_variant)

    def layer_role(self) -> str:
        return self.content_color()

    def paint_content(self, p: QPainter, rect: QRectF) -> None:
        font = md_font("label_large")
        color = self.content_color()
        tw = _text_width(self._text, font)
        iw = 18.0
        total = tw + (iw + Space.S if self._selected else 0)
        x = rect.center().x() - total / 2
        if self._selected:
            draw_icon(p, "check", QRectF(x, rect.center().y() - iw / 2, iw, iw),
                      color)
            x += iw + Space.S
        p.setFont(font)
        p.setPen(qc(color))
        p.drawText(QRectF(x, 0, tw + 2, rect.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self._text)


# 连接式分段按钮

class SegmentedButton(ThemedWidget):
    """MD3 connected segmented button：整条描边包住，段间用竖线分隔。"""

    changed = Signal(int)

    HEIGHT = 40

    def __init__(self, items: list[str], *, icons: list[str] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items = list(items)
        self._icons = list(icons) if icons else None
        self._index = 0
        self._hover = -1
        self._press = -1
        self._drag = False
        self._thumb = 0.0
        self._thumb_anim = QVariantAnimation(self)
        self._thumb_anim.setDuration(motion_duration(Dur.MEDIUM2))
        self._thumb_anim.setEasingCurve(expressive_spring())
        self._thumb_anim.valueChanged.connect(self._on_thumb)
        self.setFixedHeight(self.HEIGHT)
        self.setMinimumWidth(120)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def index(self) -> int:
        return self._index

    def set_index(self, index: int, *, emit: bool = False) -> None:
        index = max(0, min(len(self._items) - 1, index))
        if index != self._index:
            self._index = index
            self._thumb_anim.stop()
            self._thumb_anim.setStartValue(self._thumb)
            self._thumb_anim.setEndValue(float(index))
            self._thumb_anim.start()
            self.update()
            if emit:
                self.changed.emit(index)

    def _on_thumb(self, value) -> None:
        self._thumb = anim_float(value, self._thumb)
        self.update()

    def _hit(self, x: float) -> int:
        w = self.width() / len(self._items)
        return max(0, min(len(self._items) - 1, int(x // w)))

    def enterEvent(self, e):  # noqa: N802
        # 悬停时再显式重设一次光标：构造时设过，但父容器或别处的光标变更会盖掉它
        if self.isEnabled():
            self.setCursor(Qt.PointingHandCursor)
        self.update()

    def leaveEvent(self, e):  # noqa: N802
        self._hover = -1
        self._drag = False
        self.update()

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() != Qt.LeftButton:
            return
        self._press = self._hit(e.position().x())
        self._drag = True
        # 按下即选中，随后可以横向拖到另一段
        self.set_index(self._press, emit=True)
        self.update()

    def mouseMoveEvent(self, e):  # noqa: N802
        i = self._hit(e.position().x())
        if self._drag:
            self.set_index(i, emit=True)      # 拖动过程中直接切换
        elif i != self._hover:
            self._hover = i
            self.update()

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton and self._drag:
            self._drag = False
            self._press = -1
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s = THEME.s
        rect = QRectF(self.rect())
        draw_shape(p, rect, Shape.FULL, border=s.outline)

        n = len(self._items)
        seg_w = rect.width() / n

        # 选中块走弹性缓动，越界部分按容器内沿裁掉：有回弹但不跑出边框
        thumb = QRectF(self._thumb * seg_w, 0, seg_w,
                       rect.height()).adjusted(1, 1, -1, -1)

        # 紧挨选中块的分隔线跳过，否则圆角边和分隔线之间会露缝
        for i in range(1, n):
            x = i * seg_w
            if thumb.left() - 4 <= x <= thumb.right() + 4:
                continue
            p.setPen(QPen(qc(s.outline_variant), 1.0))
            p.drawLine(QPointF(x, 9), QPointF(x, rect.height() - 9))

        p.save()
        p.setClipPath(rounded_path(rect.adjusted(1, 1, -1, -1), Shape.FULL))

        if self._hover >= 0 and self._hover != self._index:
            hv = QRectF(self._hover * seg_w, 0, seg_w,
                        rect.height()).adjusted(1, 1, -1, -1)
            p.setPen(Qt.NoPen)
            p.setBrush(qc(s.on_surface, 0.08))
            p.drawPath(rounded_path(hv, Shape.FULL))

        # 选中块：位置由 _thumb 插值，切换时是弹过去的而不是跳过去
        p.setPen(Qt.NoPen)
        p.setBrush(qc(s.secondary_container))
        p.drawPath(rounded_path(thumb, Shape.FULL))
        p.restore()

        for i, label in enumerate(self._items):
            cell = QRectF(i * seg_w, 0, seg_w, rect.height())
            selected = (i == self._index)
            color = s.on_secondary_container if selected else s.on_surface
            font = md_font("label_large")
            icon = self._icons[i] if self._icons else None
            tw = _text_width(label, font)
            iw = 18.0
            total = tw + (iw + Space.XS if (selected and icon) else 0)
            x = cell.center().x() - total / 2
            if selected and icon:
                draw_icon(p, icon, QRectF(x, cell.center().y() - iw / 2, iw, iw),
                          color)
                x += iw + Space.XS
            p.setFont(font)
            p.setPen(qc(color))
            p.drawText(QRectF(x, 0, tw + 2, cell.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, label)


# 滑块

class MdSlider(MdInteractive):
    """MD3 连续滑块。"""

    TRACK = 16.0
    HANDLE_W = 4.0
    HANDLE_H = 44.0
    GAP = 6.0
    INDICATOR_H = 28.0

    # 控件高度要给值指示泡留出空间
    HEIGHT = 76

    valueChanged = Signal(float)
    # 拖动结束（松手）。用于吸附到最近的预设档位。
    released = Signal()

    def __init__(self, *, minimum: float = 0.0, maximum: float = 1.0,
                 stops: list[float] | None = None, formatter=None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._min, self._max = minimum, maximum
        self._value = minimum
        self._stops = stops or []
        self._formatter = formatter
        self._drag = False
        # 值超出本控件量程（用户手输了更大的值）：整条轨道画成空的
        self._overflow = False
        self.setFixedHeight(self.HEIGHT)
        self.setMinimumWidth(160)
        self.setCursor(Qt.SizeHorCursor)
        self._indicator = 0.0
        self._ind_anim = QVariantAnimation(self)
        self._ind_anim.setDuration(motion_duration(Dur.SHORT4))
        self._ind_anim.setEasingCurve(expressive_spring())
        self._ind_anim.valueChanged.connect(self._on_indicator)

    def sizeHint(self):  # noqa: N802
        from PySide6.QtCore import QSize
        return QSize(300, int(self.HEIGHT))

    def _track_center(self) -> float:
        """轨道中心贴着控件底部，上方全部留给值指示泡。"""
        return self.height() - self.HANDLE_H / 2

    def value(self) -> float:
        return self._value

    def set_overflow(self, on: bool) -> None:
        """当前值不在量程内：轨道留空，表示已经超出预设范围。"""
        on = bool(on)
        if on != self._overflow:
            self._overflow = on
            self.update()

    def set_value(self, v: float, *, emit: bool = False) -> None:
        v = max(self._min, min(self._max, float(v)))
        if abs(v - self._value) > 1e-9:
            self._value = v
            self.update()
            if emit:
                self.valueChanged.emit(v)

    def _t(self) -> float:
        span = self._max - self._min
        return 0.0 if span <= 0 else (self._value - self._min) / span

    def _track_rect(self) -> QRectF:
        cy = self._track_center()
        return QRectF(self.HANDLE_W * 2, cy - self.TRACK / 2,
                      self.width() - self.HANDLE_W * 4, self.TRACK)

    def _handle_x(self) -> float:
        tr = self._track_rect()
        return tr.left() + tr.width() * self._t()

    def _from_x(self, x: float) -> None:
        tr = self._track_rect()
        t = (x - tr.left()) / max(1.0, tr.width())
        self.set_value(self._min + (self._max - self._min) * max(0.0, min(1.0, t)),
                       emit=True)

    def _on_indicator(self, v) -> None:
        self._indicator = anim_float(v, self._indicator)
        self.update()

    def _animate_indicator(self, target: float) -> None:
        if abs(target - self._indicator) < 1e-6:
            return
        self._ind_anim.stop()
        self._ind_anim.setStartValue(self._indicator)
        self._ind_anim.setEndValue(target)
        self._ind_anim.start()

    def corner_radius(self) -> float:
        return Shape.NONE

    def surface_fill(self) -> str | None:
        return None

    def enterEvent(self, e):  # noqa: N802
        self._hovered = True
        self._animate_indicator(1.0)
        self.update()

    def leaveEvent(self, e):  # noqa: N802
        self._hovered = False
        if not self._drag:
            self._animate_indicator(0.0)
        self.update()

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton:
            self._drag = True
            self._animate_indicator(1.0)
            self._from_x(e.position().x())

    def mouseMoveEvent(self, e):  # noqa: N802
        if self._drag:
            self._from_x(e.position().x())

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton:
            dragged = self._drag
            self._drag = False
            if not self._hovered:
                self._animate_indicator(0.0)
            if dragged:
                self.released.emit()

    def wheelEvent(self, e):  # noqa: N802
        step = (self._max - self._min) * 0.02
        self.set_value(self._value + (step if e.angleDelta().y() > 0 else -step),
                       emit=True)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s = THEME.s
        tr = self._track_rect()
        hx = self._handle_x()
        cy = tr.center().y()
        r = Shape.FULL

        if self._overflow:
            # 空轨道：没有手柄也没有刻度，一眼看出当前值不在预设范围内
            draw_shape(p, tr, r, fill=s.surface_container_highest)
            return

        inactive = QRectF(hx + self.GAP, tr.top(), tr.right() - hx - self.GAP,
                          tr.height())
        if inactive.width() > 0:
            draw_shape(p, inactive, r, fill=s.surface_container_highest)
        active = QRectF(tr.left(), tr.top(), max(0.0, hx - self.GAP - tr.left()),
                        tr.height())
        if active.width() > 0:
            draw_shape(p, active, r, fill=s.primary)

        # 预设档位刻度点
        for stop in self._stops:
            t = (stop - self._min) / max(1e-9, self._max - self._min)
            x = tr.left() + tr.width() * t
            on_active = x <= hx - self.GAP and x >= tr.left()
            p.setPen(Qt.NoPen)
            p.setBrush(qc(s.on_primary if on_active else s.outline,
                          0.9 if on_active else 0.5))
            p.drawEllipse(QPointF(x, cy), 2.0, 2.0)

        # 手柄：4×44 竖条
        handle = QRectF(hx - self.HANDLE_W / 2, cy - self.HANDLE_H / 2,
                        self.HANDLE_W, self.HANDLE_H)
        draw_shape(p, handle, self.HANDLE_W / 2, fill=s.primary)

        if self._indicator > 0.01:              # 值指示泡
            self._paint_indicator(p, hx)

    def _paint_indicator(self, p: QPainter, hx: float) -> None:
        s = THEME.s
        text = self._format(self._value)
        font = md_font("label_large")
        tw = _text_width(text, font)
        w = max(52.0, tw + Space.L * 2)
        h = self.INDICATOR_H
        sc = 0.72 + 0.28 * self._indicator
        cx = min(max(hx, w / 2 + 2), self.width() - w / 2 - 2)
        # 泡底贴着手柄顶端留 2dp，整体向上展开
        cy = (self._track_center() - self.HANDLE_H / 2 - 2 - h / 2)

        p.save()
        p.translate(cx, cy)
        p.scale(sc, sc)
        body = QRectF(-w / 2, -h / 2, w, h)
        draw_shape(p, body, Shape.FULL, fill=s.inverse_surface)
        _center_text(p, body, text, font, s.inverse_on_surface)
        p.restore()

    def _format(self, v: float) -> str:
        return self._formatter(v) if self._formatter else f"{v:.0f}"


# 开关

class MdSwitch(MdInteractive):
    """MD3 开关：轨道 52×32，拇指未选中 16dp / 选中 24dp，选中显示对勾。"""

    W, H = 52, 32

    toggled = Signal(bool)

    # 手柄直径与左右留白：未选 → 选中
    THUMB_OFF, THUMB_ON = 16.0, 24.0
    MARGIN_OFF, MARGIN_ON = 8.0, 4.0

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.W, self.H)
        self._checked = checked
        self._t = 1.0 if checked else 0.0
        self._press_x = 0.0
        self._press_t = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(motion_duration(Dur.MEDIUM2))
        self._anim.setEasingCurve(expressive_spring())
        self._anim.valueChanged.connect(self._on_t)

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, on: bool, *, emit: bool = False) -> None:  # noqa: N802
        on = bool(on)
        changed = on != self._checked
        self._checked = on
        self._settle(1.0 if on else 0.0)
        if changed and emit:
            self.toggled.emit(on)

    def _settle(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(target)
        self._anim.start()

    def _thumb_size(self, t: float) -> float:
        return self.THUMB_OFF + (self.THUMB_ON - self.THUMB_OFF) * t

    def _thumb_center(self, t: float) -> float:
        size = self._thumb_size(t)
        margin = self.MARGIN_OFF + (self.MARGIN_ON - self.MARGIN_OFF) * t
        left = margin + size / 2
        right = self.W - margin - size / 2
        return left + (right - left) * t

    def _travel(self) -> float:
        return self._thumb_center(1.0) - self._thumb_center(0.0)

    def _on_t(self, v) -> None:
        self._t = anim_float(v, self._t)
        self.update()

    def corner_radius(self) -> float:
        return Shape.FULL

    def surface_fill(self) -> str | None:
        return None

    def layer_role(self) -> str:
        return THEME.s.primary

    def mousePressEvent(self, e):  # noqa: N802
        if e.button() != Qt.LeftButton or not self.isEnabled():
            super().mousePressEvent(e)
            return
        self._anim.stop()
        self._press_x = e.position().x()
        self._press_t = self._t
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):  # noqa: N802
        if not (e.buttons() & Qt.LeftButton):
            return
        # 不设阈值：球从第一个像素起就跟着手，拖动不会突然跳半格
        dx = e.position().x() - self._press_x
        self._t = max(0.0, min(1.0, self._press_t + dx / self._travel()))
        self.update()

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton:
            # 位移够大算拖动：球停在哪儿就是哪儿，往左拖过就留左边；
            # 只有几乎没动才算点击，这时候才切换
            dragged = (abs(e.position().x() - self._press_x)
                       >= QApplication.startDragDistance())
            self.setChecked(self._t >= 0.5 if dragged else not self._checked,
                            emit=True)
        super().mouseReleaseEvent(e)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = THEME.s
        if self._scale != 1.0:
            cx, cy = self.width() / 2, self.height() / 2
            p.translate(cx, cy)
            p.scale(self._scale, self._scale)
            p.translate(-cx, -cy)

        # MD3E 的开关是"滚"过去的：位置、粗细、颜色一起连续过渡，
        # 不是翻一下状态再各画各的
        t = max(0.0, min(1.0, self._t))
        track = QRectF(0.5, 0.5, self.W - 1, self.H - 1)
        draw_shape(p, track, Shape.FULL,
                   fill=mix(s.surface_container_highest, s.primary, t),
                   border=mix(s.outline, s.primary, t))

        if self._layer > 0.001:
            p.setPen(Qt.NoPen)
            p.setBrush(qc(s.on_surface, self._layer * 0.5))
            p.drawPath(rounded_path(track, Shape.FULL))

        # 手柄 16dp → 24dp，左右留白 8dp → 4dp，中心位置随 t 连续移动
        size = self._thumb_size(t)
        cx = self._thumb_center(t)
        cy = self.H / 2

        # MD3E：滑动途中拉长成胶囊，按下时微胖
        stretch = 8.0 * (4.0 * t * (1.0 - t))
        if self._pressed:
            stretch = max(stretch, 4.0)
        thumb = QRectF(cx - (size + stretch) / 2, cy - size / 2,
                       size + stretch, size)

        draw_shape(p, thumb, Shape.FULL,
                   fill=mix(s.outline, s.on_primary, t))
        if t > 0.55:
            p.save()
            p.setOpacity(min(1.0, (t - 0.55) / 0.3))
            icon = size * 0.62
            draw_icon(p, "check", QRectF(cx - icon / 2, cy - icon / 2,
                                         icon, icon), s.primary)
            p.restore()


# 快捷键捕获

_VK_SPECIAL = {
    Qt.Key_Space: 0x20, Qt.Key_Tab: 0x09, Qt.Key_Backtab: 0x09,
    Qt.Key_Return: 0x0D, Qt.Key_Enter: 0x0D, Qt.Key_Backspace: 0x08,
    Qt.Key_Insert: 0x2D, Qt.Key_Delete: 0x2E,
    Qt.Key_Home: 0x24, Qt.Key_End: 0x23,
    Qt.Key_PageUp: 0x21, Qt.Key_PageDown: 0x22,
    Qt.Key_Left: 0x25, Qt.Key_Up: 0x26, Qt.Key_Right: 0x27, Qt.Key_Down: 0x28,
    # 这些"特殊键"在 Qt 里也是普通 KeyPress，但 Win32 侧是独立虚拟键码
    Qt.Key_CapsLock: 0x14, Qt.Key_NumLock: 0x90, Qt.Key_ScrollLock: 0x91,
    Qt.Key_Shift: 0x10, Qt.Key_Control: 0x11, Qt.Key_Alt: 0x12,
    Qt.Key_Meta: 0x5B,
    Qt.Key_Minus: 0xBD, Qt.Key_Equal: 0xBB, Qt.Key_BracketLeft: 0xDB,
    Qt.Key_BracketRight: 0xDD, Qt.Key_Backslash: 0xDC, Qt.Key_Semicolon: 0xBA,
    Qt.Key_Apostrophe: 0xDE, Qt.Key_Comma: 0xBC, Qt.Key_Period: 0xBE,
    Qt.Key_Slash: 0xBF, Qt.Key_QuoteLeft: 0xC0,
}

_VK_NAMES = {
    0x20: "Space", 0x09: "Tab", 0x0D: "Enter", 0x08: "Backspace",
    0x2D: "Insert", 0x2E: "Delete", 0x24: "Home", 0x23: "End",
    0x21: "PgUp", 0x22: "PgDn",
    0x25: "←", 0x26: "↑", 0x27: "→", 0x28: "↓",
    0x14: "CapsLock", 0x90: "NumLock", 0x91: "ScrollLock",
    0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt", 0x5B: "Win",
    0xBD: "-", 0xBB: "=", 0xDB: "[", 0xDD: "]", 0xDC: "\\",
    0xBA: ";", 0xDE: "'", 0xBC: ",", 0xBE: ".", 0xBF: "/", 0xC0: "`",
}


def qt_key_to_vk(key: int) -> int | None:
    """Qt 键值 → Win32 虚拟键码。"""
    if Qt.Key_F1 <= key <= Qt.Key_F12:
        return 0x70 + (key - Qt.Key_F1)
    if Qt.Key_A <= key <= Qt.Key_Z:
        return 0x41 + (key - Qt.Key_A)
    if Qt.Key_0 <= key <= Qt.Key_9:
        return 0x30 + (key - Qt.Key_0)
    return _VK_SPECIAL.get(key)


def vk_name(vk: int) -> str:
    if 0x70 <= vk <= 0x7B:
        return f"F{vk - 0x70 + 1}"
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    return _VK_NAMES.get(vk, f"0x{vk:02X}")


class KeyCaptureField(MdInteractive):
    """按键捕获框：点一下，再按任意键即可绑定。"""

    HEIGHT = 40
    changed = Signal(int)

    def __init__(self, vk: int, *, width: int = 104,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vk = int(vk)
        self._capturing = False
        self.setFixedSize(width, self.HEIGHT)
        self.setFocusPolicy(Qt.StrongFocus)
        self.clicked.connect(self.begin_capture)

    def vk(self) -> int:
        return self._vk

    def set_vk(self, vk: int) -> None:
        """直接设值，不触发 changed —— 从配置文件恢复时用。"""
        self._vk = int(vk)
        self.update()

    def begin_capture(self) -> None:
        self._capturing = True
        self.setFocus(Qt.MouseFocusReason)
        self.update()

    def is_editing(self) -> bool:
        return self._capturing

    def commit_edit(self) -> None:
        if self._capturing:
            self._capturing = False
            self.clearFocus()
            self.update()

    def _bind(self, key: int) -> None:
        vk = qt_key_to_vk(key)
        if vk is None:
            return
        self._capturing = False
        self._vk = vk
        self.clearFocus()
        self.update()
        self.changed.emit(vk)

    def event(self, event):  # noqa: N802
        # Tab 会被 Qt 拿去做焦点切换，到不了 keyPressEvent，只能在这里截。
        # event() 在 __init__ 期间就会被调用，那时 _capturing 还没赋值。
        if (getattr(self, "_capturing", False)
                and event.type() == event.Type.KeyPress
                and event.key() in (Qt.Key_Tab, Qt.Key_Backtab)):
            self._bind(event.key())
            return True
        return super().event(event)

    def keyPressEvent(self, event):  # noqa: N802
        if not self._capturing:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_Escape:
            self._capturing = False
            self.clearFocus()
            self.update()
            return
        self._bind(event.key())

    def focusOutEvent(self, event):  # noqa: N802
        self._capturing = False
        self.update()
        super().focusOutEvent(event)

    def corner_radius(self) -> float:
        return Shape.XS

    def surface_fill(self) -> str | None:
        return THEME.s.surface_container_highest

    def surface_border(self) -> str | None:
        return (THEME.s.primary if self._capturing
                else THEME.s.outline_variant)

    def content_color(self) -> str:
        return THEME.s.on_surface

    def paint_content(self, p: QPainter, rect: QRectF) -> None:
        s = THEME.s
        text = "按任意键…" if self._capturing else vk_name(self._vk)
        _center_text(p, rect, text, md_font("label_large"),
                     s.primary if self._capturing else s.on_surface)

class MdTextField(ThemedWidget):
    """MD3 filled 文本框：浮动标签 + 底部指示线。"""

    HEIGHT = 56
    COMPACT_HEIGHT = 40
    valueChanged = Signal(str)
    # 回车或失焦：编辑结束
    editingFinished = Signal()

    def __init__(self, label: str, value: str = "", *, suffix: str = "",
                 width: int = 120,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._suffix = suffix
        # 没有标签就是紧凑模式：更矮，才不会撑破所在的列表行
        self._h = self.HEIGHT if label else self.COMPACT_HEIGHT
        self._hovered = False
        self._focus_t = 0.0
        self._editing = False
        self.setFixedSize(width, self._h)

        self._edit = QLineEdit(self)
        self._edit.setFrame(False)
        self._edit.setStyleSheet(
            "QLineEdit{background:transparent;border:none;padding:0;}")
        self._edit.setText(value)
        self._edit.setFont(md_font("body_large"))
        self._edit.textChanged.connect(self._on_text)
        self._edit.editingFinished.connect(self.editingFinished)
        self._edit.selectionChanged.connect(lambda: None)
        self._edit.installEventFilter(self)

        self._focus_anim = QVariantAnimation(self)
        self._focus_anim.setDuration(motion_duration(Dur.SHORT4))
        self._focus_anim.setEasingCurve(standard())
        self._focus_anim.valueChanged.connect(self._on_focus_t)
        self._apply_palette()

    def text(self) -> str:
        return self._edit.text()

    def setText(self, value: str) -> None:  # noqa: N802
        self._edit.setText(value)

    def focus_edit(self) -> None:
        """进入编辑：聚焦并全选，直接就能改数。"""
        self._edit.setFocus(Qt.MouseFocusReason)
        self._edit.selectAll()

    def is_editing(self) -> bool:
        return self._editing

    def commit_edit(self) -> None:
        """收工：失焦并通知使用方落值。"""
        if not self._editing:
            return
        self._editing = False
        self._edit.clearFocus()
        self.editingFinished.emit()

    def _on_text(self, _t: str) -> None:
        self.valueChanged.emit(self._edit.text())
        self.update()

    def _floating(self) -> bool:
        return bool(self._edit.text()) or self._edit.hasFocus()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._edit:
            if event.type() == event.Type.FocusIn:
                self._editing = True
                self._animate_focus(1.0)
            elif event.type() == event.Type.FocusOut:
                self._editing = False
                self._animate_focus(0.0)
        return super().eventFilter(obj, event)

    def _animate_focus(self, target: float) -> None:
        if abs(target - self._focus_t) < 1e-6:
            return
        self._focus_anim.stop()
        self._focus_anim.setStartValue(self._focus_t)
        self._focus_anim.setEndValue(target)
        self._focus_anim.start()

    def _on_focus_t(self, v) -> None:
        self._focus_t = anim_float(v, self._focus_t)
        self.update()

    def enterEvent(self, e):  # noqa: N802
        self._hovered = True
        self.update()

    def leaveEvent(self, e):  # noqa: N802
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):  # noqa: N802
        if self.isEnabled() and e.button() == Qt.LeftButton:
            self._edit.setFocus(Qt.MouseFocusReason)

    def resizeEvent(self, _e) -> None:  # noqa: N802
        self._layout_edit()

    def _suffix_rect(self) -> QRectF:
        if not self._suffix:
            return QRectF(self.width(), self.height(), 0, 0)
        from PySide6.QtGui import QFontMetricsF as _FM
        w = _FM(md_font("body_small")).horizontalAdvance(self._suffix) + 14
        return QRectF(self.width() - w, 0, w, self._h)

    def _layout_edit(self) -> None:
        sr = self._suffix_rect()
        right_pad = (self.width() - sr.left()) if self._suffix else Space.M
        if self._label:
            top, height = 18, self._h - 18 - 10
        else:
            top, height = 6, self._h - 14
        self._edit.setGeometry(Space.M, top,
                               max(20, self.width() - Space.M - right_pad),
                               height)
        self._edit.setAlignment((Qt.AlignLeft if self._label else Qt.AlignRight)
                                | Qt.AlignVCenter)

    def _apply_palette(self) -> None:
        from PySide6.QtGui import QPalette
        s = THEME.s
        qp = self._edit.palette()
        qp.setColor(QPalette.Text, qc(s.on_surface if self.isEnabled()
                                      else s.on_surface_variant))
        qp.setColor(QPalette.Base, QColor(Qt.transparent))
        qp.setColor(QPalette.Highlight, qc(s.primary))
        qp.setColor(QPalette.HighlightedText, qc(s.on_primary))
        self._edit.setPalette(qp)
        self._edit.setFont(md_font("body_large"))

    def _on_theme(self) -> None:
        self._apply_palette()
        self.update()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        self._apply_palette()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s = THEME.s
        enabled = self.isEnabled()
        container = QRectF(0, 0, self.width(), self._h - 2)
        fill = s.surface_container_highest
        if enabled and self._hovered and not self._edit.hasFocus():
            fill = s.surface_container_high
        draw_shape(p, container, Shape.XS, fill=fill if enabled
                   else s.surface_container)

        # 底部指示线：1dp 描边 → 2dp primary
        base_h = 1.0 + 1.0 * self._focus_t
        color = s.primary if self._focus_t > 0.01 else s.on_surface_variant
        line = QRectF(0, self._h - base_h, self.width(), base_h)
        p.setPen(Qt.NoPen)
        p.setBrush(qc(color, 1.0 if enabled else 0.4))
        p.drawRect(line)

        # 浮动标签（紧凑模式无标签）
        if self._label:
            fm = QFontMetricsF
            float_t = 1.0 if self._floating() else 0.0
            t = max(self._focus_t, float_t)
            big = md_font("body_large")
            small = md_font("body_small")
            x = Space.L
            yb = 18 + (self._h - 18) / 2 - fm(big).height() / 2 + fm(big).ascent()
            ys = Space.S + fm(small).ascent()
            y = yb + (ys - yb) * t
            font = big if t < 0.5 else small
            p.setFont(font)
            p.setPen(qc(s.primary if self._edit.hasFocus()
                        else s.on_surface_variant))
            p.drawText(QPointF(x, y), self._label)

        if self._suffix:
            _center_text(p, self._suffix_rect(), self._suffix,
                         md_font("body_small"), s.on_surface_variant)
