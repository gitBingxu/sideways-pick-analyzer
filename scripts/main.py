#!/usr/bin/env python3
"""
A杀抓启动 — 横盘选股策略

用法:
    python3 main.py                        # 全市场扫描
    python3 main.py --code 002xxx          # 分析单只股票
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
from scanner import scan_all, scan_single, format_results


def main():
    parser = argparse.ArgumentParser(
        description="A杀抓启动 — 横盘选股策略",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 main.py                  # 全市场扫描
  python3 main.py --code 002xxx    # 分析单只
  python3 main.py --top 10         # 输出Top 10
  python3 main.py --json           # JSON输出
        """,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--code", "-c", type=str, help="分析单只股票，例如 600519")
    group.add_argument("--top", "-t", type=int, default=0, help="只输出前N只")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")

    args = parser.parse_args()
    start_time = datetime.now()

    if args.code:
        # 单只分析
        print(f"🔍 分析 {args.code}...")
        result = scan_single(args.code, verbose=args.verbose)
        if result:
            from scanner import format_result
            print(format_result(result))
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("📭 未发现横盘选股信号")
    else:
        # 全市场扫描
        results = scan_all(verbose=args.verbose)
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n⏱ 耗时: {elapsed:.1f}s")

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            output = format_results(results, top=args.top)
            print(output)


if __name__ == "__main__":
    main()
