"""
全市场扫描器：遍历A股、筛选横盘股、输出结果
"""

from typing import Optional
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *
from eastmoney_api import get_stock_list, get_stock_kline
from signal_detector import (
    detect_a_shred,
    detect_consolidation,
    detect_volume_signal,
    detect_buy_pattern,
)


def scan_single(code: str, stock_name: str = "", stock_cap: float = 0,
                verbose: bool = False) -> Optional[dict]:
    """
    分析单只股票，返回横盘选股结果。
    """
    kline = get_stock_kline(code, days=120)
    if not kline or len(kline) < CONSOLIDATION_MIN_DAYS + 10:
        if verbose:
            print(f"  ⚠ {code}: K线数据不足({len(kline) if kline else 0}日)")
        return None

    # A杀检测
    a_result = detect_a_shred(kline)
    if a_result is None:
        if verbose:
            print(f"  ⚠ {code}: 未检测到A杀形态")
        return None
    drop_rate, peak_date, trough_date = a_result

    # 横盘判定
    c_result = detect_consolidation(kline, trough_date)
    if c_result is None:
        if verbose:
            print(f"  ⚠ {code}: 未检测到横盘形态")
        return None
    consol_days, consol_high, consol_low = c_result

    # 量能分析
    v_result = detect_volume_signal(kline, trough_date, kline[-1]["date"])
    if v_result is None:
        if verbose:
            print(f"  ⚠ {code}: 量能不足")
        return None

    # 买点判断
    b_result = detect_buy_pattern(kline, consol_low, consol_high)

    return {
        "code": code,
        "name": stock_name or code,
        "price": kline[-1]["close"],
        "market_cap": stock_cap,
        "a_shred_drop": round(drop_rate * 100, 1),
        "a_shred_peak_date": peak_date,
        "a_shred_trough_date": trough_date,
        "consol_days": consol_days,
        "consol_high": round(consol_high, 2),
        "consol_low": round(consol_low, 2),
        "vol_signal": v_result,
        "buy_pattern": b_result,
    }


def scan_all(verbose: bool = False) -> list[dict]:
    """
    全市场扫描：获取股票列表 → 市值过滤 → 逐一扫描
    """
    print("📡 正在获取A股股票列表...")
    stocks = get_stock_list(max_pages=15)
    print(f"✅ 获取到 {len(stocks)} 只A股")

    # 市值过滤
    filtered = [s for s in stocks
                if MIN_MARKET_CAP <= s["market_cap"] <= MAX_MARKET_CAP]
    print(f"🔍 市值 {MIN_MARKET_CAP}亿~{MAX_MARKET_CAP}亿: {len(filtered)} 只")

    to_scan = filtered[:MAX_STOCKS_SCAN]
    results = []

    for i, stock in enumerate(to_scan):
        if verbose:
            print(f"\n[{i+1}/{len(to_scan)}] {stock['code']} {stock['name']} "
                  f"(市值{stock['market_cap']}亿)")
        else:
            if (i + 1) % 30 == 0 or i == 0:
                print(f"  进度: {i+1}/{len(to_scan)}", end="\r")
                sys.stdout.flush()

        try:
            result = scan_single(
                stock["code"],
                stock_name=stock["name"],
                stock_cap=stock["market_cap"],
                verbose=verbose,
            )
            if result:
                results.append(result)
        except Exception as e:
            if verbose:
                print(f"  ✗ {stock['code']}: {e}")

        time.sleep(0.05)

    if not verbose:
        print()

    # 排序：按信号强度 + 横盘天数 + A杀深度
    def sort_key(r):
        strength_map = {"强": 3, "中": 2, "弱": 1}
        vs = strength_map.get(r.get("vol_signal", {}).get("strength", ""), 0)
        buy = 2 if r.get("buy_pattern") else 0
        consol = r.get("consol_days", 0)
        # A杀越深信号越强
        a_shred = abs(r.get("a_shred_drop", 0))
        return (vs + buy, consol, a_shred)

    results.sort(key=sort_key, reverse=True)
    print(f"🎯 扫描完成，发现 {len(results)} 只符合条件的股票")
    return results


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
