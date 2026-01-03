"""
長期保有型のWalk-Forward検証

前半期間で最適化→後半期間で評価を複数区間で実行し、実運用の外挿性を確認します。
ランダム分割seed耐性は確認できたので、最後に時系列で外挿性を確認します。

Usage:
    python walk_forward_longterm.py \
        --start 2018-01-01 \
        --end 2024-12-31 \
        --folds 3 \
        --train-min-years 2.0 \
        --horizon 12 \
        --n-trials 50
"""

import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
from dataclasses import replace, fields
import optuna

from omanta_3rd.infra.db import connect_db
from omanta_3rd.jobs.optimize_longterm import (
    split_rebalance_dates,
)
from omanta_3rd.jobs.batch_monthly_run import get_monthly_rebalance_dates
from omanta_3rd.jobs.monthly_run import StrategyParams
from omanta_3rd.jobs.optimize import EntryScoreParams
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.backtest.performance import calculate_portfolio_performance
from omanta_3rd.jobs.monthly_run import save_portfolio
from test_seed_robustness_fixed_horizon import calculate_fixed_horizon_performance


def split_dates_by_year(dates: List[str]) -> Dict[int, List[str]]:
    """
    リバランス日を年ごとに分割
    
    Args:
        dates: リバランス日のリスト（時系列順）
    
    Returns:
        年ごとの辞書: {2020: [...], 2021: [...], ...}
    """
    by_year = {}
    for date_str in dates:
        year = int(date_str.split("-")[0])
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(date_str)
    return by_year


def split_dates_into_folds(
    all_dates: List[str],
    n_folds: int,
    train_min_years: float = 2.0,
    use_2025_holdout: bool = False,
    fold_type: str = "roll",
    holdout_eval_year: Optional[int] = None,
    horizon_months: int = 12,
) -> List[Dict[str, Any]]:
    """
    リバランス日をfoldに分割（時系列順）
    
    Args:
        all_dates: 全リバランス日のリスト（時系列順）
        n_folds: fold数
        train_min_years: 最小train期間（年）
        use_2025_holdout: 最終年をホールドアウトとして使う（Trueの場合、リバランス年ベース）
        fold_type: foldタイプ（"roll": ロール、"simple": シンプル3分割）
        holdout_eval_year: 評価終了年でホールドアウトを指定（例: 2025、評価終了年ベース）
        horizon_months: ホライズン（月数、holdout_eval_year使用時に必要）
    
    Returns:
        foldごとの辞書リスト: [{"fold": 1, "train_dates": [...], "test_dates": [...], "validate_dates": [...]}, ...]
    """
    if len(all_dates) < 2:
        return []
    
    # 評価終了年ベースのホールドアウト（B案）
    if holdout_eval_year is not None:
        from dateutil.relativedelta import relativedelta
        from datetime import datetime
        
        # 評価終了年がholdout_eval_yearになるリバランス日を抽出
        holdout_test_dates = []
        optimization_dates = []
        
        for rebalance_date in all_dates:
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_dt = rebalance_dt + relativedelta(months=horizon_months)
            eval_year = eval_dt.year
            
            if eval_year == holdout_eval_year:
                holdout_test_dates.append(rebalance_date)
            else:
                optimization_dates.append(rebalance_date)
        
        holdout_test_dates = sorted(holdout_test_dates)
        
        if not holdout_test_dates:
            raise ValueError(f"評価終了年が{holdout_eval_year}になるリバランス日が見つかりません（horizon={horizon_months}M）")
        
        print(f"評価終了年{holdout_eval_year}ベースのホールドアウト: {len(holdout_test_dates)}日")
        print(f"  例: {holdout_test_dates[0]}リバランス → {horizon_months}M後 → {holdout_eval_year}年評価完了")
        print(f"最適化用データ: {len(optimization_dates)}日")
        
        # 最適化用データを評価終了年ベースで分類
        # 重要: リバランス年ではなく評価終了年で分類する
        train_dates = []
        validate_dates = []
        
        for rebalance_date in optimization_dates:
            rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
            eval_dt = rebalance_dt + relativedelta(months=horizon_months)
            eval_year = eval_dt.year
            
            if eval_year < holdout_eval_year - 1:
                # Train: 評価終了年 <= holdout_eval_year - 2
                train_dates.append(rebalance_date)
            elif eval_year == holdout_eval_year - 1:
                # Validate: 評価終了年 == holdout_eval_year - 1
                validate_dates.append(rebalance_date)
            # eval_year == holdout_eval_year は既にholdout_test_datesに含まれている
        
        train_dates = sorted(train_dates)
        validate_dates = sorted(validate_dates)
        
        if fold_type == "simple":
            # Disjointチェック
            train_set = set(train_dates)
            validate_set = set(validate_dates)
            test_set = set(holdout_test_dates)
            
            if train_set & validate_set:
                raise ValueError(f"❌ TrainとValidateが重複しています: {train_set & validate_set}")
            if train_set & test_set:
                raise ValueError(f"❌ TrainとTestが重複しています: {train_set & test_set}")
            if validate_set & test_set:
                raise ValueError(f"❌ ValidateとTestが重複しています: {validate_set & test_set}")
            
            print(f"✓ Disjointチェック: Train({len(train_dates)}) ∩ Validate({len(validate_dates)}) ∩ Test({len(holdout_test_dates)}) = ∅")
            
            if len(train_dates) > 0 and len(holdout_test_dates) > 0:
                result = [{
                    "fold": 1,
                    "train_dates": train_dates,
                    "test_dates": holdout_test_dates,
                    "train_start": train_dates[0],
                    "train_end": train_dates[-1],
                    "test_start": holdout_test_dates[0],
                    "test_end": holdout_test_dates[-1],
                    "is_holdout": True,
                    "holdout_eval_year": holdout_eval_year,
                }]
                if validate_dates:
                    result[0]["validate_dates"] = validate_dates
                    result[0]["validate_start"] = validate_dates[0]
                    result[0]["validate_end"] = validate_dates[-1]
                return result
        
        elif fold_type == "roll":
            # ロール方式: 各中間年でSplitを作成 + 最後に評価終了年がholdout_eval_yearのものを追加
            # 評価終了年ベースで分類
            dates_by_eval_year = {}
            for rebalance_date in optimization_dates:
                rebalance_dt = datetime.strptime(rebalance_date, "%Y-%m-%d")
                eval_dt = rebalance_dt + relativedelta(months=horizon_months)
                eval_year = eval_dt.year
                if eval_year not in dates_by_eval_year:
                    dates_by_eval_year[eval_year] = []
                dates_by_eval_year[eval_year].append(rebalance_date)
            
            eval_years = sorted([y for y in dates_by_eval_year.keys() if y < holdout_eval_year])
            
            folds = []
            fold_num = 1
            
            # 各中間年でSplitを作成（評価終了年ベース）
            for test_eval_year in eval_years:
                # Train: 評価終了年 < test_eval_year
                train_dates = []
                for year in eval_years:
                    if year < test_eval_year:
                        train_dates.extend(dates_by_eval_year[year])
                
                # Test: 評価終了年 == test_eval_year
                test_dates = sorted(dates_by_eval_year[test_eval_year])
                
                train_dates = sorted(train_dates)
                
                if len(train_dates) > 0 and len(test_dates) > 0:
                    folds.append({
                        "fold": fold_num,
                        "train_dates": train_dates,
                        "test_dates": test_dates,
                        "train_start": train_dates[0],
                        "train_end": train_dates[-1],
                        "test_start": test_dates[0],
                        "test_end": test_dates[-1],
                        "is_holdout": False,
                    })
                    fold_num += 1
            
            # 最後: Train（評価終了年 <= holdout_eval_year-1） → Test（評価終了年がholdout_eval_year）
            train_dates = []
            for year in eval_years:
                train_dates.extend(dates_by_eval_year[year])
            
            train_dates = sorted(train_dates)
            
            # Disjointチェック（最後のfold）
            train_set = set(train_dates)
            test_set = set(holdout_test_dates)
            if train_set & test_set:
                raise ValueError(f"❌ TrainとTestが重複しています: {train_set & test_set}")
            
            if len(train_dates) > 0 and len(holdout_test_dates) > 0:
                folds.append({
                    "fold": fold_num,
                    "train_dates": train_dates,
                    "test_dates": holdout_test_dates,
                    "train_start": train_dates[0],
                    "train_end": train_dates[-1],
                    "test_start": holdout_test_dates[0],
                    "test_end": holdout_test_dates[-1],
                    "is_holdout": True,
                    "holdout_eval_year": holdout_eval_year,
                })
            
            # 全foldでDisjointチェック
            for fold_info in folds:
                train_set = set(fold_info["train_dates"])
                test_set = set(fold_info["test_dates"])
                if train_set & test_set:
                    raise ValueError(f"❌ Fold {fold_info['fold']}: TrainとTestが重複しています")
                if "validate_dates" in fold_info:
                    validate_set = set(fold_info["validate_dates"])
                    if train_set & validate_set:
                        raise ValueError(f"❌ Fold {fold_info['fold']}: TrainとValidateが重複しています")
                    if validate_set & test_set:
                        raise ValueError(f"❌ Fold {fold_info['fold']}: ValidateとTestが重複しています")
            
            print(f"✓ 全foldでDisjointチェック完了")
            
            return folds
    
    # 最終年をホールドアウトとして分離（年をハードコードせず、データから自動算出）
    if use_2025_holdout:
        dates_by_year = split_dates_by_year(all_dates)
        # 最も新しい年をホールドアウトとして使用
        available_years = sorted(dates_by_year.keys())
        if not available_years:
            return []
        holdout_year = available_years[-1]  # 最も新しい年
        
        if holdout_year in dates_by_year:
            # 2025年を分離
            holdout_dates = sorted(dates_by_year[holdout_year])
            optimization_dates = [d for d in all_dates if d not in holdout_dates]
            
            print(f"{holdout_year}年を最終ホールドアウトとして分離: {len(holdout_dates)}日")
            print(f"最適化用データ: {len(optimization_dates)}日")
            
            if fold_type == "simple":
                # 案A: シンプル3分割
                # Train: 最初の年からholdout_year-2まで, Validate: holdout_year-1, Test: holdout_year
                dates_by_year_opt = split_dates_by_year(optimization_dates)
                opt_years = sorted(dates_by_year_opt.keys())
                
                if len(opt_years) < 2:
                    raise ValueError(f"最適化用データが不足しています。年数: {len(opt_years)}")
                
                # Train: 最初の年からholdout_year-2まで
                train_years = [y for y in opt_years if y < holdout_year - 1]
                # Validate: holdout_year-1
                validate_years = [holdout_year - 1] if (holdout_year - 1) in opt_years else []
                
                train_dates = []
                for year in train_years:
                    if year in dates_by_year_opt:
                        train_dates.extend(dates_by_year_opt[year])
                
                validate_dates = []
                for year in validate_years:
                    if year in dates_by_year_opt:
                        validate_dates.extend(dates_by_year_opt[year])
                
                train_dates = sorted(train_dates)
                validate_dates = sorted(validate_dates)
                
                if len(train_dates) > 0 and len(validate_dates) > 0 and len(holdout_dates) > 0:
                    return [{
                        "fold": 1,
                        "train_dates": train_dates,
                        "validate_dates": validate_dates,
                        "test_dates": holdout_dates,
                        "train_start": train_dates[0],
                        "train_end": train_dates[-1],
                        "validate_start": validate_dates[0],
                        "validate_end": validate_dates[-1],
                        "test_start": holdout_dates[0],
                        "test_end": holdout_dates[-1],
                        "is_holdout": True,
                    }]
            
            elif fold_type == "roll":
                # 案B: ロール（複数スプリット）+ 最終年は最後に残す
                # 例: Split1: Train 最初の年～holdout_year-3 → Test holdout_year-2
                #     Split2: Train 最初の年～holdout_year-2 → Test holdout_year-1
                #     最後: Train 最初の年～holdout_year-1 → Test holdout_year
                dates_by_year_opt = split_dates_by_year(optimization_dates)
                opt_years = sorted(dates_by_year_opt.keys())
                
                if len(opt_years) < 2:
                    raise ValueError(f"最適化用データが不足しています。年数: {len(opt_years)}")
                
                folds = []
                fold_num = 1
                
                # 各中間年でSplitを作成（holdout_year-2, holdout_year-1）
                for test_year in opt_years:
                    if test_year >= holdout_year:
                        continue  # holdout_yearは最後に処理
                    
                    # Train: 最初の年からtest_year-1まで
                    train_years = [y for y in opt_years if y < test_year]
                    test_years = [test_year]
                    
                    if len(train_years) == 0:
                        continue
                    
                    train_dates = []
                    for year in train_years:
                        train_dates.extend(dates_by_year_opt[year])
                    
                    test_dates = []
                    for year in test_years:
                        test_dates.extend(dates_by_year_opt[year])
                    
                    train_dates = sorted(train_dates)
                    test_dates = sorted(test_dates)
                    
                    if len(train_dates) > 0 and len(test_dates) > 0:
                        folds.append({
                            "fold": fold_num,
                            "train_dates": train_dates,
                            "test_dates": test_dates,
                            "train_start": train_dates[0],
                            "train_end": train_dates[-1],
                            "test_start": test_dates[0],
                            "test_end": test_dates[-1],
                            "is_holdout": False,
                        })
                        fold_num += 1
                
                # 最後: Train 最初の年～holdout_year-1 → Test holdout_year
                train_years = [y for y in opt_years if y < holdout_year]
                train_dates = []
                for year in train_years:
                    train_dates.extend(dates_by_year_opt[year])
                
                train_dates = sorted(train_dates)
                
                if len(train_dates) > 0 and len(holdout_dates) > 0:
                    folds.append({
                        "fold": fold_num,
                        "train_dates": train_dates,
                        "test_dates": holdout_dates,
                        "train_start": train_dates[0],
                        "train_end": train_dates[-1],
                        "test_start": holdout_dates[0],
                        "test_end": holdout_dates[-1],
                        "is_holdout": True,
                    })
                
                return folds
    
    # 従来のロジック（2025年ホールドアウトを使わない場合）
    folds = []
    total_months = len(all_dates)
    
    # 最小train期間（月数）
    train_min_months = int(train_min_years * 12)
    
    if total_months < train_min_months + n_folds:
        raise ValueError(f"データが不足しています。総月数: {total_months}, 最小必要: {train_min_months + n_folds}")
    
    # foldごとに分割
    for fold_idx in range(n_folds):
        # train期間の終了位置（foldが進むにつれて拡大）
        train_end_idx = train_min_months + fold_idx * (total_months - train_min_months) // n_folds
        
        # test期間の開始位置（train期間の直後）
        test_start_idx = train_end_idx + 1
        
        # test期間の終了位置（次のfoldの開始、または最後）
        if fold_idx < n_folds - 1:
            test_end_idx = train_min_months + (fold_idx + 1) * (total_months - train_min_months) // n_folds
        else:
            test_end_idx = total_months - 1
        
        if test_start_idx > test_end_idx:
            continue  # test期間が存在しない場合はスキップ
        
        train_dates = all_dates[:train_end_idx + 1]
        test_dates = all_dates[test_start_idx:test_end_idx + 1]
        
        if len(train_dates) < train_min_months or len(test_dates) == 0:
            continue
        
        folds.append({
            "fold": fold_idx + 1,
            "train_dates": train_dates,
            "test_dates": test_dates,
            "train_start": train_dates[0],
            "train_end": train_dates[-1],
            "test_start": test_dates[0],
            "test_end": test_dates[-1],
            "is_holdout": False,
        })
    
    return folds


def run_optimization_for_fold(
    train_dates: List[str],
    n_trials: int,
    study_type: str = "C",
    seed: Optional[int] = None,
    cache_dir: str = "cache/features",
) -> Dict[str, Any]:
    """
    foldのtrain期間で最適化を実行（長期保有型）
    
    Args:
        train_dates: train期間のリバランス日リスト
        n_trials: 試行回数
        study_type: スタディタイプ（A/B/C）
        seed: 乱数シード
        cache_dir: キャッシュディレクトリ
    
    Returns:
        最適化結果の辞書（best_params含む）
    """
    print(f"  Train期間で最適化を実行中... (n_trials={n_trials}, study_type={study_type})")
    print(f"  ⚠️  注意: 既存の最適化結果は使用せず、このfoldのTrain期間で新たに最適化を実行します")
    
    # 最適化を実行（optimize_longterm.pyのロジックを使用）
    from omanta_3rd.jobs.optimize_longterm import (
        objective_longterm,
        split_rebalance_dates,
    )
    from omanta_3rd.backtest.feature_cache import FeatureCache
    
    # Optunaスタディを作成（毎回新しいstudy_nameを生成）
    study_name = f"wfa_longterm_fold_{dt.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"  Study名: {study_name} (新規作成)")
    
    try:
        # Optunaスタディを作成（samplerをcreate_study時に指定）
        if seed is not None:
            sampler = optuna.samplers.TPESampler(seed=seed)
            print(f"  乱数シード: {seed} (再現性あり)")
        else:
            sampler = optuna.samplers.TPESampler()
            print(f"  乱数シード: None (再現性なし)")
        
        study = optuna.create_study(
            direction="maximize",
            study_name=study_name,
            storage=f"sqlite:///optuna_{study_name}.db",
            load_if_exists=False,  # 既存studyを読み込まない（新規作成）
            sampler=sampler,
        )
        print(f"  ✓ Optunaスタディを作成しました (load_if_exists=False)")
        
        # 特徴量キャッシュを構築
        feature_cache = FeatureCache(cache_dir=cache_dir)
        features_dict, prices_dict = feature_cache.warm(
            train_dates,
            n_jobs=-1
        )
        
        # 最適化実行
        print(f"  最適化を開始します (n_trials={n_trials})...")
        study.optimize(
            lambda trial: objective_longterm(
                trial,
                train_dates,
                study_type,
                cost_bps=0.0,
                n_jobs=1,  # WFAでは逐次実行
                features_dict=features_dict,
                prices_dict=prices_dict,
            ),
            n_trials=n_trials,
            show_progress_bar=False,
        )
        
        # 最良パラメータを取得
        best_params_raw = study.best_params.copy()
        print(f"  ✓ 最適化完了")
        print(f"    Best trial number: {study.best_trial.number}")
        print(f"    Best value: {study.best_value:.4f}")
        print(f"    Best params:")
        for key, value in sorted(best_params_raw.items()):
            print(f"      {key}: {value:.6f}")
        
        # Core Score重みの正規化
        w_quality = best_params_raw.get("w_quality", 0.0)
        w_value = best_params_raw.get("w_value", 0.0)
        w_growth = best_params_raw.get("w_growth", 0.0)
        w_record_high = best_params_raw.get("w_record_high", 0.0)
        w_size = best_params_raw.get("w_size", 0.0)
        total = w_quality + w_value + w_growth + w_record_high + w_size
        if total > 0:
            w_quality_norm = w_quality / total
            w_value_norm = w_value / total
            w_growth_norm = w_growth / total
            w_record_high_norm = w_record_high / total
            w_size_norm = w_size / total
        else:
            w_quality_norm = w_quality
            w_value_norm = w_value
            w_growth_norm = w_growth
            w_record_high_norm = w_record_high
            w_size_norm = w_size
        
        normalized_best_params = best_params_raw.copy()
        normalized_best_params["w_quality"] = w_quality_norm
        normalized_best_params["w_value"] = w_value_norm
        normalized_best_params["w_growth"] = w_growth_norm
        normalized_best_params["w_record_high"] = w_record_high_norm
        normalized_best_params["w_size"] = w_size_norm
        
        return {
            "best_value": study.best_value,
            "best_params": normalized_best_params,
            "best_params_raw": best_params_raw,
            "n_trials": n_trials,
            "best_trial_number": study.best_trial.number,
            "study_name": study_name,
        }
    except Exception as e:
        print(f"  ❌ 最適化エラー: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_backtest_with_fixed_params_longterm(
    test_dates: List[str],
    best_params: Dict[str, Any],
    horizon_months: int,
    features_dict: Dict[str, pd.DataFrame],
    prices_dict: Dict[str, Dict[str, List[float]]],
) -> Dict[str, Any]:
    """
    固定パラメータでtest期間のバックテストを実行（長期保有型・固定ホライズン）
    
    Args:
        test_dates: test期間のリバランス日リスト
        best_params: 最適化で得られたパラメータ
        horizon_months: ホライズン（月数）
        features_dict: 特徴量辞書
        prices_dict: 価格データ辞書
    
    Returns:
        メトリクスの辞書
    """
    print(f"  Test期間でバックテストを実行中... (horizon={horizon_months}M)")
    
    # StrategyParamsとEntryScoreParamsを構築
    from test_seed_robustness_fixed_horizon import build_params_from_json
    
    strategy_params, entry_params = build_params_from_json(best_params)
    
    # 固定ホライズン版のパフォーマンスを計算
    perf = calculate_fixed_horizon_performance(
        test_dates,
        strategy_params,
        entry_params,
        horizon_months=horizon_months,
        cost_bps=0.0,
        features_dict=features_dict,
        prices_dict=prices_dict,
    )
    
    return perf


def run_walk_forward_analysis_longterm(
    start_date: str,
    end_date: str,
    horizon_months: int,
    n_folds: int = 3,
    train_min_years: float = 2.0,
    n_trials: int = 50,
    study_type: str = "C",
    seed: Optional[int] = None,
    cache_dir: str = "cache/features",
    use_2025_holdout: bool = False,
    fold_type: str = "roll",
    holdout_eval_year: Optional[int] = None,
    n_jobs_fold: int = 1,
) -> Dict[str, Any]:
    """
    長期保有型のWalk-Forward Analysisを実行
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        horizon_months: ホライズン（月数、例：12, 24, 36）
        n_folds: fold数
        train_min_years: 最小train期間（年）
        n_trials: 最適化の試行回数
        study_type: スタディタイプ（A/B/C）
        seed: 乱数シード
        cache_dir: キャッシュディレクトリ
        use_2025_holdout: 最終年をホールドアウトとして使う（リバランス年ベース）
        fold_type: foldタイプ（"roll"または"simple"）
        holdout_eval_year: 評価終了年でホールドアウトを指定（例: 2025、評価終了年ベース）
    
    Returns:
        WFA結果の辞書
    """
    print("=" * 80)
    print("長期保有型 Walk-Forward Analysis")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"ホライズン: {horizon_months}ヶ月")
    print(f"Fold数: {n_folds}")
    print(f"最小Train期間: {train_min_years}年")
    print(f"最適化試行回数: {n_trials}")
    print(f"スタディタイプ: {study_type}")
    if seed is not None:
        print(f"乱数シード: {seed}（再現性あり）")
    else:
        print(f"乱数シード: None（再現性なし）")
    if use_2025_holdout:
        print(f"⭐ 最終年をホールドアウトとして使用: {fold_type}方式")
        # ホライズンと終了日の関係をチェック
        from dateutil.relativedelta import relativedelta
        from datetime import datetime
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        required_end_dt = end_dt + relativedelta(months=horizon_months)
        required_end_str = required_end_dt.strftime("%Y-%m-%d")
        print(f"⚠️  警告: {horizon_months}Mホライズンで評価するには、{required_end_str}までの価格データが必要です")
        print(f"   現在の終了日: {end_date}")
        print(f"   推奨: --end {required_end_str} または --horizon 12/24 に変更してください")
    print()
    
    # リバランス日を取得
    print("リバランス日を取得します...")
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"✓ リバランス日数: {len(rebalance_dates)}")
    print()
    
    # foldに分割
    print("foldに分割します...")
    if holdout_eval_year is not None:
        print(f"⭐ 評価終了年{holdout_eval_year}ベースのホールドアウト: {fold_type}方式")
        print(f"   {horizon_months}Mホライズンで評価終了年が{holdout_eval_year}になるリバランス日をテストに使用")
        print(f"注意: --folds パラメータは {fold_type} 方式では無視されます")
    elif use_2025_holdout:
        print(f"⭐ 最終年をホールドアウトとして使用: {fold_type}方式")
        print(f"注意: --folds パラメータは {fold_type} 方式では無視されます")
    folds = split_dates_into_folds(
        rebalance_dates,
        n_folds,
        train_min_years,
        use_2025_holdout=use_2025_holdout,
        fold_type=fold_type,
        holdout_eval_year=holdout_eval_year,
        horizon_months=horizon_months,
    )
    print(f"✓ {len(folds)}個のfoldを作成")
    for fold_info in folds:
        if fold_info.get("is_holdout", False):
            holdout_year = int(fold_info["test_start"].split("-")[0])
            print(f"  Fold {fold_info['fold']}: 最終ホールドアウト（{holdout_year}年）")
        else:
            print(f"  Fold {fold_info['fold']}: Train {fold_info['train_start']} ～ {fold_info['train_end']}, Test {fold_info['test_start']} ～ {fold_info['test_end']}")
    print()
    
    # 特徴量キャッシュを構築（全期間分）
    print("特徴量キャッシュを構築します...")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    features_dict, prices_dict = feature_cache.warm(
        rebalance_dates,
        n_jobs=-1
    )
    print(f"✓ 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # 各foldで実行
    print("=" * 80)
    print("各foldでWalk-Forward Analysisを実行します...")
    print("=" * 80)
    
    # 並列化の設定
    import multiprocessing as mp
    if n_jobs_fold == -1:
        n_jobs_fold = min(len(folds), mp.cpu_count())
    elif n_jobs_fold <= 0:
        n_jobs_fold = 1
    else:
        n_jobs_fold = min(n_jobs_fold, len(folds), mp.cpu_count())
    
    if n_jobs_fold > 1:
        print(f"並列実行: {n_jobs_fold}プロセス（fold間並列化）")
    else:
        print("逐次実行（fold間）")
    print()
    
    fold_results = []
    
    # fold間の並列化
    if n_jobs_fold > 1 and len(folds) > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from dataclasses import fields
        
        def _process_single_fold_wrapper(
            fold_info: Dict[str, Any],
            horizon_months: int,
            n_trials: int,
            study_type: str,
            seed: Optional[int],
            cache_dir: str,
            features_dict: Dict[str, pd.DataFrame],
            prices_dict: Dict[str, Dict[str, List[float]]],
        ) -> Dict[str, Any]:
            """単一foldの処理をラップ（並列化用）"""
            try:
                fold_num = fold_info["fold"]
                train_dates = fold_info["train_dates"]
                test_dates = fold_info["test_dates"]
                
                # Train期間で最適化
                opt_result = run_optimization_for_fold(
                    train_dates,
                    n_trials=n_trials,
                    study_type=study_type,
                    seed=seed,
                    cache_dir=cache_dir,
                )
                
                if opt_result is None:
                    return {"fold": fold_num, "error": "最適化に失敗しました"}
                
                best_params = opt_result["best_params"]
                best_value = opt_result["best_value"]
                
                # Test期間でバックテスト（固定ホライズン）
                test_perf = run_backtest_with_fixed_params_longterm(
                    test_dates,
                    best_params,
                    horizon_months=horizon_months,
                    features_dict=features_dict,
                    prices_dict=prices_dict,
                )
                
                fold_result = {
                    "fold": fold_num,
                    "train_start": fold_info["train_start"],
                    "train_end": fold_info["train_end"],
                    "test_start": fold_info["test_start"],
                    "test_end": fold_info["test_end"],
                    "train_dates_count": len(train_dates),
                    "test_dates_count": len(test_dates),
                    "is_holdout": fold_info.get("is_holdout", False),
                    "optimization": {
                        "best_value": float(best_value) if best_value is not None else None,
                        "best_params": best_params,
                        "n_trials": n_trials,
                        "best_trial_number": opt_result.get("best_trial_number"),
                        "study_name": opt_result.get("study_name"),
                    },
                    "test_performance": test_perf,
                }
                
                if "validate_dates" in fold_info and len(fold_info.get("validate_dates", [])) > 0:
                    validate_dates = fold_info["validate_dates"]
                    fold_result["validate_start"] = fold_info.get("validate_start")
                    fold_result["validate_end"] = fold_info.get("validate_end")
                    fold_result["validate_dates_count"] = len(validate_dates)
                
                # holdout_eval_yearをfold_resultに含める（並列化時の表示用）
                if "holdout_eval_year" in fold_info:
                    fold_result["holdout_eval_year"] = fold_info["holdout_eval_year"]
                
                return fold_result
            except Exception as e:
                import traceback
                print(f"  ❌ Fold {fold_info.get('fold', '?')}の処理中にエラー: {e}")
                traceback.print_exc()
                return {"fold": fold_info.get("fold", 0), "error": str(e)}
        
        # 並列実行
        with ProcessPoolExecutor(max_workers=n_jobs_fold) as executor:
            future_to_fold = {
                executor.submit(
                    _process_single_fold_wrapper,
                    fold_info,
                    horizon_months,
                    n_trials,
                    study_type,
                    seed,
                    cache_dir,
                    features_dict,
                    prices_dict,
                ): fold_info["fold"]
                for fold_info in folds
            }
            
            # 完了したfoldから順に処理
            for future in as_completed(future_to_fold):
                fold_num = future_to_fold[future]
                fold_result = future.result()
                
                if "error" in fold_result:
                    print(f"  ❌ Fold {fold_num}: {fold_result['error']}")
                    continue
                
                fold_results.append(fold_result)
                
                # 結果を表示
                print()
                print(f"[Fold {fold_result['fold']}/{len(folds)}] 完了")
                is_holdout = fold_result.get("is_holdout", False)
                if is_holdout:
                    if "holdout_eval_year" in fold_result:
                        eval_year = fold_result["holdout_eval_year"]
                        print(f"  ⭐ 最終ホールドアウト（評価終了年: {eval_year}年）")
                    else:
                        print(f"  ⭐ 最終ホールドアウト")
                print(f"  Train期間: {fold_result['train_start']} ～ {fold_result['train_end']} ({fold_result['train_dates_count']}日)")
                print(f"  Test期間: {fold_result['test_start']} ～ {fold_result['test_end']} ({fold_result['test_dates_count']}日)")
                test_perf = fold_result["test_performance"]
                print(f"  年率超過リターン（平均）: {test_perf.get('mean_annual_excess_return_pct', 0):.4f}%")
                print(f"  年率超過リターン（中央値）: {test_perf.get('median_annual_excess_return_pct', 0):.4f}%")
                print(f"  勝率: {test_perf.get('win_rate', 0):.2%}")
                print(f"  ポートフォリオ数: {test_perf.get('num_portfolios', 0)}")
        
        # fold番号順にソート
        fold_results.sort(key=lambda x: x["fold"])
    
    else:
        # 逐次実行（既存のコード）
        for fold_info in folds:
        fold_num = fold_info["fold"]
        train_dates = fold_info["train_dates"]
        test_dates = fold_info["test_dates"]
        
        print()
        is_holdout = fold_info.get("is_holdout", False)
        if is_holdout:
            if "holdout_eval_year" in fold_info:
                eval_year = fold_info["holdout_eval_year"]
                print(f"[Fold {fold_num}/{len(folds)}] ⭐ 最終ホールドアウト（評価終了年: {eval_year}年）")
            else:
                holdout_year = int(fold_info["test_start"].split("-")[0])
                print(f"[Fold {fold_num}/{len(folds)}] ⭐ 最終ホールドアウト（{holdout_year}年）")
        else:
            print(f"[Fold {fold_num}/{len(folds)}]")
        print(f"  Train期間: {fold_info['train_start']} ～ {fold_info['train_end']} ({len(train_dates)}日)")
        if "validate_dates" in fold_info and len(fold_info.get("validate_dates", [])) > 0:
            validate_dates = fold_info["validate_dates"]
            print(f"  Validate期間: {fold_info.get('validate_start', 'N/A')} ～ {fold_info.get('validate_end', 'N/A')} ({len(validate_dates)}日)")
        print(f"  Test期間: {fold_info['test_start']} ～ {fold_info['test_end']} ({len(test_dates)}日)")
        
        # 評価終了年ベースの確認（デバッグ用）
        if "holdout_eval_year" in fold_info:
            from dateutil.relativedelta import relativedelta
            from datetime import datetime
            print(f"  【評価終了年ベースの確認】")
            print(f"    Test: 評価終了年={fold_info['holdout_eval_year']} → リバランス年={sorted(set([int(d.split('-')[0]) for d in test_dates]))}")
            if "validate_dates" in fold_info and len(validate_dates) > 0:
                validate_eval_years = sorted(set([
                    (datetime.strptime(d, "%Y-%m-%d") + relativedelta(months=horizon_months)).year
                    for d in validate_dates
                ]))
                print(f"    Validate: 評価終了年={validate_eval_years} → リバランス年={sorted(set([int(d.split('-')[0]) for d in validate_dates]))}")
            train_eval_years = sorted(set([
                (datetime.strptime(d, "%Y-%m-%d") + relativedelta(months=horizon_months)).year
                for d in train_dates
            ]))
            print(f"    Train: 評価終了年={train_eval_years} → リバランス年={sorted(set([int(d.split('-')[0]) for d in train_dates]))}")
        
        # Train期間で最適化
        opt_result = run_optimization_for_fold(
            train_dates,
            n_trials=n_trials,
            study_type=study_type,
            seed=seed,
            cache_dir=cache_dir,
        )
        
        if opt_result is None:
            print(f"  ❌ Fold {fold_num}の最適化に失敗しました")
            continue
        
        best_params = opt_result["best_params"]
        best_value = opt_result["best_value"]
        
        # 最適化結果の詳細は既にrun_optimization_for_fold内で出力済み
        
        # Test期間でバックテスト（固定ホライズン）
        test_perf = run_backtest_with_fixed_params_longterm(
            test_dates,
            best_params,
            horizon_months=horizon_months,
            features_dict=features_dict,
            prices_dict=prices_dict,
        )
        
        fold_result = {
            "fold": fold_num,
            "train_start": fold_info["train_start"],
            "train_end": fold_info["train_end"],
            "test_start": fold_info["test_start"],
            "test_end": fold_info["test_end"],
            "train_dates_count": len(train_dates),
            "test_dates_count": len(test_dates),
            "is_holdout": is_holdout,
            "optimization": {
                "best_value": float(best_value) if best_value is not None else None,
                "best_params": best_params,
                "n_trials": n_trials,
                "best_trial_number": opt_result.get("best_trial_number"),
                "study_name": opt_result.get("study_name"),
            },
            "test_performance": test_perf,
        }
        
        if "validate_dates" in fold_info and len(fold_info.get("validate_dates", [])) > 0:
            validate_dates = fold_info["validate_dates"]
            fold_result["validate_start"] = fold_info.get("validate_start")
            fold_result["validate_end"] = fold_info.get("validate_end")
            fold_result["validate_dates_count"] = len(validate_dates)
        
        fold_results.append(fold_result)
        
        print(f"  ✓ Test期間の評価完了")
        print(f"    年率超過リターン（平均）: {test_perf.get('mean_annual_excess_return_pct', 0):.4f}%")
        print(f"    年率超過リターン（中央値）: {test_perf.get('median_annual_excess_return_pct', 0):.4f}%")
        print(f"    勝率: {test_perf.get('win_rate', 0):.2%}")
        print(f"    ポートフォリオ数: {test_perf.get('num_portfolios', 0)}")
    
    if not fold_results:
        raise RuntimeError("No fold results were calculated")
    
    # 集計
    test_mean_excess_returns = [
        r["test_performance"].get("mean_annual_excess_return_pct", 0)
        for r in fold_results
    ]
    test_median_excess_returns = [
        r["test_performance"].get("median_annual_excess_return_pct", 0)
        for r in fold_results
    ]
    test_win_rates = [
        r["test_performance"].get("win_rate", 0)
        for r in fold_results
    ]
    
    mean_mean_excess = np.mean(test_mean_excess_returns) if test_mean_excess_returns else 0.0
    median_mean_excess = np.median(test_mean_excess_returns) if test_mean_excess_returns else 0.0
    mean_median_excess = np.mean(test_median_excess_returns) if test_median_excess_returns else 0.0
    mean_win_rate = np.mean(test_win_rates) if test_win_rates else 0.0
    
    # 結果を表示
    print()
    print("=" * 80)
    print("【Walk-Forward Analysis結果】")
    print("=" * 80)
    print(f"Fold数: {len(fold_results)}")
    print()
    print("Test期間の年率超過リターン（平均）の統計:")
    print(f"  平均: {mean_mean_excess:.4f}%")
    print(f"  中央値: {median_mean_excess:.4f}%")
    print(f"  最小: {np.min(test_mean_excess_returns) if test_mean_excess_returns else 0:.4f}%")
    print(f"  最大: {np.max(test_mean_excess_returns) if test_mean_excess_returns else 0:.4f}%")
    print()
    print("Test期間の年率超過リターン（中央値）の平均:")
    print(f"  平均: {mean_median_excess:.4f}%")
    print()
    print("Test期間の勝率の平均:")
    print(f"  平均: {mean_win_rate:.2%}")
    print()
    
    # 結果を辞書にまとめる
    result = {
        "start_date": start_date,
        "end_date": end_date,
        "horizon_months": int(horizon_months),
        "n_folds": int(n_folds),
        "train_min_years": float(train_min_years),
        "n_trials": int(n_trials),
        "study_type": str(study_type),
        "use_2025_holdout": bool(use_2025_holdout),
        "fold_type": str(fold_type),
        "fold_results": fold_results,
        "summary": {
            "mean_mean_excess_return_pct": float(mean_mean_excess),
            "median_mean_excess_return_pct": float(median_mean_excess),
            "mean_median_excess_return_pct": float(mean_median_excess),
            "mean_win_rate": float(mean_win_rate),
            "min_mean_excess_return_pct": float(np.min(test_mean_excess_returns)) if test_mean_excess_returns else 0.0,
            "max_mean_excess_return_pct": float(np.max(test_mean_excess_returns)) if test_mean_excess_returns else 0.0,
        },
    }
    
    # 2025年ホールドアウトの結果を特別に表示
    if use_2025_holdout or holdout_eval_year is not None:
        holdout_results = [r for r in fold_results if r.get("is_holdout", False)]
        if holdout_results:
            holdout_result = holdout_results[0]
            holdout_perf = holdout_result["test_performance"]
            print()
            print("=" * 80)
            if "holdout_eval_year" in holdout_result:
                eval_year = holdout_result["holdout_eval_year"]
                print(f"⭐ 【評価終了年{eval_year}年最終ホールドアウト結果】")
            else:
                holdout_year = int(holdout_result["test_start"].split("-")[0])
                print(f"⭐ 【{holdout_year}年最終ホールドアウト結果】")
            print("=" * 80)
            print(f"Train期間: {holdout_result['train_start']} ～ {holdout_result['train_end']}")
            print(f"Test期間: {holdout_result['test_start']} ～ {holdout_result['test_end']}")
            print(f"年率超過リターン（平均）: {holdout_perf.get('mean_annual_excess_return_pct', 0):.4f}%")
            print(f"年率超過リターン（中央値）: {holdout_perf.get('median_annual_excess_return_pct', 0):.4f}%")
            print(f"勝率: {holdout_perf.get('win_rate', 0):.2%}")
            print(f"ポートフォリオ数: {holdout_perf.get('num_portfolios', 0)}")
            print()
            result["holdout_2025"] = {
                "test_performance": holdout_perf,
                "train_start": holdout_result["train_start"],
                "train_end": holdout_result["train_end"],
                "test_start": holdout_result["test_start"],
                "test_end": holdout_result["test_end"],
            }
    
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="長期保有型のWalk-Forward検証"
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="開始日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="終了日（YYYY-MM-DD）",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        required=True,
        choices=[12, 24, 36],
        help="ホライズン（月数: 12, 24, 36）",
    )
    parser.add_argument(
        "--folds",
        type=int,
        default=3,
        help="fold数（デフォルト: 3）",
    )
    parser.add_argument(
        "--train-min-years",
        type=float,
        default=2.0,
        help="最小Train期間（年、デフォルト: 2.0）",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=50,
        help="最適化の試行回数（デフォルト: 50）",
    )
    parser.add_argument(
        "--study-type",
        type=str,
        default="C",
        choices=["A", "B", "C"],
        help="スタディタイプ（A: BB寄り・低ROE、B: Value寄り・ROE高め、C: 統合・広範囲、デフォルト: C）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="乱数シード（デフォルト: None）",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="cache/features",
        help="キャッシュディレクトリ（デフォルト: cache/features）",
    )
    parser.add_argument(
        "--use-2025-holdout",
        action="store_true",
        help="2025年を最終ホールドアウトとして使用（デフォルト: False）",
    )
    parser.add_argument(
        "--fold-type",
        type=str,
        default="roll",
        choices=["roll", "simple"],
        help="foldタイプ（roll: ロール方式、simple: シンプル3分割、デフォルト: roll）",
    )
    parser.add_argument(
        "--holdout-eval-year",
        type=int,
        default=None,
        help="評価終了年でホールドアウトを指定（例: 2025、評価終了年ベース、デフォルト: None）",
    )
    parser.add_argument(
        "--n-jobs-fold",
        type=int,
        default=1,
        help="fold間の並列数（-1で自動、デフォルト: 1（逐次実行））",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="結果をJSONファイルに保存（Noneの場合は自動生成）",
    )
    
    args = parser.parse_args()
    
    try:
        result = run_walk_forward_analysis_longterm(
            start_date=args.start,
            end_date=args.end,
            horizon_months=args.horizon,
            n_folds=args.folds,
            train_min_years=args.train_min_years,
            n_trials=args.n_trials,
            study_type=args.study_type,
            seed=args.seed,
            cache_dir=args.cache_dir,
            use_2025_holdout=args.use_2025_holdout,
            fold_type=args.fold_type,
            holdout_eval_year=args.holdout_eval_year,
            n_jobs_fold=args.n_jobs_fold,
        )
        
        # 結果をJSONファイルに保存
        if args.output is None:
            output_file = f"walk_forward_longterm_{args.horizon}M.json"
        else:
            output_file = args.output
        
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"結果を保存しました: {output_file}")
        except Exception as e:
            print(f"❌ 結果の保存中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        print()
        print("=" * 80)
        print("✅ 処理が正常に完了しました")
        print("=" * 80)
        
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ エラーが発生しました: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        raise
    finally:
        # ターミナルが閉じないように待機（エラー時も含む）
        print()
        print("Enterキーを押して終了してください...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            # パイプやリダイレクト経由で実行されている場合は待機しない
            pass

