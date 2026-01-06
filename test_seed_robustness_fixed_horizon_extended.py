"""
固定ホライズン版 seed耐性テスト（拡張版：より長い期間）

より長い期間でテストして、テストポートフォリオ数を増やします。
各seedでテストポートフォリオ数が7本しかない問題を解決します。

Usage:
    python test_seed_robustness_fixed_horizon_extended.py \
        --json-file optimization_result_optimization_longterm_studyC_20260102_205614.json \
        --start 2018-01-01 \
        --end 2024-12-31 \
        --horizon 12 \
        --n-seeds 20
"""

import argparse
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta

# test_seed_robustness_fixed_horizon.pyの関数を再利用
from test_seed_robustness_fixed_horizon import (
    load_best_params,
    build_params_from_json,
    calculate_fixed_horizon_performance,
    get_monthly_rebalance_dates,
)
from omanta_3rd.backtest.feature_cache import FeatureCache
from omanta_3rd.jobs.optimize_longterm import split_rebalance_dates


def test_seed_robustness_fixed_horizon_extended(
    json_file: str,
    start_date: str,
    end_date: str,
    horizon_months: int,
    n_seeds: int = 20,
    train_ratio: float = 0.8,
    cost_bps: float = 0.0,
    cache_dir: str = "cache/features",
    n_jobs: int = -1,
) -> Dict[str, Any]:
    """
    固定ホライズン版 seed耐性テスト（拡張版：より長い期間）
    
    Args:
        json_file: 最良パラメータを含むJSONファイル
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        horizon_months: ホライズン（月数、例：12, 24, 36）
        n_seeds: テストするseedの数
        train_ratio: 学習データの割合
        cost_bps: 取引コスト（bps）
        cache_dir: キャッシュディレクトリ
        n_jobs: 並列数
    
    Returns:
        テスト結果の辞書
    """
    print("=" * 80)
    print(f"固定ホライズン版 seed耐性テスト（拡張版・{horizon_months}M）")
    print("=" * 80)
    print(f"JSONファイル: {json_file}")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"ホライズン: {horizon_months}ヶ月")
    print(f"テストseed数: {n_seeds}")
    print(f"学習/テスト分割: {train_ratio:.1%} / {1-train_ratio:.1%}")
    print()
    
    # 最良パラメータを読み込む
    print("最良パラメータを読み込みます...")
    best_params = load_best_params(json_file)
    strategy_params, entry_params = build_params_from_json(best_params)
    print("✓ パラメータ読み込み完了")
    print()
    
    # リバランス日を取得
    print("リバランス日を取得します...")
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"✓ リバランス日数: {len(rebalance_dates)}")
    print()
    
    # 特徴量キャッシュを構築
    print("特徴量キャッシュを構築します...")
    feature_cache = FeatureCache(cache_dir=cache_dir)
    features_dict, prices_dict = feature_cache.warm(
        rebalance_dates,
        n_jobs=-1
    )
    print(f"✓ 特徴量: {len(features_dict)}日分、価格データ: {len(prices_dict)}日分")
    print()
    
    # 各seedでテスト（並列化対応）
    print("=" * 80)
    print("各seedでテストデータのパフォーマンスを計算します...")
    print("=" * 80)
    
    # 並列化実行
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import multiprocessing as mp
    from dataclasses import fields
    from omanta_3rd.jobs.longterm_run import StrategyParams
    from omanta_3rd.jobs.optimize import EntryScoreParams
    
    # 並列数（デフォルト: CPU数、SQLite環境では制限）
    if n_jobs == -1:
        n_jobs = min(mp.cpu_count(), 4)  # SQLite環境では4並列まで推奨
    else:
        n_jobs = min(n_jobs, mp.cpu_count())
    
    # dataclassを辞書に変換（pickle可能にするため）
    strategy_params_dict = {
        field.name: getattr(strategy_params, field.name)
        for field in fields(StrategyParams)
    }
    entry_params_dict = {
        field.name: getattr(entry_params, field.name)
        for field in fields(EntryScoreParams)
    }
    
    test_results = []
    seed_details = []
    
    print(f"並列実行: {n_jobs}プロセス")
    
    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        # 全seedのタスクを投入
        future_to_seed = {
            executor.submit(
                _process_single_seed_wrapper,
                seed,
                rebalance_dates,
                train_ratio,
                horizon_months,
                cost_bps,
                strategy_params_dict,
                entry_params_dict,
                features_dict,
                prices_dict,
            ): seed
            for seed in range(1, n_seeds + 1)
        }
        
        # 完了したタスクから順に処理
        for future in as_completed(future_to_seed):
            seed, test_mean_excess_ann, seed_detail = future.result()
            
            if test_mean_excess_ann is not None and seed_detail is not None:
                test_results.append(test_mean_excess_ann)
                seed_details.append(seed_detail)
                
                print(f"\n[Seed {seed}/{n_seeds}]")
                print(f"  学習データ: {len(seed_detail['train_dates'])}日, テストデータ: {len(seed_detail['test_dates'])}日")
                print(f"  テストポートフォリオ数: {seed_detail.get('test_num_portfolios', 0)}")
                print(f"  テストデータ年率超過リターン（平均）: {test_mean_excess_ann:.4f}%")
    
    if not test_results:
        raise RuntimeError("No test results were calculated")
    
    # 統計を計算
    test_results_array = np.array(test_results)
    
    mean_val = np.mean(test_results_array)
    median_val = np.median(test_results_array)
    std_val = np.std(test_results_array)
    min_val = np.min(test_results_array)
    max_val = np.max(test_results_array)
    
    percentile_10 = np.percentile(test_results_array, 10)
    percentile_25 = np.percentile(test_results_array, 25)
    percentile_75 = np.percentile(test_results_array, 75)
    percentile_90 = np.percentile(test_results_array, 90)
    
    positive_ratio = np.sum(test_results_array > 0) / len(test_results_array)
    
    # テストポートフォリオ数の統計
    num_portfolios_list = [detail.get('test_num_portfolios', 0) for detail in seed_details]
    avg_num_portfolios = np.mean(num_portfolios_list) if num_portfolios_list else 0.0
    min_num_portfolios = np.min(num_portfolios_list) if num_portfolios_list else 0
    max_num_portfolios = np.max(num_portfolios_list) if num_portfolios_list else 0
    
    # 結果を表示
    print()
    print("=" * 80)
    print(f"【固定ホライズン{horizon_months}M seed耐性テスト結果（拡張版）】")
    print("=" * 80)
    print(f"テストseed数: {n_seeds}")
    print(f"最良パラメータ（固定）: {json_file}")
    print(f"期間: {start_date} ～ {end_date}")
    print()
    print("テストポートフォリオ数の統計:")
    print(f"  平均: {avg_num_portfolios:.1f}本")
    print(f"  最小: {min_num_portfolios}本")
    print(f"  最大: {max_num_portfolios}本")
    print()
    print("テストデータ年率超過リターン（平均）の分布:")
    print(f"  平均: {mean_val:.4f}%")
    print(f"  中央値: {median_val:.4f}%")
    print(f"  標準偏差: {std_val:.4f}%")
    print(f"  最小値: {min_val:.4f}%")
    print(f"  最大値: {max_val:.4f}%")
    print()
    print("パーセンタイル:")
    print(f"  下位10%: {percentile_10:.4f}%")
    print(f"  下位25%: {percentile_25:.4f}%")
    print(f"  上位25%: {percentile_75:.4f}%")
    print(f"  上位10%: {percentile_90:.4f}%")
    print()
    print(f"正の値の割合: {positive_ratio:.1%} ({np.sum(test_results_array > 0)}/{n_seeds})")
    print()
    
    # 合格判定（事前に固定）
    print("【合格判定】")
    if horizon_months == 12:
        # 12M: 中央値 > 0、正の割合 ≥ 60%
        passed = bool(median_val > 0 and positive_ratio >= 0.60)
        criteria = "中央値 > 0 かつ 正の割合 ≥ 60%"
    elif horizon_months == 24:
        # 24M: 中央値 > 0（正の割合は参考）
        passed = bool(median_val > 0)
        criteria = "中央値 > 0"
    else:  # 36M
        # 36M: 中央値が0付近でも「極端に悪くない」こと（p10が大崩れしない等）
        passed = bool(percentile_10 > -2.0)  # p10が-2%以上
        criteria = "下位10% > -2.0%"
    
    if passed:
        print(f"✅ 合格: {criteria}を満たしています")
    else:
        print(f"❌ 不合格: {criteria}を満たしていません")
    print()
    
    # 結果を辞書にまとめる（JSONシリアライズ可能な型に変換）
    result = {
        "json_file": json_file,
        "start_date": start_date,
        "end_date": end_date,
        "horizon_months": int(horizon_months),
        "n_seeds": int(n_seeds),
        "train_ratio": float(train_ratio),
        "test_results": [float(x) for x in test_results],
        "statistics": {
            "mean": float(mean_val),
            "median": float(median_val),
            "std": float(std_val),
            "min": float(min_val),
            "max": float(max_val),
            "percentile_10": float(percentile_10),
            "percentile_25": float(percentile_25),
            "percentile_75": float(percentile_75),
            "percentile_90": float(percentile_90),
            "positive_ratio": float(positive_ratio),
        },
        "portfolio_statistics": {
            "avg_num_portfolios": float(avg_num_portfolios),
            "min_num_portfolios": int(min_num_portfolios),
            "max_num_portfolios": int(max_num_portfolios),
        },
        "seed_details": [
            {
                "seed": int(detail["seed"]),
                "train_dates": detail["train_dates"],
                "test_dates": detail["test_dates"],
                "test_mean_annual_excess_return_pct": float(detail["test_mean_annual_excess_return_pct"]) if detail["test_mean_annual_excess_return_pct"] is not None else None,
                "test_median_annual_excess_return_pct": float(detail["test_median_annual_excess_return_pct"]) if detail["test_median_annual_excess_return_pct"] is not None else None,
                "test_mean_annual_return_pct": float(detail["test_mean_annual_return_pct"]) if detail["test_mean_annual_return_pct"] is not None else None,
                "test_win_rate": float(detail["test_win_rate"]) if detail["test_win_rate"] is not None else None,
                "test_num_portfolios": int(detail["test_num_portfolios"]) if detail["test_num_portfolios"] is not None else None,
            }
            for detail in seed_details
        ],
        "passed": bool(passed),
        "criteria": str(criteria),
    }
    
    return result


# 並列化用のグローバル関数（test_seed_robustness_fixed_horizon.pyから再利用）
# 注意: _process_single_seed_wrapperはグローバル関数として定義されているため、
# 直接インポートできない可能性があるため、同じ定義をここに含める
def _process_single_seed_wrapper(
    seed: int,
    rebalance_dates: List[str],
    train_ratio: float,
    horizon_months: int,
    cost_bps: float,
    strategy_params_dict: Dict[str, Any],
    entry_params_dict: Dict[str, Any],
    features_dict: Dict[str, pd.DataFrame],
    prices_dict: Dict[str, Dict[str, List[float]]],
) -> tuple[int, Optional[float], Optional[Dict[str, Any]]]:
    """単一seedの処理をラップ（並列化用）"""
    try:
        from omanta_3rd.jobs.longterm_run import StrategyParams
        from omanta_3rd.jobs.optimize import EntryScoreParams
        
        # dataclassを再構築
        strategy_params = StrategyParams(**strategy_params_dict)
        entry_params = EntryScoreParams(**entry_params_dict)

        # データ分割
        train_dates, test_dates = split_rebalance_dates(
            rebalance_dates,
            train_ratio=train_ratio,
            random_seed=seed,
        )

        # テストデータでパフォーマンスを計算（固定ホライズン）
        test_perf = calculate_fixed_horizon_performance(
            test_dates,
            strategy_params,
            entry_params,
            horizon_months=horizon_months,
            cost_bps=cost_bps,
            features_dict=features_dict,
            prices_dict=prices_dict,
        )

        test_mean_excess_ann = float(test_perf["mean_annual_excess_return_pct"])

        seed_detail = {
            "seed": int(seed),
            "train_dates": train_dates,
            "test_dates": test_dates,
            "test_mean_annual_excess_return_pct": test_mean_excess_ann,
            "test_median_annual_excess_return_pct": float(test_perf.get("median_annual_excess_return_pct", 0.0)),
            "test_mean_annual_return_pct": float(test_perf.get("mean_annual_return_pct", 0.0)),
            "test_win_rate": float(test_perf.get("win_rate", 0.0)),
            "test_num_portfolios": int(test_perf.get("num_portfolios", 0)),
        }

        return seed, test_mean_excess_ann, seed_detail
    except Exception as e:
        import traceback
        print(f"  [Seed {seed}] エラー: {e}")
        traceback.print_exc()
        return seed, None, None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="固定ホライズン版 seed耐性テスト（拡張版：より長い期間）"
    )
    parser.add_argument(
        "--json-file",
        type=str,
        required=True,
        help="最良パラメータを含むJSONファイル",
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
        "--n-seeds",
        type=int,
        default=20,
        help="テストするseedの数（デフォルト: 20）",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="学習データの割合（デフォルト: 0.8）",
    )
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=0.0,
        help="取引コスト（bps、デフォルト: 0.0）",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="cache/features",
        help="キャッシュディレクトリ（デフォルト: cache/features）",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=-1,
        help="並列数（-1で自動、デフォルト: -1）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="結果をJSONファイルに保存（Noneの場合は自動生成）",
    )
    
    args = parser.parse_args()
    
    try:
        result = test_seed_robustness_fixed_horizon_extended(
            json_file=args.json_file,
            start_date=args.start,
            end_date=args.end,
            horizon_months=args.horizon,
            n_seeds=args.n_seeds,
            train_ratio=args.train_ratio,
            cost_bps=args.cost_bps,
            cache_dir=args.cache_dir,
            n_jobs=args.n_jobs,
        )
        
        # 結果をJSONファイルに保存
        if args.output is None:
            output_file = f"seed_robustness_fixed_horizon_{args.horizon}M_extended.json"
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

