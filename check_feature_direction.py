#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特徴量の向き（符号）チェックスクリプト

ChatGPTのアドバイスに基づき、各特徴量について、Train内で
「featureが高いほど将来リターンが高いのか（期待方向）」
を確認し、重みの符号・スコア化が直感と一致しているか確認します。
"""

import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
from omanta_3rd.infra.db import connect_db
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.backtest.performance import calculate_portfolio_performance
from omanta_3rd.jobs.longterm_run import save_portfolio

def get_future_return(conn, code: str, rebalance_date: str, horizon_months: int) -> float:
    """指定されたリバランス日からhorizon_months後のリターンを取得"""
    rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
    eval_dt = rebalance_dt + relativedelta(months=horizon_months)
    eval_date = eval_dt.strftime("%Y-%m-%d")
    
    # 翌営業日を取得
    next_trading_day_df = pd.read_sql_query(
        """
        SELECT MIN(date) as next_date
        FROM prices_daily
        WHERE date > ?
          AND (open IS NOT NULL OR close IS NOT NULL)
        ORDER BY date
        LIMIT 1
        """,
        conn,
        params=(rebalance_date,),
    )
    
    if next_trading_day_df.empty:
        return None
    
    next_trading_day = str(next_trading_day_df['next_date'].iloc[0])
    
    # 購入価格（翌営業日の始値）
    buy_price_df = pd.read_sql_query(
        """
        SELECT open, close
        FROM prices_daily
        WHERE code = ? AND date = ?
        """,
        conn,
        params=(code, next_trading_day),
    )
    
    if buy_price_df.empty:
        return None
    
    buy_price = buy_price_df['open'].iloc[0]
    if pd.isna(buy_price):
        buy_price = buy_price_df['close'].iloc[0]
    
    if pd.isna(buy_price) or buy_price <= 0:
        return None
    
    # 評価価格（評価日の終値）
    sell_price_df = pd.read_sql_query(
        """
        SELECT close
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """,
        conn,
        params=(code, eval_date),
    )
    
    if sell_price_df.empty:
        return None
    
    sell_price = sell_price_df['close'].iloc[0]
    if pd.isna(sell_price) or sell_price <= 0:
        return None
    
    # リターンを計算
    return (sell_price - buy_price) / buy_price * 100

def check_feature_direction(train_dates: list, horizon_months: int = 12):
    """特徴量の向きをチェック"""
    print("=" * 80)
    print("特徴量の向き（符号）チェック")
    print("=" * 80)
    print(f"Train期間: {train_dates[0]} ～ {train_dates[-1]}")
    print(f"ホライズン: {horizon_months}ヶ月")
    print()
    
    # 特徴量キャッシュを読み込む
    print("特徴量キャッシュを読み込みます...")
    feature_cache = FeatureCache(cache_dir="cache/features")
    features_dict, prices_dict = feature_cache.warm(
        train_dates,
        n_jobs=1
    )
    print(f"✓ 特徴量: {len(features_dict)}日分")
    
    # 各リバランス日で特徴量と将来リターンの相関を計算
    print("\n各リバランス日で特徴量と将来リターンの相関を計算中...")
    
    feature_correlations = {}  # {feature_name: [correlations]}
    
    with connect_db() as conn:
        for i, rebalance_date in enumerate(train_dates, 1):
            if rebalance_date not in features_dict:
                continue
            
            print(f"  処理中 ({i}/{len(train_dates)}): {rebalance_date}")
            
            features_df = features_dict[rebalance_date]
            
            # 将来リターンを計算
            future_returns = []
            valid_codes = []
            
            for code in features_df['code']:
                future_return = get_future_return(conn, code, rebalance_date, horizon_months)
                if future_return is not None:
                    future_returns.append(future_return)
                    valid_codes.append(code)
            
            if len(future_returns) < 100:  # 最低100銘柄必要
                print(f"    ⚠️  有効な銘柄数が少ない（{len(future_returns)}銘柄）ためスキップ")
                continue
            
            # 有効な銘柄のみで特徴量をフィルタ
            valid_features_df = features_df[features_df['code'].isin(valid_codes)].copy()
            valid_features_df = valid_features_df.reset_index(drop=True)
            
            # 各特徴量と将来リターンの相関を計算
            for col in valid_features_df.columns:
                if col in ['code', 'date']:
                    continue
                
                if col not in feature_correlations:
                    feature_correlations[col] = []
                
                # 数値型に変換（文字列やその他の型をNaNに変換）
                feature_values = pd.to_numeric(valid_features_df[col], errors='coerce').values
                
                # NaNを除外
                valid_mask = ~pd.isna(feature_values) & ~pd.isna(future_returns)
                if valid_mask.sum() < 50:  # 最低50サンプル必要
                    continue
                
                valid_features = feature_values[valid_mask]
                valid_returns = np.array(future_returns)[valid_mask]
                
                # 相関を計算（数値型であることを確認）
                if len(valid_features) > 1 and np.std(valid_features) > 0:
                    corr = np.corrcoef(valid_features, valid_returns)[0, 1]
                    if not np.isnan(corr):
                        feature_correlations[col].append(corr)
    
    # 結果を集計
    print("\n" + "=" * 80)
    print("特徴量と将来リターンの相関結果")
    print("=" * 80)
    
    print(f"\n{'特徴量名':<30} {'平均相関':<12} {'期待方向':<15} {'判定':<10}")
    print("-" * 80)
    
    # 期待方向の定義（一般的な投資理論に基づく）
    expected_directions = {
        'roe': '正（高いほど良い）',
        'roe_trend': '正（高いほど良い）',
        'profit_growth': '正（高いほど良い）',
        'per': '負（低いほど良い）',
        'pbr': '負（低いほど良い）',
        'forward_per': '負（低いほど良い）',
        'core_score': '正（高いほど良い）',
        'entry_score': '正（高いほど良い）',
        'rsi': '負（低いほど良い、買われすぎ回避）',
        'bb_z': '負（低いほど良い、下振れで買う）',
        'liquidity': '正（高いほど良い）',
    }
    
    results = []
    
    for feature_name, correlations in feature_correlations.items():
        if len(correlations) == 0:
            continue
        
        mean_corr = np.mean(correlations)
        
        # 期待方向を判定
        expected_dir = expected_directions.get(feature_name.lower(), '不明')
        
        # 判定
        if expected_dir == '正（高いほど良い）':
            if mean_corr > 0.05:
                judgment = '✓ 正しい'
            elif mean_corr < -0.05:
                judgment = '❌ 逆'
            else:
                judgment = '⚠️  弱い'
        elif expected_dir == '負（低いほど良い）':
            if mean_corr < -0.05:
                judgment = '✓ 正しい'
            elif mean_corr > 0.05:
                judgment = '❌ 逆'
            else:
                judgment = '⚠️  弱い'
        else:
            judgment = '不明'
        
        results.append({
            'feature': feature_name,
            'mean_corr': mean_corr,
            'expected': expected_dir,
            'judgment': judgment,
        })
        
        print(f"{feature_name:<30} {mean_corr:>10.4f}   {expected_dir:<15} {judgment:<10}")
    
    # 問題のある特徴量を特定
    print("\n" + "=" * 80)
    print("問題のある特徴量")
    print("=" * 80)
    
    problematic = [r for r in results if '❌' in r['judgment']]
    if problematic:
        print("\n⚠️  符号が逆になっている可能性のある特徴量:")
        for r in problematic:
            print(f"  - {r['feature']}: 平均相関={r['mean_corr']:.4f}, 期待方向={r['expected']}")
    else:
        print("\n✓ 符号が逆になっている特徴量は見つかりませんでした")
    
    weak = [r for r in results if '⚠️' in r['judgment']]
    if weak:
        print("\n⚠️  相関が弱い特徴量:")
        for r in weak:
            print(f"  - {r['feature']}: 平均相関={r['mean_corr']:.4f}")
    
    return results

def main():
    """メイン処理"""
    # Walk-Forward Analysis結果からtrain期間を取得
    import json
    
    with open('walk_forward_longterm_12M_roll_evalYear2025.json', 'r', encoding='utf-8') as f:
        wf_result = json.load(f)
    
    # Fold 2のtrain期間を使用（2020-2021年、24ヶ月）
    fold2 = next((f for f in wf_result['fold_results'] if f['fold'] == 2), None)
    if fold2:
        train_dates = fold2['train_dates']
        check_feature_direction(train_dates, horizon_months=12)
    else:
        print("Fold 2が見つかりません")

if __name__ == "__main__":
    main()


