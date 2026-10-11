# -*- coding: utf-8 -*-
"""Material Design 3 颜色系统。"""

from __future__ import annotations

import math
from dataclasses import dataclass

# OKLab / OKLCH 基础转换


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _linear_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def _oklab_to_linear(L: float, a: float, b: float) -> tuple[float, float, float]:
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def rgb_to_hex(r: float, g: float, b: float) -> str:
    f = lambda x: max(0, min(255, round(x * 255)))  # noqa: E731
    return f"#{f(r):02X}{f(g):02X}{f(b):02X}"


def mix(a: str, b: str, t: float) -> str:
    """按 t（0–1）在两色之间取中间色。控件做状态过渡时用。"""
    t = max(0.0, min(1.0, float(t)))
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return rgb_to_hex((ra + (rb - ra) * t) / 255,
                      (ga + (gb - ga) * t) / 255,
                      (ba + (bb - ba) * t) / 255)


def seed_to_lch(hex_color: str) -> tuple[float, float, float]:
    """种子色 → (L, C, h)，其中 h 为弧度。"""
    r, g, b = (c / 255 for c in hex_to_rgb(hex_color))
    L, a, bb = _linear_to_oklab(_srgb_to_linear(r), _srgb_to_linear(g),
                                _srgb_to_linear(b))
    return L, math.hypot(a, bb), math.atan2(bb, a)


def _lch_to_linear(L: float, C: float, h: float) -> tuple[float, float, float]:
    return _oklab_to_linear(L, C * math.cos(h), C * math.sin(h))


def _in_gamut(L: float, C: float, h: float) -> bool:
    r, g, b = _lch_to_linear(L, C, h)
    eps = 1e-4
    return all(-eps <= v <= 1 + eps for v in (r, g, b))


def tone_to_l(t: float) -> float:
    """MD3 的 tone 是 CIELAB 明度 L*（0–100），不是 OKLab 的 L。

    两者必须换算：L* 先按 CIE 公式变成相对亮度 Y，灰度下 OKLab 的
    L 恰好等于 Y 的三次方根。直接拿 t/100 当 L 用，低色调会被压到近黑
    （tone 6 会变成 #000102 而不是 #111318），深色模式就整个糊成一片。
    """
    t = max(0.0, min(100.0, float(t)))
    y = t / 903.3 if t <= 8.0 else ((t + 16.0) / 116.0) ** 3
    return y ** (1.0 / 3.0)


def tone(hue: float, chroma: float, t: float) -> str:
    """生成某个色调板在色调值 t（0–100）上的颜色。"""
    L = tone_to_l(t)
    C = chroma
    if not _in_gamut(L, C, hue):
        lo, hi = 0.0, C
        for _ in range(18):
            mid = (lo + hi) / 2
            if _in_gamut(L, mid, hue):
                lo = mid
            else:
                hi = mid
        C = lo
    r, g, b = _lch_to_linear(L, C, hue)
    return rgb_to_hex(_linear_to_srgb(r), _linear_to_srgb(g), _linear_to_srgb(b))


# 颜色角色

@dataclass(frozen=True)
class Scheme:
    """MD3 完整颜色角色表。控件里只允许引用角色，不允许出现字面量色值。"""

    name: str
    dark: bool

    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str

    secondary: str
    on_secondary: str
    secondary_container: str
    on_secondary_container: str

    tertiary: str
    on_tertiary: str
    tertiary_container: str
    on_tertiary_container: str

    error: str
    on_error: str
    error_container: str
    on_error_container: str

    # 运行态。MD3 标准角色表里没有 success，这里按同一套 tonal 规则扩一个
    success: str
    on_success: str
    success_container: str
    on_success_container: str

    surface: str
    on_surface: str
    surface_variant: str
    on_surface_variant: str
    surface_dim: str
    surface_bright: str
    surface_container_lowest: str
    surface_container_low: str
    surface_container: str
    surface_container_high: str
    surface_container_highest: str

    outline: str
    outline_variant: str
    inverse_surface: str
    inverse_on_surface: str
    inverse_primary: str
    scrim: str
    shadow: str
    surface_tint: str

# MD3 各色调板的彩度基准（OKLCH 尺度，已按经验换算自 HCT 的 36/16/24/4/8/50）
CHROMA = {
    "primary": 0.145,
    "secondary": 0.065,
    "tertiary": 0.105,
    "neutral": 0.010,
    "neutral_variant": 0.024,
    "error": 0.170,
    "success": 0.130,
}

SEED = "#0B57D0"          # 种子色：只有一个地方需要改
ERROR_SEED = "#B3261E"    # MD3 标准错误色
SUCCESS_SEED = "#1E8E3E"  # 运行态绿


def _palettes(seed: str = SEED):
    _, _, h_primary = seed_to_lch(seed)
    _, _, h_error = seed_to_lch(ERROR_SEED)
    _, _, h_success = seed_to_lch(SUCCESS_SEED)
    return {
        # 三级色按 MD3 惯例把色相旋转 +60°，制造和谐的对比
        "primary": (h_primary, CHROMA["primary"]),
        "secondary": (h_primary, CHROMA["secondary"]),
        "tertiary": (h_primary + math.radians(60), CHROMA["tertiary"]),
        "neutral": (h_primary, CHROMA["neutral"]),
        "neutral_variant": (h_primary, CHROMA["neutral_variant"]),
        "error": (h_error, CHROMA["error"]),
        "success": (h_success, CHROMA["success"]),
    }


def build_scheme(dark: bool, seed: str = SEED) -> Scheme:
    pal = _palettes(seed)

    def t(name: str, tone_value: float) -> str:
        hue, chroma = pal[name]
        return tone(hue, chroma, tone_value)

    if not dark:
        return Scheme(
            name="light", dark=False,
            primary=t("primary", 40), on_primary=t("primary", 100),
            primary_container=t("primary", 90),
            on_primary_container=t("primary", 10),
            secondary=t("secondary", 40), on_secondary=t("secondary", 100),
            secondary_container=t("secondary", 90),
            on_secondary_container=t("secondary", 10),
            tertiary=t("tertiary", 40), on_tertiary=t("tertiary", 100),
            tertiary_container=t("tertiary", 90),
            on_tertiary_container=t("tertiary", 10),
            error=t("error", 40), on_error=t("error", 100),
            error_container=t("error", 90),
            on_error_container=t("error", 10),
            success=t("success", 40), on_success=t("success", 100),
            success_container=t("success", 90),
            on_success_container=t("success", 10),
            surface=t("neutral", 98), on_surface=t("neutral", 10),
            surface_variant=t("neutral_variant", 90),
            on_surface_variant=t("neutral_variant", 30),
            surface_dim=t("neutral", 87), surface_bright=t("neutral", 98),
            surface_container_lowest=t("neutral", 100),
            surface_container_low=t("neutral", 96),
            surface_container=t("neutral", 94),
            surface_container_high=t("neutral", 92),
            surface_container_highest=t("neutral", 90),
            outline=t("neutral_variant", 50),
            outline_variant=t("neutral_variant", 80),
            inverse_surface=t("neutral", 20),
            inverse_on_surface=t("neutral", 95),
            inverse_primary=t("primary", 80),
            scrim=t("neutral", 0), shadow=t("neutral", 0),
            surface_tint=t("primary", 40),
        )

    return Scheme(
        name="dark", dark=True,
        primary=t("primary", 80), on_primary=t("primary", 20),
        primary_container=t("primary", 30),
        on_primary_container=t("primary", 90),
        secondary=t("secondary", 80), on_secondary=t("secondary", 20),
        secondary_container=t("secondary", 30),
        on_secondary_container=t("secondary", 90),
        tertiary=t("tertiary", 80), on_tertiary=t("tertiary", 20),
        tertiary_container=t("tertiary", 30),
        on_tertiary_container=t("tertiary", 90),
        error=t("error", 80), on_error=t("error", 20),
        error_container=t("error", 30),
        on_error_container=t("error", 90),
        success=t("success", 80), on_success=t("success", 20),
        success_container=t("success", 30),
        on_success_container=t("success", 90),
        surface=t("neutral", 6), on_surface=t("neutral", 90),
        surface_variant=t("neutral_variant", 30),
        on_surface_variant=t("neutral_variant", 80),
        surface_dim=t("neutral", 6), surface_bright=t("neutral", 24),
        surface_container_lowest=t("neutral", 4),
        surface_container_low=t("neutral", 10),
        surface_container=t("neutral", 12),
        surface_container_high=t("neutral", 17),
        surface_container_highest=t("neutral", 22),
        outline=t("neutral_variant", 60),
        outline_variant=t("neutral_variant", 30),
        inverse_surface=t("neutral", 90),
        inverse_on_surface=t("neutral", 20),
        inverse_primary=t("primary", 40),
        scrim=t("neutral", 0), shadow=t("neutral", 0),
        surface_tint=t("primary", 80),
    )


LIGHT = build_scheme(dark=False)
DARK = build_scheme(dark=True)
