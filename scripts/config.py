"""
横盘选股策略 — 可配置参数
"""

# ===== 市值筛选 =====
MAX_MARKET_CAP = 60  # 亿，流通市值上限
MIN_MARKET_CAP = 10  # 亿，流通市值下限（过小流动性差）

# ===== A杀检测 =====
A_SHA_LOOKBACK = 60          # 观察周期（交易日）
A_SHA_MIN_DROP = -0.30       # 最小跌幅 -30%
A_SHA_MAX_DAYS = 10          # 从高点跌到最低点的最大天数
A_SHA_MAX_REBOUND = 0.10     # 下跌途中最大反弹不超过 10%

# ===== 横盘判定 =====
CONSOLIDATION_MIN_DAYS = 20   # 最小横盘天数
CONSOLIDATION_MAX_DAYS = 120  # 最大横盘天数
CONSOLIDATION_TOLERANCE = 0.15  # 横盘振幅容忍度（高/低比-1）
CONSOLIDATION_HIGH_Q = 0.85  # 上轨分位
CONSOLIDATION_LOW_Q = 0.15   # 下轨分位

# ===== 量能分析 =====
VOLUME_MA_WINDOW = 5         # 均量窗口
VOLUME_SPIKE_RATIO = 1.5     # 放量倍数（vol / ma5 >= 此值算放量）
VOLUME_SPIKE_COUNT = 2       # 横盘期间至少出现 N 次放量
VOLUME_SHRINK_RATIO = 0.6    # 缩量阈值（回调日 vol / ma5 <= 此值）

# ===== 买点形态①：放量长阳回踩 =====
LONG_YANG_MIN_PCT = 5.0       # 放量阳线最小涨幅（%）
LONG_YANG_VOL_RATIO = 2.0     # 放量倍数
PULLBACK_MAX_RETRACE = 0.50   # 从长阳高点最多回落 50%

# ===== 买点形态②：破位反转 =====
BREAKDOWN_DAYS = 3            # 跌破下轨后最大持续天数
RECOVERY_VOL_RATIO = 1.3      # 收回时放量倍数

# ===== 扫描器 =====
SCAN_TOP_N = 20               # 默认输出前 N 只
MAX_STOCKS_SCAN = 3000        # 最多扫描股票数（防超时）
