"""最終選定候補のデータをSQLiteデータベースに保存"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# データベースパス
DB_PATH = Path(r"C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite")

# 入力ファイル
CANDIDATES_JSON = "final_selected_candidates.json"


def ensure_db_directory(db_path: Path):
    """データベースディレクトリが存在することを確認"""
    db_path.parent.mkdir(parents=True, exist_ok=True)


def create_tables(conn: sqlite3.Connection):
    """テーブルを作成"""
    cursor = conn.cursor()
    
    # 最終選定候補テーブル（基本情報とパラメータ）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_params_monthly_rebalance (
            trial_number INTEGER PRIMARY KEY,
            cluster INTEGER,
            train_sharpe REAL,
            ranking INTEGER,
            recommendation_text TEXT,
            -- パラメータ
            w_quality REAL,
            w_growth REAL,
            w_record_high REAL,
            w_size REAL,
            w_value REAL,
            w_forward_per REAL,
            roe_min REAL,
            bb_weight REAL,
            liquidity_quantile_cut REAL,
            rsi_base REAL,
            rsi_max REAL,
            bb_z_base REAL,
            bb_z_max REAL,
            -- メタデータ
            created_at TEXT,
            updated_at TEXT,
            -- JSONファイルの保存先パス
            json_file_path TEXT
        )
    """)
    
    # json_file_pathカラムが存在しない場合は追加
    cursor.execute("PRAGMA table_info(strategy_params_monthly_rebalance)")
    columns = [row[1] for row in cursor.fetchall()]
    if "json_file_path" not in columns:
        cursor.execute("""
            ALTER TABLE strategy_params_monthly_rebalance
            ADD COLUMN json_file_path TEXT
        """)
    
    # インデックス作成
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_strategy_params_monthly_rebalance_json_file
        ON strategy_params_monthly_rebalance(json_file_path)
    """)
    
    # パフォーマンス指標テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_rebalance_candidate_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trial_number INTEGER NOT NULL,
            evaluation_type TEXT NOT NULL,
            -- 2023-2024 Holdout期間
            sharpe_excess_0bps REAL,
            sharpe_excess_10bps REAL,
            sharpe_excess_20bps REAL,
            sharpe_excess_30bps REAL,
            sharpe_excess_2023 REAL,
            sharpe_excess_2024 REAL,
            cagr_excess_2023 REAL,
            cagr_excess_2024 REAL,
            max_drawdown REAL,
            max_drawdown_diff REAL,
            max_drawdown_10bps REAL,
            max_drawdown_20bps REAL,
            turnover_annual REAL,
            sharpe_after_cost_10bps REAL,
            sharpe_after_cost_20bps REAL,
            -- 2025疑似ライブ
            sharpe_excess_2025_10bps REAL,
            cagr_excess_2025_10bps REAL,
            max_drawdown_2025 REAL,
            sharpe_after_cost_2025 REAL,
            -- メタデータ
            created_at TEXT,
            FOREIGN KEY (trial_number) REFERENCES strategy_params_monthly_rebalance(trial_number)
        )
    """)
    
    # インデックス作成
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_monthly_rebalance_performance_trial 
        ON monthly_rebalance_candidate_performance(trial_number)
    """)
    
    conn.commit()


def load_candidates_data(json_file: str) -> Dict[str, Any]:
    """JSONファイルから候補データを読み込む"""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def insert_candidate(cursor: sqlite3.Cursor, trial_number: int, data: Dict[str, Any], ranking: int):
    """候補の基本情報とパラメータを挿入"""
    params = data.get('params', {})
    
    # 推奨テキスト
    recommendation_texts = {
        196: "実運用（コストや不確実性込み）で最も堅い一本",
        96: "上振れ狙い（2025の強さ重視）",
        180: "2023-2024の強さ優先（ただし20bpsで少し落ちる）",
        168: "比較的マイルド（だがコストに弱め）"
    }
    
    now = datetime.now().isoformat()
    
    # JSONファイルの絶対パスを取得
    json_file_path = str(Path(CANDIDATES_JSON).absolute())
    
    cursor.execute("""
        INSERT OR REPLACE INTO strategy_params_monthly_rebalance (
            trial_number, cluster, train_sharpe, ranking, recommendation_text,
            w_quality, w_growth, w_record_high, w_size, w_value, w_forward_per,
            roe_min, bb_weight, liquidity_quantile_cut,
            rsi_base, rsi_max, bb_z_base, bb_z_max,
            created_at, updated_at, json_file_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trial_number,
        None,  # cluster情報は候補JSONに含まれていない場合はNone
        None,  # train_sharpe
        ranking,
        recommendation_texts.get(trial_number, ""),
        params.get('w_quality'),
        params.get('w_growth'),
        params.get('w_record_high'),
        params.get('w_size'),
        params.get('w_value'),
        params.get('w_forward_per'),
        params.get('roe_min'),
        params.get('bb_weight'),
        params.get('liquidity_quantile_cut'),
        params.get('rsi_base'),
        params.get('rsi_max'),
        params.get('bb_z_base'),
        params.get('bb_z_max'),
        now,
        now,
        json_file_path
    ))


def insert_performance(cursor: sqlite3.Cursor, trial_number: int, data: Dict[str, Any]):
    """パフォーマンス指標を挿入"""
    holdout_2023_2024 = data.get('holdout_2023_2024', {})
    cost_sensitivity = data.get('cost_sensitivity', {})
    holdout_2025 = data.get('holdout_2025', {})
    
    now = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO final_candidate_performance (
            trial_number, evaluation_type,
            sharpe_excess_0bps, sharpe_excess_10bps, sharpe_excess_20bps, sharpe_excess_30bps,
            sharpe_excess_2023, sharpe_excess_2024,
            cagr_excess_2023, cagr_excess_2024,
            max_drawdown, max_drawdown_diff,
            max_drawdown_10bps, max_drawdown_20bps,
            turnover_annual,
            sharpe_after_cost_10bps, sharpe_after_cost_20bps,
            sharpe_excess_2025_10bps, cagr_excess_2025_10bps,
            max_drawdown_2025, sharpe_after_cost_2025,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trial_number,
        "comprehensive",  # 総合評価
        holdout_2023_2024.get('sharpe_excess_0bps'),
        cost_sensitivity.get('sharpe_excess_10bps'),
        cost_sensitivity.get('sharpe_excess_20bps'),
        cost_sensitivity.get('sharpe_excess_30bps'),
        holdout_2023_2024.get('sharpe_excess_2023'),
        holdout_2023_2024.get('sharpe_excess_2024'),
        holdout_2023_2024.get('cagr_excess_2023'),
        holdout_2023_2024.get('cagr_excess_2024'),
        holdout_2023_2024.get('max_drawdown'),
        holdout_2023_2024.get('max_drawdown_diff'),
        cost_sensitivity.get('max_drawdown_10bps'),
        cost_sensitivity.get('max_drawdown_20bps'),
        holdout_2023_2024.get('turnover_annual'),
        cost_sensitivity.get('sharpe_after_cost_10bps'),
        cost_sensitivity.get('sharpe_after_cost_20bps'),
        holdout_2025.get('sharpe_excess_2025_10bps'),
        holdout_2025.get('cagr_excess_2025_10bps'),
        holdout_2025.get('max_drawdown_2025'),
        holdout_2025.get('sharpe_after_cost_2025'),
        now
    ))


def main():
    """メイン処理"""
    print(f"データベースパス: {DB_PATH}")
    
    # データベースディレクトリの確認
    ensure_db_directory(DB_PATH)
    
    # JSONデータを読み込む
    print(f"JSONファイルを読み込んでいます: {CANDIDATES_JSON}")
    candidates_data = load_candidates_data(CANDIDATES_JSON)
    
    # データベースに接続
    conn = sqlite3.connect(str(DB_PATH))
    try:
        # テーブルを作成
        print("テーブルを作成しています...")
        create_tables(conn)
        
        cursor = conn.cursor()
        
        # ランキング（順位）
        rankings = {196: 1, 96: 2, 180: 3, 168: 4}
        
        # 各候補を挿入
        for trial_str, data in candidates_data.items():
            trial_number = int(trial_str)
            ranking = rankings.get(trial_number, 0)
            
            print(f"  Trial #{trial_number} を保存中...")
            
            # 基本情報とパラメータを挿入
            insert_candidate(cursor, trial_number, data, ranking)
            
            # パフォーマンス指標を挿入
            insert_performance(cursor, trial_number, data)
        
        conn.commit()
        print(f"\nデータの保存が完了しました: {DB_PATH}")
        
        # 確認: 保存されたデータを表示
        print("\n=== 保存されたデータの確認 ===")
        cursor.execute("""
            SELECT trial_number, ranking, recommendation_text 
            FROM strategy_params_monthly_rebalance 
            ORDER BY ranking
        """)
        for row in cursor.fetchall():
            print(f"  #{row[0]}: ランキング{row[1]}位 - {row[2]}")
        
        cursor.execute("SELECT COUNT(*) FROM monthly_rebalance_candidate_performance")
        count = cursor.fetchone()[0]
        print(f"\nパフォーマンス指標レコード数: {count}")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()

