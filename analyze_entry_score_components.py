#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
entry_scoreの構成要素を分解して相関を分析

ChatGPTのアドバイスに基づき、entry_scoreを構成する要素
（RSI、BB Z-score、各期間のスコア等）を
個別に分析し、どれが逆風になっているかを特定します。

注意: entry_scoreはRSIとBB（ボリンジャーバンド）のみを使用しています。
"""

import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
from omanta_3rd.infra.db import connect_db
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.jobs.longterm_run import _rsi_from_series, _bb_zscore

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

def calculate_entry_score_components(conn, code: str, as_of_date: str, params=None):
    """entry_scoreの構成要素を計算（RSIとBBベース）"""
    # 過去の価格データを取得（20日、60日、90日分必要）
    sql = """
        SELECT date, adj_close
        FROM prices_daily
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 120
    """
    prices_df = pd.read_sql_query(sql, conn, params=(code, as_of_date))
    
    if len(prices_df) < 90:
        return None
    
    # 日付順にソート（古い順）
    prices_df = prices_df.sort_values('date')
    close_series = prices_df['adj_close']
    
    # デフォルトパラメータ（longterm_run.pyのPARAMSから）
    if params is None:
        from omanta_3rd.jobs.longterm_run import PARAMS
        rsi_base = PARAMS.rsi_base
        rsi_max = PARAMS.rsi_max
        bb_z_base = PARAMS.bb_z_base
        bb_z_max = PARAMS.bb_z_max
        bb_weight = PARAMS.bb_weight
        rsi_weight = PARAMS.rsi_weight
    else:
        rsi_base = params.get('rsi_base', 51.18)
        rsi_max = params.get('rsi_max', 73.58)
        bb_z_base = params.get('bb_z_base', -0.57)
        bb_z_max = params.get('bb_z_max', 2.16)
        bb_weight = params.get('bb_weight', 0.5527)
        rsi_weight = params.get('rsi_weight', 0.4473)
    
    components = {}
    
    # 各期間（20, 60, 90日）で計算
    for n in [20, 60, 90]:
        if len(close_series) < n + 1:
            continue
        
        # RSIとBB Z-scoreを計算
        rsi = _rsi_from_series(close_series, n)
        bb_z = _bb_zscore(close_series, n)
        
        # BBスコアを計算
        bb_score = np.nan
        if not pd.isna(bb_z):
            if bb_z_max != bb_z_base:
                bb_score = (bb_z - bb_z_base) / (bb_z_max - bb_z_base)
            else:
                bb_score = 0.0
            bb_score = np.clip(bb_score, 0.0, 1.0)
        
        # RSIスコアを計算
        rsi_score = np.nan
        if not pd.isna(rsi):
            if rsi_max != rsi_base:
                rsi_score = (rsi - rsi_base) / (rsi_max - rsi_base)
            else:
                rsi_score = 0.0
            rsi_score = np.clip(rsi_score, 0.0, 1.0)
        
        # 期間別のスコアを計算
        period_score = np.nan
        total_weight = bb_weight + rsi_weight
        if total_weight > 0:
            if not pd.isna(bb_score) and not pd.isna(rsi_score):
                period_score = (bb_weight * bb_score + rsi_weight * rsi_score) / total_weight
            elif not pd.isna(bb_score):
                period_score = bb_score
            elif not pd.isna(rsi_score):
                period_score = rsi_score
        
        # 各期間の値を保存
        components[f'rsi_{n}d'] = rsi
        components[f'bb_z_{n}d'] = bb_z
        components[f'bb_score_{n}d'] = bb_score
        components[f'rsi_score_{n}d'] = rsi_score
        components[f'period_score_{n}d'] = period_score
    
    # 最終スコア（3期間の最大値）
    period_scores = [components.get(f'period_score_{n}d', np.nan) for n in [20, 60, 90]]
    valid_scores = [s for s in period_scores if not pd.isna(s)]
    if valid_scores:
        components['entry_score'] = max(valid_scores)
    else:
        components['entry_score'] = np.nan
    
    return components

def analyze_entry_score_components(train_dates: list, horizon_months: int = 12, entry_params: dict = None):
    """entry_scoreの構成要素を分析"""
    print("=" * 80)
    print("entry_score構成要素の相関分析")
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
    
    # 各リバランス日でentry_scoreの構成要素と将来リターンの相関を計算
    print("各リバランス日でentry_score構成要素と将来リターンの相関を計算中...")
    
    component_correlations = {
        'rsi_20d': [],
        'rsi_60d': [],
        'rsi_90d': [],
        'bb_z_20d': [],
        'bb_z_60d': [],
        'bb_z_90d': [],
        'bb_score_20d': [],
        'bb_score_60d': [],
        'bb_score_90d': [],
        'rsi_score_20d': [],
        'rsi_score_60d': [],
        'rsi_score_90d': [],
        'period_score_20d': [],
        'period_score_60d': [],
        'period_score_90d': [],
        'entry_score': [],
    }
    
    with connect_db() as conn:
        for i, rebalance_date in enumerate(train_dates, 1):
            if rebalance_date not in features_dict:
                continue
            
            print(f"  処理中 ({i}/{len(train_dates)}): {rebalance_date}")
            
            features_df = features_dict[rebalance_date]
            
            # 将来リターンとentry_score構成要素を計算
            future_returns = []
            valid_codes = []
            components_list = []
            
            for code in features_df['code']:
                future_return = get_future_return(conn, code, rebalance_date, horizon_months)
                if future_return is None:
                    continue
                
                components = calculate_entry_score_components(conn, code, rebalance_date, params=entry_params)
                if components is None:
                    continue
                
                future_returns.append(future_return)
                valid_codes.append(code)
                components_list.append(components)
            
            if len(future_returns) < 100:  # 最低100銘柄必要
                print(f"    ⚠️  有効な銘柄数が少ない（{len(future_returns)}銘柄）ためスキップ")
                continue
            
            # 各構成要素と将来リターンの相関を計算
            for component_name in component_correlations.keys():
                component_values = [c.get(component_name, np.nan) for c in components_list]
                
                # NaNを除外
                valid_mask = ~pd.isna(component_values) & ~pd.isna(future_returns)
                if valid_mask.sum() < 50:  # 最低50サンプル必要
                    continue
                
                valid_components = np.array(component_values)[valid_mask]
                valid_returns = np.array(future_returns)[valid_mask]
                
                # 相関を計算
                if len(valid_components) > 1 and np.std(valid_components) > 0:
                    corr = np.corrcoef(valid_components, valid_returns)[0, 1]
                    if not np.isnan(corr):
                        component_correlations[component_name].append(corr)
    
    # 結果を表示
    print("\n" + "=" * 80)
    print("entry_score構成要素と将来リターンの相関結果")
    print("=" * 80)
    
    print(f"\n{'構成要素':<30} {'平均相関':<12} {'期待方向':<15} {'判定':<10}")
    print("-" * 80)
    
    expected_directions = {
        'rsi_20d': '正（高いほど良い、順張り）',
        'rsi_60d': '正（高いほど良い、順張り）',
        'rsi_90d': '正（高いほど良い、順張り）',
        'bb_z_20d': '正（高いほど良い、順張り）',
        'bb_z_60d': '正（高いほど良い、順張り）',
        'bb_z_90d': '正（高いほど良い、順張り）',
        'bb_score_20d': '正（高いほど良い）',
        'bb_score_60d': '正（高いほど良い）',
        'bb_score_90d': '正（高いほど良い）',
        'rsi_score_20d': '正（高いほど良い）',
        'rsi_score_60d': '正（高いほど良い）',
        'rsi_score_90d': '正（高いほど良い）',
        'period_score_20d': '正（高いほど良い）',
        'period_score_60d': '正（高いほど良い）',
        'period_score_90d': '正（高いほど良い）',
        'entry_score': '正（高いほど良い）',
    }
    
    results = []
    for component_name, correlations in component_correlations.items():
        if len(correlations) == 0:
            continue
        
        mean_corr = np.mean(correlations)
        expected_dir = expected_directions.get(component_name, '不明')
        
        # 判定
        if expected_dir == '正（高いほど良い）' or expected_dir == '正（高いほど良い、順張り）':
            if mean_corr > 0.05:
                judgment = '✓ 正しい'
            elif mean_corr < -0.05:
                judgment = '❌ 逆（符号逆転）'
            elif mean_corr < 0:
                judgment = '⚠️  弱い（負の相関）'
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
            'component': component_name,
            'mean_corr': mean_corr,
            'expected': expected_dir,
            'judgment': judgment,
        })
        
        print(f"{component_name:<30} {mean_corr:>10.4f}   {expected_dir:<15} {judgment:<10}")
    
    # 問題のある構成要素を特定
    print("\n" + "=" * 80)
    print("問題のある構成要素")
    print("=" * 80)
    
    problematic = [r for r in results if '❌' in r['judgment']]
    if problematic:
        print("\n❌ 符号が逆になっている構成要素（統計的に有意）:")
        for r in problematic:
            print(f"  - {r['component']}: 平均相関={r['mean_corr']:.4f}, 期待方向={r['expected']}")
    else:
        print("\n✓ 符号が逆になっている構成要素（統計的に有意）は見つかりませんでした")
    
    negative_weak = [r for r in results if '負の相関' in r['judgment']]
    if negative_weak:
        print("\n⚠️  負の相関を示している構成要素（注意が必要）:")
        for r in negative_weak:
            print(f"  - {r['component']}: 平均相関={r['mean_corr']:.4f}, 期待方向={r['expected']}")
        print("  → 順張り設計が逆効果になっている可能性があります")
    
    weak = [r for r in results if '⚠️' in r['judgment'] and '負の相関' not in r['judgment']]
    if weak:
        print("\n⚠️  相関が弱い構成要素:")
        for r in weak:
            print(f"  - {r['component']}: 平均相関={r['mean_corr']:.4f}")
    
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
        
        # 最適化されたパラメータを取得（Fold 2のbest_paramsから）
        best_params = fold2.get('best_params', {})
        entry_params = best_params.get('entry_params', {})
        
        print(f"使用するentry_scoreパラメータ:")
        print(f"  rsi_base: {entry_params.get('rsi_base', 'N/A')}")
        print(f"  rsi_max: {entry_params.get('rsi_max', 'N/A')}")
        print(f"  bb_z_base: {entry_params.get('bb_z_base', 'N/A')}")
        print(f"  bb_z_max: {entry_params.get('bb_z_max', 'N/A')}")
        print(f"  bb_weight: {entry_params.get('bb_weight', 'N/A')}")
        print()
        
        analyze_entry_score_components(train_dates, horizon_months=12, entry_params=entry_params)
    else:
        print("Fold 2が見つかりません")

if __name__ == "__main__":
    main()

