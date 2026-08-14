# -*- coding: utf-8 -*-
"""
期权分析模块 — 数据统一存储在本项目 market.db

数据流：
  1. 优先从本地 market.db 读取（毫秒级）
  2. 数据过期时从网络刷新（akshare 合约 + 新浪行情）并写入 market.db
  3. 首次启动可从 ETFWatcher 数据库一次性导入（迁移）
"""
from __future__ import annotations

import re
import time
import threading
from datetime import date
from typing import Literal

from . import database as db

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

# ETF 期权标的清单（code -> 名称），共 11 个：沪市 6 + 深市 5
ETF_OPTION_UNDERLYINGS: dict[str, str] = {
    "510050": "上证50ETF",
    "510300": "沪深300ETF",
    "510500": "中证500ETF",
    "588000": "科创50ETF",
    "588080": "科创50ETF易方达",
    "588050": "科创50ETF工银",
    "159919": "沪深300ETF",
    "159915": "创业板ETF",
    "159922": "中证500ETF",
    "159901": "深证100ETF",
    "159952": "创业板ETF易方达",
}

# 标的前缀映射（code -> sh/sz）
UNDERLYING_PREFIX: dict[str, str] = {
    "510050": "sh", "510300": "sh", "510500": "sh",
    "588000": "sh", "588080": "sh", "588050": "sh",
    "159919": "sz", "159915": "sz", "159922": "sz",
    "159901": "sz", "159952": "sz",
}

_refresh_lock = threading.Lock()


# ==================== 辅助函数 ====================

def _extract_code(text: str) -> str:
    m = re.search(r"\((\d{6})\)", text)
    return m.group(1) if m else ""


def _fmt_expire(e: str) -> str:
    """'20260722' -> '2026-07-22'"""
    if len(e) == 8 and e.isdigit():
        return f"{e[:4]}-{e[4:6]}-{e[6:]}"
    return e


def _days_left(e: str, today: date) -> int | None:
    try:
        if len(e) == 8 and e.isdigit():
            d = date(int(e[:4]), int(e[4:6]), int(e[6:]))
        else:
            d = date.fromisoformat(e)
        return (d - today).days
    except ValueError:
        return None


def _nn(v) -> int | None:
    if v is None:
        return None
    try:
        return max(0, int(v))
    except (ValueError, TypeError):
        return None


# ==================== 网络数据获取 ====================

def _fetch_contracts_from_network() -> list[dict]:
    """从 akshare 获取全部 ETF 期权合约"""
    all_contracts: list[dict] = []

    # 沪市
    try:
        import akshare as ak
        df = ak.option_current_day_sse()
        for _, row in df.iterrows():
            underlying = _extract_code(str(row.get("标的券名称及代码", "")))
            if not underlying or underlying not in ETF_OPTION_UNDERLYINGS:
                continue
            option_code = str(row.get("合约编码", "")).strip()
            option_name = str(row.get("合约简称", "")).strip()
            option_type: Literal["call", "put"] = "call" if "购" in option_name or str(row.get("类型", "")) == "认购" else "put"
            strike = float(row.get("行权价", 0))
            expire = str(row.get("到期日", "")).strip().replace("-", "")
            underlying_code = f"{UNDERLYING_PREFIX[underlying]}{underlying}"
            all_contracts.append({
                "option_code": option_code,
                "underlying_code": underlying_code,
                "option_name": option_name,
                "exchange": "SSE",
                "option_type": option_type,
                "strike": strike,
                "expire_date": expire,
            })
    except Exception:
        pass

    # 深市
    try:
        import akshare as ak
        df = ak.option_current_day_szse()
        for _, row in df.iterrows():
            # 深市列名可能是 "标的证券代码" 或 "标的证券简称(代码)"
            underlying = ""
            raw_underlying_field = str(row.get("标的证券代码", "")).strip()
            raw_name_code_field = str(row.get("标的证券简称(代码)", "")).strip()

            if raw_underlying_field and raw_underlying_field in ETF_OPTION_UNDERLYINGS:
                underlying = raw_underlying_field
            elif raw_name_code_field:
                # 格式如 "深证100ETF易方达(159901)"，提取括号里的代码
                extracted = _extract_code(raw_name_code_field)
                if extracted and extracted in ETF_OPTION_UNDERLYINGS:
                    underlying = extracted
                else:
                    # 尝试名称模糊匹配
                    for code in ETF_OPTION_UNDERLYINGS:
                        if code.startswith("159") and ETF_OPTION_UNDERLYINGS[code] in raw_name_code_field:
                            underlying = code
                            break

            if not underlying or underlying not in ETF_OPTION_UNDERLYINGS:
                continue

            option_code = str(row.get("合约编码", "")).strip()
            option_name = str(row.get("合约简称", "")).strip()
            option_type: Literal["call", "put"] = "call" if "购" in option_name else "put"
            strike = float(row.get("行权价格", row.get("行权价", 0)))
            expire = str(row.get("到期日", "")).strip().replace("-", "")
            underlying_code = f"sz{underlying}"
            all_contracts.append({
                "option_code": option_code,
                "underlying_code": underlying_code,
                "option_name": option_name,
                "exchange": "SZSE",
                "option_type": option_type,
                "strike": strike,
                "expire_date": expire,
            })
    except Exception:
        pass

    return all_contracts


def _fetch_quotes_from_sina(option_codes: list[str]) -> dict[str, dict]:
    """从新浪获取期权行情 + Greeks"""
    if not _HAS_HTTPX or not option_codes:
        return {}

    all_results: dict[str, dict] = {}
    client = httpx.Client(timeout=10.0, headers={"Referer": "https://finance.sina.com.cn"})

    try:
        # 分批请求行情（每批50个）
        batch_size = 50
        for i in range(0, len(option_codes), batch_size):
            batch = option_codes[i:i + batch_size]
            symbols = ",".join(f"CON_OP_{c}" for c in batch)
            try:
                resp = client.get(f"http://hq.sinajs.cn/list={symbols}")
                resp.raise_for_status()
                text = resp.content.decode("gbk", errors="replace")
                for line in text.split(";"):
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    prefix, value = line.split("=", 1)
                    code = prefix.replace("var hq_str_CON_OP_", "").strip()
                    value = value.strip().strip('"')
                    if not value:
                        continue
                    parts = value.split(",")
                    if len(parts) < 38:
                        continue
                    try:
                        def _f(idx, default=0.0):
                            try: return float(parts[idx]) if parts[idx] else default
                            except: return default
                        def _i(idx, default=0):
                            try: return int(float(parts[idx])) if parts[idx] else default
                            except: return default

                        all_results[code] = {
                            "buy_vol": _i(0), "buy_price": _f(1),
                            "price": _f(2), "sell_price": _f(3), "sell_vol": _i(4),
                            "open_interest": _i(5), "volume": _i(41),
                            "strike": _f(7), "change_pct": _f(6) or _f(38),
                            "expire_date": parts[46] if len(parts) > 46 else "",
                        }
                    except Exception:
                        continue
            except Exception:
                pass
            if i + batch_size < len(option_codes):
                time.sleep(0.15)

        # 补充 Greeks
        for i in range(0, len(option_codes), batch_size):
            batch = [c for c in option_codes[i:i + batch_size] if c in all_results]
            if not batch:
                continue
            symbols = ",".join(f"CON_SO_{c}" for c in batch)
            try:
                resp = client.get(f"http://hq.sinajs.cn/list={symbols}")
                resp.raise_for_status()
                text = resp.content.decode("gbk", errors="replace")
                for line in text.split(";"):
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    prefix, value = line.split("=", 1)
                    code = prefix.replace("var hq_str_CON_SO_", "").strip()
                    value = value.strip().strip('"')
                    if not value or code not in all_results:
                        continue
                    parts = value.split(",")
                    if len(parts) >= 11:
                        try:
                            all_results[code].update({
                                "delta": float(parts[6]) if parts[6] else 0.0,
                                "gamma": float(parts[7]) if parts[7] else 0.0,
                                "theta": float(parts[8]) if parts[8] else 0.0,
                                "vega": float(parts[9]) if parts[9] else 0.0,
                                "iv": float(parts[10]) if parts[10] else 0.0,
                            })
                        except (ValueError, IndexError):
                            pass
            except Exception:
                pass
            if i + batch_size < len(option_codes):
                time.sleep(0.15)
    finally:
        client.close()

    return all_results


def _fetch_etf_price_from_sina(underlying_code: str) -> dict | None:
    """从新浪获取标的 ETF 最新价格"""
    if not _HAS_HTTPX:
        return None
    try:
        client = httpx.Client(timeout=8.0, headers={"Referer": "https://finance.sina.com.cn"})
        resp = client.get(f"http://hq.sinajs.cn/list={underlying_code}")
        text = resp.content.decode("gbk", errors="replace")
        client.close()
        if "=" not in text:
            return None
        value = text.split("=", 1)[1].strip().strip('"')
        if not value:
            return None
        parts = value.split(",")
        if len(parts) > 6:
            return {
                "code": underlying_code,
                "name": parts[0] if parts[0] else underlying_code,
                "price": float(parts[3]) if parts[3] else None,
                "prev_close": float(parts[2]) if parts[2] else None,
                "open": float(parts[1]) if parts[1] else None,
                "high": float(parts[4]) if parts[4] else None,
                "low": float(parts[5]) if parts[5] else None,
                "volume": int(float(parts[8])) if len(parts) > 8 and parts[8] else None,
            }
    except Exception:
        pass
    return None


# ==================== 数据刷新（网络 → 写入本地 market.db） ====================

def refresh_option_data(underlying_code: str = None):
    """从网络获取最新期权数据并写入本地数据库.

    - underlying_code 为 None 时刷新合约列表 + 全部标的行情
    - 指定标的时只刷新该标的行情
    """
    with _refresh_lock:
        # 刷新合约（如果过期或合约数量不足）
        existing_count = sum(r[1] for r in db.count_option_contracts_by_underlying())
        if not db.option_contracts_fresh(max_age_hours=6) or existing_count < 800:
            contracts = _fetch_contracts_from_network()
            if contracts:
                db.write_option_contracts(contracts)

        # 确定要刷新行情的标的列表
        if underlying_code:
            codes_to_refresh = [underlying_code]
        else:
            # 从数据库获取有合约的标的
            rows = db.count_option_contracts_by_underlying()
            codes_to_refresh = [r[0] for r in rows]

        # 刷新行情
        for u_code in codes_to_refresh:
            contracts = db.read_option_contracts(u_code)
            if not contracts:
                continue
            option_codes = [c["option_code"] for c in contracts]
            quotes_raw = _fetch_quotes_from_sina(option_codes)

            # 组装为 write 格式
            quotes_to_write = []
            for c in contracts:
                q = quotes_raw.get(c["option_code"])
                if q:
                    quotes_to_write.append({
                        "option_code": c["option_code"],
                        "underlying_code": u_code,
                        "option_type": c["option_type"],
                        "strike": c["strike"],
                        "price": q.get("price"),
                        "change_pct": q.get("change_pct"),
                        "volume": q.get("volume"),
                        "open_interest": q.get("open_interest"),
                        "iv": q.get("iv"),
                        "delta": q.get("delta"),
                        "gamma": q.get("gamma"),
                        "theta": q.get("theta"),
                        "vega": q.get("vega"),
                        "buy_price": q.get("buy_price"),
                        "buy_vol": q.get("buy_vol"),
                        "sell_price": q.get("sell_price"),
                        "sell_vol": q.get("sell_vol"),
                        "expire_date": c["expire_date"],
                    })
            if quotes_to_write:
                db.write_option_quotes(quotes_to_write)

            # 刷新标的 ETF 行情
            etf_data = _fetch_etf_price_from_sina(u_code)
            if etf_data and etf_data.get("price") and etf_data["price"] > 0:
                db.write_option_etf_quotes([etf_data])


# ==================== 从 ETFWatcher 数据库迁移 ====================

def migrate_from_watcher_db() -> bool:
    """从 ETFWatcher 数据库一次性导入期权数据到 market.db.

    返回是否成功导入了数据。
    合约/行情：仅在本地为空时导入（避免覆盖更新的数据）
    信号：始终增量导入（按日去重）
    """
    import sqlite3
    from pathlib import Path

    # 查找 ETFWatcher 数据库
    db_path = Path.home() / "Library/Application Support/ETFWatcher/etf_watcher.db"
    if not db_path.exists():
        try:
            import platformdirs
            db_path = Path(platformdirs.user_data_dir("ETFWatcher")) / "etf_watcher.db"
        except ImportError:
            pass
    if not db_path.exists():
        return False

    imported_any = False

    try:
        conn = sqlite3.connect(str(db_path), timeout=3)
        conn.row_factory = sqlite3.Row

        # 导入合约（仅在本地为空时）
        existing = db.count_option_contracts_by_underlying()
        if not existing:
            rows = conn.execute("SELECT * FROM option_contracts").fetchall()
            contracts = []
            for r in rows:
                contracts.append({
                    "option_code": r["option_code"],
                    "underlying_code": r["underlying_code"],
                    "option_name": r["option_name"],
                    "exchange": r["exchange"],
                    "option_type": r["option_type"],
                    "strike": r["strike"],
                    "expire_date": r["expire_date"],
                })
            if contracts:
                db.write_option_contracts(contracts)
                imported_any = True

            # 导入行情
            quote_rows = conn.execute("SELECT * FROM option_quotes").fetchall()
            quotes = []
            for r in quote_rows:
                quotes.append({
                    "option_code": r["option_code"],
                    "underlying_code": r["underlying_code"],
                    "option_type": r["option_type"],
                    "strike": r["strike"],
                    "price": r["price"],
                    "change_pct": r["change_pct"],
                    "volume": r["volume"],
                    "open_interest": r["open_interest"],
                    "iv": r["iv"],
                    "delta": r["delta"],
                    "gamma": r.get("gamma"),
                    "theta": r.get("theta"),
                    "vega": r.get("vega"),
                    "buy_price": r["buy_price"],
                    "buy_vol": r["buy_vol"],
                    "sell_price": r["sell_price"],
                    "sell_vol": r["sell_vol"],
                    "expire_date": r["expire_date"],
                })
            if quotes:
                db.write_option_quotes(quotes)
                imported_any = True

            # 导入 ETF 行情快照
            etf_codes = list({q["underlying_code"] for q in quotes if q.get("underlying_code")})
            etf_quotes = []
            for code in etf_codes:
                row = conn.execute(
                    "SELECT code, name, price, prev_close FROM quote_snapshots WHERE code = ? ORDER BY ts DESC LIMIT 1",
                    (code,)
                ).fetchone()
                if row and row["price"] and row["price"] > 0:
                    etf_quotes.append({
                        "code": row["code"],
                        "name": row["name"],
                        "price": row["price"],
                        "prev_close": row["prev_close"],
                    })
            if etf_quotes:
                db.write_option_etf_quotes(etf_quotes)

        # 导入信号（始终增量导入，INSERT OR IGNORE 去重）
        signal_rows = conn.execute(
            "SELECT date, code, name, signal_key, label, detail, level, ts FROM signals ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
        signals = []
        for r in signal_rows:
            signals.append({
                "date": r["date"],
                "code": r["code"],
                "name": r["name"],
                "signal_key": r["signal_key"],
                "label": r["label"],
                "detail": r["detail"],
                "level": r["level"],
                "ts": r["ts"],
            })
        if signals:
            db.write_option_signals(signals)
            imported_any = True

        conn.close()
        return imported_any

    except Exception:
        return False


# ==================== 分析数据组装（纯函数） ====================

def build_analysis_data(
    contracts: list[dict],
    quotes: dict[str, dict],
    underlying_code: str,
    underlying_name: str,
    underlying_price: float | None = None,
    today: date | None = None,
) -> dict:
    """组装期权分析页 payload（纯函数）."""
    if today is None:
        today = date.today()

    spot = underlying_price

    # 按到期日分组
    expiries = sorted({c["expire_date"] for c in contracts if c.get("expire_date")})
    rows_by_expiry: dict[str, list[dict]] = {}

    for expiry in expiries:
        strikes: dict[float, dict] = {}
        for c in contracts:
            if c.get("expire_date") != expiry:
                continue
            slot = strikes.setdefault(c["strike"], {"strike": c["strike"], "calls": [], "puts": []})
            side = _side_payload(c, quotes.get(c["option_code"]))
            slot["calls" if c["option_type"] == "call" else "puts"].append(side)

        rows = []
        for strike in sorted(strikes):
            slot = strikes[strike]
            slot["calls"].sort(key=lambda s: s["code"])
            slot["puts"].sort(key=lambda s: s["code"])
            rows.append(slot)
        rows_by_expiry[expiry] = rows

    underlying = {
        "code": underlying_code,
        "name": underlying_name,
        "price": spot,
        "change": None,
        "change_pct": None,
    }

    default_expiry = expiries[0] if expiries else None

    # ===== 波动率微笑 =====
    smile_by_expiry: dict[str, dict] = {}
    for expiry, rows in rows_by_expiry.items():
        strikes_list: list[float] = []
        call_ivs: list[float | None] = []
        put_ivs: list[float | None] = []
        for row in rows:
            strikes_list.append(row["strike"])
            c_iv = None
            for c in row.get("calls", []):
                if c.get("iv") is not None:
                    c_iv = round(c["iv"] * 100, 2)
                    break
            p_iv = None
            for p in row.get("puts", []):
                if p.get("iv") is not None:
                    p_iv = round(p["iv"] * 100, 2)
                    break
            call_ivs.append(c_iv)
            put_ivs.append(p_iv)
        smile_by_expiry[expiry] = {"strikes": strikes_list, "callIV": call_ivs, "putIV": put_ivs}

    # ===== 持仓量分布 =====
    oi_by_expiry: dict[str, dict] = {}
    for expiry, rows in rows_by_expiry.items():
        strikes_oi = []
        call_ois = []
        put_ois = []
        for row in rows:
            strikes_oi.append(row["strike"])
            call_ois.append(sum((c.get("oi") or 0) for c in row.get("calls", [])))
            put_ois.append(sum((p.get("oi") or 0) for p in row.get("puts", [])))

        call_wall = strikes_oi[call_ois.index(max(call_ois))] if call_ois and max(call_ois) > 0 else None
        put_wall = strikes_oi[put_ois.index(max(put_ois))] if put_ois and max(put_ois) > 0 else None

        max_pain = None
        if strikes_oi and (sum(call_ois) + sum(put_ois)) > 0:
            min_pain_value = float("inf")
            for settle in strikes_oi:
                pain = sum((settle - k) * call_ois[i] for i, k in enumerate(strikes_oi) if settle > k) + \
                       sum((k - settle) * put_ois[i] for i, k in enumerate(strikes_oi) if settle < k)
                if pain < min_pain_value:
                    min_pain_value = pain
                    max_pain = settle

        oi_by_expiry[expiry] = {"strikes": strikes_oi, "callOI": call_ois, "putOI": put_ois,
                                "callWall": call_wall, "putWall": put_wall, "maxPain": max_pain}

    # ===== 卖方指标 =====
    seller_by_expiry: dict[str, dict] = {}
    for expiry, rows in rows_by_expiry.items():
        if not rows or not spot:
            continue
        atm_idx = min(range(len(rows)), key=lambda i: abs(rows[i]["strike"] - spot))
        atm_strike = rows[atm_idx]["strike"]

        atm_call_iv = next((c["iv"] for c in rows[atm_idx].get("calls", []) if c.get("iv")), None)
        atm_put_iv = next((p["iv"] for p in rows[atm_idx].get("puts", []) if p.get("iv")), None)
        if atm_call_iv and atm_put_iv:
            atm_iv = (atm_call_iv + atm_put_iv) / 2
        else:
            atm_iv = atm_call_iv or atm_put_iv

        # 25Δ 偏斜
        iv_25d_put, iv_25d_call = None, None
        best_put_dist, best_call_dist = 1.0, 1.0
        for row in rows:
            for c in row.get("calls", []):
                d, iv = c.get("delta"), c.get("iv")
                if d is not None and iv is not None and abs(d - 0.25) < best_call_dist:
                    best_call_dist = abs(d - 0.25)
                    iv_25d_call = iv
            for p in row.get("puts", []):
                d, iv = p.get("delta"), p.get("iv")
                if d is not None and iv is not None and abs(d - (-0.25)) < best_put_dist:
                    best_put_dist = abs(d - (-0.25))
                    iv_25d_put = iv
        skew_25d = round((iv_25d_put - iv_25d_call) * 100, 2) if iv_25d_put and iv_25d_call else None

        total_call_oi = sum((c.get("oi") or 0) for row in rows for c in row.get("calls", []))
        total_put_oi = sum((p.get("oi") or 0) for row in rows for p in row.get("puts", []))
        pcr_oi = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else None

        atm_call_price = next((c["price"] for c in rows[atm_idx].get("calls", []) if c.get("price") and c["price"] > 0), None)
        atm_put_price = next((p["price"] for p in rows[atm_idx].get("puts", []) if p.get("price") and p["price"] > 0), None)
        expected_move = round((atm_call_price + atm_put_price) / spot * 100, 2) if atm_call_price and atm_put_price and spot > 0 else None

        seller_by_expiry[expiry] = {
            "atmStrike": atm_strike,
            "atmIV": round(atm_iv * 100, 2) if atm_iv else None,
            "skew25D": skew_25d,
            "pcrOI": pcr_oi,
            "expectedMove": expected_move,
            "totalCallOI": total_call_oi,
            "totalPutOI": total_put_oi,
            "days": _days_left(expiry, today),
        }

    # ===== IV 期限结构 =====
    iv_term = [{"expiry": _fmt_expire(e), "days": seller_by_expiry[e]["days"], "atmIV": seller_by_expiry[e]["atmIV"]}
               for e in expiries if e in seller_by_expiry and seller_by_expiry[e].get("atmIV")]

    # ===== 波动率曲面 =====
    all_strikes = sorted({k for sm in smile_by_expiry.values() for k in sm["strikes"]})
    surface_rows = []
    for expiry in expiries:
        sm = smile_by_expiry.get(expiry)
        if not sm:
            continue
        iv_map = {}
        for i, k in enumerate(sm["strikes"]):
            c_iv, p_iv = sm["callIV"][i], sm["putIV"][i]
            if c_iv is not None and p_iv is not None:
                iv_map[k] = round((c_iv + p_iv) / 2, 2)
            elif c_iv is not None:
                iv_map[k] = c_iv
            elif p_iv is not None:
                iv_map[k] = p_iv
        surface_rows.append({"expiry": _fmt_expire(expiry), "days": _days_left(expiry, today),
                             "ivs": [iv_map.get(k) for k in all_strikes]})

    vol_surface = {"strikes": all_strikes, "rows": surface_rows} if all_strikes and surface_rows else None

    return {
        "title": "期权分析",
        "meta": f"{underlying_name} · {len(contracts)} 合约",
        "underlying": underlying,
        "expiries": [{"date": e, "label": _fmt_expire(e), "days": _days_left(e, today)} for e in expiries],
        "defaultExpiry": default_expiry,
        "rows": rows_by_expiry,
        "smile": smile_by_expiry,
        "oi": oi_by_expiry,
        "seller": seller_by_expiry,
        "ivTerm": iv_term,
        "surface": vol_surface,
    }


def _side_payload(c: dict, q: dict | None) -> dict:
    """单个合约展示数据."""
    side: dict = {"code": c["option_code"], "name": c.get("option_name", "")}
    if q:
        price = q.get("price") or None
        side.update({
            "price": price,
            "change_pct": q.get("change_pct") if price is not None else None,
            "sell_price": q.get("sell_price") or None,
            "sell_vol": _nn(q.get("sell_vol")),
            "buy_price": q.get("buy_price") or None,
            "buy_vol": _nn(q.get("buy_vol")),
            "volume": _nn(q.get("volume")),
            "oi": _nn(q.get("open_interest")),
            "iv": q.get("iv") or None,
            "delta": q.get("delta") or None,
        })
    return side


# ==================== 对外主接口 ====================

def get_option_underlyings() -> list[dict]:
    """返回可用的期权标的列表.

    优先本地数据库，没数据时尝试迁移或网络刷新。
    """
    # 尝试从本地读取
    rows = db.count_option_contracts_by_underlying()
    if not rows:
        # 尝试从 ETFWatcher 迁移
        migrate_from_watcher_db()
        rows = db.count_option_contracts_by_underlying()
    if not rows:
        # 网络刷新
        refresh_option_data()
        rows = db.count_option_contracts_by_underlying()

    result = []
    for r in rows:
        code = r[0]
        pure_code = code.replace("sh", "").replace("sz", "")
        name = ETF_OPTION_UNDERLYINGS.get(pure_code, code)
        result.append({"code": code, "name": name, "contract_count": r[1]})
    return result


def get_option_analysis(underlying_code: str) -> dict:
    """获取指定标的的期权分析数据.

    从本地 market.db 读取，数据过期时自动刷新。
    """
    pure_code = underlying_code.replace("sh", "").replace("sz", "")
    name = ETF_OPTION_UNDERLYINGS.get(pure_code, underlying_code)

    # 读取本地合约
    contracts = db.read_option_contracts(underlying_code)
    if not contracts:
        # 没有合约数据，尝试刷新
        refresh_option_data(underlying_code)
        contracts = db.read_option_contracts(underlying_code)
    if not contracts:
        return build_analysis_data([], {}, underlying_code, name)

    # 读取本地行情
    quote_rows = db.read_option_quotes(underlying_code)
    quotes: dict[str, dict] = {q["option_code"]: q for q in quote_rows}

    # 如果行情为空或过期，刷新
    if not quotes:
        refresh_option_data(underlying_code)
        quote_rows = db.read_option_quotes(underlying_code)
        quotes = {q["option_code"]: q for q in quote_rows}

    # 读取标的价格
    etf_quote = db.read_option_etf_quote(underlying_code)
    underlying_price = etf_quote["price"] if etf_quote and etf_quote.get("price") else None

    result = build_analysis_data(contracts, quotes, underlying_code, name, underlying_price)

    # 补充标的详细行情（涨跌幅、今开、最高、最低等）
    if etf_quote and etf_quote.get("price"):
        prev = etf_quote.get("prev_close") or 0
        price = etf_quote["price"]
        change = round(price - prev, 4) if prev else None
        change_pct = round((price - prev) / prev * 100, 2) if prev and prev > 0 else None
        result["underlying"].update({
            "price": price,
            "prev_close": prev,
            "open": etf_quote.get("open"),
            "high": etf_quote.get("high"),
            "low": etf_quote.get("low"),
            "volume": etf_quote.get("volume"),
            "change": change,
            "change_pct": change_pct,
        })

    return result


def get_option_signals(underlying_code: str = None, limit: int = 50) -> list[dict]:
    """获取期权信号记录（从本地 market.db）.

    首次调用时自动从 ETFWatcher 导入信号。
    """
    signals = db.read_option_signals(underlying_code, limit)
    if not signals:
        # 尝试导入
        migrate_from_watcher_db()
        signals = db.read_option_signals(underlying_code, limit)
    return signals


def get_etf_kline(underlying_code: str, days: int = 120) -> dict:
    """获取标的 ETF 的日K线数据.

    使用 tushare pro_bar(asset='FD') 获取 ETF 日K。
    返回 {'ts_code': str, 'data': [{date, open, high, low, close, vol, pct_chg}...]}
    """
    pure_code = underlying_code.replace("sh", "").replace("sz", "")
    suffix = "SH" if underlying_code.startswith("sh") else "SZ"
    ts_code = f"{pure_code}.{suffix}"

    # 先查缓存（stock_kline 表由 database.py 统一建）
    import datetime
    start = (datetime.datetime.now() - datetime.timedelta(days=int(days * 2))).strftime('%Y%m%d')
    cached = db.read_stock_kline(ts_code, start)
    if cached and len(cached) >= days * 0.7:
        return {"ts_code": ts_code, "data": cached[-days:]}

    # 从 tushare 获取
    try:
        import tushare as ts
        from .config import TUSHARE_TOKEN
        ts.set_token(TUSHARE_TOKEN)
        import time as _time
        _time.sleep(0.3)
        df = ts.pro_bar(ts_code=ts_code, start_date=start, adj='qfq', asset='FD')
        if df is None or df.empty:
            return {"ts_code": ts_code, "data": []}

        import pandas as pd
        for col in ('open', 'high', 'low', 'close', 'vol', 'pct_chg'):
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['close']).sort_values('trade_date').reset_index(drop=True)

        data = []
        for _, row in df.iterrows():
            data.append({
                "date": row["trade_date"],
                "open": round(float(row["open"]), 3),
                "high": round(float(row["high"]), 3),
                "low": round(float(row["low"]), 3),
                "close": round(float(row["close"]), 3),
                "vol": round(float(row["vol"]), 0),
                "pct_chg": round(float(row["pct_chg"]), 2) if pd.notna(row["pct_chg"]) else 0,
            })

        # 写入缓存
        if data:
            db.write_stock_kline(ts_code, data)

        return {"ts_code": ts_code, "data": data[-days:]}
    except Exception as e:
        return {"ts_code": ts_code, "data": [], "error": str(e)}


def get_etf_minute_kline(underlying_code: str, period: int = 1) -> dict:
    """获取标的 ETF 当日分钟K线（从 ETFWatcher 数据库的 minute_bars 表读取）.

    period: 1=1分钟, 5=5分钟, 15=15分钟, 30=30分钟, 60=60分钟
    返回 {'code': str, 'period': int, 'data': [{ts, open, high, low, close, volume}...]}

    数据来源：ETFWatcher 后台轮询 TDX/东财 实时写入的分钟K线。
    """
    import sqlite3
    from pathlib import Path
    import datetime

    # 查找 ETFWatcher 数据库
    db_path = Path.home() / "Library/Application Support/ETFWatcher/etf_watcher.db"
    if not db_path.exists():
        try:
            import platformdirs
            db_path = Path(platformdirs.user_data_dir("ETFWatcher")) / "etf_watcher.db"
        except ImportError:
            pass
    if not db_path.exists():
        return {"code": underlying_code, "period": period, "data": []}

    try:
        conn = sqlite3.connect(str(db_path), timeout=3)
        # 获取当日的分钟 K 线
        today = datetime.datetime.now().strftime('%Y%m%d')
        ts_start = today + "000000"

        rows = conn.execute(
            "SELECT ts, open, high, low, close, volume FROM minute_bars WHERE code = ? AND ts >= ? ORDER BY ts",
            (underlying_code, ts_start)
        ).fetchall()
        conn.close()

        if not rows:
            return {"code": underlying_code, "period": period, "data": []}

        # 1 分钟直接返回
        bars = [{"ts": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]} for r in rows]

        if period == 1:
            # 格式化时间为 HH:MM
            for b in bars:
                ts = b["ts"]
                if len(ts) >= 12:
                    b["time"] = f"{ts[8:10]}:{ts[10:12]}"
                else:
                    b["time"] = ts
            return {"code": underlying_code, "period": period, "data": bars}

        # 聚合为 N 分钟
        aggregated = _aggregate_bars(bars, period)
        return {"code": underlying_code, "period": period, "data": aggregated}

    except Exception:
        return {"code": underlying_code, "period": period, "data": []}


def _aggregate_bars(bars: list[dict], period: int) -> list[dict]:
    """将 1 分钟 K 线聚合为 N 分钟（按 A 股交易时段对齐）."""
    if not bars:
        return []

    # A股时段分钟序号映射（9:30=0, 11:30=119, 13:01=120, 15:00=239）
    def _bar_minute_index(ts: str) -> int:
        """将 ts（YYYYMMDDHHMMSS）转为当日交易分钟序号（0-239）"""
        hh, mm = int(ts[8:10]), int(ts[10:12])
        if hh < 12:  # 上午 9:30-11:30
            return (hh - 9) * 60 + mm - 30
        else:  # 下午 13:00-15:00
            return 120 + (hh - 13) * 60 + mm

    result = []
    bucket_bars = []
    current_bucket = -1

    for bar in bars:
        ts = bar["ts"]
        if len(ts) < 12:
            continue
        idx = _bar_minute_index(ts)
        bucket = idx // period

        if bucket != current_bucket:
            if bucket_bars:
                result.append(_merge_bucket(bucket_bars))
            bucket_bars = [bar]
            current_bucket = bucket
        else:
            bucket_bars.append(bar)

    if bucket_bars:
        result.append(_merge_bucket(bucket_bars))

    return result


def _merge_bucket(bars: list[dict]) -> dict:
    """合并一组 bar 为一根 K 线."""
    first = bars[0]
    ts = first["ts"]
    time_label = f"{ts[8:10]}:{ts[10:12]}" if len(ts) >= 12 else ts
    return {
        "ts": first["ts"],
        "time": time_label,
        "open": first["open"],
        "high": max(b["high"] for b in bars),
        "low": min(b["low"] for b in bars),
        "close": bars[-1]["close"],
        "volume": sum(b["volume"] for b in bars),
    }
