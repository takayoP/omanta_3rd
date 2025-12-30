"""
performance_metrics.jsonをCSV形式に変換

各ポートフォリオごとの指標をCSVファイルに出力します。
"""

from __future__ import annotations

import json
import pandas as pd
import numpy as np
from typing import Dict, Any, List


def convert_metrics_to_csv(json_file: str, output_file: str):
    """
    performance_metrics.jsonをCSV形式に変換
    
    Args:
        json_file: 入力JSONファイルのパス
        output_file: 出力CSVファイルのパス
    """
    print(f"JSONファイルを読み込み中: {json_file}")
    
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 各ポートフォリオごとの指標を抽出
    portfolio_metrics = data.get("portfolio_metrics", [])
    
    if not portfolio_metrics:
        print("❌ ポートフォリオ指標が見つかりません")
        return
    
    print(f"ポートフォリオ数: {len(portfolio_metrics)}")
    
    # CSV用のデータを準備
    csv_rows = []
    
    for pm in portfolio_metrics:
        # NaNやNoneを適切に処理
        def safe_value(val):
            if val is None:
                return None
            if isinstance(val, str) and val.lower() == "nan":
                return None
            if isinstance(val, float) and (pd.isna(val) or np.isnan(val)):
                return None
            if val == float('inf'):
                return None  # 無限大もNoneとして扱う
            return val
        
        row = {
            "rebalance_date": pm.get("rebalance_date"),
            "num_stocks": pm.get("num_stocks"),
            "mean_return": safe_value(pm.get("mean_return")),
            "median_return": safe_value(pm.get("median_return")),
            "std_return": safe_value(pm.get("std_return")),
            "min_return": safe_value(pm.get("min_return")),
            "max_return": safe_value(pm.get("max_return")),
            "profit_factor": safe_value(pm.get("profit_factor")),
            "sharpe_ratio": safe_value(pm.get("sharpe_ratio")),
            "sortino_ratio": safe_value(pm.get("sortino_ratio")),
            "win_rate": safe_value(pm.get("win_rate")),
            "avg_win": safe_value(pm.get("avg_win")),
            "avg_loss": safe_value(pm.get("avg_loss")),
            "win_loss_ratio": safe_value(pm.get("win_loss_ratio")),
            "max_consecutive_wins": pm.get("max_consecutive_wins"),
            "max_consecutive_losses": pm.get("max_consecutive_losses"),
            "total_gains": safe_value(pm.get("total_gains")),
            "total_losses": safe_value(pm.get("total_losses")),
            "volatility": safe_value(pm.get("volatility")),
        }
        csv_rows.append(row)
    
    # DataFrameに変換
    df = pd.DataFrame(csv_rows)
    
    # CSVファイルに保存
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"✅ CSVファイルを保存しました: {output_file}")
    print(f"   行数: {len(df)}")
    print(f"   列数: {len(df.columns)}")
    print()
    print("列名:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i}. {col}")
    
    # サマリー統計も出力
    print()
    print("=" * 80)
    print("【サマリー統計】")
    print("=" * 80)
    print(df.describe())
    
    # 別ファイルとして、集計統計も出力
    summary_file = output_file.replace(".csv", "_summary.csv")
    summary_data = {
        "指標": [
            "平均リターン（ポートフォリオ平均）",
            "中央値リターン（ポートフォリオ平均）",
            "標準偏差（ポートフォリオ平均）",
            "シャープレシオ（ポートフォリオ平均）",
            "ソルティノレシオ（ポートフォリオ平均）",
            "勝率（ポートフォリオ平均）",
            "平均勝ち（ポートフォリオ平均）",
            "平均負け（ポートフォリオ平均）",
            "勝ち/負け比率（ポートフォリオ平均）",
            "プロフィットファクタ（ポートフォリオ平均）",
            "総利益（ポートフォリオ平均）",
            "総損失（ポートフォリオ平均）",
        ],
        "平均": [
            df["mean_return"].mean(),
            df["median_return"].mean(),
            df["std_return"].mean(),
            df["sharpe_ratio"].mean() if df["sharpe_ratio"].notna().any() else None,
            df["sortino_ratio"].mean() if df["sortino_ratio"].notna().any() else None,
            df["win_rate"].mean() if df["win_rate"].notna().any() else None,
            df["avg_win"].mean() if df["avg_win"].notna().any() else None,
            df["avg_loss"].mean() if df["avg_loss"].notna().any() else None,
            df["win_loss_ratio"].mean() if df["win_loss_ratio"].notna().any() else None,
            df["profit_factor"].mean() if df["profit_factor"].notna().any() else None,
            df["total_gains"].mean(),
            df["total_losses"].mean(),
        ],
        "最小": [
            df["mean_return"].min(),
            df["median_return"].min(),
            df["std_return"].min(),
            df["sharpe_ratio"].min() if df["sharpe_ratio"].notna().any() else None,
            df["sortino_ratio"].min() if df["sortino_ratio"].notna().any() else None,
            df["win_rate"].min() if df["win_rate"].notna().any() else None,
            df["avg_win"].min() if df["avg_win"].notna().any() else None,
            df["avg_loss"].min() if df["avg_loss"].notna().any() else None,
            df["win_loss_ratio"].min() if df["win_loss_ratio"].notna().any() else None,
            df["profit_factor"].min() if df["profit_factor"].notna().any() else None,
            df["total_gains"].min(),
            df["total_losses"].min(),
        ],
        "最大": [
            df["mean_return"].max(),
            df["median_return"].max(),
            df["std_return"].max(),
            df["sharpe_ratio"].max() if df["sharpe_ratio"].notna().any() else None,
            df["sortino_ratio"].max() if df["sortino_ratio"].notna().any() else None,
            df["win_rate"].max() if df["win_rate"].notna().any() else None,
            df["avg_win"].max() if df["avg_win"].notna().any() else None,
            df["avg_loss"].max() if df["avg_loss"].notna().any() else None,
            df["win_loss_ratio"].max() if df["win_loss_ratio"].notna().any() else None,
            df["profit_factor"].max() if df["profit_factor"].notna().any() else None,
            df["total_gains"].max(),
            df["total_losses"].max(),
        ],
    }
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(summary_file, index=False, encoding="utf-8-sig")
    print()
    print(f"✅ サマリーCSVファイルを保存しました: {summary_file}")


if __name__ == "__main__":
    import sys
    
    json_file = "performance_metrics.json"
    output_file = "performance_metrics.csv"
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    convert_metrics_to_csv(json_file, output_file)

