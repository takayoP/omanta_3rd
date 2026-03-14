"""
V1 スリム化: 下位スコアを凍結する ScoreProfile と、月次最適化で探索する PolicyParams。

- ScoreProfile: 固定。core_score_ref / entry_score_ref の計算式を決める。
- PolicyParams: Optuna が探索。entry_share, top_n, sector_cap 等。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class ScoreProfile:
    """下位スコア（core / entry）を決める固定パラメータ。V1では凍結。"""
    version: str  # 例: "v1_ref"
    pool_size: int
    roe_min: float
    liquidity_quantile_cut: float  # 流動性下限 quantile（固定値）
    core_weights: Dict[str, float]   # w_quality, w_value, w_growth, w_record_high, w_size, w_forward_per, w_pbr
    entry_params: Dict[str, float]  # rsi_base, rsi_max, bb_z_base, bb_z_max, bb_weight, rsi_weight


@dataclass(frozen=True)
class PolicyParams:
    """月次最適化で探索する上位ポリシー。V1では Optuna が触るのはここだけ。"""
    entry_share: float       # 0.0〜0.35, w_core = 1 - entry_share
    top_n: int              # 採用銘柄数 (8,10,12,14,16)
    sector_cap: int         # セクター上限 (2〜4)
    liquidity_floor_q: float  # 流動性下限 quantile (0.30〜0.60)
    rebalance_buffer: int   # 0〜3 rank, 現保有を残しやすく
    lambda_turnover: float  # 0.00〜0.20, 目的関数で回転率ペナルティ


# -----------------------------------------------------------------------------
# v1_ref: 過去の良好 trial 群の中央値 or 現行 default。式の母体は longterm_run.build_features。
# -----------------------------------------------------------------------------

def get_default_policy_params() -> PolicyParams:
    """run_strategy で最適化しないときのデフォルトポリシー。"""
    return PolicyParams(
        entry_share=0.2,
        top_n=12,
        sector_cap=4,
        liquidity_floor_q=0.15,
        rebalance_buffer=0,
        lambda_turnover=0.0,
    )


def get_v1_ref_score_profile() -> ScoreProfile:
    """
    V1 で使用する固定 ScoreProfile。
    現行 longterm_run の PARAMS デフォルトをベースにした値。
    将来: holdout/WFA 通過 trial 群の中央値に差し替え可能。
    """
    return ScoreProfile(
        version="v1_ref",
        pool_size=80,
        roe_min=0.0621,
        liquidity_quantile_cut=0.1509,
        core_weights={
            "w_quality": 0.1519,
            "w_value": 0.3908,
            "w_growth": 0.1120,
            "w_record_high": 0.0364,
            "w_size": 0.2448,
            "w_forward_per": 0.4977,
            "w_pbr": 0.5023,
        },
        entry_params={
            "rsi_base": 51.18,
            "rsi_max": 73.58,
            "bb_z_base": -0.57,
            "bb_z_max": 2.16,
            "bb_weight": 0.5527,
            "rsi_weight": 0.4473,
        },
    )


def policy_params_to_dict(p: PolicyParams) -> Dict[str, Any]:
    """PolicyParams を JSON 保存用の辞書に。"""
    return {
        "entry_share": p.entry_share,
        "top_n": p.top_n,
        "sector_cap": p.sector_cap,
        "liquidity_floor_q": p.liquidity_floor_q,
        "rebalance_buffer": p.rebalance_buffer,
        "lambda_turnover": p.lambda_turnover,
    }


def dict_to_policy_params(d: Dict[str, Any]) -> PolicyParams:
    """辞書から PolicyParams を復元。"""
    return PolicyParams(
        entry_share=float(d["entry_share"]),
        top_n=int(d["top_n"]),
        sector_cap=int(d["sector_cap"]),
        liquidity_floor_q=float(d["liquidity_floor_q"]),
        rebalance_buffer=int(d.get("rebalance_buffer", 0)),
        lambda_turnover=float(d.get("lambda_turnover", 0.0)),
    )
