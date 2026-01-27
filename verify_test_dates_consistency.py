#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
optimize_longterm_mainとcompare_lambda_penaltiesでtest_datesが一致することを確認するスクリプト

ChatGPTのフィードバックに基づき、「この修正で compare と optimize の test_dates が必ず一致する」
の根拠を確認するためのスクリプトです。
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from dateutil.relativedelta import relativedelta

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

from omanta_3rd.jobs.batch_longterm_run import get_monthly_rebalance_dates
from omanta_3rd.jobs.optimize_longterm import split_rebalance_dates


def verify_test_dates_consistency(
    start_date: str = "2018-01-01",
    end_date: str = "2023-12-31",
    as_of_date: str = "2023-12-31",
    train_end_date: str = "2022-12-31",
    horizon_months: int = 24,
):
    """
    optimize_longterm_mainとcompare_lambda_penaltiesでtest_datesが一致することを確認
    
    Args:
        start_date: 開始日
        end_date: 終了日
        as_of_date: 評価日
        train_end_date: 学習期間終了日
        horizon_months: ホライズン（月数）
    """
    print("=" * 80)
    print("test_datesの一致確認")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"評価日: {as_of_date}")
    print(f"学習期間終了日: {train_end_date}")
    print(f"ホライズン: {horizon_months}M")
    print()
    
    # リバランス日を取得
    evaluation_end_date = as_of_date if as_of_date else end_date
    rebalance_dates = get_monthly_rebalance_dates(start_date, evaluation_end_date)
    print(f"リバランス日数: {len(rebalance_dates)}")
    print(f"最初: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
    print(f"最後: {rebalance_dates[-1] if rebalance_dates else 'N/A'}")
    print()
    
    # optimize_longterm_mainと同じロジックでtest_datesを計算
    print("【optimize_longterm_mainのロジック】")
    print("-" * 80)
    try:
        train_dates_opt, test_dates_opt = split_rebalance_dates(
            rebalance_dates,
            train_ratio=0.8,
            random_seed=42,
            time_series_split=True,
            train_end_date=train_end_date,
            horizon_months=horizon_months,
            require_full_horizon=True,
            as_of_date=as_of_date,
        )
        
        # 24Mホライズンの場合、test_datesが空になったら再計算
        if horizon_months == 24 and as_of_date and train_end_date and not test_dates_opt:
            as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
            test_max_dt = as_of_dt - relativedelta(months=24)
            test_max_date = test_max_dt.strftime("%Y-%m-%d")
            
            train_end_dt = datetime.strptime(train_end_date, "%Y-%m-%d")
            train_max_dt = train_end_dt - relativedelta(months=24)
            train_max_date = train_max_dt.strftime("%Y-%m-%d")
            
            # test期間は (train_max_dt, test_max_dt] に限定
            test_dates_opt = []
            for d in rebalance_dates:
                d_dt = datetime.strptime(d, "%Y-%m-%d")
                if d_dt > train_max_dt and d_dt <= test_max_dt:
                    test_dates_opt.append(d)
            
            print(f"⚠️  test_datesが空のため、再計算しました")
            print(f"   train_max_rb: {train_max_date}")
            print(f"   test_max_rb: {test_max_date}")
        
        print(f"train_dates: {len(train_dates_opt)}件")
        print(f"  最初: {train_dates_opt[0] if train_dates_opt else 'N/A'}")
        print(f"  最後: {train_dates_opt[-1] if train_dates_opt else 'N/A'}")
        print(f"test_dates: {len(test_dates_opt)}件")
        print(f"  最初: {test_dates_opt[0] if test_dates_opt else 'N/A'}")
        print(f"  最後: {test_dates_opt[-1] if test_dates_opt else 'N/A'}")
        
        # 境界確認
        if train_dates_opt and test_dates_opt:
            train_last_dt = datetime.strptime(train_dates_opt[-1], "%Y-%m-%d")
            test_first_dt = datetime.strptime(test_dates_opt[0], "%Y-%m-%d")
            if train_last_dt >= test_first_dt:
                print(f"   ⚠️  警告: train_datesの最終日({train_dates_opt[-1]}) >= test_datesの最初日({test_dates_opt[0]}) - 重複の可能性")
            else:
                print(f"   ✓ 境界確認OK: train_datesの最終日({train_dates_opt[-1]}) < test_datesの最初日({test_dates_opt[0]})")
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # compare_lambda_penaltiesと同じロジックでtest_datesを計算
    print("【compare_lambda_penaltiesのロジック】")
    print("-" * 80)
    try:
        as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
        test_max_dt = as_of_dt - relativedelta(months=24)
        test_max_date = test_max_dt.strftime("%Y-%m-%d")
        
        train_end_dt = datetime.strptime(train_end_date, "%Y-%m-%d")
        train_max_dt = train_end_dt - relativedelta(months=24)
        train_max_date = train_max_dt.strftime("%Y-%m-%d")
        
        # 生成範囲はtest_max_dtまで
        all_dates = get_monthly_rebalance_dates(start_date, test_max_date)
        
        # test期間は (train_max_dt, test_max_dt] に限定
        test_dates_compare = []
        for d in all_dates:
            d_dt = datetime.strptime(d, "%Y-%m-%d")
            if d_dt > train_max_dt and d_dt <= test_max_dt:
                test_dates_compare.append(d)
        
        print(f"train_max_rb: {train_max_date}")
        print(f"test_max_rb: {test_max_date}")
        print(f"test_dates: {len(test_dates_compare)}件")
        print(f"  最初: {test_dates_compare[0] if test_dates_compare else 'N/A'}")
        print(f"  最後: {test_dates_compare[-1] if test_dates_compare else 'N/A'}")
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # 比較
    print("【比較結果】")
    print("-" * 80)
    
    # test_datesの一致確認
    test_dates_opt_set = set(test_dates_opt)
    test_dates_compare_set = set(test_dates_compare)
    
    if test_dates_opt_set == test_dates_compare_set:
        print("✅ test_dates: 完全一致")
        print(f"   件数: {len(test_dates_opt)}件")
        print(f"   内容: {sorted(test_dates_opt)}")
    else:
        print("❌ test_dates: 不一致")
        only_opt = test_dates_opt_set - test_dates_compare_set
        only_compare = test_dates_compare_set - test_dates_opt_set
        if only_opt:
            print(f"   optimizeのみ: {sorted(only_opt)}")
        if only_compare:
            print(f"   compareのみ: {sorted(only_compare)}")
        common = test_dates_opt_set & test_dates_compare_set
        print(f"   共通: {len(common)}件 / optimize: {len(test_dates_opt)}件 / compare: {len(test_dates_compare)}件")
    
    print()
    
    # 境界確認の詳細
    if train_dates_opt and test_dates_opt:
        print("【境界確認の詳細】")
        print("-" * 80)
        train_last_dt = datetime.strptime(train_dates_opt[-1], "%Y-%m-%d")
        test_first_dt = datetime.strptime(test_dates_opt[0], "%Y-%m-%d")
        train_max_dt = train_end_dt - relativedelta(months=24)
        
        print(f"train_datesの最終日: {train_dates_opt[-1]} ({train_last_dt})")
        print(f"test_datesの最初日: {test_dates_opt[0]} ({test_first_dt})")
        print(f"train_max_rb (境界): {train_max_date} ({train_max_dt})")
        print(f"差（日数）: {(test_first_dt - train_last_dt).days}日")
        
        if train_last_dt >= test_first_dt:
            print("⚠️  警告: train_datesとtest_datesが重複している可能性があります")
        else:
            print("✓ 境界確認OK: train_datesとtest_datesは重複していません")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="test_datesの一致確認")
    parser.add_argument("--start", type=str, default="2018-01-01", help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, default="2023-12-31", help="終了日（YYYY-MM-DD）")
    parser.add_argument("--as-of", type=str, default="2023-12-31", help="評価日（YYYY-MM-DD）")
    parser.add_argument("--train-end", type=str, default="2022-12-31", help="学習期間終了日（YYYY-MM-DD）")
    parser.add_argument("--horizon", type=int, default=24, help="ホライズン（月数）")
    
    args = parser.parse_args()
    
    verify_test_dates_consistency(
        start_date=args.start,
        end_date=args.end,
        as_of_date=args.as_of,
        train_end_date=args.train_end,
        horizon_months=args.horizon,
    )

