#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
2022-2023期間限定の特徴量分析

ChatGPTのアドバイスに基づき、rollで崩壊した2022-2023期間に限定して
相関分析と分位分析を実行します。
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

def analyze_period_2022_2023(horizon_months: int = 12):
    """2022-2023期間限定の分析"""
    print("=" * 80)
    print("2022-2023期間限定の特徴量分析")
    print("=" * 80)
    print(f"期間: 2022-01-31 ～ 2023-12-29")
    print(f"ホライズン: {horizon_months}ヶ月")
    print()
    
    # 2022-2023のリバランス日を生成（月末）
    train_dates = []
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2023, 12, 31)
    
    current_date = start_date
    while current_date <= end_date:
        # 月末日を取得
        if current_date.month == 12:
            next_month = datetime(current_date.year + 1, 1, 1)
        else:
            next_month = datetime(current_date.year, current_date.month + 1, 1)
        
        # 月末日を計算（次の月の1日の前日）
        month_end = next_month - relativedelta(days=1)
        train_dates.append(month_end.strftime("%Y-%m-%d"))
        
        current_date = next_month
    
    print(f"リバランス日数: {len(train_dates)}")
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
    
    # 相関分析
    print("=" * 80)
    print("1. 相関分析")
    print("=" * 80)
    
    feature_correlations = {}
    
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
            
            if len(future_returns) < 100:
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
                
                feature_values = pd.to_numeric(valid_features_df[col], errors='coerce').values
                
                # NaNを除外
                valid_mask = ~pd.isna(feature_values) & ~pd.isna(future_returns)
                if valid_mask.sum() < 50:
                    continue
                
                valid_features = feature_values[valid_mask]
                valid_returns = np.array(future_returns)[valid_mask]
                
                # 相関を計算
                if len(valid_features) > 1 and np.std(valid_features) > 0:
                    corr = np.corrcoef(valid_features, valid_returns)[0, 1]
                    if not np.isnan(corr):
                        feature_correlations[col].append(corr)
    
    # 相関結果を表示
    print(f"\n{'特徴量名':<30} {'平均相関':<12} {'期待方向':<15} {'判定':<10}")
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
    
    correlation_results = []
    for feature_name, correlations in feature_correlations.items():
        if len(correlations) == 0:
            continue
        
        mean_corr = np.mean(correlations)
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
        
        correlation_results.append({
            'feature': feature_name,
            'mean_corr': mean_corr,
            'expected': expected_dir,
            'judgment': judgment,
        })
        
        print(f"{feature_name:<30} {mean_corr:>10.4f}   {expected_dir:<15} {judgment:<10}")
    
    # 分位分析
    print("\n" + "=" * 80)
    print("2. 分位分析")
    print("=" * 80)
    
    feature_quantile_results = {}
    
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
            
            if len(future_returns) < 100:
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
                if valid_mask.sum() < 100:
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
    
    # 分位結果を表示
    print(f"\n{'特徴量名':<30} {'上位20%-下位20%':<15} {'上位10%-下位10%':<15} {'期待方向':<15} {'判定':<10}")
    print("-" * 80)
    
    quantile_results = []
    for feature_name, quantile_data in feature_quantile_results.items():
        if len(quantile_data['top20_vs_bottom20']) == 0:
            continue
        
        mean_diff_20 = np.mean(quantile_data['top20_vs_bottom20'])
        mean_diff_10 = np.mean(quantile_data['top10_vs_bottom10']) if len(quantile_data['top10_vs_bottom10']) > 0 else np.nan
        
        expected_dir = expected_directions.get(feature_name.lower(), '不明')
        
        # 判定
        if expected_dir == '正（高いほど良い）':
            if mean_diff_20 > 2.0:
                judgment = '✓ 正しい'
            elif mean_diff_20 < -2.0:
                judgment = '❌ 逆'
            else:
                judgment = '⚠️  弱い'
        elif expected_dir == '負（低いほど良い）':
            if mean_diff_20 < -2.0:
                judgment = '✓ 正しい'
            elif mean_diff_20 > 2.0:
                judgment = '❌ 逆'
            else:
                judgment = '⚠️  弱い'
        else:
            judgment = '不明'
        
        quantile_results.append({
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
    print("問題のある特徴量（2022-2023期間）")
    print("=" * 80)
    
    problematic_corr = [r for r in correlation_results if '❌' in r['judgment']]
    problematic_quantile = [r for r in quantile_results if '❌' in r['judgment']]
    
    if problematic_corr or problematic_quantile:
        if problematic_corr:
            print("\n⚠️  相関が逆になっている特徴量:")
            for r in problematic_corr:
                print(f"  - {r['feature']}: 平均相関={r['mean_corr']:.4f}")
        
        if problematic_quantile:
            print("\n⚠️  分位差が逆になっている特徴量:")
            for r in problematic_quantile:
                print(f"  - {r['feature']}: 上位20%-下位20%={r['mean_diff_20']:.2f}%")
    else:
        print("\n✓ 符号が逆になっている特徴量は見つかりませんでした")
    
    return correlation_results, quantile_results

def main():
    """メイン処理"""
    analyze_period_2022_2023(horizon_months=12)

if __name__ == "__main__":
    main()

