#!/usr/bin/env python3
"""
A杀抓启动 — 横盘选股策略

用法:
    python3 main.py                        # 智能扫描（快照有效则增量）
    python3 main.py --code 002xxx          # 分析单只股票
    python3 main.py --refresh              # 强制全市场扫描
    python3 main.py --top 10               # 输出Top 10
    python3 main.py --json                 # JSON输出
    python3 main.py --verbose              # 详细日志
"""

import sys
import json
import argparse
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import MIN_MARKET_CAP, MAX_MARKET_CAP, MAX_STOCKS_SCAN
from eastmoney_api import get_stock_list
from scanner import scan_all, scan_single, scan_from_pool, format_results
from snapshot import load_snapshot, save_snapshot, is_snapshot_fresh


def main():
    parser = argparse.ArgumentParser(
        description="A杀抓启动 — 横盘选股策略",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 main.py                  # 智能扫描
  python3 main.py --code 002xxx    # 分析单只
  python3 main.py --refresh        # 强制全扫
  python3 main.py --top 10         # 输出Top 10
  python3 main.py --json           # JSON输出
        """,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--code", "-c", type=str, help="分析单只股票，例如 600519")
    group.add_argument("--top", "-t", type=int, default=0, help="只输出前N只")
    parser.add_argument("--refresh", "-r", action="store_true", help="强制全市场扫描")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")

    args = parser.parse_args()
    start_time = datetime.now()

    if args.code:
        print(f"🔍 分析 {args.code}...")
        result = scan_single(args.code, verbose=args.verbose)
        if result:
            from scanner import format_result
            print(format_result(result))
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("📭 未发现横盘选股信号")
        return

    snapshot = load_snapshot()

    if args.refresh or snapshot is None or not is_snapshot_fresh(snapshot):
        if snapshot is None:
            print("📋 未检测到快照，执行全市场扫描...")
        elif args.refresh:
            print("🔄 --refresh 强制全市场扫描...")
        else:
            age = 999
            try:
                from datetime import date
                age = (date.today() - date.fromisoformat(snapshot["scan_date"])).days
            except Exception:
                pass
            print(f"📋 快照已过期({age}天前)，执行全市场扫描...")

        print("📡 正在获取A股主板股票列表（流通市值10-60亿，非ST）...")
        stocks = get_stock_list(max_pages=15)

        filtered = [s for s in stocks
                    if MIN_MARKET_CAP <= s["market_cap"] <= MAX_MARKET_CAP]
        print(f"✅ 获取到 {len(stocks)} 只 → 市值筛选后 {len(filtered)} 只")

        to_scan = filtered[:MAX_STOCKS_SCAN]
        print(f"🔍 扫描 {len(to_scan)} 只股票...")
        results, pool = scan_all(to_scan, verbose=args.verbose)

        save_snapshot(pool)
        print(f"📊 A杀候选池: {len(pool)} 只")
    else:
        pool = snapshot.get("pool", [])
        print(f"📋 快照有效（{snapshot['scan_date']}），候选池 {len(pool)} 只，增量扫描...")
        results, new_pool = scan_from_pool(pool, verbose=args.verbose)
        save_snapshot(new_pool, scan_date=snapshot["scan_date"])
        print(f"📊 候选池更新: {len(pool)} → {len(new_pool)} 只")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n⏱ 耗时: {elapsed:.1f}s")
    print(f"🎯 发现 {len(results)} 只符合条件的股票\n")

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        output = format_results(results, top=args.top)
        print(output)


if __name__ == "__main__":
    main()
