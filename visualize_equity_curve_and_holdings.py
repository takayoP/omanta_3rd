"""最終選定候補の資産曲線と保有銘柄の推移を可視化"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
import numpy as np

# 日本語フォントの設定
plt.rcParams['font.family'] = 'DejaVu Sans'

# データベースパス
DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

# 対象のtrial_number
SELECTED_TRIALS = [96, 168, 180, 196]

# 入力ファイル
HOLDOUT_2023_2024_FILE = "holdout_results_studyB_20251231_174014.json"
HOLDOUT_2025_FILE = "holdout_2025_live_10bps.json"

# 出力ディレクトリ
OUTPUT_DIR = Path("visualizations")
OUTPUT_DIR.mkdir(exist_ok=True)


def load_json(filepath: str) -> Dict[str, Any]:
    """JSONファイルを読み込む"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_monthly_returns_from_db(trial_number: int, evaluation_period: str) -> pd.DataFrame:
    """データベースから月次超過リターンを取得"""
    with sqlite3.connect(str(DB_PATH)) as conn:
        df = pd.read_sql_query("""
            SELECT period_date, excess_return
            FROM monthly_rebalance_candidate_monthly_returns
            WHERE trial_number = ? AND evaluation_period = ?
            ORDER BY period_date
        """, conn, params=(trial_number, evaluation_period))
        df['period_date'] = pd.to_datetime(df['period_date'])
        return df


def calculate_equity_curve_from_returns(returns: List[float], initial_value: float = 1.0) -> List[float]:
    """月次リターンから資産曲線を計算"""
    equity = [initial_value]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    return equity


def get_topix_returns(evaluation_period: str) -> Optional[pd.DataFrame]:
    """TOPIXの月次リターンを取得（簡易版：必要に応じて実装）"""
    # 暫定的にNoneを返す（資産曲線は超過リターンから計算するため、TOPIXは必須ではない）
    return None


def plot_equity_curves(data_by_trial: Dict[int, Dict[str, Any]], evaluation_period: str, output_path: Path):
    """資産曲線をプロット"""
    fig, ax = plt.subplots(figsize=(14, 8))
    
    trial_names = {
        196: "#196 (1位: バランス型)",
        96: "#96 (2位: 上振れ型)",
        180: "#180 (3位: 2023-2024強)",
        168: "#168 (4位: 堅実型)"
    }
    
    colors = {
        196: '#1f77b4',  # 青
        96: '#ff7f0e',   # オレンジ
        180: '#2ca02c',  # 緑
        168: '#d62728'   # 赤
    }
    
    # TOPIXの資産曲線（省略：超過リターンから資産曲線を直接計算するため）
    
    # 各候補の資産曲線
    for trial_number in SELECTED_TRIALS:
        if trial_number not in data_by_trial:
            continue
        
        data = data_by_trial[trial_number]
        # monthly_returns（ポートフォリオリターン）を使用
        monthly_returns = data.get('monthly_returns', [])
        monthly_dates = data.get('monthly_dates', [])
        
        if not monthly_returns or not monthly_dates:
            # フォールバック: monthly_excess_returnsを使用（TOPIX超過リターン）
            monthly_returns = data.get('monthly_excess_returns', [])
            if not monthly_returns:
                continue
        
        # 資産曲線を計算
        equity = calculate_equity_curve_from_returns(monthly_returns)
        
        # 日付を処理
        dates_list = monthly_dates if isinstance(monthly_dates, list) else list(monthly_dates)
        dates = pd.to_datetime(dates_list)
        # 最初の日付を追加（equity_curveは1つ多い）
        first_date = dates[0] - pd.Timedelta(days=15)  # 月初に合わせる
        dates_full = pd.to_datetime([first_date] + dates_list)
        
        if len(equity) == len(dates_full):
            label = trial_names.get(trial_number, f"#{trial_number}")
            ax.plot(dates_full, equity, color=colors.get(trial_number, 'gray'), 
                   linewidth=2, label=label, marker='o', markersize=4)
    
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Equity Curve (Normalized to 1.0)', fontsize=12)
    title = 'Asset Curve Comparison'
    if evaluation_period == 'holdout_2023_2024':
        title += ' (2023-2024 Holdout)'
    elif evaluation_period == 'holdout_2025':
        title += ' (2025 Pseudo-Live)'
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    
    # 日付フォーマット
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"資産曲線を保存しました: {output_path}")


def get_portfolio_holdings_from_json(holdout_data: Dict[str, Any], trial_number: int) -> Dict[str, pd.DataFrame]:
    """JSONデータからポートフォリオ保有銘柄を取得（実際にはポートフォリオ情報はJSONに含まれていない可能性があるため、エラーハンドリングを追加）"""
    holdings = {}
    
    # JSONにはポートフォリオ情報が含まれていない可能性があるため、
    # データベースから取得するか、再計算が必要
    # ここでは空の辞書を返す
    return holdings


def visualize_holdings_overlap(data_by_trial: Dict[int, Dict[str, Any]], evaluation_period: str, output_path: Path):
    """保有銘柄の推移を可視化（簡易版：データが利用可能な場合のみ）"""
    # ポートフォリオ情報がJSONに含まれていない場合、この機能はスキップ
    print(f"保有銘柄の推移の可視化は、ポートフォリオ情報が必要なため、別途実装が必要です。")
    print(f"データベースから直接取得するか、evaluate_candidates_holdout.pyを実行してポートフォリオ情報を保存する必要があります。")


def main():
    """メイン処理"""
    print("資産曲線と保有銘柄の推移を可視化します...")
    
    # JSONデータを読み込む
    holdout_2023_2024_data = load_json(HOLDOUT_2023_2024_FILE)
    holdout_2025_data = load_json(HOLDOUT_2025_FILE)
    
    # 各候補のデータを整理
    data_2023_2024 = {}
    data_2025 = {}
    
    for result in holdout_2023_2024_data.get('results', []):
        trial_number = result.get('trial_number')
        if trial_number in SELECTED_TRIALS:
            data_2023_2024[trial_number] = result.get('holdout_metrics', {})
    
    for result in holdout_2025_data.get('results', []):
        trial_number = result.get('trial_number')
        if trial_number in SELECTED_TRIALS:
            data_2025[trial_number] = result.get('holdout_metrics', {})
    
    # 資産曲線をプロット
    if data_2023_2024:
        plot_equity_curves(data_2023_2024, 'holdout_2023_2024', 
                          OUTPUT_DIR / 'equity_curve_2023_2024.png')
    
    if data_2025:
        plot_equity_curves(data_2025, 'holdout_2025', 
                          OUTPUT_DIR / 'equity_curve_2025.png')
    
    print("\n可視化が完了しました！")
    print(f"出力ディレクトリ: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

