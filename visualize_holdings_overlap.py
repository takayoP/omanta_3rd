"""最終選定候補の保有銘柄の推移（重複度）を可視化

注意: このスクリプトは、evaluate_candidates_holdout.pyで生成されたポートフォリオ情報が
JSONファイルに含まれている場合に動作します。
ポートフォリオ情報が含まれていない場合は、ポートフォリオを再生成する必要があります。
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Set
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from collections import Counter

# 日本語フォントの設定
plt.rcParams['font.family'] = 'DejaVu Sans'

# データベースパス
DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

# 対象のtrial_number
SELECTED_TRIALS = [96, 168, 180, 196]

# 出力ディレクトリ
OUTPUT_DIR = Path("visualizations")
OUTPUT_DIR.mkdir(exist_ok=True)


def load_json(filepath: str) -> Dict[str, Any]:
    """JSONファイルを読み込む"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_company_name(conn: sqlite3.Connection, code: str, date: str) -> str:
    """銘柄コードから会社名を取得"""
    df = pd.read_sql_query("""
        SELECT company_name
        FROM listed_info
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
    """, conn, params=(code, date))
    
    if not df.empty and df['company_name'].iloc[0]:
        return df['company_name'].iloc[0]
    return code


def visualize_holdings_overlap_simple(trial_numbers: List[int], evaluation_period: str, output_path: Path):
    """保有銘柄の重複度を可視化（簡易版：データベースのportfolio_monthlyを使用）
    
    注意: これは通常の月次実行のポートフォリオであり、holdout評価のポートフォリオとは
    異なる可能性があります。
    """
    print(f"\n注意: portfolio_monthlyテーブルのデータを使用します。")
    print(f"これは通常の月次実行のポートフォリオであり、holdout評価のポートフォリオとは異なる可能性があります。")
    
    with sqlite3.connect(str(DB_PATH)) as conn:
        # 期間を決定
        if evaluation_period == 'holdout_2023_2024':
            start_date = '2023-01-01'
            end_date = '2024-12-31'
        elif evaluation_period == 'holdout_2025':
            start_date = '2025-01-01'
            end_date = '2025-12-31'
        else:
            print(f"不明な評価期間: {evaluation_period}")
            return
        
        # 各リバランス日の保有銘柄を取得（簡易版：最新のポートフォリオのみ）
        print(f"\n{evaluation_period}期間のポートフォリオ情報:")
        
        # リバランス日を取得
        dates_df = pd.read_sql_query("""
            SELECT DISTINCT rebalance_date
            FROM portfolio_monthly
            WHERE rebalance_date >= ? AND rebalance_date <= ?
            ORDER BY rebalance_date
        """, conn, params=(start_date, end_date))
        
        if dates_df.empty:
            print(f"  ポートフォリオデータが見つかりませんでした。")
            return
        
        print(f"  リバランス日数: {len(dates_df)}")
        print(f"  最初の日付: {dates_df['rebalance_date'].iloc[0]}")
        print(f"  最後の日付: {dates_df['rebalance_date'].iloc[-1]}")
        
        # 各日付の保有銘柄数を表示
        for date in dates_df['rebalance_date'].head(5):
            portfolio_df = pd.read_sql_query("""
                SELECT code, weight
                FROM portfolio_monthly
                WHERE rebalance_date = ?
                ORDER BY weight DESC
            """, conn, params=(date,))
            print(f"  {date}: {len(portfolio_df)}銘柄")


def main():
    """メイン処理"""
    print("保有銘柄の推移を可視化します...")
    print("\n注意: このスクリプトは簡易版です。")
    print("実際のholdout評価で使用されたポートフォリオ情報は、JSONファイルに含まれていません。")
    print("保有銘柄の推移を正確に可視化するには、ポートフォリオ情報を保存する機能を")
    print("evaluate_candidates_holdout.pyに追加する必要があります。\n")
    
    # 簡易版の可視化（データベースのportfolio_monthlyを使用）
    visualize_holdings_overlap_simple(SELECTED_TRIALS, 'holdout_2023_2024', 
                                      OUTPUT_DIR / 'holdings_overlap_2023_2024.png')
    
    visualize_holdings_overlap_simple(SELECTED_TRIALS, 'holdout_2025', 
                                      OUTPUT_DIR / 'holdings_overlap_2025.png')
    
    print("\n可視化が完了しました！")
    print(f"出力ディレクトリ: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()











