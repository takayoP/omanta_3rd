"""BB/RSI（テクニカル指標）"""

from __future__ import annotations

from typing import Optional, List, Any
import sqlite3

import numpy as np
import pandas as pd

from ..infra.db import connect_db


def calculate_bollinger_bands(
    conn: sqlite3.Connection,
    code: str,
    end_date: str,
    period: int = 20,
    num_std: float = 2.0,
) -> Optional[dict]:
    """
    ボリンジャーバンドを計算
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        end_date: 終了日（YYYY-MM-DD）
        period: 期間（デフォルト20日）
        num_std: 標準偏差の倍数（デフォルト2.0）
        
    Returns:
        {"upper": 上限, "middle": 中央（SMA）, "lower": 下限} または None
    """
    sql = """
        SELECT adj_close
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
    """
    rows = conn.execute(sql, (code, end_date, period)).fetchall()
    
    if len(rows) < period:
        return None
    
    prices = [row["adj_close"] for row in reversed(rows) if row["adj_close"] is not None]
    
    if len(prices) < period:
        return None
    
    # 単純移動平均
    sma = sum(prices) / len(prices)
    
    # 標準偏差
    variance = sum((p - sma) ** 2 for p in prices) / len(prices)
    std = variance ** 0.5
    
    return {
        "upper": sma + num_std * std,
        "middle": sma,
        "lower": sma - num_std * std,
    }


def calculate_rsi(
    conn: sqlite3.Connection,
    code: str,
    end_date: str,
    period: int = 14,
) -> Optional[float]:
    """
    RSIを計算
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        end_date: 終了日（YYYY-MM-DD）
        period: 期間（デフォルト14日）
        
    Returns:
        RSI（0-100、None if 計算不可）
    """
    sql = """
        SELECT adj_close
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
    """
    rows = conn.execute(sql, (code, end_date, period + 1)).fetchall()
    
    if len(rows) < period + 1:
        return None
    
    prices = [row["adj_close"] for row in reversed(rows) if row["adj_close"] is not None]
    
    if len(prices) < period + 1:
        return None
    
    # 価格変動を計算
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))
    
    if not gains or not losses:
        return None
    
    avg_gain = sum(gains) / len(gains)
    avg_loss = sum(losses) / len(losses)
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


# ---------------------------------------------------------------------------
# Series-based versions (used by longterm_run / optimize pipelines)
# ---------------------------------------------------------------------------

def rsi_from_series(close: pd.Series, n: int) -> float:
    """pd.Series の終値からRSIを計算"""
    if close is None or close.size < n + 1:
        return np.nan
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.rolling(n).mean().iloc[-1]
    avg_loss = loss.rolling(n).mean().iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return np.nan
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi)


def bb_zscore(close: pd.Series, n: int) -> float:
    """pd.Series の終値からボリンジャーバンドZスコアを計算"""
    if close is None or close.size < n:
        return np.nan
    window = close.iloc[-n:]
    mu = window.mean()
    sd = window.std(ddof=0)
    if pd.isna(mu) or pd.isna(sd) or sd == 0:
        return np.nan
    z = (window.iloc[-1] - mu) / sd
    return float(z)


def _entry_score(close: pd.Series, params: Any) -> float:
    """
    Entry score計算（グローバルPARAMSのパラメータを使用）

    Args:
        close: 終値のSeries
        params: StrategyParams（PARAMS相当のオブジェクト）
    """
    bb_z_values = []
    rsi_values = []

    for n in (20, 60, 200):
        z = bb_zscore(close, n)
        rsi = rsi_from_series(close, n)

        if not pd.isna(z):
            bb_z_values.append(z)
        if not pd.isna(rsi):
            rsi_values.append(rsi)

    if not bb_z_values and not rsi_values:
        return np.nan

    bb_z = np.nanmax(bb_z_values) if bb_z_values else np.nan
    rsi = np.nanmax(rsi_values) if rsi_values else np.nan

    bb_score = np.nan
    rsi_score = np.nan

    if not pd.isna(bb_z):
        bb_z_base = params.bb_z_base
        bb_z_max = params.bb_z_max
        if bb_z_max != bb_z_base:
            bb_score = (bb_z - bb_z_base) / (bb_z_max - bb_z_base)
        else:
            bb_score = 0.0
        bb_score = np.clip(bb_score, 0.0, 1.0)

    if not pd.isna(rsi):
        rsi_base = params.rsi_base
        rsi_max = params.rsi_max
        if rsi_max != rsi_base:
            rsi_score = (rsi - rsi_base) / (rsi_max - rsi_base)
        else:
            rsi_score = 0.0
        rsi_score = np.clip(rsi_score, 0.0, 1.0)

    bb_weight = params.bb_weight
    rsi_weight = params.rsi_weight
    total_weight = bb_weight + rsi_weight

    if total_weight > 0:
        if not pd.isna(bb_score) and not pd.isna(rsi_score):
            return float((bb_weight * bb_score + rsi_weight * rsi_score) / total_weight)
        elif not pd.isna(bb_score):
            return float(bb_score)
        elif not pd.isna(rsi_score):
            return float(rsi_score)

    return np.nan


def _entry_score_with_params(close: pd.Series, params: Any) -> float:
    """
    パラメータ化されたentry_score計算

    Args:
        close: 終値のSeries
        params: EntryScoreParams（dataclass）
    """
    bb_z_values = []
    rsi_values = []

    for n in (20, 60, 200):
        z = bb_zscore(close, n)
        rsi = rsi_from_series(close, n)

        if not pd.isna(z):
            bb_z_values.append(z)
        if not pd.isna(rsi):
            rsi_values.append(rsi)

    if not bb_z_values and not rsi_values:
        return np.nan

    bb_z = np.nanmax(bb_z_values) if bb_z_values else np.nan
    rsi = np.nanmax(rsi_values) if rsi_values else np.nan

    bb_score = np.nan
    rsi_score = np.nan

    if not pd.isna(bb_z):
        bb_z_diff = params.bb_z_max - params.bb_z_base
        if abs(bb_z_diff) >= getattr(params, 'bb_z_min_width', 0.5):
            raw_score = (bb_z - params.bb_z_base) / bb_z_diff
            bb_score = np.clip(raw_score, 0.0, 1.0)
        else:
            bb_score = np.nan

    if not pd.isna(rsi):
        rsi_diff = params.rsi_max - params.rsi_base
        if abs(rsi_diff) >= getattr(params, 'rsi_min_width', 10.0):
            raw_score = (rsi - params.rsi_base) / rsi_diff
            rsi_score = np.clip(raw_score, 0.0, 1.0)
        else:
            rsi_score = np.nan

    total_weight = params.bb_weight + params.rsi_weight
    if total_weight > 0:
        if not pd.isna(bb_score) and not pd.isna(rsi_score):
            return float((params.bb_weight * bb_score + params.rsi_weight * rsi_score) / total_weight)
        elif not pd.isna(bb_score):
            return float(bb_score)
        elif not pd.isna(rsi_score):
            return float(rsi_score)

    return np.nan


def _calculate_entry_score_with_params(
    feat: pd.DataFrame,
    prices_win: pd.DataFrame,
    params: Any,
) -> pd.DataFrame:
    """
    パラメータ化されたentry_scoreをDataFrame全体に計算

    Args:
        feat: 特徴量DataFrame
        prices_win: 価格データ
        params: EntryScoreParams

    Returns:
        entry_scoreが追加されたfeat
    """
    close_map = {
        c: g["adj_close"].reset_index(drop=True)
        for c, g in prices_win.groupby("code")
    }
    feat["entry_score"] = feat["code"].apply(
        lambda c: _entry_score_with_params(close_map.get(c), params)
        if c in close_map
        else np.nan
    )
    return feat
