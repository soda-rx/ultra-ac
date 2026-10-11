# -*- coding: utf-8 -*-
"""加载指示器：一枚转圈的圆环。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..theme import THEME
from .primitives import qc

SIZE = 52
STROKE = 4.0
SWEEP = 280.0
STEP = 9.0
FRAME_MS = 16


class LoadingRing(QWidget):
    """不知道进度，转就完了。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(SIZE, SIZE)
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)
        THEME.changed.connect(self.update)

    def start(self) -> None:
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle + STEP) % 360.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = THEME.s
        ring = QRectF(self.rect()).adjusted(STROKE, STROKE, -STROKE, -STROKE)
        pen = QPen(qc(s.outline_variant), STROKE)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(ring, 0, 360 * 16)
        pen.setColor(qc(s.primary))
        p.setPen(pen)
        p.drawArc(ring, int(-self._angle * 16), int(-SWEEP * 16))
