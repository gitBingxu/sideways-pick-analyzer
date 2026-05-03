#!/usr/bin/env python3
"""
数据源封装：腾讯 API（K线+实时行情）+ 东方财富（股票列表）

腾讯 API 稳定不易拦截，东方财富 clist/get 也可用。
"""

import json
import re
import time
import urllib.request
import urllib.parse


# ─── 通用 HTTP 请求 ──────────────────────────────────────

def _fetch(url: str, encoding: str = "utf-8", max_retries: int = 3,
           headers: dict = None) -> str:
    """带重试的 HTTP GET，返回原始文本。"""
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": "https://quote.eastmoney.com/",
        }
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode(encoding)
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
    raise last_err


def _fetch_json(url: str, max_retries: int = 3) -> dict:
    """HTTP GET + JSON 解析（自动处理 JSONP 包装）。"""
    raw = _fetch(url, max_retries=max_retries)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON found in response: {raw[:200]}")
    data = json.loads(match.group())
    if isinstance(data, dict) and data.get("rc") is not None and data["rc"] != 0:
        raise ValueError(f"API error rc={data['rc']} msg={data.get('msg','')}")
    return data


# ─── 市场/前缀工具 ────────────────────────────────────────

def _market_prefix(code: str) -> str:
    """返回腾讯前缀：sh / sz"""
    if code[:3] in ("600", "601", "603", "605", "688"):
        return "sh"
    return "sz"


def _em_market(code: str) -> str:
    """返回东方财富市场代码：1=沪, 0=深"""
    if code[:3] in ("600", "601", "603", "605", "688"):
        return "1"
    return "0"


# ─── 股票列表（东方财富 clist/get）─────────────────────────

def get_stock_list(max_pages: int = 15) -> list[dict]:
    """
    获取A股全市场股票列表（含代码、名称、流通市值）。
    max_pages: 每页100只，15页 = 1500只，涵盖90%以上活跃A股
    返回: [{"code":"600519","name":"贵州茅台","market_cap":17341.31}, ...]
    market_cap 单位为亿
    """
    fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"  # 深A主板+创业板+沪A主板+科创板
    fields = "f12,f14,f20,f21"  # 代码,名称,总市值,流通市值
    all_stocks = []
    page = 1
    page_size = 100

    while True:
        params = {
            "pn": str(page),
            "pz": str(page_size),
            "po": "1",
            "np": "1",
            "ut": "fa5fd1943c7b386f172d6893dbfbfdc4",
            "fltt": "2",
            "invt": "2",
            "fid": "f12",
            "fs": fs,
            "fields": fields,
        }
        qs = urllib.parse.urlencode(params)
        url = f"https://push2.eastmoney.com/api/qt/clist/get?{qs}"
        try:
            data = _fetch_json(url, max_retries=2)
        except Exception:
            break

        items = data.get("data", {}).get("diff", [])
        if not items:
            break

        for item in items:
            code = str(item.get("f12", ""))
            name = str(item.get("f14", ""))
            cap_val = item.get("f21") or item.get("f20")
            if cap_val is None:
                continue
            if isinstance(cap_val, str):
                cap_val = cap_val.strip()
                if cap_val in ("", "-"):
                    continue
                cap_val = float(cap_val)
            # 东方财富返回单位为元 → 亿
            cap_yi = cap_val / 100000000
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


# ─── 日K线（腾讯 API）──────────────────────────────────────

def get_stock_kline(code: str, days: int = 120) -> list[dict]:
    """
    获取个股日K线（腾讯 API）。
    返回: [{"date":"2026-04-01","open":...,"high":...,"low":...,"close":...,
            "pct":...,"volume":...,"amount":...}, ...]
    """
    prefix = _market_prefix(code)
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={prefix}{code},day,,,{days},qfq")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://gu.qq.com/",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    key = f"{prefix}{code}"
    klines = data.get("data", {}).get(key, {}).get("qfqday", [])
    if not klines:
        klines = data.get("data", {}).get(key, {}).get("day", [])

    if not klines:
        return []

    results = []
    pre_close = None
    for line in klines:
        date_str = str(line[0])
        open_p = float(line[1])
        close_p = float(line[2])
        high_p = float(line[3])
        low_p = float(line[4])
        vol = float(line[5]) if len(line) > 5 else 0
        pct = (close_p - pre_close) / pre_close * 100 if pre_close else 0
        results.append({
            "date": date_str,
            "open": open_p,
            "close": close_p,
            "high": high_p,
            "low": low_p,
            "pre_close": pre_close or open_p,
            "pct": round(pct, 2),
            "volume": vol,
            "amount": 0,
        })
        pre_close = close_p
    return results


# ─── 实时行情（腾讯 API）───────────────────────────────────

def get_stock_quote(code: str) -> dict:
    """
    获取个股实时行情（腾讯 API）。
    返回: {"code":"600519","name":"贵州茅台","price":1384.79,"pct":-1.17,
           "market_cap":17341.31}
    market_cap 单位亿（从腾讯原始字段取，可能不精确）。
    """
    prefix = _market_prefix(code)
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    try:
        raw = _fetch(url, encoding="gbk")
    except Exception:
        return {"code": code, "name": "", "price": 0, "pct": 0, "market_cap": 0}

    # 解析腾讯格式
    match = re.search(r'\"(.+)\"', raw)
    if not match:
        return {"code": code, "name": "", "price": 0, "pct": 0, "market_cap": 0}

    parts = match.group(1).split("~")
    try:
        price = float(parts[3]) if len(parts) > 3 and parts[3] else 0
    except (ValueError, IndexError):
        price = 0
    try:
        pct = float(parts[32]) if len(parts) > 32 and parts[32] else 0
    except (ValueError, IndexError):
        pct = 0
    try:
        total_cap = float(parts[45]) if len(parts) > 45 and parts[45] else 0
    except (ValueError, IndexError):
        total_cap = 0

    return {
        "code": code,
        "name": parts[1] if len(parts) > 1 else "",
        "price": price,
        "pct": pct,
        "market_cap": total_cap,
    }
