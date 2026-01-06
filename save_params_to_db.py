#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
パラメータをDBに保存するスクリプト

JSONファイルからパラメータを読み込み、DBに保存します。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from omanta_3rd.infra.db import connect_db

def create_table_if_not_exists(conn):
    """パラメータテーブルを作成（存在しない場合）"""
    # テーブルが存在するか確認
    cursor = conn.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='strategy_params'
    """)
    table_exists = cursor.fetchone() is not None
    
    if not table_exists:
        # テーブルが存在しない場合は作成
        sql_file = Path("sql/create_strategy_params_table.sql")
        if sql_file.exists():
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql = f.read()
            conn.executescript(sql)
            conn.commit()
            print("✓ テーブルを作成しました")
        else:
            print("⚠️  SQLファイルが見つかりません: sql/create_strategy_params_table.sql")
            return
    else:
        print("✓ テーブルは既に存在します")
    
    # カラム追加（既存テーブルの場合）
    try:
        cursor = conn.execute("PRAGMA table_info(strategy_params)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "json_file_path" not in columns:
            conn.execute("ALTER TABLE strategy_params ADD COLUMN json_file_path TEXT")
            conn.commit()
            print("✓ JSONファイルパスカラムを追加しました")
        else:
            print("✓ JSONファイルパスカラムは既に存在します")
        
        if "portfolio_type" not in columns:
            conn.execute("ALTER TABLE strategy_params ADD COLUMN portfolio_type TEXT DEFAULT 'longterm'")
            conn.commit()
            print("✓ ポートフォリオタイプカラムを追加しました")
        else:
            print("✓ ポートフォリオタイプカラムは既に存在します")
    except Exception as e:
        print(f"⚠️  カラム追加でエラー: {e}")

def save_param_to_db(conn, param_file: str):
    """パラメータファイルをDBに保存"""
    with open(param_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    metadata = data.get("metadata", {})
    params = data.get("params", {})
    
    # param_idを決定
    if "operational_24M" in param_file:
        param_id = "operational_24M"
    elif "12M_momentum" in param_file:
        param_id = "12M_momentum"
    elif "12M_reversal" in param_file:
        param_id = "12M_reversal"
    elif "operational_monthly_rebalance" in param_file or "monthly_rebalance" in param_file:
        param_id = "operational_monthly_rebalance"
    else:
        param_id = Path(param_file).stem
    
    # JSONファイルの絶対パスを取得
    json_file_path = str(Path(param_file).absolute())
    
    # ポートフォリオタイプを決定（メタデータから取得、なければファイル名から推測）
    portfolio_type = metadata.get("portfolio_type", "longterm")
    if portfolio_type == "longterm" and ("monthly_rebalance" in param_file.lower() or "timeseries" in param_file.lower()):
        portfolio_type = "monthly_rebalance"
    
    # 既存レコードを確認
    cursor = conn.execute(
        "SELECT param_id FROM strategy_params WHERE param_id = ?",
        (param_id,)
    )
    exists = cursor.fetchone() is not None
    
    now = datetime.now().isoformat()
    
    if exists:
        # 更新
        conn.execute("""
            UPDATE strategy_params SET
                horizon_months = ?,
                strategy_type = ?,
                portfolio_type = ?,
                strategy_mode = ?,
                source_fold = ?,
                source_test_period = ?,
                description = ?,
                recommended_for = ?,
                w_quality = ?,
                w_growth = ?,
                w_record_high = ?,
                w_size = ?,
                w_value = ?,
                w_forward_per = ?,
                roe_min = ?,
                bb_weight = ?,
                liquidity_quantile_cut = ?,
                rsi_base = ?,
                rsi_max = ?,
                bb_z_base = ?,
                bb_z_max = ?,
                rsi_min_width = ?,
                bb_z_min_width = ?,
                metadata_json = ?,
                performance_json = ?,
                cross_validation_json = ?,
                json_file_path = ?,
                updated_at = ?
            WHERE param_id = ?
        """, (
            metadata.get("horizon_months"),
            metadata.get("strategy_type"),
            portfolio_type,
            metadata.get("strategy_mode"),
            metadata.get("source_fold"),
            metadata.get("source_test_period"),
            metadata.get("description"),
            metadata.get("recommended_for"),
            params.get("w_quality"),
            params.get("w_growth"),
            params.get("w_record_high"),
            params.get("w_size"),
            params.get("w_value"),
            params.get("w_forward_per"),
            params.get("roe_min"),
            params.get("bb_weight"),
            params.get("liquidity_quantile_cut"),
            params.get("rsi_base"),
            params.get("rsi_max"),
            params.get("bb_z_base"),
            params.get("bb_z_max"),
            params.get("rsi_min_width"),
            params.get("bb_z_min_width"),
            json.dumps(metadata, ensure_ascii=False),
            json.dumps(metadata.get("source_performance", {}), ensure_ascii=False),
            json.dumps(metadata.get("cross_validation_performance", {}), ensure_ascii=False),
            json_file_path,
            now,
            param_id
        ))
        print(f"  ✓ 更新: {param_id}")
    else:
        # 新規挿入
        conn.execute("""
            INSERT INTO strategy_params (
                param_id, horizon_months, strategy_type, portfolio_type, strategy_mode,
                source_fold, source_test_period, description, recommended_for,
                w_quality, w_growth, w_record_high, w_size, w_value,
                w_forward_per, roe_min, bb_weight, liquidity_quantile_cut,
                rsi_base, rsi_max, bb_z_base, bb_z_max,
                rsi_min_width, bb_z_min_width,
                metadata_json, performance_json, cross_validation_json,
                json_file_path,
                created_at, updated_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            param_id,
            metadata.get("horizon_months"),
            metadata.get("strategy_type"),
            portfolio_type,
            metadata.get("strategy_mode"),
            metadata.get("source_fold"),
            metadata.get("source_test_period"),
            metadata.get("description"),
            metadata.get("recommended_for"),
            params.get("w_quality"),
            params.get("w_growth"),
            params.get("w_record_high"),
            params.get("w_size"),
            params.get("w_value"),
            params.get("w_forward_per"),
            params.get("roe_min"),
            params.get("bb_weight"),
            params.get("liquidity_quantile_cut"),
            params.get("rsi_base"),
            params.get("rsi_max"),
            params.get("bb_z_base"),
            params.get("bb_z_max"),
            params.get("rsi_min_width"),
            params.get("bb_z_min_width"),
            json.dumps(metadata, ensure_ascii=False),
            json.dumps(metadata.get("source_performance", {}), ensure_ascii=False),
            json.dumps(metadata.get("cross_validation_performance", {}), ensure_ascii=False),
            json_file_path,
            now,
            now,
            1  # is_active
        ))
        print(f"  ✓ 新規保存: {param_id}")
    
    conn.commit()

def main():
    print("=" * 80)
    print("パラメータをDBに保存")
    print("=" * 80)
    print()
    
    param_files = [
        "params_operational_24M.json",
        "params_12M_momentum.json",
        "params_12M_reversal.json",
        "params_operational_monthly_rebalance.json",
    ]
    
    with connect_db() as conn:
        # テーブル作成
        create_table_if_not_exists(conn)
        print()
        
        # 各パラメータファイルを保存
        for param_file in param_files:
            if Path(param_file).exists():
                print(f"処理中: {param_file}")
                save_param_to_db(conn, param_file)
            else:
                print(f"⚠️  ファイルが見つかりません: {param_file}")
        print()
        
        # 保存されたパラメータを確認
        print("保存されたパラメータ:")
        cursor = conn.execute("""
            SELECT param_id, horizon_months, strategy_type, portfolio_type, strategy_mode, 
                   description, recommended_for, is_active
            FROM strategy_params
            ORDER BY strategy_type, horizon_months, param_id
        """)
        
        for row in cursor.fetchall():
            param_id, horizon, stype, ptype, mode, desc, rec, active = row
            status = "有効" if active else "無効"
            ptype_label = "長期保有型" if ptype == "longterm" else "月次リバランス型"
            print(f"  [{status}] {param_id}")
            print(f"    ホライズン: {horizon}M, タイプ: {stype}, ポートフォリオタイプ: {ptype_label}, モード: {mode}")
            print(f"    推奨用途: {rec}")
            if desc:
                print(f"    説明: {desc[:60]}...")
            print()
    
    print("=" * 80)
    print("完了")
    print("=" * 80)

if __name__ == "__main__":
    main()

