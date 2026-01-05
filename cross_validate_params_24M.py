#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
24Mホライズンのパラメータ横持ち再評価スクリプト

ChatGPTのアドバイスに基づき、24Mの異なるfoldのパラメータを他のfoldのtest期間に適用して再評価します。
これにより、以下の原因を切り分けます：
- どのパラメータでも2022/2023が悪い → 戦略レジーム弱点
- 特定foldのparamsだけ悪い → 最適化/過学習/探索範囲の問題
- 2023(+25%)が本物かどうかを確定
"""

import json
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from omanta_3rd.infra.db import connect_db
from test_seed_robustness_fixed_horizon import (
    build_params_from_json,
    calculate_fixed_horizon_performance,
)
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.jobs.optimize_timeseries import _run_single_backtest_portfolio_only
from omanta_3rd.jobs.monthly_run import save_portfolio
from omanta_3rd.backtest.performance import calculate_portfolio_performance
from dataclasses import fields
from omanta_3rd.jobs.monthly_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams

def load_wf_result(json_file: str) -> dict:
    """Walk-Forward Analysis結果を読み込む"""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def evaluate_params_on_test_period(
    test_dates: list,
    params: dict,
    horizon_months: int,
    features_dict: dict,
    prices_dict: dict,
) -> dict:
    """指定されたパラメータでtest期間を評価"""
    strategy_params, entry_params = build_params_from_json(params)
    
    # dataclassを辞書に変換
    strategy_params_dict = {
        field.name: getattr(strategy_params, field.name)
        for field in fields(StrategyParams)
    }
    entry_params_dict = {
        field.name: getattr(entry_params, field.name)
        for field in fields(EntryScoreParams)
    }
    
    portfolios = {}
    
    # ポートフォリオを選定
    for rebalance_date in test_dates:
        if rebalance_date not in features_dict:
            continue
        
        features_df = features_dict[rebalance_date]
        portfolio = _run_single_backtest_portfolio_only(
            rebalance_date,
            strategy_params_dict,
            entry_params_dict,
            features_df,
            prices_dict.get(rebalance_date) if prices_dict else None,
        )
        if portfolio is not None and not portfolio.empty:
            portfolios[rebalance_date] = portfolio
    
    if not portfolios:
        return {"error": "No portfolios were generated"}
    
    # パフォーマンスを計算
    with connect_db() as conn:
        latest_date_df = pd.read_sql_query(
            "SELECT MAX(date) as max_date FROM prices_daily",
            conn
        )
        latest_date = latest_date_df["max_date"].iloc[0] if not latest_date_df.empty else None
        
        if latest_date is None:
            return {"error": "No price data available"}
        
        performances = []
        annual_returns = []
        annual_excess_returns = []
        
        for rebalance_date in sorted(portfolios.keys()):
            # 評価日を計算（24Mホライズン）
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_dt = rebalance_dt + relativedelta(months=horizon_months)
            eval_date = eval_dt.strftime("%Y-%m-%d")
            
            if eval_date > latest_date:
                continue
            
            # ポートフォリオをDBに一時保存
            portfolio_df = portfolios[rebalance_date]
            save_portfolio(conn, portfolio_df)
            conn.commit()
            
            # パフォーマンスを計算
            perf = calculate_portfolio_performance(
                rebalance_date=rebalance_date,
                as_of_date=eval_date,
                portfolio_table="portfolio_monthly",
            )
            
            # 一時的に保存したポートフォリオを削除
            conn.execute(
                "DELETE FROM portfolio_monthly WHERE rebalance_date = ?",
                (rebalance_date,)
            )
            conn.commit()
            
            if "error" not in perf:
                total_return_pct = perf.get("total_return_pct")
                topix_comparison = perf.get("topix_comparison", {})
                excess_return_pct = topix_comparison.get("excess_return_pct")
                
                holding_years = horizon_months / 12.0
                
                if total_return_pct is not None and not pd.isna(total_return_pct):
                    return_factor = 1 + total_return_pct / 100
                    if return_factor > 0:
                        annual_return = return_factor ** (1 / holding_years) - 1
                        annual_return_pct = annual_return * 100
                        if not isinstance(annual_return_pct, complex):
                            annual_returns.append(annual_return_pct)
                
                if excess_return_pct is not None and not pd.isna(excess_return_pct):
                    excess_factor = 1 + excess_return_pct / 100
                    if excess_factor > 0:
                        annual_excess_return = excess_factor ** (1 / holding_years) - 1
                        annual_excess_return_pct = annual_excess_return * 100
                        if not isinstance(annual_excess_return_pct, complex):
                            annual_excess_returns.append(annual_excess_return_pct)
                
                performances.append(perf)
        
        if not performances:
            return {"error": "No performances were calculated"}
        
        import numpy as np
        
        mean_annual_excess_return = np.mean(annual_excess_returns) if annual_excess_returns else 0.0
        median_annual_excess_return = np.median(annual_excess_returns) if annual_excess_returns else 0.0
        win_rate = sum(1 for r in annual_excess_returns if r > 0) / len(annual_excess_returns) if annual_excess_returns else 0.0
        
        return {
            "mean_annual_excess_return_pct": mean_annual_excess_return,
            "median_annual_excess_return_pct": median_annual_excess_return,
            "win_rate": win_rate,
            "num_portfolios": len(performances),
        }

def main():
    """24Mホライズンのパラメータ横持ち再評価を実行"""
    wf_json = "walk_forward_longterm_24M_roll_evalYear2025.json"
    horizon_months = 24
    
    print("=" * 80)
    print("24Mホライズン パラメータ横持ち再評価")
    print("=" * 80)
    print()
    print("目的:")
    print("  1. Fold1（2022）のbest_paramsを2023テストに当てる")
    print("  2. Fold2（2023）のbest_paramsを2022テストに当てる")
    print("  3. 2023(+25%)が本物かどうかを確定")
    print()
    
    # Walk-Forward Analysis結果を読み込む
    wf_result = load_wf_result(wf_json)
    
    # 各foldの情報を取得
    folds = {}
    for fold_data in wf_result['fold_results']:
        fold_label = fold_data['fold_label']
        folds[fold_label] = {
            'test_dates': fold_data['test_dates'],
            'params': fold_data['optimization']['best_params'],
            'original_perf': fold_data['test_performance'],
            'test_start': fold_data['test_start'],
            'test_end': fold_data['test_end'],
        }
    
    print("Fold情報:")
    for fold_label, fold_info in folds.items():
        print(f"  {fold_label}:")
        print(f"    Test期間: {fold_info['test_start']} ～ {fold_info['test_end']}")
        print(f"    元の年率超過: {fold_info['original_perf']['ann_excess_mean']:.2f}%")
        print(f"    元の勝率: {fold_info['original_perf']['win_rate']:.1%}")
    print()
    
    # 特徴量キャッシュを読み込む
    print("特徴量キャッシュを読み込みます...")
    feature_cache = FeatureCache(cache_dir="cache/features")
    
    # 全test_datesを収集
    all_test_dates = []
    for fold_data in wf_result['fold_results']:
        all_test_dates.extend(fold_data['test_dates'])
    all_test_dates = sorted(set(all_test_dates))
    
    features_dict, prices_dict = feature_cache.warm(
        all_test_dates,
        n_jobs=1
    )
    print(f"✓ 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # 横持ち再評価を実行
    print("=" * 80)
    print("パラメータ横持ち再評価を実行します...")
    print("=" * 80)
    print()
    
    results = {}
    
    # 各foldのパラメータを他のfoldのtest期間に適用
    for source_fold_label, source_fold_info in folds.items():
        source_params = source_fold_info['params']
        results[source_fold_label] = {}
        
        print(f"【{source_fold_label}のパラメータを適用】")
        print(f"  Test期間: {source_fold_info['test_start']} ～ {source_fold_info['test_end']}")
        print(f"  元の結果: 年率超過 {source_fold_info['original_perf']['ann_excess_mean']:.2f}%, "
              f"勝率 {source_fold_info['original_perf']['win_rate']:.1%}")
        print()
        
        for target_fold_label, target_fold_info in folds.items():
            if source_fold_label == target_fold_label:
                continue
            
            print(f"  → {target_fold_label}のtest期間（{target_fold_info['test_start']} ～ {target_fold_info['test_end']}）で評価中...")
            
            test_dates = target_fold_info['test_dates']
            perf = evaluate_params_on_test_period(
                test_dates,
                source_params,
                horizon_months,
                features_dict,
                prices_dict,
            )
            
            if "error" not in perf:
                results[source_fold_label][target_fold_label] = perf
                print(f"    年率超過リターン: {perf['mean_annual_excess_return_pct']:.2f}%, "
                      f"勝率: {perf['win_rate']:.1%}, "
                      f"ポートフォリオ数: {perf['num_portfolios']}")
            else:
                print(f"    ❌ エラー: {perf['error']}")
        print()
    
    # 結果を表示
    print("=" * 80)
    print("パラメータ横持ち再評価結果")
    print("=" * 80)
    print()
    
    print("【結果サマリー】")
    print(f"{'パラメータ元':<20} {'適用先':<20} {'年率超過':<12} {'勝率':<10} {'元の結果':<12}")
    print("-" * 80)
    
    for source_fold_label, target_results in results.items():
        for target_fold_label, perf in target_results.items():
            original_perf = folds[target_fold_label]['original_perf']
            original_excess = original_perf['ann_excess_mean']
            
            print(f"{source_fold_label:<20} {target_fold_label:<20} "
                  f"{perf['mean_annual_excess_return_pct']:>10.2f}% "
                  f"{perf['win_rate']:>8.1%} "
                  f"{original_excess:>10.2f}%")
    
    # 結果をJSONに保存
    output_file = "cross_validate_params_24M_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n結果を保存しました: {output_file}")
    print()
    
    # 分析
    print("=" * 80)
    print("分析")
    print("=" * 80)
    print()
    
    # 2022/2023の分析
    print("【2022/2023の分析】")
    print()
    
    # Fold1（2022）のパラメータを2023に当てた結果
    if 'fold1' in results and 'holdout_eval2025' in results['fold1']:
        fold1_to_2023 = results['fold1']['holdout_eval2025']
        fold1_original = folds['fold1']['original_perf']
        fold1_2023_original = folds['holdout_eval2025']['original_perf']
        
        print("1. Fold1（2022）のパラメータを2023テストに適用:")
        print(f"   結果: 年率超過 {fold1_to_2023['mean_annual_excess_return_pct']:.2f}%, "
              f"勝率 {fold1_to_2023['win_rate']:.1%}")
        print(f"   元の2022結果: {fold1_original['ann_excess_mean']:.2f}%")
        print(f"   元の2023結果: {fold1_2023_original['ann_excess_mean']:.2f}%")
        print()
        
        if fold1_to_2023['mean_annual_excess_return_pct'] > 0:
            print("   ✓ 2022パラメータが2023でも勝つ → 安定性が高い")
        else:
            print("   ⚠️  2022パラメータが2023で負ける → レジーム依存の可能性")
        print()
    
    # Fold2（2023）のパラメータを2022に当てた結果
    if 'holdout_eval2025' in results and 'fold1' in results['holdout_eval2025']:
        fold2_to_2022 = results['holdout_eval2025']['fold1']
        fold2_original = folds['holdout_eval2025']['original_perf']
        fold2_2022_original = folds['fold1']['original_perf']
        
        print("2. Fold2（2023）のパラメータを2022テストに適用:")
        print(f"   結果: 年率超過 {fold2_to_2022['mean_annual_excess_return_pct']:.2f}%, "
              f"勝率 {fold2_to_2022['win_rate']:.1%}")
        print(f"   元の2023結果: {fold2_original['ann_excess_mean']:.2f}%")
        print(f"   元の2022結果: {fold2_2022_original['ann_excess_mean']:.2f}%")
        print()
        
        if fold2_to_2022['mean_annual_excess_return_pct'] > 0:
            print("   ✓ 2023パラメータが2022でも勝つ → 2023(+25%)は本物の可能性が高い")
        else:
            print("   ⚠️  2023パラメータが2022で崩壊する → \"2023特化\"の可能性（過学習/レジーム依存）")
        print()
    
    # 総合判断
    print("【総合判断】")
    print()
    
    if 'fold1' in results and 'holdout_eval2025' in results['fold1']:
        fold1_to_2023_excess = results['fold1']['holdout_eval2025']['mean_annual_excess_return_pct']
    else:
        fold1_to_2023_excess = None
    
    if 'holdout_eval2025' in results and 'fold1' in results['holdout_eval2025']:
        fold2_to_2022_excess = results['holdout_eval2025']['fold1']['mean_annual_excess_return_pct']
    else:
        fold2_to_2022_excess = None
    
    if fold1_to_2023_excess is not None and fold2_to_2022_excess is not None:
        if fold1_to_2023_excess > 0 and fold2_to_2022_excess > 0:
            print("  ✓ どっちの年でもそこそこ勝つ params がある → 運用候補が強い")
        elif fold2_to_2022_excess < 0:
            print("  ⚠️  2023 params が2022で崩壊する → \"2023特化\"の可能性（過学習/レジーム依存）")
        elif fold1_to_2023_excess < 0:
            print("  ⚠️  2022 params が2023で崩壊する → レジーム依存の可能性")
    else:
        print("  ⚠️  評価が完了していません")

if __name__ == "__main__":
    main()

