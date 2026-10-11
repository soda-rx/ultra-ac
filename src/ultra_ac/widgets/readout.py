# -*- coding: utf-8 -*-
"""MD3 主数值显示：频率读数。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QRegularExpression, Signal
from PySide6.QtGui import (QFontMetricsF, QPainter,
                           QRegularExpressionValidator)
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from ..theme import Shape, Space, THEME
from .primitives import ThemedWidget, draw_shape, md_font, qc

HEIGHT = 84

# 中文/全角句号都当小数点
_DOT_ALIASES = ("。", "．", "｡")
# 只允许数字和一个小数点
_NUMBER_RE = QRegularExpression(r"\d*\.?\d*")


class RateDisplay(ThemedWidget):
    """大号 CPS 读数。点一下即可直接输入数值，滚轮微调。"""

    valueChanged = Signal(float)

    def __init__(self, value: float = 100.0, *, minimum: float = 1.0,
                 maximum: float = 200.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = value
        self._min, self._max = minimum, maximum
        self._hovered = False
        self._cancelling = False
        self.setFixedHeight(HEIGHT)
        # 不改成 SizeHorCursor：那个"左右可拖"的光标在读数上显得莫名其妙。
        # 悬停时的淡底色已经足够提示可交互。
        self.setCursor(Qt.IBeamCursor)

        self._edit = QLineEdit(self)
        self._edit.setFrame(False)
        self._edit.setStyleSheet(
            "QLineEdit{background:transparent;border:none;padding:0;}")
        self._edit.setFont(md_font("display_medium"))
        self._edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # 输入校验：字母、符号直接敲不进去，自然也就不会有非法内容
        self._edit.setValidator(QRegularExpressionValidator(_NUMBER_RE, self._edit))
        self._edit.editingFinished.connect(self._commit)
        self._edit.textChanged.connect(self._on_edit_text)
        self._edit.installEventFilter(self)
        self._edit.hide()
        self._sync_edit_geometry()

    def value(self) -> float:
        return self._value

    def set_value(self, v: float, *, emit: bool = False) -> None:
        v = max(self._min, min(self._max, float(v)))
        if abs(v - self._value) > 1e-9:
            self._value = v
            self._sync_edit_geometry()
            self.update()
            if emit:
                self.valueChanged.emit(v)

    def text(self) -> str:
        return f"{self._value:.1f}"

    def _sync_edit_geometry(self) -> None:
        fm = QFontMetricsF(md_font("display_medium"))
        # 编辑时按编辑框里的内容量宽度，这样打长了不会和右边的 "CPS" 撞上
        text = self._edit.text() if self._edit.isVisible() else self.text()
        w = int(fm.horizontalAdvance(text)) + 12
        h = int(fm.height()) + 4
        self._edit.setGeometry(0, 10, max(80, w), h)

    def _on_edit_text(self, _text: str) -> None:
        self._sync_edit_geometry()
        self.update()

    def start_edit(self) -> None:
        self._edit.setText(self.text())
        self._sync_edit_geometry()
        self._edit.show()
        self._edit.setFocus(Qt.MouseFocusReason)
        self._edit.selectAll()
        # 挂在应用上：这样"点界面任何别的地方"也能算输入完成，
        # 否则点到不接收焦点的控件（滑块、chip）时编辑框不会失焦，永远提交不了
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _stop_filter(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def _commit(self) -> None:
        if self._cancelling:
            return
        self._stop_filter()
        raw = self._edit.text().strip()
        if raw:
            # 只有真的填了东西才应用；清空 = 不更改
            try:
                v = float(raw)
            except ValueError:
                pass                  # 不是合法数字也保持原值
            else:
                self.set_value(v, emit=True)
        self._edit.hide()
        self.update()

    def _cancel(self) -> None:
        """Esc 放弃编辑。先置标志，hide() 触发的 editingFinished 便不会误提交。"""
        self._cancelling = True
        self._edit.hide()
        self._cancelling = False
        self._stop_filter()
        self.update()

    def is_editing(self) -> bool:
        return self._edit.isVisible()

    def commit_edit(self) -> None:
        self._commit()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_Escape:
                self._cancel()
                return True
            # 中文输入法下打出来的句号直接当小数点用
            if event.text() in _DOT_ALIASES:
                self._edit.insert(".")
                return True
        return super().eventFilter(obj, event)

    def enterEvent(self, e):  # noqa: N802
        self._hovered = True
        self.update()

    def leaveEvent(self, e):  # noqa: N802
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):  # noqa: N802
        # 点一下就进入编辑并全选，可以直接敲数值。
        # 原来这里是"按住左右拖动改值"，但那样想点时很容易被误判成拖动，点不中。
        if e.button() == Qt.LeftButton and self._edit.isHidden():
            self.start_edit()

    def wheelEvent(self, e):  # noqa: N802
        step = max(0.1, self._value * 0.02)
        self.set_value(self._value + (step if e.angleDelta().y() > 0 else -step),
                       emit=True)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.TextAntialiasing)
        s = THEME.s

        if self._hovered and self._edit.isHidden():
            draw_shape(p, QRectF(-8, 0, self.width() + 16, self.height()),
                       Shape.S, fill=s.on_surface, fill_alpha=0.05)
        editing = self._edit.isVisible()
        if editing:
            # 编辑框就显示在同一个位置，这里再画一遍大数字就会叠影
            x = self._edit.geometry().right() + Space.M
        else:
            big = md_font("display_medium")
            p.setFont(big)
            p.setPen(qc(s.on_surface if self.isEnabled()
                        else s.on_surface_variant))
            p.drawText(QRectF(0, 6, self.width(), 52),
                       Qt.AlignLeft | Qt.AlignVCenter, self.text())
            x = QFontMetricsF(big).horizontalAdvance(self.text()) + Space.M

        p.setFont(md_font("label_large"))
        p.setPen(qc(s.primary))
        p.drawText(QRectF(x, 8, 120, 20), Qt.AlignLeft | Qt.AlignVCenter, "CPS")

        p.setFont(md_font("body_small"))
        p.setPen(qc(s.on_surface_variant))
        p.drawText(QRectF(x, 30, 200, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, format_interval(self._value))


def format_interval(cps: float) -> str:
    """间隔显示：超过 100ms 就换成秒。"""
    ms = 1000.0 / max(0.001, cps)
    if ms > 100.0:
        return f"间隔 {ms / 1000.0:.2f} s"
    return f"间隔 {ms:.2f} ms"
