# -*- coding: utf-8 -*-
"""数据适配层 —— 从 trade_backend 的表读数据，适配成 core/ 模块期望的格式

trade_backend 的表结构（SQLAlchemy ORM）：
  stock_daily:      (ts_code, trade_date:Date, open, high, low, close, pre_close, change, pct_chg, vol, amount:千元)
  stock_daily_basic: (ts_code, trade_date:Date, turnover_rate, pe, pb, ps, total_mv, circ_mv, ...)

market_congestion core/ 期望的格式：
  daily:       (date:TEXT='YYYYMMDD', ts_code, open, high, low, close, pre_close, pct_chg, vol, amount_yuan:元)
  daily_basic: (date:TEXT='YYYYMMDD', ts_code, circ_mv)

本模块提供与原 core/database.py 完全相同的函数签名，
core/ 下的计算模块 import database as db 后无感切换数据源。

注意：
  - 行情读取从 stock_daily/stock_daily_basic 读（trade 的调度器已在同步）
  - 期权/拥挤度历史等 market_congestion 独有的表，在本库中自行创建
  - write 操作（pipeline 写入行情）不再需要——数据同步由 trade 的 scheduler 统一完成
"""

import json
import logging
import threading

import pandas as pd
from sqlalchemy import text

from app.db.base import SessionLocal, engine

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 表主键注册（market_congestion 自有的表需要 upsert）
# ---------------------------------------------------------------------------
TABLE_KEYS: dict[str, list[str]] = {
    'mc_summary': ['key'],
    'mc_stock_kline': ['ts_code', 'date'],
    'mc_option_contracts': ['option_code'],
    'mc_option_quotes': ['option_code'],
    'mc_option_etf_quotes': ['code'],
    'mc_option_signals': ['date', 'code', 'signal_key'],
    'mc_congestion_history': ['date', 'board', 'top_percent', 'denominator'],
    'mc_margin': ['date'],
}

_init_done = False
_init_lock = threading.Lock()

# ---------------------------------------------------------------------------
# 建表（market_congestion 独有的表，加 mc_ 前缀避免冲突）
# ---------------------------------------------------------------------------

_DDL = """
-- 视图：把 trade 的表映射为 core/ 代码期望的旧表名
CREATE OR REPLACE VIEW daily AS
SELECT
    TO_CHAR(trade_date, 'YYYYMMDD') as date,
    ts_code,
    open::double precision,
    high::double precision,
    low::double precision,
    close::double precision,
    pre_close::double precision,
    pct_chg::double precision,
    vol::double precision,
    (amount * 1000)::double precision as amount_yuan
FROM stock_daily;

CREATE OR REPLACE VIEW daily_basic AS
SELECT
    TO_CHAR(trade_date, 'YYYYMMDD') as date,
    ts_code,
    circ_mv::double precision
FROM stock_daily_basic;

-- cached_dates 视图：从 stock_daily 的交易日去重
CREATE OR REPLACE VIEW cached_dates AS
SELECT
    TO_CHAR(trade_date, 'YYYYMMDD') as date,
    1 as has_daily,
    CASE WHEN EXISTS (
        SELECT 1 FROM stock_daily_basic b WHERE b.trade_date = d.trade_date LIMIT 1
    ) THEN 1 ELSE 0 END as has_basic,
    1 as has_adj
FROM (SELECT DISTINCT trade_date FROM stock_daily) d;

-- adj_factor：core 代码中有引用但 trade 不存储复权因子，创建空表兼容
CREATE TABLE IF NOT EXISTS adj_factor (
    date TEXT NOT NULL, ts_code TEXT NOT NULL, adj_factor DOUBLE PRECISION DEFAULT 1.0,
    PRIMARY KEY (date, ts_code)
);

-- summary 视图指向 mc_summary（兼容 core 直接引用 summary 表的代码）
CREATE OR REPLACE VIEW summary AS SELECT * FROM mc_summary;

-- margin 视图指向 mc_margin
CREATE OR REPLACE VIEW margin AS SELECT * FROM mc_margin;

CREATE TABLE IF NOT EXISTS mc_summary (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS mc_margin (date TEXT PRIMARY KEY, rzye DOUBLE PRECISION);

CREATE TABLE IF NOT EXISTS mc_stock_kline (
    ts_code TEXT NOT NULL, date TEXT NOT NULL,
    open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION,
    close DOUBLE PRECISION, vol DOUBLE PRECISION, pct_chg DOUBLE PRECISION,
    PRIMARY KEY (ts_code, date)
);

CREATE TABLE IF NOT EXISTS mc_option_contracts (
    option_code TEXT PRIMARY KEY, underlying_code TEXT NOT NULL,
    option_name TEXT, exchange TEXT, option_type TEXT,
    strike DOUBLE PRECISION, expire_date TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mc_opt_contracts_underlying ON mc_option_contracts(underlying_code);

CREATE TABLE IF NOT EXISTS mc_option_quotes (
    option_code TEXT PRIMARY KEY, underlying_code TEXT, option_type TEXT,
    strike DOUBLE PRECISION,
    price DOUBLE PRECISION, change_pct DOUBLE PRECISION,
    volume BIGINT, open_interest BIGINT,
    iv DOUBLE PRECISION, delta DOUBLE PRECISION, gamma DOUBLE PRECISION,
    theta DOUBLE PRECISION, vega DOUBLE PRECISION,
    buy_price DOUBLE PRECISION, buy_vol BIGINT,
    sell_price DOUBLE PRECISION, sell_vol BIGINT,
    expire_date TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mc_opt_quotes_underlying ON mc_option_quotes(underlying_code);

CREATE TABLE IF NOT EXISTS mc_option_etf_quotes (
    code TEXT PRIMARY KEY, name TEXT,
    price DOUBLE PRECISION, prev_close DOUBLE PRECISION,
    open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION, volume BIGINT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mc_option_signals (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL, code TEXT, name TEXT, signal_key TEXT,
    label TEXT, detail TEXT, level TEXT, ts TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, code, signal_key)
);
CREATE INDEX IF NOT EXISTS idx_mc_opt_signals_date ON mc_option_signals(date);

CREATE TABLE IF NOT EXISTS mc_congestion_history (
    date TEXT NOT NULL,
    board TEXT NOT NULL,
    top_percent INTEGER NOT NULL,
    denominator TEXT NOT NULL,
    congestion DOUBLE PRECISION,
    total_amount_yi DOUBLE PRECISION,
    top_amount_yi DOUBLE PRECISION,
    total_stocks INTEGER,
    top_n INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, board, top_percent, denominator)
);
CREATE INDEX IF NOT EXISTS idx_mc_cong_hist_date ON mc_congestion_history(date);
"""


def _init_tables():
    """创建 market_congestion 独有的表和兼容视图"""
    global _init_done
    if _init_done:
        return
    with _init_lock:
        if _init_done:
            return
        with engine.connect() as conn:
            # 逐条执行 DDL（视图的 CREATE OR REPLACE 不能和其他语句混在一个 execute 里）
            for stmt in _DDL.split(';'):
                stmt = stmt.strip()
                if stmt and not stmt.startswith('--'):
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        log.warning("DDL 执行跳过: %s... -> %s", stmt[:60], e)
            conn.commit()
        _init_done = True
        log.info("market_congestion 独有表已创建/验证")


def _ensure_init():
    if not _init_done:
        _init_tables()


# ---------------------------------------------------------------------------
# 通用读写助手
# ---------------------------------------------------------------------------

def read_sql(sql: str, params=None) -> pd.DataFrame:
    """执行查询返回 DataFrame"""
    _ensure_init()
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        rows = result.fetchall()
    return pd.DataFrame(rows, columns=cols) if cols else pd.DataFrame()


def _execute(sql: str, params=None):
    """执行写入语句"""
    _ensure_init()
    with engine.connect() as conn:
        conn.execute(text(sql), params or {})
        conn.commit()


def upsert_rows(table: str, columns: list[str], rows: list[tuple],
                conflict_cols: list[str] | None = None, batch_size: int = 2000) -> int:
    """批量 upsert（仅用于 mc_ 前缀表）"""
    if not rows:
        return 0
    _ensure_init()
    keys = conflict_cols or TABLE_KEYS.get(table)
    col_list = ', '.join(columns)
    placeholders = ', '.join([f':{c}' for c in columns])

    if keys:
        updates = [f'{c} = EXCLUDED.{c}' for c in columns if c not in keys]
        tail = (f' ON CONFLICT ({", ".join(keys)}) DO UPDATE SET ' + ', '.join(updates)
                if updates else f' ON CONFLICT ({", ".join(keys)}) DO NOTHING')
    else:
        tail = ''
    sql = f'INSERT INTO {table} ({col_list}) VALUES ({placeholders}){tail}'

    total = 0
    with engine.connect() as conn:
        for i in range(0, len(rows), batch_size):
            chunk = rows[i:i + batch_size]
            params_list = [dict(zip(columns, r)) for r in chunk]
            for p in params_list:
                conn.execute(text(sql), p)
            total += len(chunk)
        conn.commit()
    return total


def upsert_df(table: str, df: pd.DataFrame, columns: list[str] | None = None,
              conflict_cols: list[str] | None = None) -> int:
    if df is None or df.empty:
        return 0
    cols = [c for c in (columns or list(df.columns)) if c in df.columns]
    sub = df[cols].astype(object).where(pd.notna(df[cols]), None)
    rows = [tuple(r) for r in sub.itertuples(index=False, name=None)]
    return upsert_rows(table, cols, rows, conflict_cols)


# ---------------------------------------------------------------------------
# 日K读取 —— 从 trade 的 stock_daily 表读，适配格式
# ---------------------------------------------------------------------------

def list_daily_dates() -> list[str]:
    """获取 stock_daily 表中有数据的所有交易日（YYYYMMDD 格式，升序）"""
    _ensure_init()
    df = read_sql(
        "SELECT DISTINCT TO_CHAR(trade_date, 'YYYYMMDD') as date "
        "FROM stock_daily ORDER BY date"
    )
    return df['date'].tolist() if not df.empty else []


def has_daily(date: str) -> bool:
    """trade 的 stock_daily 是否有该日期数据"""
    # date 格式: YYYYMMDD
    df = read_sql(
        "SELECT 1 FROM stock_daily WHERE trade_date = TO_DATE(:d, 'YYYYMMDD') LIMIT 1",
        {"d": date}
    )
    return not df.empty


def read_daily(date: str) -> pd.DataFrame | None:
    """读取某日全市场行情，返回与 core 期望一致的 DataFrame

    core 期望列: ts_code, open, high, low, close, pre_close, pct_chg, vol, amount_yuan
    trade 的 stock_daily: ts_code, open, high, low, close, pre_close, pct_chg, vol, amount(千元)
    """
    df = read_sql(
        "SELECT ts_code, open, high, low, close, pre_close, pct_chg, vol, "
        "amount * 1000 as amount_yuan "
        "FROM stock_daily WHERE trade_date = TO_DATE(:d, 'YYYYMMDD')",
        {"d": date}
    )
    if df.empty:
        return None
    # 转为 float（trade 用 Numeric/Decimal）
    for col in ['open', 'high', 'low', 'close', 'pre_close', 'pct_chg', 'vol', 'amount_yuan']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def write_daily(date: str, df: pd.DataFrame):
    """行情写入 —— 不再需要，数据由 trade 的 scheduler 同步"""
    log.debug("write_daily called but skipped (trade scheduler handles sync)")


# ---------------------------------------------------------------------------
# daily_basic 读取 —— 从 trade 的 stock_daily_basic 表读
# ---------------------------------------------------------------------------

def has_basic(date: str) -> bool:
    df = read_sql(
        "SELECT 1 FROM stock_daily_basic WHERE trade_date = TO_DATE(:d, 'YYYYMMDD') LIMIT 1",
        {"d": date}
    )
    return not df.empty


def read_basic(date: str) -> pd.DataFrame | None:
    """core 期望: ts_code, circ_mv（万元）
    trade 的 stock_daily_basic: ts_code, trade_date, circ_mv（万元）"""
    df = read_sql(
        "SELECT ts_code, circ_mv FROM stock_daily_basic "
        "WHERE trade_date = TO_DATE(:d, 'YYYYMMDD')",
        {"d": date}
    )
    if df.empty:
        return None
    df['circ_mv'] = pd.to_numeric(df['circ_mv'], errors='coerce')
    return df


def write_basic(date: str, df: pd.DataFrame):
    """不再需要，数据由 trade 的 scheduler 同步"""
    log.debug("write_basic called but skipped")


# ---------------------------------------------------------------------------
# adj_factor —— trade 没有单独的 adj_factor 表，暂时返回空
# 如果后续需要，可以从 tushare 直接拉取
# ---------------------------------------------------------------------------

def has_adj(date: str) -> bool:
    return True  # 假装有，避免触发下载


def read_adj(date: str) -> pd.DataFrame | None:
    """返回空 —— 后续如果有复权需求再接入"""
    return None


def write_adj(date: str, df: pd.DataFrame):
    pass


# ---------------------------------------------------------------------------
# 融资余额 —— 使用 mc_margin 表
# ---------------------------------------------------------------------------

def read_margin_all() -> dict:
    _ensure_init()
    df = read_sql("SELECT date, rzye FROM mc_margin ORDER BY date")
    if df.empty:
        return {}
    return dict(zip(df['date'], df['rzye']))


def write_margin_batch(data_dict: dict):
    if not data_dict:
        return
    rows = [(k, v) for k, v in data_dict.items()]
    upsert_rows('mc_margin', ['date', 'rzye'], rows)


# ---------------------------------------------------------------------------
# 汇总数据（JSON KV）—— 使用 mc_summary 表
# ---------------------------------------------------------------------------

def read_summary(key: str):
    _ensure_init()
    df = read_sql("SELECT value FROM mc_summary WHERE key = :k", {"k": key})
    if df.empty:
        return None
    try:
        return json.loads(df.iloc[0]['value'])
    except Exception:
        return None


def write_summary(key: str, value):
    _ensure_init()
    v = json.dumps(value, ensure_ascii=False)
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO mc_summary (key, value) VALUES (:k, :v) "
            "ON CONFLICT (key) DO UPDATE SET value = :v"
        ), {"k": key, "v": v})
        conn.commit()


# ---------------------------------------------------------------------------
# 个股/ETF 日K 缓存 —— mc_stock_kline
# ---------------------------------------------------------------------------

def read_stock_kline(ts_code: str, start_date: str) -> list[dict]:
    _ensure_init()
    df = read_sql(
        "SELECT date, open, high, low, close, vol, pct_chg FROM mc_stock_kline "
        "WHERE ts_code = :code AND date >= :start ORDER BY date",
        {"code": ts_code, "start": start_date}
    )
    return df.to_dict('records') if not df.empty else []


def write_stock_kline(ts_code: str, data: list[dict]) -> int:
    if not data:
        return 0
    cols = ['ts_code', 'date', 'open', 'high', 'low', 'close', 'vol', 'pct_chg']
    rows = [
        (ts_code, d['date'], d.get('open'), d.get('high'), d.get('low'),
         d.get('close'), d.get('vol'), d.get('pct_chg'))
        for d in data
    ]
    return upsert_rows('mc_stock_kline', cols, rows)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def get_db_info() -> dict:
    _ensure_init()
    df = read_sql("SELECT COUNT(DISTINCT TO_CHAR(trade_date, 'YYYYMMDD')) as cnt FROM stock_daily")
    days = int(df.iloc[0]['cnt']) if not df.empty else 0
    try:
        df2 = read_sql("SELECT pg_database_size(current_database()) as sz")
        size_kb = int(df2.iloc[0]['sz']) // 1024 if not df2.empty else 0
    except Exception:
        size_kb = 0
    return {'days': days, 'size_kb': size_kb}


def get_cache_info() -> dict:
    return get_db_info()


def backend_info() -> dict:
    return {'backend': 'postgres (trade_backend shared)', 'location': 'yingplus'}


# ---------------------------------------------------------------------------
# 期权合约 —— mc_option_contracts
# ---------------------------------------------------------------------------

def read_option_contracts(underlying_code: str = None) -> list[dict]:
    _ensure_init()
    if underlying_code:
        df = read_sql(
            "SELECT * FROM mc_option_contracts WHERE underlying_code = :code",
            {"code": underlying_code}
        )
    else:
        df = read_sql("SELECT * FROM mc_option_contracts")
    return df.to_dict('records') if not df.empty else []


def write_option_contracts(contracts: list[dict]):
    if not contracts:
        return
    cols = ['option_code', 'underlying_code', 'option_name', 'exchange',
            'option_type', 'strike', 'expire_date']
    rows = [
        (c['option_code'], c['underlying_code'], c.get('option_name', ''),
         c.get('exchange', ''), c['option_type'], c['strike'], c['expire_date'])
        for c in contracts
    ]
    upsert_rows('mc_option_contracts', cols, rows)


def count_option_contracts_by_underlying() -> list[tuple]:
    _ensure_init()
    df = read_sql(
        "SELECT underlying_code, COUNT(*) as cnt FROM mc_option_contracts "
        "GROUP BY underlying_code ORDER BY underlying_code"
    )
    return [(r['underlying_code'], r['cnt']) for _, r in df.iterrows()] if not df.empty else []


# ---------------------------------------------------------------------------
# 期权行情 —— mc_option_quotes
# ---------------------------------------------------------------------------

def read_option_quotes(underlying_code: str) -> list[dict]:
    _ensure_init()
    df = read_sql(
        "SELECT * FROM mc_option_quotes WHERE underlying_code = :code",
        {"code": underlying_code}
    )
    return df.to_dict('records') if not df.empty else []


def write_option_quotes(quotes: list[dict]):
    if not quotes:
        return
    cols = ['option_code', 'underlying_code', 'option_type', 'strike', 'price',
            'change_pct', 'volume', 'open_interest', 'iv', 'delta', 'gamma',
            'theta', 'vega', 'buy_price', 'buy_vol', 'sell_price', 'sell_vol',
            'expire_date']
    rows = [tuple(q.get(c) for c in cols) for q in quotes]
    upsert_rows('mc_option_quotes', cols, rows)


# ---------------------------------------------------------------------------
# 期权标的 ETF —— mc_option_etf_quotes
# ---------------------------------------------------------------------------

def read_option_etf_quote(code: str) -> dict | None:
    _ensure_init()
    df = read_sql("SELECT * FROM mc_option_etf_quotes WHERE code = :code", {"code": code})
    return df.to_dict('records')[0] if not df.empty else None


def write_option_etf_quotes(quotes: list[dict]):
    if not quotes:
        return
    cols = ['code', 'name', 'price', 'prev_close', 'open', 'high', 'low', 'volume']
    rows = [tuple(q.get(c) for c in cols) for q in quotes]
    upsert_rows('mc_option_etf_quotes', cols, rows)


# ---------------------------------------------------------------------------
# 期权信号 —— mc_option_signals
# ---------------------------------------------------------------------------

def read_option_signals(code: str = None, limit: int = 50) -> list[dict]:
    _ensure_init()
    cols = ['date', 'code', 'name', 'signal_key', 'label', 'detail', 'level', 'ts']
    sel = ', '.join(cols)
    if code:
        df = read_sql(
            f"SELECT {sel} FROM mc_option_signals WHERE code = :code "
            f"ORDER BY created_at DESC LIMIT :lim",
            {"code": code, "lim": limit}
        )
    else:
        df = read_sql(
            f"SELECT {sel} FROM mc_option_signals ORDER BY created_at DESC LIMIT :lim",
            {"lim": limit}
        )
    return df.to_dict('records') if not df.empty else []


def write_option_signals(signals: list[dict]):
    if not signals:
        return
    cols = ['date', 'code', 'name', 'signal_key', 'label', 'detail', 'level', 'ts']
    rows = [
        (s['date'], s.get('code', ''), s.get('name', ''), s.get('signal_key', ''),
         s.get('label', ''), s.get('detail', ''), s.get('level', 'info'), s.get('ts', ''))
        for s in signals
    ]
    upsert_rows('mc_option_signals', cols, rows, conflict_cols=['date', 'code', 'signal_key'])


# ---------------------------------------------------------------------------
# 拥挤度历史 —— mc_congestion_history
# ---------------------------------------------------------------------------

_HIST_COLS = ['date', 'board', 'top_percent', 'denominator', 'congestion',
              'total_amount_yi', 'top_amount_yi', 'total_stocks', 'top_n']


def read_congestion_history(start_date: str = None, end_date: str = None) -> list[dict]:
    _ensure_init()
    where_parts = []
    params = {}
    if start_date:
        where_parts.append('date >= :start')
        params['start'] = start_date
    if end_date:
        where_parts.append('date <= :end')
        params['end'] = end_date
    clause = (' WHERE ' + ' AND '.join(where_parts)) if where_parts else ''
    sel = ', '.join(_HIST_COLS)
    df = read_sql(f'SELECT {sel} FROM mc_congestion_history{clause} ORDER BY date DESC', params)
    return df.to_dict('records') if not df.empty else []


def write_congestion_history(records: list[dict]) -> int:
    if not records:
        return 0
    rows = []
    for r in records:
        if not r or not r.get('date'):
            continue
        rows.append((
            r['date'], r.get('board', ''), int(r.get('top_percent') or 5),
            r.get('denominator') or 'board', r.get('congestion'),
            r.get('total_amount_yi'), r.get('top_amount_yi'),
            r.get('total_stocks'), r.get('top_n'),
        ))
    return upsert_rows('mc_congestion_history', _HIST_COLS, rows)


def clear_congestion_history() -> None:
    _execute("TRUNCATE TABLE mc_congestion_history")


def option_contracts_fresh(max_age_hours: int = 6) -> bool:
    _ensure_init()
    df = read_sql(
        "SELECT updated_at FROM mc_option_contracts ORDER BY updated_at DESC LIMIT 1"
    )
    if df.empty:
        return False
    import datetime
    value = df.iloc[0]['updated_at']
    try:
        updated = value if isinstance(value, datetime.datetime) else \
            datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if updated.tzinfo is not None:
            updated = updated.replace(tzinfo=None)
        return (datetime.datetime.utcnow() - updated).total_seconds() < max_age_hours * 3600
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 兼容层（core 代码中还有些地方用 get_conn().execute() 的旧写法）
# ---------------------------------------------------------------------------

class _CompatResult:
    """兼容 core 里 conn.execute(sql, params).fetchall() 的用法"""
    def __init__(self, rows):
        self._rows = rows
        self._pos = 0

    def fetchall(self):
        return self._rows

    def fetchone(self):
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row


class _CompatConnection:
    """兼容 core 里 db.get_conn() 的用法"""

    def execute(self, sql: str, params=None):
        _ensure_init()
        # 把 ? 占位符转成 :p0, :p1, ... 具名参数
        if params and '?' in sql:
            parts = sql.split('?')
            new_sql = parts[0]
            named_params = {}
            for i, p in enumerate(params):
                new_sql += f':_p{i}' + parts[i + 1]
                named_params[f'_p{i}'] = p
            sql = new_sql
            params = named_params
        elif params and isinstance(params, (list, tuple)):
            # 位置参数转具名
            named = {}
            parts = sql.split('%s')
            new_sql = parts[0]
            for i, p in enumerate(params):
                new_sql += f':_p{i}' + parts[i + 1]
                named[f'_p{i}'] = p
            sql = new_sql
            params = named

        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            if result.returns_rows:
                rows = [tuple(r) for r in result.fetchall()]
            else:
                rows = []
            conn.commit()
        return _CompatResult(rows)

    def executemany(self, sql, seq_of_params):
        _ensure_init()
        with engine.connect() as conn:
            for params in seq_of_params:
                if '?' in sql:
                    parts = sql.split('?')
                    new_sql = parts[0]
                    named = {}
                    for i, p in enumerate(params):
                        new_sql += f':_p{i}' + parts[i + 1]
                        named[f'_p{i}'] = p
                    conn.execute(text(new_sql), named)
                else:
                    conn.execute(text(sql), dict(enumerate(params)))
            conn.commit()

    def executescript(self, script):
        _ensure_init()
        with engine.connect() as conn:
            for stmt in script.split(';'):
                stmt = stmt.strip()
                if stmt and not stmt.startswith('--'):
                    conn.execute(text(stmt))
            conn.commit()

    def commit(self):
        pass

    def rollback(self):
        pass


_conn_proxy = _CompatConnection()


def get_conn():
    """兼容 core 中 db.get_conn() 的调用"""
    _ensure_init()
    return _conn_proxy


# ---------------------------------------------------------------------------
# 初始化入口
# ---------------------------------------------------------------------------

def init_db() -> dict:
    _init_tables()
    return backend_info()
