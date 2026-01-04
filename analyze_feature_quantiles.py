#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特徴量の分位（quantile）分析

ChatGPTのアドバイスに基づき、各特徴量について
上位20% vs 下位20%、上位10% vs 下位10%の
forward return差を計算します。
"""

import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
from omanta_3rd.infra.db import connect_db
from omanta_3rd.backtest.feature_cache import FeatureCache

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

def analyze_feature_quantiles(train_dates: list, horizon_months: int = 12):
    """特徴量の分位分析"""
    print("=" * 80)
    print("特徴量の分位（quantile）分析")
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
    print()
    
    # 各リバランス日で特徴量の分位と将来リターンの差を計算
    print("各リバランス日で特徴量の分位分析を実行中...")
    
    feature_quantile_results = {}  # {feature_name: {'top20_vs_bottom20': [], 'top10_vs_bottom10': []}}
    
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
            valid_features_df['future_return'] = future_returns
            
            # 各特徴量の分位分析
            for col in valid_features_df.columns:
                if col in ['code', 'date', 'future_return']:
                    continue
                
                if col not in feature_quantile_results:
                    feature_quantile_results[col] = {
                        'top20_vs_bottom20': [],
                        'top10_vs_bottom10': [],
                    }
                
                # NaNを除外
                valid_mask = ~pd.isna(valid_features_df[col])
                if valid_mask.sum() < 100:  # 最低100サンプル必要
                    continue
                
                df_valid = valid_features_df[valid_mask].copy()
                
                # 上位20% vs 下位20%
                top20_threshold = df_valid[col].quantile(0.8)
                bottom20_threshold = df_valid[col].quantile(0.2)
                
                top20_returns = df_valid[df_valid[col] >= top20_threshold]['future_return']
                bottom20_returns = df_valid[df_valid[col] <= bottom20_threshold]['future_return']
                
                if len(top20_returns) > 0 and len(bottom20_returns) > 0:
                    diff_20 = top20_returns.mean() - bottom20_returns.mean()
                    feature_quantile_results[col]['top20_vs_bottom20'].append(diff_20)
                
                # 上位10% vs 下位10%
                top10_threshold = df_valid[col].quantile(0.9)
                bottom10_threshold = df_valid[col].quantile(0.1)
                
                top10_returns = df_valid[df_valid[col] >= top10_threshold]['future_return']
                bottom10_returns = df_valid[df_valid[col] <= bottom10_threshold]['future_return']
                
                if len(top10_returns) > 0 and len(bottom10_returns) > 0:
                    diff_10 = top10_returns.mean() - bottom10_returns.mean()
                    feature_quantile_results[col]['top10_vs_bottom10'].append(diff_10)
    
    # 結果を表示
    print("\n" + "=" * 80)
    print("特徴量の分位分析結果")
    print("=" * 80)
    
    print(f"\n{'特徴量名':<30} {'上位20%-下位20%':<15} {'上位10%-下位10%':<15} {'期待方向':<15} {'判定':<10}")
    print("-" * 80)
    
    expected_directions = {
        'roe': '正（高いほど良い）',
        'roe_trend': '正（高いほど良い）',
        'profit_growth': '正（高いほど良い）',
        'per': '負（低いほど良い）',
        'pbr': '負（低いほど良い）',
        'forward_per': '負（低いほど良い）',
        'core_score': '正（高いほど良い）',
        'entry_score': '正（高いほど良い）',
    }
    
    results = []
    for feature_name, quantile_data in feature_quantile_results.items():
        if len(quantile_data['top20_vs_bottom20']) == 0:
            continue
        
        mean_diff_20 = np.mean(quantile_data['top20_vs_bottom20'])
        mean_diff_10 = np.mean(quantile_data['top10_vs_bottom10']) if len(quantile_data['top10_vs_bottom10']) > 0 else np.nan
        
        expected_dir = expected_directions.get(feature_name.lower(), '不明')
        
        # 判定（上位20%-下位20%の差で判定）
        if expected_dir == '正（高いほど良い）':
            if mean_diff_20 > 2.0:  # 2%以上の差
                judgment = '✓ 正しい'
            elif mean_diff_20 < -2.0:
                judgment = '❌ 逆'
            else:
                judgment = '⚠️  弱い'
        elif expected_dir == '負（低いほど良い）':
            if mean_diff_20 < -2.0:  # 上位が下位より2%以上低い（負の差）
                judgment = '✓ 正しい'
            elif mean_diff_20 > 2.0:
                judgment = '❌ 逆'
            else:
                judgment = '⚠️  弱い'
        else:
            judgment = '不明'
        
        results.append({
            'feature': feature_name,
            'mean_diff_20': mean_diff_20,
            'mean_diff_10': mean_diff_10,
            'expected': expected_dir,
            'judgment': judgment,
        })
        
        diff_10_str = f"{mean_diff_10:>6.2f}" if not np.isnan(mean_diff_10) else "N/A"
        print(f"{feature_name:<30} {mean_diff_20:>6.2f}%        {diff_10_str:>6.2f}%        {expected_dir:<15} {judgment:<10}")
    
    # 問題のある特徴量を特定
    print("\n" + "=" * 80)
    print("問題のある特徴量")
    print("=" * 80)
    
    problematic = [r for r in results if '❌' in r['judgment']]
    if problematic:
        print("\n⚠️  符号が逆になっている可能性のある特徴量:")
        for r in problematic:
            print(f"  - {r['feature']}: 上位20%-下位20%={r['mean_diff_20']:.2f}%, 期待方向={r['expected']}")
    else:
        print("\n✓ 符号が逆になっている特徴量は見つかりませんでした")
    
    weak = [r for r in results if '⚠️' in r['judgment']]
    if weak:
        print("\n⚠️  分位差が弱い特徴量:")
        for r in weak:
            print(f"  - {r['feature']}: 上位20%-下位20%={r['mean_diff_20']:.2f}%")
    
    return results

def main():
    """メイン処理"""
    import json
    
    with open('walk_forward_longterm_12M_roll_evalYear2025.json', 'r', encoding='utf-8') as f:
        wf_result = json.load(f)
    
    # Fold 2のtrain期間を使用（2020-2021年、24ヶ月）
    fold2 = next((f for f in wf_result['fold_results'] if f['fold'] == 2), None)
    if fold2:
        train_dates = fold2['train_dates']
        analyze_feature_quantiles(train_dates, horizon_months=12)
    else:
        print("Fold 2が見つかりません")

if __name__ == "__main__":
    main()

