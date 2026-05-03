#!/usr/bin/env python3
"""
东方财富公开 API 封装（横盘选股专用版）
"""

import json
import re
import time
import urllib.request
import urllib.parse
from typing import Optional


def _fetch(url: str, max_retries: int = 3) -> dict:
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://quote.eastmoney.com/",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise ValueError(f"no JSON: {raw[:200]}")
            data = json.loads(match.group())
            if isinstance(data, dict) and data.get("rc") is not None and data["rc"] != 0:
                raise ValueError(f"API rc={data['rc']} msg={data.get('msg','')}")
            return data
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
    raise last_err


def get_stock_list(market: str = "A", max_pages: int = 10) -> list[dict]:
    """
    获取A股全市场股票列表（含代码、名称、流通市值）。
    返回: [{"code":"600519","name":"贵州茅台","market_cap":25000}, ...]
    """
    # A股市场 filter: 沪A+深A+创业板+科创板
    fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
    fields = "f12,f14,f20,f21"  # 代码,名称,总市值,流通市值
    all_stocks = []
    page = 1
    page_size = 100

    while True:
        params = {
            "pn": str(page),
            "pz": "100",
            "po": "1",
            "np": "1",
            "ut": "fa5fd1943c7b386f172d6893dbfbfdc4",
            "fltt": "2",
            "invt": "2",
            "fid": "f12",  # 按代码排序
            "fs": fs,
            "fields": fields,
        }
        qs = urllib.parse.urlencode(params)
        url = f"https://push2.eastmoney.com/api/qt/clist/get?{qs}"
        data = _fetch(url)
        items = data.get("data", {}).get("diff", [])
        if not items:
            break
        for item in items:
            code = str(item.get("f12", ""))
            name = str(item.get("f14", ""))
            # 流通市值（万元），转为亿
            cap_w = item.get("f21") or item.get("f20") or 0
            if isinstance(cap_w, str):
                cap_w = cap_w.strip()
                if cap_w in ("", "-"):
                    continue
                cap_w = float(cap_w)
            cap_yi = cap_w / 100000000  # 元 → 亿
            all_stocks.append({
                "code": code,
                "name": name,
                "market_cap": round(cap_yi, 2),
            })
        if len(items) < page_size or page >= max_pages:
            break
        page += 1
        time.sleep(0.15)

    return all_stocks


def get_stock_kline(code: str, days: int = 120) -> list[dict]:
    """
    获取个股日K线。
    code: "600519" 或 "002xxx"
    days: 交易日数（最多取此天数）
    返回: [{"date":"2026-04-01","open":...,"high":...,"low":...,"close":...,
            "pct":...,"volume":...,"amount":...}, ...]
    优先东方财富（支持更长周期）。
    """
    market = "1" if code[:3] in ("600","601","603","605","688") else \
             "0" if code[:3] in ("000","001","002","003","300") else "0"
    secid = f"{market}.{code}"
    params = {
        "secid": secid,
        "klt": "101",
        "lmt": str(days),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "fa5fd1943c7b386f172d6893dbfbfdc4",
        "fqt": "1",
    }
    qs = urllib.parse.urlencode(params)
    try:
        data = _fetch(f"https://push2.eastmoney.com/api/qt/stock/kline/get?{qs}")
    except Exception:
        return []
    results = []
    klines = data.get("data", {}).get("klines", [])
    pre_close = None
    for line in klines:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        open_p  = float(parts[1])
        close_p = float(parts[2])
        high_p  = float(parts[3])
        low_p   = float(parts[4])
        vol     = float(parts[5])
        amt     = float(parts[6])
        pct = (close_p - pre_close) / pre_close * 100 if pre_close else 0
        results.append({
            "date": parts[0],
            "open": open_p,
            "close": close_p,
            "high": high_p,
            "low": low_p,
            "pre_close": pre_close or open_p,
            "pct": round(pct, 2),
            "volume": vol,
            "amount": amt,
        })
        pre_close = close_p
    return results


def get_stock_quote(code: str) -> dict:
    """
    获取个股实时行情（含流通市值）。
    返回: {"code":"600519","name":"贵州茅台","price":1500,"pct":1.5,
           "open":1480,"high":1505,"low":1475,
           "volume":50000,"amount":7e9,"market_cap":25000}
    market_cap 单位为亿。
    """
    market = "1" if code[:3] in ("600","601","603","605","688") else \
             "0" if code[:3] in ("000","001","002","003","300") else "0"
    secid = f"{market}.{code}"
    params = {
        "secid": secid,
        "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f20,f21",
    }
    qs = urllib.parse.urlencode(params)
    data = _fetch(f"https://push2.eastmoney.com/api/qt/stock/get?{qs}")
    d = data.get("data", {})
    cap_w = d.get("f21") or d.get("f20") or 0
    return {
        "code": d.get("f57", code),
        "name": d.get("f58", ""),
        "price": (d.get("f43") or 0) / 100,
        "pct": (d.get("f170") or 0) / 100,
        "open": (d.get("f44") or 0) / 100,
        "high": (d.get("f45") or 0) / 100,
        "low": (d.get("f46") or 0) / 100,
        "volume": d.get("f47") or 0,
        "amount": d.get("f48") or 0,
        "market_cap": round(cap_w / 100000000, 2),
    }
