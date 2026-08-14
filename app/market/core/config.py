# -*- coding: utf-8 -*-
"""全局配置：路径、常量、板块映射"""

import os
import sys


def _get_data_dir():
    """获取数据存储目录。

    - 开发模式：项目根目录/cache
    - 打包后 macOS：~/Library/Application Support/每日复盘/
    - 打包后 Windows：exe 同目录/cache（Windows 用户习惯）
    """
    if not getattr(sys, 'frozen', False):
        # 开发模式
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return base, os.path.join(base, 'cache')

    # 打包模式
    if sys.platform == 'darwin':
        # macOS: 用户 Application Support 目录（更新 app 不丢数据）
        home = os.path.expanduser('~')
        data_dir = os.path.join(home, 'Library', 'Application Support', '每日复盘')
        base = os.path.dirname(sys.executable)
        return base, data_dir
    else:
        # Windows: exe 同目录
        base = os.path.dirname(sys.executable)
        return base, os.path.join(base, 'cache')


BASE_DIR, CACHE_DIR = _get_data_dir()

def _env(key, default=''):
    """读环境变量。

    空字符串视为「没设置」—— docker compose 里 `${VAR:-}` 会注入空值，
    用 os.environ.get(key, default) 会拿到 '' 而不是 default，坑过一次。
    """
    return (os.environ.get(key) or '').strip() or default


# ==================== 数据库 ====================
# 由 app/market/database.py 适配层处理，不再直接用 DATABASE_URL
# 保留此变量仅为兼容性（不会被使用）
DATABASE_URL = _env('DATABASE_URL', '')

DAILY_CACHE_DIR = os.path.join(CACHE_DIR, 'daily')        # 按日原始行情缓存
BASIC_CACHE_DIR = os.path.join(CACHE_DIR, 'daily_basic')  # 按日流通市值缓存（换手率用）
ADJ_CACHE_DIR = os.path.join(CACHE_DIR, 'adj_factor')     # 按日复权因子缓存（价格类指标用）
HISTORY_FILE = os.path.join(CACHE_DIR, 'history.json')

CACHE_KEEP_DAYS = 90          # 缓存自动清理天数
HISTORY_MAX = 600             # 历史记录上限（8组×60天=480，留余量）
REQUEST_INTERVAL = 0.3        # 批量请求间隔（秒）
RETRY_TIMES = 3               # 网络请求重试次数
RETRY_DELAY = 1.0             # 重试间隔（秒）
MARKET_CLOSE_HOUR = 15        # 收盘时间（15:30 前当日 daily 数据不完整，不缓存）
MARKET_CLOSE_MINUTE = 30
BASIC_UPDATE_HOUR = 17        # daily_basic 通常 15:30~17:00 更新完，17 点前当日不缓存
WARM_DAYS = 365               # 启动预热天数（近一年，首次较慢之后秒开）

# ---- 信号参数（文档 8.2 CONFIG 集中管理） ----
WARN_THRESHOLD = 3            # 预警触发数（≥N 项 → 预警）
TURNOVER_PCT_LINE = 0.9       # 换手率分位过热线
CONC_PCT_LINE = 0.9           # 集中度分位过热线
ABOVE60_LINE = 0.5            # 站上MA60占比警戒线
BIAS_PCT_LINE = 0.9           # BIAS60 分位透支线
NHNL_DIV_RATIO = 0.5          # NHNL 不足近60日峰值的比例 → 顶背离

# tushare token：优先从 trade_backend 的 settings 读取
try:
    from app.core.config import settings as _trade_settings
    TUSHARE_TOKEN = _trade_settings.tushare_token or _env(
        'TUSHARE_TOKEN',
        '1960c9d578a6906eed762295ee0d466b00c9c5e088988eb80929e96d',
    )
except Exception:
    TUSHARE_TOKEN = _env(
        'TUSHARE_TOKEN',
        '1960c9d578a6906eed762295ee0d466b00c9c5e088988eb80929e96d',
    )

BOARD_OPTIONS = ['全部A股', '沪深主板', '创业板', '科创板', '北交所']

BOARD_MAP = {
    '全部A股': None,
    '沪深主板': '沪深主板',
    '创业板': '创业板',
    '科创板': '科创板',
    '北交所': '北交所',
}

THRESHOLD_OPTIONS = [3, 5, 10]

BOARD_SHARE_ORDER = ['沪深主板', '创业板', '科创板', '北交所', '其他']

# 分位数窗口
PCTILE_WINDOW = 250       # 分位滚动窗口（约一年交易日）
PCTILE_MIN_PERIODS = 20   # 窗口内最少数据量

# 各类汇总缓存文件
STOCK_INFO_FILE = os.path.join(CACHE_DIR, 'stock_info.pkl')
SHARES_CACHE_FILE = os.path.join(CACHE_DIR, 'board_shares.json')
MARKET_DAILY_FILE = os.path.join(CACHE_DIR, 'market_daily.json')
INDUSTRY_DAILY_FILE = os.path.join(CACHE_DIR, 'industry_daily.pkl')
INDEX_DAILY_FILE = os.path.join(CACHE_DIR, 'index_daily.pkl')    # 指数日线（趋势指标用）
BREADTH_FILE = os.path.join(CACHE_DIR, 'breadth_daily.pkl')      # 市场广度
CONC_DAILY_FILE = os.path.join(CACHE_DIR, 'conc_daily.json')     # 前5%集中度走势

INDEX_TS_CODE = '000985.CSI'   # 中证全指（趋势/确认层指标基准）
MARGIN_CACHE_FILE = os.path.join(CACHE_DIR, 'margin_daily.json')  # 融资余额缓存

for _d in (CACHE_DIR,):
    os.makedirs(_d, exist_ok=True)


def get_board(ts_code):
    """根据股票代码判断板块（北交所：.BJ 后缀，常见前缀 43/83/87/88/92）"""
    code = ts_code.split('.')[0]
    prefix = code[:2] if len(code) >= 2 else code
    if ts_code.endswith('.BJ') or prefix in ('43', '83', '87', '88', '92'):
        return '北交所'
    if prefix == '68':
        return '科创板'
    elif prefix == '30':
        return '创业板'
    elif prefix in ('60', '00'):
        return '沪深主板'
    return '其他'
