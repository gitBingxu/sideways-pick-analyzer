"""
快照管理：记录扫描快照，支持增量扫描。
"""

import json
import os
from datetime import date

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SNAPSHOT_MAX_AGE_DAYS

SNAPSHOT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "snapshot.json"
)


def _ensure_dir():
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)


def load_snapshot():
    """加载快照，返回 dict 或 None。"""
    if not os.path.exists(SNAPSHOT_FILE):
        return None
    with open(SNAPSHOT_FILE, "r") as f:
        return json.load(f)


def save_snapshot(pool, scan_date=None):
    """保存快照。pool: list[dict], scan_date: ISO日期字符串，默认今天。"""
    _ensure_dir()
    snapshot = {
        "scan_date": scan_date or date.today().isoformat(),
        "pool": pool,
    }
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def is_snapshot_fresh(snapshot):
    """判断快照是否在有效期内。"""
    if not snapshot:
        return False
    sd_str = snapshot.get("scan_date", "")
    try:
        sd = date.fromisoformat(sd_str)
    except (ValueError, TypeError):
        return False
    return (date.today() - sd).days < SNAPSHOT_MAX_AGE_DAYS
