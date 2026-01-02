"""テスト結果の詳細パフォーマンス（月次超過リターン等）をデータベースに保存"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# データベースパス
DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

# 入力ファイル
HOLDOUT_2023_2024_FILE = "holdout_results_studyB_20251231_174014.json"
HOLDOUT_2025_FILE = "holdout_2025_live_10bps.json"

# 対象のtrial_number
SELECTED_TRIALS = [96, 168, 180, 196]


def ensure_db_directory(db_path: Path):
    """データベースディレクトリが存在することを確認"""
    db_path.parent.mkdir(parents=True, exist_ok=True)


def create_tables(conn: sqlite3.Connection):
    """テーブルを作成"""
    cursor = conn.cursor()
    
    # 月次超過リターンの時系列データ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_rebalance_candidate_monthly_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_number INTEGER NOT NULL,
            evaluation_period TEXT NOT NULL,
            -- "holdout_2023_2024" または "holdout_2025"
            period_date TEXT NOT NULL,
            -- YYYY-MM-DD（月末日）
            excess_return REAL,
            -- 月次超過リターン（小数、例: 0.05 = 5%）
            created_at TEXT,
            FOREIGN KEY (trial_number) REFERENCES monthly_rebalance_final_selected_candidates(trial_number),
            UNIQUE(trial_number, evaluation_period, period_date)
        )
    """)
    
    # 詳細パフォーマンス指標（追加指標）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_rebalance_candidate_detailed_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_number INTEGER NOT NULL,
            evaluation_period TEXT NOT NULL,
            -- "holdout_2023_2024" または "holdout_2025"
            cost_bps REAL,
            -- 取引コスト（bps、0.0, 10.0, 20.0等）
            -- 基本指標
            cagr REAL,
            mean_return REAL,
            mean_excess_return REAL,
            total_return REAL,
            volatility REAL,
            sharpe_ratio REAL,
            sortino_ratio REAL,
            win_rate REAL,
            profit_factor REAL,
            -- 詳細指標
            num_periods INTEGER,
            num_missing_stocks INTEGER,
            mean_excess_return_monthly REAL,
            mean_excess_return_annual REAL,
            vol_excess_monthly REAL,
            vol_excess_annual REAL,
            max_drawdown_topix REAL,
            turnover_monthly REAL,
            turnover_annual REAL,
            num_missing_stocks_total INTEGER,
            missing_stocks_per_period REAL,
            missing_handling TEXT,
            missing_periods_count INTEGER,
            has_missing_periods INTEGER,
            -- コスト関連
            sharpe_excess_after_cost REAL,
            mean_excess_return_after_cost_monthly REAL,
            mean_excess_return_after_cost_annual REAL,
            vol_excess_after_cost_monthly REAL,
            vol_excess_after_cost_annual REAL,
            annual_cost_bps REAL,
            annual_cost_pct REAL,
            -- メタデータ
            created_at TEXT,
            FOREIGN KEY (trial_number) REFERENCES monthly_rebalance_final_selected_candidates(trial_number),
            UNIQUE(trial_number, evaluation_period, cost_bps)
        )
    """)
    
    # インデックス作成
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_monthly_rebalance_returns_trial_period 
        ON monthly_rebalance_candidate_monthly_returns(trial_number, evaluation_period)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_monthly_rebalance_detailed_metrics_trial_period 
        ON monthly_rebalance_candidate_detailed_metrics(trial_number, evaluation_period)
    """)
    
    conn.commit()


def load_json(filepath: str) -> Dict[str, Any]:
    """JSONファイルを読み込む"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def insert_monthly_returns(
    cursor: sqlite3.Cursor,
    trial_number: int,
    evaluation_period: str,
    monthly_returns: List[float],
    monthly_dates: List[str]
):
    """月次超過リターンの時系列データを挿入"""
    now = datetime.now().isoformat()
    
    for date, excess_return in zip(monthly_dates, monthly_returns):
        cursor.execute("""
            INSERT OR REPLACE INTO monthly_rebalance_candidate_monthly_returns (
                trial_number, evaluation_period, period_date, excess_return, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (trial_number, evaluation_period, date, excess_return, now))


def insert_detailed_metrics(
    cursor: sqlite3.Cursor,
    trial_number: int,
    evaluation_period: str,
    cost_bps: float,
    metrics: Dict[str, Any]
):
    """詳細パフォーマンス指標を挿入"""
    now = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO monthly_rebalance_candidate_detailed_metrics (
            trial_number, evaluation_period, cost_bps,
            cagr, mean_return, mean_excess_return, total_return,
            volatility, sharpe_ratio, sortino_ratio, win_rate, profit_factor,
            num_periods, num_missing_stocks,
            mean_excess_return_monthly, mean_excess_return_annual,
            vol_excess_monthly, vol_excess_annual,
            max_drawdown_topix, turnover_monthly, turnover_annual,
            num_missing_stocks_total, missing_stocks_per_period, missing_handling,
            missing_periods_count, has_missing_periods,
            sharpe_excess_after_cost,
            mean_excess_return_after_cost_monthly, mean_excess_return_after_cost_annual,
            vol_excess_after_cost_monthly, vol_excess_after_cost_annual,
            annual_cost_bps, annual_cost_pct,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trial_number, evaluation_period, cost_bps,
        metrics.get('cagr'),
        metrics.get('mean_return'),
        metrics.get('mean_excess_return'),
        metrics.get('total_return'),
        metrics.get('volatility'),
        metrics.get('sharpe_ratio'),
        metrics.get('sortino_ratio'),
        metrics.get('win_rate'),
        metrics.get('profit_factor'),
        metrics.get('num_periods'),
        metrics.get('num_missing_stocks'),
        metrics.get('mean_excess_return_monthly'),
        metrics.get('mean_excess_return_annual'),
        metrics.get('vol_excess_monthly'),
        metrics.get('vol_excess_annual'),
        metrics.get('max_drawdown_topix'),
        metrics.get('turnover_monthly'),
        metrics.get('turnover_annual'),
        metrics.get('num_missing_stocks_total'),
        metrics.get('missing_stocks_per_period'),
        metrics.get('missing_handling'),
        metrics.get('missing_periods_count'),
        1 if metrics.get('has_missing_periods', False) else 0,
        metrics.get('sharpe_excess_after_cost'),
        metrics.get('mean_excess_return_after_cost_monthly'),
        metrics.get('mean_excess_return_after_cost_annual'),
        metrics.get('vol_excess_after_cost_monthly'),
        metrics.get('vol_excess_after_cost_annual'),
        metrics.get('annual_cost_bps'),
        metrics.get('annual_cost_pct'),
        now
    ))


def process_holdout_2023_2024(cursor: sqlite3.Cursor, holdout_data: Dict[str, Any]):
    """2023-2024 Holdout結果を処理"""
    print("2023-2024 Holdout結果を処理中...")
    
    for result in holdout_data.get('results', []):
        trial_number = result.get('trial_number')
        if trial_number not in SELECTED_TRIALS:
            continue
        
        metrics = result.get('holdout_metrics', {})
        
        # 月次超過リターンの時系列データ
        monthly_returns = metrics.get('monthly_excess_returns', [])
        monthly_dates = metrics.get('monthly_dates', [])
        if monthly_returns and monthly_dates:
            insert_monthly_returns(
                cursor, trial_number, 'holdout_2023_2024',
                monthly_returns, monthly_dates
            )
        
        # 詳細パフォーマンス指標（コスト0bps）
        insert_detailed_metrics(
            cursor, trial_number, 'holdout_2023_2024', 0.0, metrics
        )
        
        print(f"  Trial #{trial_number}: 月次データ{len(monthly_returns)}件、詳細指標を保存")


def process_holdout_2025(cursor: sqlite3.Cursor, holdout_2025_data: Dict[str, Any]):
    """2025疑似ライブ結果を処理"""
    print("2025疑似ライブ結果を処理中...")
    
    cost_bps = holdout_2025_data.get('config', {}).get('cost_bps', 10.0)
    
    for result in holdout_2025_data.get('results', []):
        trial_number = result.get('trial_number')
        if trial_number not in SELECTED_TRIALS:
            continue
        
        metrics = result.get('holdout_metrics', {})
        
        # 月次超過リターンの時系列データ
        monthly_returns = metrics.get('monthly_excess_returns', [])
        monthly_dates = metrics.get('monthly_dates', [])
        if monthly_returns and monthly_dates:
            insert_monthly_returns(
                cursor, trial_number, 'holdout_2025',
                monthly_returns, monthly_dates
            )
        
        # 詳細パフォーマンス指標
        insert_detailed_metrics(
            cursor, trial_number, 'holdout_2025', cost_bps, metrics
        )
        
        print(f"  Trial #{trial_number}: 月次データ{len(monthly_returns)}件、詳細指標を保存（コスト{cost_bps}bps）")


def main():
    """メイン処理"""
    print(f"データベースパス: {DB_PATH}")
    
    # データベースディレクトリの確認
    ensure_db_directory(DB_PATH)
    
    # JSONデータを読み込む
    print(f"JSONファイルを読み込んでいます...")
    holdout_2023_2024_data = load_json(HOLDOUT_2023_2024_FILE)
    holdout_2025_data = load_json(HOLDOUT_2025_FILE)
    
    # データベースに接続
    conn = sqlite3.connect(str(DB_PATH))
    try:
        # テーブルを作成
        print("テーブルを作成しています...")
        create_tables(conn)
        
        cursor = conn.cursor()
        
        # 2023-2024 Holdout結果を処理
        process_holdout_2023_2024(cursor, holdout_2023_2024_data)
        
        # 2025疑似ライブ結果を処理
        process_holdout_2025(cursor, holdout_2025_data)
        
        conn.commit()
        print(f"\nデータの保存が完了しました: {DB_PATH}")
        
        # 確認: 保存されたデータを表示
        print("\n=== 保存されたデータの確認 ===")
        cursor.execute("""
            SELECT trial_number, evaluation_period, COUNT(*) as count
            FROM monthly_rebalance_candidate_monthly_returns
            GROUP BY trial_number, evaluation_period
            ORDER BY trial_number, evaluation_period
        """)
        print("\n月次超過リターン:")
        for row in cursor.fetchall():
            print(f"  Trial #{row[0]} ({row[1]}): {row[2]}件")
        
        cursor.execute("""
            SELECT trial_number, evaluation_period, cost_bps
            FROM monthly_rebalance_candidate_detailed_metrics
            ORDER BY trial_number, evaluation_period, cost_bps
        """)
        print("\n詳細パフォーマンス指標:")
        for row in cursor.fetchall():
            print(f"  Trial #{row[0]} ({row[1]}, {row[2]}bps)")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()

