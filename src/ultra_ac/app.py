# -*- coding: utf-8 -*-
"""程序入口。"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from .single_instance import SingleInstance, WakeListener, wake_existing
from .system import system_animations_enabled, system_prefers_dark
from .theme import THEME, set_motion_enabled
from .ui.main_window import MainWindow

# 截图模式下等底部面板滑入动画走完
SHOT_DELAY_MS = 900


def enable_dpi_awareness() -> None:
    """必须在 QApplication 之前调用。"""
    user32 = ctypes.WinDLL("user32")
    try:                                   # PER_MONITOR_AWARE_V2 = -4
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:                                   # 退回 Win8.1 的接口
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="Ultra AC", description="Ultra AC")
    p.add_argument("--theme", choices=("auto", "light", "dark"), default="auto",
                   help="启动主题；auto 表示跟随系统配色")
    p.add_argument("--sheet", action="store_true", help="启动时打开设置面板")
    p.add_argument("--about", action="store_true", help="启动时打开关于面板")
    p.add_argument("--running", action="store_true", help="以运行态外观启动")
    p.add_argument("--hud", action="store_true",
                   help="截图时一并渲染悬浮窗（仅配合 --shot 使用）")
    p.add_argument("--shot", metavar="PATH",
                   help="渲染一张窗口截图到 PATH 后退出（外观回归用）")
    return p


class _NullStream:
    """--windowed 打包后 sys.stdout / sys.stderr 是 None。"""

    def write(self, _data) -> int:
        return 0

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def main(argv: list[str] | None = None) -> int:
    if sys.stdout is None:
        sys.stdout = _NullStream()  # type: ignore[assignment]
    if sys.stderr is None:
        sys.stderr = _NullStream()  # type: ignore[assignment]

    args = build_parser().parse_args(argv)

    # 两者都必须在 QApplication 之前设置
    enable_dpi_awareness()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Ultra AC")

    # 只允许跑一个：已经有实例就把它叫起来，自己退出（截图回归不受此限）
    guard = None
    if not args.shot:
        guard = SingleInstance()
        if not guard.acquire():
            wake_existing()
            return 0

    if args.theme == "auto":
        THEME.set_dark(system_prefers_dark())
    else:
        THEME.set_dark(args.theme == "dark")
    # 系统关了“显示动画效果”，程序内所有过渡也一帧到位
    set_motion_enabled(system_animations_enabled())

    win = MainWindow()
    app.aboutToQuit.connect(win.shutdown)
    wake = WakeListener(win)
    wake.activated.connect(win.restore)
    app.aboutToQuit.connect(wake.detach)
    win.show()

    def finish_boot() -> None:
        from .widgets.icons import LOGO_BG, LOGO_FG, app_icon_qicon
        from .widgets.primitives import ensure_fonts

        # logo 固定白底黑线，不跟随深浅色 —— 与 exe 文件图标是同一份绘制代码
        app.setWindowIcon(app_icon_qicon(LOGO_BG, LOGO_FG))
        ensure_fonts()
        win.load()
        if args.running:
            # 截图模式只改外观：真启动会真的往桌面注入点击
            win.set_preview(True)
        if args.hud:
            win.hud.set_state(True, 97.3)
            win.hud.show_hud()
        if args.sheet:
            win.open_settings()
        elif args.about:
            win.open_about()
        if args.shot:
            def _capture() -> None:
                if args.shot:
                    ok = win.grab().save(args.shot)
                    print(f"{'wrote' if ok else 'FAILED'} {args.shot} "
                          f"({win.width()}x{win.height()})")
                    # 悬浮窗是独立的顶层窗口，不在主窗口的截图里，单独存一张
                    if args.hud:
                        path = args.shot.replace(".png", "-hud.png")
                        if win.hud.grab().save(path):
                            print(f"wrote {path} (hud)")
                app.quit()

            QTimer.singleShot(SHOT_DELAY_MS, _capture)
            # 兜底：这个模式下 Qt 的收尾偶尔会卡住，回归脚本不该为此挂几分钟
            QTimer.singleShot(4000, lambda: os._exit(1))

    # 窗口先弹出来（转圈），弹完再装界面
    win.pop_in(finish_boot)

    rc = app.exec()
    if guard is not None:
        guard.release()
    if args.shot:
        # 正常路径到这里就结束，硬退是为了避开偶发卡死的解释器收尾
        sys.stdout.flush()
        os._exit(rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
