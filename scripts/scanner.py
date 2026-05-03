"""
全市场扫描器：遍历A股、筛选横盘股、输出结果
"""

import sys
import time
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *
from eastmoney_api import get_stock_list, get_stock_kline, get_stock_quote
from signal_detector import (
    detect_a_shred,
    detect_consolidation,
    detect_volume_signal,
    detect_buy_pattern,
)


def scan_single(code: str, verbose: bool = False) -> Optional[dict]:
    """
    分析单只股票，返回横盘选股结果。
    """
    kline = get_stock_kline(code, days=120)
    if not kline or len(kline) < CONSOLIDATION_MIN_DAYS + 10:
        if verbose:
            print(f"  ⚠ {code}: K线数据不足")
        return None

    quote = get_stock_quote(code)
    cap = quote.get("market_cap", 0)

    # 1. A杀检测
    a_shred_result = detect_a_shred(kline)
    if a_shred_result is None:
        if verbose:
            print(f"  ⚠ {code}: 未检测到A杀形态")
        return None
    drop_rate, peak_date, trough_date = a_shred_result

    # 2. 横盘判定
    consol_result = detect_consolidation(kline, trough_date)
    if consol_result is None:
        if verbose:
            print(f"  ⚠ {code}: 未检测到横盘形态")
        return None
    consol_days, consol_high, consol_low = consol_result

    # 3. 量能分析
    vol_result = detect_volume_signal(kline, trough_date, kline[-1]["date"])
    if vol_result is None:
        if verbose:
            print(f"  ⚠ {code}: 量能不足")
        return None

    # 4. 买点判断
    buy_result = detect_buy_pattern(kline, consol_low, consol_high)

    return {
        "code": code,
        "name": quote.get("name", ""),
        "price": quote.get("price", 0),
        "market_cap": cap,
        "a_shred_drop": drop_rate,
        "a_shred_peak_date": peak_date,
        "a_shred_trough_date": trough_date,
        "consol_days": consol_days,
        "consol_high": consol_high,
        "consol_low": consol_low,
        "vol_signal": vol_result,
        "buy_pattern": buy_result,
    }


def scan_all(verbose: bool = False) -> list[dict]:
    """
    全市场扫描，返回排序后的结果列表。
    """
    print("📡 正在获取A股全市场股票列表...")
    stocks = get_stock_list()
    print(f"✅ 获取到 {len(stocks)} 只股票")

    # 市值过滤
    filtered = [s for s in stocks if MIN_MARKET_CAP <= s["market_cap"] <= MAX_MARKET_CAP]
    print(f"🔍 市值 {MIN_MARKET_CAP}亿~{MAX_MARKET_CAP}亿: {len(filtered)} 只")

    # 限制扫描数量
    to_scan = filtered[:MAX_STOCKS_SCAN]
    if verbose:
        print(f"📊 开始扫描 {len(to_scan)} 只股票...")

    results = []
    for i, stock in enumerate(to_scan):
        if verbose:
            print(f"\n[{i+1}/{len(to_scan)}] {stock['code']} {stock['name']} (市值{stock['market_cap']}亿)")
        else:
            # 进度条
            if (i + 1) % 50 == 0 or i == 0:
                print(f"  进度: {i+1}/{len(to_scan)}", end="\r")
                sys.stdout.flush()

        result = scan_single(stock["code"], verbose=verbose)
        if result:
            result["name"] = stock["name"]
            result["market_cap"] = stock["market_cap"]
            results.append(result)

        # 限速
        time.sleep(0.05)

    if not verbose:
        print()

    # 排序：按信号强度 + 横盘天数
    def sort_key(r):
        strength_map = {"强": 3, "中": 2, "弱": 1}
        vol_strength = strength_map.get(r.get("vol_signal", {}).get("strength", ""), 0)
        has_buy = 2 if r.get("buy_pattern") else 0
        return (vol_strength + has_buy, r.get("consol_days", 0))

    results.sort(key=sort_key, reverse=True)

    print(f"🎯 扫描完成，发现 {len(results)} 只符合条件的股票")
    return results


def format_result(result: dict, idx: int = 0) -> str:
    """格式化单条结果。"""
    cap = result.get("market_cap", 0)
    drop = result.get("a_shred_drop", 0)
    consol_days = result.get("consol_days", 0)
    consol_high = result.get("consol_high", 0)
    consol_low = result.get("consol_low", 0)
    vol = result.get("vol_signal", {})
    buy = result.get("buy_pattern")

    lines = []
    header = f"  {idx}. {result['code']}  {result['name']}  💰 {cap}亿"
    lines.append(header)
    lines.append(f"     📉 A杀幅度: {drop*100:.1f}%  ({result['a_shred_peak_date']} → {result['a_shred_trough_date']})")
    lines.append(f"     📊 横盘: {consol_days}天  区间: {consol_low:.2f} ~ {consol_high:.2f}")
    lines.append(f"     🔥 量能: {vol.get('strength','?')} (放量{vol.get('spike_days',0)}天, 放量长阳{vol.get('long_yang_days',0)}次)")

    if buy:
        lines.append(f"     ⭐ 买点: {buy['type']}")
        lines.append(f"        🎯 入场: {buy['entry']}  止损: {buy['stop_loss']}")
        lines.append(f"        📝 {buy['description']}")
    else:
        lines.append(f"     💤 暂无买点信号")

    return "\n".join(lines)


def format_results(results: list[dict], top: int = 0) -> str:
    """格式化扫描结果。"""
    if not results:
        return "📭 未找到符合条件的横盘选股信号"

    if top > 0:
        results = results[:top]

    output = []
    output.append("╔══════════════════════════════════════════════════════════╗")
    output.append("║          横盘选股扫描结果                               ║")
    output.append("╠══════════════════════════════════════════════════════════╣")
    for i, r in enumerate(results, 1):
        output.append(format_result(r, i))
        if i < len(results):
            output.append("╟──────────────────────────────────────────────────────╢")
    output.append("╚══════════════════════════════════════════════════════════╝")
    return "\n".join(output)
