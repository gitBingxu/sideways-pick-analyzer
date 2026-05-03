# 横盘选股策略 — A杀抓启动

基于 B站视频《A杀抓启动》交易策略的 Python 量化工具。

## 策略原理

A 股小市值股票经历一轮快速猛烈下跌（A杀）后，在底部区域长时间横盘整理。主力资金通过多次放量试盘、缩量回调完成筹码交换，随后启动拉升。

**选股三部曲：**
1. A杀筛选（跌幅≥30%，快速完成）
2. 横盘判定（≥20交易日，振幅收敛）
3. 量能确认（放量试盘信号+买点形态）

## 安装

```bash
git clone https://github.com/gitBingxu/sideways-pick-analyzer
cd sideways-pick-analyzer
```

无需安装第三方库（仅使用 Python 标准库）。

## 使用

```bash
# 全市场扫描
python3 scripts/main.py

# 只输出 Top 10
python3 scripts/main.py --top 10

# 分析单只股票
python3 scripts/main.py --code 600519

# 详细日志
python3 scripts/main.py --verbose

# JSON 格式
python3 scripts/main.py --json
```

## 参数调优

所有参数集中在 `scripts/config.py`，可根据不同市场环境调整。

**推荐参数组合（保守型）：**
- A_SHA_MIN_DROP = -0.35
- CONSOLIDATION_TOLERANCE = 0.12
- LONG_YANG_VOL_RATIO = 2.5

**推荐参数组合（激进型）：**
- A_SHA_MIN_DROP = -0.25
- CONSOLIDATION_TOLERANCE = 0.20
- LONG_YANG_VOL_RATIO = 1.5

## 文件结构

```
sideways-pick-analyzer/
├── scripts/
│   ├── main.py              # 主入口 CLI
│   ├── eastmoney_api.py     # 东方财富API封装
│   ├── scanner.py           # 全市场扫描器
│   ├── signal_detector.py   # 形态识别算法
│   └── config.py            # 参数配置
├── SKILL.md                 # 元数据
└── README.md
```

## 数据源

东方财富公开 API，无需登录，免费使用。

## 风险提示

⚠️ 本工具仅用于技术分析和策略研究，不构成任何投资建议。
股市有风险，投资需谨慎。
