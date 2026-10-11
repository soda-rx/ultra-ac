# -*- coding: utf-8 -*-
"""Material Symbols 风格图标。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

GRID = 24.0
DEFAULT_THICKNESS = 2.0

# 应用 logo 的固定配色（白底黑线）。exe 图标、窗口图标、标题栏三处共用，
# 不跟随深浅色主题 —— logo 就该是固定的。
LOGO_BG = "#FFFFFF"
LOGO_FG = "#000000"


def _pen(color: str, width: float = DEFAULT_THICKNESS) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _polyline(p: QPainter, points: list[tuple[float, float]]) -> None:
    path = QPainterPath(QPointF(*points[0]))
    for pt in points[1:]:
        path.lineTo(QPointF(*pt))
    p.drawPath(path)


# 各图标

def _check(p: QPainter, c: str) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 2.2))
    _polyline(p, [(5.5, 12.5), (10.0, 17.0), (18.5, 7.5)])


def _close(p: QPainter, c: str) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 2.0))
    _polyline(p, [(6.5, 6.5), (17.5, 17.5)])
    _polyline(p, [(17.5, 6.5), (6.5, 17.5)])


def _remove(p: QPainter, c: str) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 2.0))
    _polyline(p, [(6.0, 12.0), (18.0, 12.0)])


def _expand_more(p: QPainter, c: str) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 2.0))
    _polyline(p, [(6.5, 9.5), (12.0, 15.0), (17.5, 9.5)])


def _expand_less(p: QPainter, c: str) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 2.0))
    _polyline(p, [(6.5, 14.5), (12.0, 9.0), (17.5, 14.5)])


def _delete(p: QPainter, c: str) -> None:
    """垃圾桶 —— 破坏性操作（比如清配置）用。"""
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 1.7))
    _polyline(p, [(4.4, 6.6), (19.6, 6.6)])                      # 盖沿
    _polyline(p, [(9.6, 6.6), (9.6, 4.2), (14.4, 4.2), (14.4, 6.6)])   # 提手
    _polyline(p, [(6.7, 6.6), (7.5, 20.2),
                  (16.5, 20.2), (17.3, 6.6)])                    # 桶身
    _polyline(p, [(10.3, 9.6), (10.3, 17.1)])
    _polyline(p, [(13.7, 9.6), (13.7, 17.1)])


def _edit(p: QPainter, c: str) -> None:
    """铅笔 —— 点击编辑数值。"""
    pen = _pen(c, 1.7)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    body = QPainterPath(QPointF(6.0, 15.0))
    for pt in ((15.2, 5.8), (18.2, 8.8), (9.0, 18.0)):
        body.lineTo(QPointF(*pt))
    body.closeSubpath()
    p.drawPath(body)
    tip = QPainterPath(QPointF(6.0, 15.0))
    tip.lineTo(9.0, 18.0)
    tip.lineTo(4.4, 19.6)
    tip.closeSubpath()
    p.drawPath(tip)


def _warning(p: QPainter, c: str) -> None:
    """三角警示 —— 频率超出量程时提示用。"""
    path = QPainterPath(QPointF(12.0, 3.6))
    path.lineTo(21.6, 20.0)
    path.lineTo(2.4, 20.0)
    path.closeSubpath()
    pen = _pen(c, 1.8)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    _polyline(p, [(12.0, 9.8), (12.0, 14.6)])
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(12.0, 17.2), 1.15, 1.15)


def _contrast(p: QPainter, c: str) -> None:
    """对比度图标：圆形轮廓 + 右半实心。"""
    p.setBrush(QColor(c))
    p.setPen(Qt.NoPen)
    path = QPainterPath()
    path.moveTo(12.0, 4.0)
    path.arcTo(QRectF(4.0, 4.0, 16.0, 16.0), 90.0, -180.0)
    path.closeSubpath()
    p.drawPath(path)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 1.8))
    p.drawEllipse(QRectF(4.0, 4.0, 16.0, 16.0))


def _tune(p: QPainter, c: str) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 1.9))
    for y, kx in ((7.5, 15.0), (12.0, 9.0), (16.5, 13.0)):
        _polyline(p, [(4.5, y), (19.5, y)])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c))
        p.drawEllipse(QPointF(kx, y), 2.4, 2.4)
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(c, 1.9))


def draw_app_icon(p: QPainter, rect: QRectF, *, bg: str, fg: str) -> None:
    """应用图标（MD3 Expressive 风格）。"""
    size = min(rect.width(), rect.height())
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.translate(rect.center().x() - size / 2, rect.center().y() - size / 2)
    p.scale(size / GRID, size / GRID)

    # 瓦片：22% 圆角，是 Material You 图标的标准容器形状
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(bg))
    p.drawRoundedRect(QRectF(0.6, 0.6, 22.8, 22.8), 5.4, 5.4)

    # 点击涟漪：右上角一道弧
    ring = QPen(QColor(fg), 1.9)
    ring.setCapStyle(Qt.RoundCap)
    p.setPen(ring)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(2.6, 2.6, 18.8, 18.8), 8 * 16, 74 * 16)

    # 光标箭头：圆角描边 + 填充，小尺寸下依然清晰
    arrow = QPainterPath(QPointF(9.0, 6.2))
    for pt in ((9.0, 17.6), (12.0, 14.9), (13.9, 19.0),
               (16.1, 18.0), (14.2, 13.9), (17.9, 13.4)):
        arrow.lineTo(QPointF(*pt))
    arrow.closeSubpath()
    edge = QPen(QColor(fg), 1.5)
    edge.setJoinStyle(Qt.RoundJoin)
    edge.setCapStyle(Qt.RoundCap)
    p.setPen(edge)
    p.setBrush(QColor(fg))
    p.drawPath(arrow)
    p.restore()


def app_icon_pixmap(size: int, *, bg: str, fg: str):
    """渲染成 QPixmap，供托盘与窗口图标使用。"""
    from PySide6.QtGui import QPixmap
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_app_icon(p, QRectF(0, 0, size, size), bg=bg, fg=fg)
    p.end()
    return pm


def app_icon_qicon(bg: str, fg: str):
    """多尺寸 QIcon：托盘和任务栏在不同 DPI 下会挑不同尺寸。"""
    from PySide6.QtGui import QIcon
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_icon_pixmap(size, bg=bg, fg=fg))
    return icon


def _refresh(p: QPainter, c: str) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 1.9))
    path = QPainterPath()
    path.arcMoveTo(QRectF(5.0, 5.0, 14.0, 14.0), 70.0)
    path.arcTo(QRectF(5.0, 5.0, 14.0, 14.0), 70.0, 285.0)
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(c))
    head = QPainterPath(QPointF(19.6, 3.6))
    for pt in ((19.6, 10.4), (13.2, 7.2)):
        head.lineTo(QPointF(*pt))
    head.closeSubpath()
    p.drawPath(head)


def _info(p: QPainter, c: str) -> None:
    """圆里一个 i —— 用于「关于」。"""
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 1.9))
    p.drawEllipse(QRectF(3.6, 3.6, 16.8, 16.8))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(c))
    p.drawEllipse(QPointF(12.0, 7.9), 1.35, 1.35)
    p.drawRoundedRect(QRectF(11.0, 10.5, 2.0, 6.7), 1.0, 1.0)


def _push_pin(p: QPainter, c: str) -> None:
    """图钉 —— 用于窗口置顶。"""
    path = QPainterPath(QPointF(8.6, 3.6))
    for pt in ((15.4, 3.6), (15.4, 9.2), (17.8, 12.6),
               (6.2, 12.6), (8.6, 9.2)):
        path.lineTo(QPointF(*pt))
    path.closeSubpath()
    edge = QPen(QColor(c), 1.4)
    edge.setJoinStyle(Qt.RoundJoin)
    p.setPen(edge)
    p.setBrush(QColor(c))
    p.drawPath(path)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(c, 1.7))
    _polyline(p, [(12.0, 12.6), (12.0, 20.6)])


_ICONS = {
    "check": _check,
    "close": _close,
    "remove": _remove,
    "expand_more": _expand_more,
    "expand_less": _expand_less,
    "delete": _delete,
    "edit": _edit,
    "warning": _warning,
    "contrast": _contrast,
    "tune": _tune,
    "refresh": _refresh,
    "info": _info,
    "push_pin": _push_pin,
}

AVAILABLE = tuple(sorted(_ICONS))


def draw_icon(p: QPainter, name: str, rect: QRectF, color: str) -> None:
    """在 rect 内居中绘制图标。"""
    fn = _ICONS.get(name)
    if fn is None:
        raise KeyError(f"未知图标 {name!r}，可用：{AVAILABLE}")
    size = min(rect.width(), rect.height())
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.translate(rect.center().x() - size / 2, rect.center().y() - size / 2)
    p.scale(size / GRID, size / GRID)
    fn(p, color)
    p.restore()


