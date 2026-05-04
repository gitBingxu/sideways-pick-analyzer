"""
形态识别算法：A杀检测、横盘判定、量能分析、买点判断
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from typing import Optional
from config import *


def detect_a_shred(kline: list[dict]) -> Optional[tuple]:
    """
    检测A杀形态。
    输入: K线列表（需按日期正序）
    返回: (跌幅(float), 起点日期(str), 终点日期(str)) 或 None
    """
    if len(kline) < A_SHA_LOOKBACK:
        return None

    recent = kline[-A_SHA_LOOKBACK:]

    # 1. 找到近期最高点
    peak_idx = 0
    peak_price = float("-inf")
    for i, bar in enumerate(recent):
        if bar["high"] > peak_price:
            peak_price = bar["high"]
            peak_idx = i
    peak_date = recent[peak_idx]["date"]

    # 2. 从峰值后找最低点（限定 A_SHA_MAX_DAYS 天内）
    post_peak = recent[peak_idx:]
    if len(post_peak) < 2:
        return None

    trough_idx = 0
    trough_price = float("inf")
    for i, bar in enumerate(post_peak):
        if i > A_SHA_MAX_DAYS:
            break
        if bar["low"] < trough_price:
            trough_price = bar["low"]
            trough_idx = i
    trough_date = post_peak[trough_idx]["date"]

    # 3. 计算跌幅
    drop_rate = (trough_price - peak_price) / peak_price
    if drop_rate > A_SHA_MIN_DROP:
        return None  # 跌幅不够

    # 4. 验证：下跌途中无显著反弹
    for i in range(1, trough_idx + 1):
        bar = post_peak[i]
        rebound = (bar["high"] - post_peak[0]["close"]) / post_peak[0]["close"]
        if rebound > A_SHA_MAX_REBOUND:
            return None

    return (round(drop_rate, 4), peak_date, trough_date)


def detect_consolidation(kline: list[dict], trough_date: str,
                         min_days: int = None) -> Optional[tuple]:
    """
    检测横盘整理形态（从A杀最低点之后）。
    输入: K线列表, A杀最低点日期, min_days(默认取 CONSOLIDATION_MIN_DAYS)
    返回: (横盘天数(int), 上轨价(float), 下轨价(float)) 或 None
    """
    if min_days is None:
        min_days = CONSOLIDATION_MIN_DAYS
    # 找到A杀最低点之后的K线
    start_idx = None
    for i, bar in enumerate(kline):
        if bar["date"] >= trough_date:
            start_idx = i
            break
    if start_idx is None:
        return None

    post_kline = kline[start_idx:]
    if len(post_kline) < min_days:
        return None

    # 限制最大观察天数
    post_kline = post_kline[:CONSOLIDATION_MAX_DAYS]

    # 计算横盘区间
    highs = [bar["high"] for bar in post_kline]
    lows = [bar["low"] for bar in post_kline]
    highs.sort()
    lows.sort()
    hi = len(highs)
    lo = len(lows)
    upper = highs[int(hi * CONSOLIDATION_HIGH_Q)]
    lower = lows[int(lo * CONSOLIDATION_LOW_Q)]

    # 区间振幅
    amplitude = (upper - lower) / lower if lower > 0 else 999
    if amplitude > CONSOLIDATION_TOLERANCE:
        return None

    return (len(post_kline), upper, lower)


def detect_volume_signal(kline: list[dict], consol_start: str, consol_end: str) -> Optional[dict]:
    """
    检测横盘期间量能信号。
    返回: {"spike_days": int, "strength": str} 或 None
    """
    # 找到横盘区间数据
    consol_data = []
    found_start = False
    for bar in kline:
        if bar["date"] >= consol_start and not found_start:
            found_start = True
        if found_start:
            if bar["date"] > consol_end:
                break
            consol_data.append(bar)

    if len(consol_data) < CONSOLIDATION_MIN_DAYS:
        return None

    # 计算5日均量
    volumes = [bar["volume"] for bar in consol_data]
    ma5 = []
    for i in range(len(volumes)):
        window = max(0, i - VOLUME_MA_WINDOW + 1)
        ma5.append(sum(volumes[window:i+1]) / (i - window + 1) if (i - window + 1) > 0 else volumes[i])

    spike_days = 0
    long_yang_days = 0
    for i, bar in enumerate(consol_data):
        if i == 0:
            continue
        if ma5[i] > 0 and bar["volume"] >= ma5[i] * VOLUME_SPIKE_RATIO:
            spike_days += 1
            # 放量且为阳线
            if bar["close"] > bar["open"]:
                pct = (bar["close"] - bar["pre_close"]) / bar["pre_close"] * 100
                if pct >= LONG_YANG_MIN_PCT and bar["volume"] >= ma5[i] * LONG_YANG_VOL_RATIO:
                    long_yang_days += 1

    if spike_days < VOLUME_SPIKE_COUNT:
        return None

    # 信号强度
    if long_yang_days >= 2:
        strength = "强"
    elif long_yang_days >= 1:
        strength = "中"
    else:
        strength = "弱"

    return {
        "spike_days": spike_days,
        "long_yang_days": long_yang_days,
        "strength": strength,
    }


def detect_buy_pattern(kline: list[dict], consol_low: float, consol_high: float) -> Optional[dict]:
    """
    检测买点形态。
    返回: {"type": str, "entry": float, "stop_loss": float, "description": str} 或 None
    """
    if len(kline) < 10:
        return None

    recent = kline[-30:]

    # ===== 形态①：放量长阳回踩型 =====
    # 寻找放量长阳
    volumes = [bar["volume"] for bar in recent]
    ma5_vol = []
    for i in range(len(volumes)):
        window = max(0, i - VOLUME_MA_WINDOW + 1)
        ma5_vol.append(sum(volumes[window:i+1]) / (i - window + 1) if (i - window + 1) > 0 else volumes[i])

    for i in range(len(recent) - 3, 2, -1):  # 从后往前找，留出回调空间
        bar = recent[i]
        if ma5_vol[i] <= 0:
            continue
        pct = (bar["close"] - bar["pre_close"]) / bar["pre_close"] * 100
        if pct >= LONG_YANG_MIN_PCT and bar["volume"] >= ma5_vol[i] * LONG_YANG_VOL_RATIO:
            yang_high = bar["high"]
            yang_low = bar["low"]
            # 检查后续是否回调
            post_bars = recent[i+1:]
            if len(post_bars) < 2:
                continue
            pullback_low = min(b["low"] for b in post_bars)
            pullback = (yang_high - pullback_low) / (yang_high - yang_low)
            # 回调至中下部且不破阳线底部
            if pullback_low >= yang_low and pullback >= 0.35 and pullback <= PULLBACK_MAX_RETRACE:
                # 最近一日不破防守位
                last_close = recent[-1]["close"]
                last_low = recent[-1]["low"]
                stop_loss = min(yang_low, consol_low)
                if last_low > stop_loss:
                    entry_target = last_close
                    return {
                        "type": "放量长阳回踩型",
                        "entry": round(entry_target, 2),
                        "stop_loss": round(stop_loss, 2),
                        "description": (
                            f"{bar['date']}出现放量长阳(涨幅{pct:.1f}%)，"
                            f"回调至阳线中下部，不破底部"
                        ),
                    }

    # ===== 形态②：破位反转型 =====
    for i in range(len(recent) - BREAKDOWN_DAYS, 1, -1):
        # 检查是否有连续跌破下轨
        broke_days = 0
        for j in range(i, min(i + BREAKDOWN_DAYS + 2, len(recent))):
            if recent[j]["close"] < consol_low:
                broke_days += 1
        if 1 <= broke_days <= BREAKDOWN_DAYS:
            # 检查是否快速收回
            recovered = recent[-1]["close"] >= consol_low
            if recovered:
                # 收回时放量
                last_vol = recent[-1]["volume"]
                prev_avg = sum(b["volume"] for b in recent[-6:-1]) / 5 if len(recent) >= 6 else 0
                if prev_avg > 0 and last_vol >= prev_avg * RECOVERY_VOL_RATIO:
                    stop_loss = min(
                        min(b["low"] for b in recent[-BREAKDOWN_DAYS-1:]) * 0.97,
                        consol_low * 0.97,
                    )
                    return {
                        "type": "破位反转型",
                        "entry": round(recent[-1]["close"], 2),
                        "stop_loss": round(stop_loss, 2),
                        "description": (
                            f"跌破横盘下轨{consol_low:.2f}后{broke_days}日快速收回，"
                            f"收回时放量"
                        ),
                    }

    return None
