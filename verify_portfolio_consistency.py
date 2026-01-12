#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
optimize/compare/本番で同一条件のportfolio_hashを比較するスクリプト

ChatGPTフィードバックに基づき、最適化ルート、比較ルート、本番運用ルートで
同じ条件でポートフォリオを生成し、portfolio_hashが一致するか確認します。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import hashlib

from omanta_3rd.jobs.longterm_run import StrategyParams, build_features, select_portfolio
from omanta_3rd.jobs.optimize import EntryScoreParams, _select_portfolio_with_params
from omanta_3rd.infra.db import connect_db


def calculate_portfolio_hash(portfolio_df) -> str:
    """ポートフォリオのハッシュを計算"""
    if portfolio_df is None or portfolio_df.empty:
        return "EMPTY"
    
    # codeとweightでハッシュを計算
    codes = sorted(portfolio_df["code"].tolist())
    weights = sorted(portfolio_df["weight"].tolist())
    
    hash_str = f"{','.join(codes)}|{','.join([f'{w:.10f}' for w in weights])}"
    return hashlib.md5(hash_str.encode()).hexdigest()


def get_portfolio_from_optimize_route(
    rebalance_date: str,
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
) -> Dict[str, Any]:
    """最適化ルートでポートフォリオを生成"""
    print(f"[optimize route] 開始: {rebalance_date}")
    
    try:
        with connect_db(read_only=True) as conn:
            feat = build_features(
                conn, rebalance_date,
                strategy_params=strategy_params,
                entry_params=entry_params
            )
        
        if feat is None or feat.empty:
            return {"error": "特徴量が空", "function": "_select_portfolio_with_params"}
        
        # 最適化ルート: _select_portfolio_with_params を使用
        portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)
        
        if portfolio is None or portfolio.empty:
            return {"error": "ポートフォリオが空", "function": "_select_portfolio_with_params"}
        
        portfolio_hash = calculate_portfolio_hash(portfolio)
        
        return {
            "selected_codes": portfolio["code"].tolist(),
            "weights": portfolio["weight"].tolist(),
            "portfolio_hash": portfolio_hash,
            "function": "_select_portfolio_with_params",
            "num_stocks": len(portfolio),
        }
    except Exception as e:
        return {"error": str(e), "function": "_select_portfolio_with_params"}


def get_portfolio_from_compare_route(
    rebalance_date: str,
    params_file: str,
) -> Dict[str, Any]:
    """比較ルートでポートフォリオを生成"""
    print(f"[compare route] 開始: {rebalance_date}")
    
    try:
        # compare_lambda_penalties.py の run_backtest_with_params_file を使用
        # ただし、これはパフォーマンス計算も行うので、ポートフォリオだけを取得する方法を確認する必要がある
        # 現時点では、内部で使用している関数を確認して、同じ方法でポートフォリオを生成する
        
        # パラメータファイルを読み込む
        with open(params_file, "r", encoding="utf-8") as f:
            params_data = json.load(f)
        
        strategy_params_dict = params_data.get("strategy", {})
        entry_params_dict = params_data.get("entry", {})
        
        strategy_params = StrategyParams(**strategy_params_dict)
        entry_params = EntryScoreParams(**entry_params_dict)
        
        with connect_db(read_only=True) as conn:
            feat = build_features(
                conn, rebalance_date,
                strategy_params=strategy_params,
                entry_params=entry_params
            )
        
        if feat is None or feat.empty:
            return {"error": "特徴量が空", "function": "unknown"}
        
        # compare_lambda_penalties.py が実際に使用している関数を確認
        # 現時点では、compare側が select_portfolio を使用している可能性がある
        # これを確認するために、両方の方法で試す
        
        # 方法1: select_portfolio (longterm_run.py)
        portfolio_v1 = select_portfolio(feat, strategy_params=strategy_params)
        hash_v1 = calculate_portfolio_hash(portfolio_v1) if portfolio_v1 is not None and not portfolio_v1.empty else None
        
        # 方法2: _select_portfolio_with_params
        portfolio_v2 = _select_portfolio_with_params(feat, strategy_params, entry_params)
        hash_v2 = calculate_portfolio_hash(portfolio_v2) if portfolio_v2 is not None and not portfolio_v2.empty else None
        
        # 実際に使用されている方を返す（現時点では両方試して比較）
        # TODO: compare_lambda_penalties.py の実装を確認して、実際に使用されている方を特定
        
        return {
            "selected_codes_v1": portfolio_v1["code"].tolist() if portfolio_v1 is not None and not portfolio_v1.empty else None,
            "weights_v1": portfolio_v1["weight"].tolist() if portfolio_v1 is not None and not portfolio_v1.empty else None,
            "portfolio_hash_v1": hash_v1,
            "function_v1": "select_portfolio (longterm_run.py)",
            "selected_codes_v2": portfolio_v2["code"].tolist() if portfolio_v2 is not None and not portfolio_v2.empty else None,
            "weights_v2": portfolio_v2["weight"].tolist() if portfolio_v2 is not None and not portfolio_v2.empty else None,
            "portfolio_hash_v2": hash_v2,
            "function_v2": "_select_portfolio_with_params",
            "num_stocks_v1": len(portfolio_v1) if portfolio_v1 is not None and not portfolio_v1.empty else 0,
            "num_stocks_v2": len(portfolio_v2) if portfolio_v2 is not None and not portfolio_v2.empty else 0,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "function": "unknown"}


def get_portfolio_from_production_route(
    rebalance_date: str,
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
) -> Dict[str, Any]:
    """本番運用ルートでポートフォリオを生成"""
    print(f"[production route] 開始: {rebalance_date}")
    
    try:
        with connect_db(read_only=True) as conn:
            feat = build_features(
                conn, rebalance_date,
                strategy_params=strategy_params,
                entry_params=entry_params
            )
        
        if feat is None or feat.empty:
            return {"error": "特徴量が空", "function": "select_portfolio (longterm_run.py)"}
        
        # 本番運用ルート: _select_portfolio_with_params（等ウェイト版）を使用
        from omanta_3rd.jobs.optimize import _select_portfolio_with_params
        portfolio = _select_portfolio_with_params(feat, strategy_params, entry_params)
        
        if portfolio is None or portfolio.empty:
            return {"error": "ポートフォリオが空", "function": "select_portfolio (longterm_run.py)"}
        
        portfolio_hash = calculate_portfolio_hash(portfolio)
        
        return {
            "selected_codes": portfolio["code"].tolist(),
            "weights": portfolio["weight"].tolist(),
            "portfolio_hash": portfolio_hash,
            "function": "_select_portfolio_with_params",
            "num_stocks": len(portfolio),
        }
    except Exception as e:
        return {"error": str(e), "function": "select_portfolio (longterm_run.py)"}


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="optimize/compare/本番で同一条件のportfolio_hashを比較")
    parser.add_argument("--rebalance-date", type=str, required=True, help="リバランス日 (YYYY-MM-DD)")
    parser.add_argument("--params-file", type=str, required=True, help="パラメータファイルのパス")
    
    args = parser.parse_args()
    
    rebalance_date = args.rebalance_date
    params_file = args.params_file
    
    print("=" * 80)
    print("ポートフォリオ一貫性確認スクリプト")
    print("=" * 80)
    print(f"リバランス日: {rebalance_date}")
    print(f"パラメータファイル: {params_file}")
    print()
    
    # パラメータファイルを読み込む
    if not Path(params_file).exists():
        print(f"❌ パラメータファイルが見つかりません: {params_file}")
        sys.exit(1)
    
    with open(params_file, "r", encoding="utf-8") as f:
        params_data = json.load(f)
    
    strategy_params_dict = params_data.get("strategy", {})
    entry_params_dict = params_data.get("entry", {})
    
    strategy_params = StrategyParams(**strategy_params_dict)
    entry_params = EntryScoreParams(**entry_params_dict)
    
    # 各ルートでポートフォリオを生成
    result_optimize = get_portfolio_from_optimize_route(rebalance_date, strategy_params, entry_params)
    result_compare = get_portfolio_from_compare_route(rebalance_date, params_file)
    result_production = get_portfolio_from_production_route(rebalance_date, strategy_params, entry_params)
    
    # 結果を表示
    print()
    print("=" * 80)
    print("【結果】")
    print("=" * 80)
    print()
    
    print("【optimize route】")
    if "error" in result_optimize:
        print(f"  ❌ エラー: {result_optimize['error']}")
    else:
        print(f"  関数: {result_optimize['function']}")
        print(f"  銘柄数: {result_optimize['num_stocks']}")
        print(f"  portfolio_hash: {result_optimize['portfolio_hash']}")
        print(f"  銘柄: {result_optimize['selected_codes']}")
        print(f"  重み: {[f'{w:.6f}' for w in result_optimize['weights']]}")
    print()
    
    print("【compare route】")
    if "error" in result_compare:
        print(f"  ❌ エラー: {result_compare['error']}")
    else:
        print(f"  関数（v1）: {result_compare.get('function_v1', 'N/A')}")
        if result_compare.get('portfolio_hash_v1'):
            print(f"  portfolio_hash（v1）: {result_compare['portfolio_hash_v1']}")
        print(f"  関数（v2）: {result_compare.get('function_v2', 'N/A')}")
        if result_compare.get('portfolio_hash_v2'):
            print(f"  portfolio_hash（v2）: {result_compare['portfolio_hash_v2']}")
    print()
    
    print("【production route】")
    if "error" in result_production:
        print(f"  ❌ エラー: {result_production['error']}")
    else:
        print(f"  関数: {result_production['function']}")
        print(f"  銘柄数: {result_production['num_stocks']}")
        print(f"  portfolio_hash: {result_production['portfolio_hash']}")
        print(f"  銘柄: {result_production['selected_codes']}")
        print(f"  重み: {[f'{w:.6f}' for w in result_production['weights']]}")
    print()
    
    # 比較結果
    print("=" * 80)
    print("【比較結果】")
    print("=" * 80)
    print()
    
    if "error" not in result_optimize and "error" not in result_production:
        hash_optimize = result_optimize["portfolio_hash"]
        hash_production = result_production["portfolio_hash"]
        
        if hash_optimize == hash_production:
            print("✅ optimize route と production route: 一致")
        else:
            print("❌ optimize route と production route: 不一致")
            print(f"   optimize: {hash_optimize}")
            print(f"   production: {hash_production}")
    
    if "error" not in result_compare:
        hash_compare_v1 = result_compare.get("portfolio_hash_v1")
        hash_compare_v2 = result_compare.get("portfolio_hash_v2")
        
        if hash_compare_v1 and "error" not in result_optimize:
            if hash_compare_v1 == result_optimize["portfolio_hash"]:
                print("✅ compare route (v1) と optimize route: 一致")
            else:
                print("❌ compare route (v1) と optimize route: 不一致")
        
        if hash_compare_v2 and "error" not in result_optimize:
            if hash_compare_v2 == result_optimize["portfolio_hash"]:
                print("✅ compare route (v2) と optimize route: 一致")
            else:
                print("❌ compare route (v2) と optimize route: 不一致")
    
    print()


if __name__ == "__main__":
    main()

