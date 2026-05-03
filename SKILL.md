---
name: sideways-pick-analyzer
description: >
  A杀抓启动 — 横盘选股策略。检测A股小市值股票经历A杀（快速大跌）后长时横盘整理，
  识别放量试盘信号和买点形态，捕捉主力启动拉升前的入场机会。
  基于东方财富公开API驱动，无需登录。
---

# A杀抓启动 — 横盘选股策略

基于东方财富公开 API 的全自动横盘选股工具，无需要登录。

## 策略逻辑

1. **A杀**：股票经历快速猛烈下跌（跌幅 ≥ 30%，10个交易日内）
2. **横盘**：A杀后在底部长时间横盘整理（≥ 20 个交易日，振幅 ≤ 15%）
3. **试盘**：横盘期间主力放量试盘信号
4. **买点**：放量长阳回踩型 / 破位反转型两种买点形态

## 快速使用

```bash
# 全市场扫描
python3 scripts/main.py

# 输出Top 10
python3 scripts/main.py --top 10

# 分析单只股票
python3 scripts/main.py --code 002xxx

# JSON输出
python3 scripts/main.py --json
```

## 参数配置

见 `scripts/config.py`，所有参数均可自定义：

| 参数 | 默认值 | 说明 |
|---|---|---|
| MAX_MARKET_CAP | 60亿 | 流通市值上限 |
| A_SHA_MIN_DROP | -30% | A杀最小跌幅 |
| CONSOLIDATION_MIN_DAYS | 20天 | 最小横盘天数 |
| CONSOLIDATION_TOLERANCE | 15% | 横盘振幅容忍度 |
| VOLUME_SPIKE_RATIO | 1.5倍 | 放量阈值 |
| LONG_YANG_MIN_PCT | 5% | 放量长阳最小涨幅 |

## 输出说明

```
1. 600xxx  某某股份  💰 28亿
   📉 A杀幅度: -38.0%  (2026-03-10 → 2026-03-18)
   📊 横盘: 25天  区间: 8.50 ~ 10.20
   🔥 量能: 强 (放量5天, 放量长阳2次)
   ⭐ 买点: 放量长阳回踩型
      🎯 入场: 9.60  止损: 8.40
```

## 依赖

- Python 3.9+
- 无需安装第三方库（仅用标准库：urllib, json, re）
