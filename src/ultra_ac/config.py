# -*- coding: utf-8 -*-
"""设置持久化。"""

from __future__ import annotations

import json
import os
from pathlib import Path

DIR_NAME = "Ultra AC"
FILE_NAME = "settings.json"


def config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if not base:
        # 极少数环境下 APPDATA 缺失，退回默认位置
        base = str(Path.home() / "AppData" / "Roaming")
    return Path(base) / DIR_NAME


def config_path() -> Path:
    return config_dir() / FILE_NAME


def load() -> dict:
    """读配置。文件不存在、内容损坏、或不是 JSON 对象，一律当空配置处理。"""
    try:
        with open(config_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(data: dict) -> bool:
    """写配置。"""
    try:
        folder = config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / (FILE_NAME + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, config_path())
        return True
    except OSError:
        return False


def clear() -> bool:
    """删掉配置文件。连同可能留下的临时文件一起清。"""
    ok = True
    for path in (config_path(), config_dir() / (FILE_NAME + ".tmp")):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            ok = False
    return ok
