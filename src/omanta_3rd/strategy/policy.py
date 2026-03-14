"""
選定ポリシー: score_candidates の結果からポートフォリオを選ぶ純粋関数。
longterm / monthly 共通。rebalance_buffer で前回保有を残しやすくする。
"""

from __future__ import annotations

from typing import Optional, Dict, List
import pandas as pd

from ..config.score_profile import PolicyParams


def select_portfolio(
    scored_df: pd.DataFrame,
    policy_params: PolicyParams,
    rebalance_date: str,
    prev_portfolio: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    スコア付き候補から top_n を選び、セクター上限・流動性フィルタを適用する。
    純粋関数（DB を書かない）。

    Args:
        scored_df: score_candidates の戻り値。total_score, sector33, liquidity_60d 等を持つ想定。
        policy_params: top_n, sector_cap, liquidity_floor_q, rebalance_buffer
        rebalance_date: リバランス日 (YYYY-MM-DD)
        prev_portfolio: 前回ポートフォリオ (code 列を持つ DataFrame)。rebalance_buffer で優先残す。

    Returns:
        rebalance_date, code, weight, total_score, core_score_ref, entry_score_ref, rank 等を含む DataFrame。
    """
    if scored_df.empty:
        return pd.DataFrame()

    f = scored_df.copy()

    # 流動性フィルタ
    q = f["liquidity_60d"].quantile(policy_params.liquidity_floor_q)
    f = f[(f["liquidity_60d"].notna()) & (f["liquidity_60d"] >= q)]

    # ROE は snapshot 側で既に score_profile に含まれるが、ここでは scored_df に roe がある想定
    # 必要なら score_profile.roe_min でフィルタするが、V1 では snapshot 生成側でフィルタ済みを想定し、
    # ここでは liquidity と total_score のみ使用する。roe 列があれば roe_min で切るのは prepare_features 側に寄せる。
    if "roe" in f.columns and hasattr(policy_params, "roe_min"):
        # PolicyParams に roe_min を入れていないので、ここでは省略。必要なら PolicyParams に追加。
        pass

    if f.empty:
        return pd.DataFrame()

    # total_score でソート
    f = f.sort_values("total_score", ascending=False).reset_index(drop=True)

    # プール: 上位を多めに取る（pool_size は ScoreProfile 側のため、ここでは scored_df の行数で十分）
    pool = f.copy()

    # 前回保有を rebalance_buffer だけランクで優遇
    prev_codes: List[str] = []
    if prev_portfolio is not None and not prev_portfolio.empty and "code" in prev_portfolio.columns:
        prev_codes = prev_portfolio["code"].astype(str).tolist()

    selected_rows: List[dict] = []
    sector_counts: Dict[str, int] = {}
    buffer_used = 0

    for rank, (_, r) in enumerate(pool.iterrows(), start=1):
        code = str(r.get("code", ""))
        sec = r.get("sector33") or "UNKNOWN"

        # セクター上限
        if sector_counts.get(sec, 0) >= policy_params.sector_cap:
            continue

        # rebalance_buffer: 前回保有は buffer 内なら優先して採用
        if code in prev_codes and buffer_used < policy_params.rebalance_buffer:
            selected_rows.append({**r.to_dict(), "rank": rank, "action": "hold"})
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
            buffer_used += 1
            if len(selected_rows) >= policy_params.top_n:
                break
            continue

        selected_rows.append({**r.to_dict(), "rank": rank, "action": "new" if code not in prev_codes else "add"})
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        if len(selected_rows) >= policy_params.top_n:
            break

    if not selected_rows:
        return pd.DataFrame()

    sel = pd.DataFrame(selected_rows)
    n = len(sel)
    sel["weight"] = 1.0 / n
    sel["rebalance_date"] = rebalance_date

    # 出力列を整理
    out_cols = ["rebalance_date", "code", "weight", "rank", "total_score", "action"]
    for c in ["core_score_ref", "entry_score_ref", "core_score", "entry_score", "sector33"]:
        if c in sel.columns and c not in out_cols:
            out_cols.append(c)
    out_cols = [c for c in out_cols if c in sel.columns]
    return sel[out_cols].copy()
