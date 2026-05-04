"""
扫描器：全市场扫描 + 增量池扫描 + 单股分析。
"""

from typing import Optional
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *
from eastmoney_api import get_stock_kline
from signal_detector import (
    detect_a_shred,
    detect_consolidation,
    detect_volume_signal,
    detect_buy_pattern,
)


def _analyze_stock(code: str, name: str = "", cap: float = 0,
                   verbose: bool = False) -> tuple:
    """
    拉一次K线，跑完整检测管线。
    返回: (result | None, pool_entry | None)
      - result: 满足全部条件的结果字典（含买点判断）
      - pool_entry: 只要A杀后横盘≥POOL_MIN天就产出，用于建池
    """
    kline = get_stock_kline(code, days=120)
    min_len = max(CONSOLIDATION_MIN_DAYS, POOL_MIN_CONSOLIDATION_DAYS) + 10
    if not kline or len(kline) < min_len:
        if verbose:
            print(f"  ⚠ {code}: K线数据不足({len(kline) if kline else 0}日)")
        return None, None

    # A杀检测
    a_result = detect_a_shred(kline)
    if a_result is None:
        if verbose:
            print(f"  ⚠ {code}: 未检测到A杀形态")
        return None, None
    drop_rate, peak_date, trough_date = a_result

    base = {
        "code": code,
        "name": name or code,
        "market_cap": cap,
        "a_shred_trough_date": trough_date,
        "a_shred_drop": round(drop_rate * 100, 1),
    }

    # 池子检测：A杀后横盘 ≥ POOL_MIN 天
    pool_entry = None
    pool_consol = detect_consolidation(kline, trough_date,
                                       min_days=POOL_MIN_CONSOLIDATION_DAYS)
    if pool_consol is not None:
        pool_days, pool_high, pool_low = pool_consol
        pool_entry = dict(base)
        pool_entry["consol_days"] = pool_days
        pool_entry["consol_high"] = round(pool_high, 2)
        pool_entry["consol_low"] = round(pool_low, 2)

    # 完整检测
    c_result = detect_consolidation(kline, trough_date)
    if c_result is None:
        if verbose and pool_entry is None:
            print(f"  ⚠ {code}: 未检测到横盘形态")
        return None, pool_entry
    consol_days, consol_high, consol_low = c_result

    v_result = detect_volume_signal(kline, trough_date, kline[-1]["date"])
    if v_result is None:
        if verbose:
            print(f"  ⚠ {code}: 量能不足")
        return None, pool_entry

    b_result = detect_buy_pattern(kline, consol_low, consol_high)

    result = {
        **base,
        "price": kline[-1]["close"],
        "a_shred_peak_date": peak_date,
        "consol_days": consol_days,
        "consol_high": round(consol_high, 2),
        "consol_low": round(consol_low, 2),
        "vol_signal": v_result,
        "buy_pattern": b_result,
    }
    return result, pool_entry


def scan_single(code: str, stock_name: str = "", stock_cap: float = 0,
                verbose: bool = False) -> Optional[dict]:
    """分析单只股票，返回完整选股结果或 None。"""
    result, _ = _analyze_stock(code, stock_name, stock_cap, verbose)
    return result


def scan_all(stocks: list[dict], verbose: bool = False) -> tuple:
    """
    全市场扫描。
    stocks: 预过滤后的股票列表 [{"code","name","market_cap"}, ...]
    返回: (results, pool)
    """
    results = []
    pool = []

    for i, stock in enumerate(stocks):
        if verbose:
            print(f"\n[{i+1}/{len(stocks)}] {stock['code']} {stock['name']} "
                  f"(市值{stock['market_cap']}亿)")
        else:
            if (i + 1) % 30 == 0 or i == 0:
                print(f"  进度: {i+1}/{len(stocks)}", end="\r")
                sys.stdout.flush()

        try:
            result, pool_entry = _analyze_stock(
                stock["code"],
                name=stock["name"],
                cap=stock["market_cap"],
                verbose=verbose,
            )
            if result:
                results.append(result)
            if pool_entry:
                pool.append(pool_entry)
        except Exception as e:
            if verbose:
                print(f"  ✗ {stock['code']}: {e}")

        time.sleep(0.05)

    if not verbose:
        print()

    results.sort(key=_sort_key, reverse=True)
    return results, pool


def scan_from_pool(pool: list[dict], verbose: bool = False) -> tuple:
    """
    增量扫描：仅扫描池中股票。
    pool: 快照中的候选列表 [{"code","name","market_cap","a_shred_trough_date",...}, ...]
    返回: (results, new_pool)
      - results: 满足全部条件的结果
      - new_pool: A杀仍有效的池子（过期的剔除）
    """
    results = []
    new_pool = []

    for i, entry in enumerate(pool):
        if verbose:
            print(f"\n[池 {i+1}/{len(pool)}] {entry['code']} {entry.get('name', '')}")
        else:
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  池扫描: {i+1}/{len(pool)}", end="\r")
                sys.stdout.flush()

        try:
            result, new_entry = _analyze_stock(
                entry["code"],
                name=entry.get("name", ""),
                cap=entry.get("market_cap", 0),
                verbose=verbose,
            )
            if new_entry:
                new_pool.append(new_entry)
            if result:
                results.append(result)
        except Exception as e:
            if verbose:
                print(f"  ✗ {entry['code']}: {e}")

        time.sleep(0.05)

    if not verbose:
        print()

    results.sort(key=_sort_key, reverse=True)
    return results, new_pool


def _sort_key(r: dict) -> tuple:
    """排序键：信号强度 + 买点 + 横盘天数 + A杀深度。"""
    strength_map = {"强": 3, "中": 2, "弱": 1}
    vs = strength_map.get(r.get("vol_signal", {}).get("strength", ""), 0)
    buy = 2 if r.get("buy_pattern") else 0
    consol = r.get("consol_days", 0)
    a_shred = abs(r.get("a_shred_drop", 0))
    return (vs + buy, consol, a_shred)


def format_result(result: dict, idx: int = 0) -> str:
    """格式化单条结果。"""
    cap = result.get("market_cap", 0)
    drop = result.get("a_shred_drop", 0)
    cdays = result.get("consol_days", 0)
    chi = result.get("consol_high", 0)
    clo = result.get("consol_low", 0)
    vol = result.get("vol_signal", {})
    buy = result.get("buy_pattern")

    lines = [
        f"  {idx}. {result['code']}  {result['name']}  💰 {cap}亿",
        f"     📉 A杀: -{abs(drop):.1f}%  ({result['a_shred_peak_date']} → "
        f"{result['a_shred_trough_date']})",
        f"     📊 横盘: {cdays}天  区间: {clo} ~ {chi}",
        f"     🔥 量能: {vol.get('strength','?')} "
        f"(放量{vol.get('spike_days',0)}天, "
        f"放量长阳{vol.get('long_yang_days',0)}次)",
    ]

    if buy:
        lines.append(f"     ⭐ 买点: {buy['type']}")
        lines.append(f"        🎯 入场: {buy['entry']}  止损: {buy['stop_loss']}")
        lines.append(f"        📝 {buy['description']}")
    else:
        lines.append("     💤 暂无买点信号")

    return "\n".join(lines)


def format_results(results: list[dict], top: int = 0) -> str:
    """格式化扫描结果。"""
    if not results:
        return "📭 未找到符合条件的横盘选股信号"

    if top > 0:
        results = results[:top]

    output = [
        "╔══════════════════════════════════════════════════════════╗",
        "║          横盘选股扫描结果                               ║",
        "╠══════════════════════════════════════════════════════════╣",
    ]
    for i, r in enumerate(results, 1):
        output.append(format_result(r, i))
        if i < len(results):
            output.append("╟──────────────────────────────────────────────────────╢")
    output.append("╚══════════════════════════════════════════════════════════╝")
    return "\n".join(output)
