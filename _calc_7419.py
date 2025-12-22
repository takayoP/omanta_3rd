"""
コード7419（ノジマ）のPER、PBR、Forward PERを計算
現在のロジックで実際に計算を実行
"""

from src.omanta_3rd.infra.db import connect_db
from src.omanta_3rd.jobs.monthly_run import build_features
import pandas as pd
import sqlite3

# マイグレーション: closeカラムが存在しない場合は追加
def ensure_close_column(conn):
    """closeカラムが存在しない場合は追加"""
    cursor = conn.cursor()
    try:
        # カラムの存在確認
        cursor.execute("PRAGMA table_info(prices_daily)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'close' not in columns:
            print("closeカラムが存在しないため、追加します...")
            cursor.execute("ALTER TABLE prices_daily ADD COLUMN close REAL")
            conn.commit()
            print("closeカラムを追加しました")
        else:
            print("closeカラムは既に存在します")
    except Exception as e:
        print(f"マイグレーションエラー: {e}")
        conn.rollback()

# 評価日（過去の会話から2025-12-19を使用）
asof = "2025-12-19"
code = "7419"

print(f"コード {code}（ノジマ）の計算を実行します")
print(f"評価日: {asof}")
print("-" * 80)

with connect_db() as conn:
    # マイグレーション: closeカラムの確認
    ensure_close_column(conn)
    
    # 特徴量を計算
    feat = build_features(conn, asof)
    
    # コード7419のデータを取得
    code_data = feat[feat["code"] == code].copy()
    
    if code_data.empty:
        print(f"エラー: コード {code} のデータが見つかりません")
    else:
        row = code_data.iloc[0]
        
        print(f"\n【計算結果】")
        print(f"銘柄コード: {row.get('code')}")
        print(f"評価日: {row.get('as_of_date')}")
        print(f"\n【価格データ】")
        print(f"未調整終値 (close): {row.get('market_cap_latest_basis', 0) / row.get('shares_latest_basis', 1):.2f}円" if pd.notna(row.get('shares_latest_basis')) and row.get('shares_latest_basis') > 0 else "N/A")
        print(f"評価日時点の株数: {row.get('shares_latest_basis', 0):,.0f}株" if pd.notna(row.get('shares_latest_basis')) else "N/A")
        print(f"時価総額: {row.get('market_cap_latest_basis', 0):,.0f}円" if pd.notna(row.get('market_cap_latest_basis')) else "N/A")
        
        print(f"\n【財務データ】")
        # 財務データを直接取得
        fy_data = pd.read_sql_query(
            """
            SELECT profit, equity, shares_outstanding, treasury_shares, current_period_end
            FROM fins_statements
            WHERE code = ?
              AND type_of_current_period = 'FY'
              AND disclosed_date <= ?
            ORDER BY current_period_end DESC, disclosed_date DESC
            LIMIT 1
            """,
            conn,
            params=(code, asof),
        )
        
        if not fy_data.empty:
            fy_row = fy_data.iloc[0]
            print(f"利益 (profit): {fy_row.get('profit', 0):,.0f}円" if pd.notna(fy_row.get('profit')) else "N/A")
            print(f"純資産 (equity): {fy_row.get('equity', 0):,.0f}円" if pd.notna(fy_row.get('equity')) else "N/A")
            print(f"発行済み株式数: {fy_row.get('shares_outstanding', 0):,.0f}株" if pd.notna(fy_row.get('shares_outstanding')) else "N/A")
            print(f"自己株式数: {fy_row.get('treasury_shares', 0):,.0f}株" if pd.notna(fy_row.get('treasury_shares')) else "N/A")
            print(f"期末日: {fy_row.get('current_period_end', 'N/A')}")
        
        # 予想データを取得
        fc_data = pd.read_sql_query(
            """
            SELECT forecast_profit, disclosed_date
            FROM fins_statements
            WHERE code = ?
              AND disclosed_date <= ?
              AND type_of_current_period = 'FY'
              AND forecast_profit IS NOT NULL
            ORDER BY disclosed_date DESC
            LIMIT 1
            """,
            conn,
            params=(code, asof),
        )
        
        if not fc_data.empty:
            fc_row = fc_data.iloc[0]
            print(f"予想利益 (forecast_profit): {fc_row.get('forecast_profit', 0):,.0f}円" if pd.notna(fc_row.get('forecast_profit')) else "N/A")
            print(f"予想開示日: {fc_row.get('disclosed_date', 'N/A')}")
        
        print(f"\n【計算結果】")
        print(f"PER: {row.get('per', 'N/A')}" if pd.notna(row.get('per')) else "PER: N/A")
        print(f"PBR: {row.get('pbr', 'N/A')}" if pd.notna(row.get('pbr')) else "PBR: N/A")
        print(f"Forward PER: {row.get('forward_per', 'N/A')}" if pd.notna(row.get('forward_per')) else "Forward PER: N/A")
        
        print(f"\n【期待値との比較】")
        print(f"期待値: Forward PER=8.95, PER=7.9, PBR=1.52")
        print(f"計算値: Forward PER={row.get('forward_per', 'N/A')}, PER={row.get('per', 'N/A')}, PBR={row.get('pbr', 'N/A')}")
        
        # 分割倍率を確認
        if not fy_data.empty:
            fy_end = fy_data.iloc[0].get('current_period_end')
            if pd.notna(fy_end):
                if hasattr(fy_end, 'strftime'):
                    fy_end_str = fy_end.strftime("%Y-%m-%d")
                else:
                    fy_end_str = str(fy_end)
                
                # 分割倍率を計算
                split_data = pd.read_sql_query(
                    """
                    SELECT date, adjustment_factor
                    FROM prices_daily
                    WHERE code = ?
                      AND date > ?
                      AND date <= ?
                      AND adjustment_factor IS NOT NULL
                      AND adjustment_factor != 1.0
                    ORDER BY date ASC
                    """,
                    conn,
                    params=(code, fy_end_str, asof),
                )
                
                if not split_data.empty:
                    print(f"\n【分割・併合情報】")
                    print(f"FY期末: {fy_end_str}")
                    print(f"評価日: {asof}")
                    print(f"分割・併合イベント:")
                    split_mult = 1.0
                    for _, split_row in split_data.iterrows():
                        adj_factor = split_row.get('adjustment_factor')
                        if pd.notna(adj_factor) and adj_factor > 0:
                            split_mult *= (1.0 / float(adj_factor))
                            print(f"  {split_row.get('date')}: adjustment_factor={adj_factor:.6f} (株数倍率={1.0/float(adj_factor):.6f})")
                    print(f"累積分割倍率: {split_mult:.6f}")
                else:
                    print(f"\n【分割・併合情報】")
                    print(f"FY期末から評価日までの間に分割・併合はありません")
                    print(f"累積分割倍率: 1.0")

print("\n" + "=" * 80)
