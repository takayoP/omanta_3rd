"""
整合性チェックスクリプト（A-0）

レジーム切替の整合性をチェックします：
1. 各リバランス日で、レジーム判定に使ったTOPIX終値の最終日が d（=月末終値を含める運用）になっているか
2. MAが足りない初期期間が range になること
3. regime → params_id がポリシー通りに選ばれていること（up/down/rangeの分布も出す）
4. params_id に応じて horizon_months が切り替わっていること（12/24が混在しているはず）

使用方法:
    python -m omanta_3rd.jobs.check_regime_consistency --start 2020-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd

from ..infra.db import connect_db
from ..jobs.batch_longterm_run import get_monthly_rebalance_dates
from ..market.regime import get_market_regime, get_topix_close_series
from ..config.regime_policy import get_params_id_for_regime
from ..config.params_registry import get_registry_entry
from ..config.settings import PROJECT_ROOT


def check_regime_consistency(
    start_date: str,
    end_date: str,
    output_path: str | None = None,
) -> Dict[str, Any]:
    """
    レジーム切替の整合性をチェック
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        output_path: 出力パス（Noneの場合は標準出力）
    
    Returns:
        チェック結果の辞書
    """
    print("=" * 80)
    print("レジーム切替整合性チェック")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print("=" * 80)
    print()
    
    # リバランス日を取得
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"リバランス日数: {len(rebalance_dates)}")
    print()
    
    results = []
    errors = []
    regime_counts = {"up": 0, "down": 0, "range": 0}
    params_id_counts = {}
    horizon_months_counts = {}
    
    with connect_db() as conn:
        for rebalance_date in rebalance_dates:
            result = {
                "rebalance_date": rebalance_date,
                "errors": [],
                "warnings": [],
            }
            
            # 1. TOPIX終値の最終日が rebalance_date になっているかチェック
            topix_close = get_topix_close_series(conn, rebalance_date, lookback_days=250)
            if not topix_close.empty:
                topix_last_date = topix_close.index[-1].strftime("%Y-%m-%d")
                if topix_last_date != rebalance_date:
                    error_msg = f"TOPIX終値の最終日が一致しません: {topix_last_date} != {rebalance_date}"
                    result["errors"].append(error_msg)
                    errors.append(f"{rebalance_date}: {error_msg}")
            else:
                error_msg = f"TOPIX終値データが取得できませんでした"
                result["errors"].append(error_msg)
                errors.append(f"{rebalance_date}: {error_msg}")
            
            # 2. レジーム判定
            regime_info = get_market_regime(conn, rebalance_date)
            regime = regime_info["regime"]
            result["regime"] = regime
            result["regime_info"] = regime_info
            
            # MAが足りない初期期間が range になること
            if len(topix_close) < 200:
                if regime != "range":
                    error_msg = f"MAが足りない初期期間なのに range ではありません: {regime}"
                    result["errors"].append(error_msg)
                    errors.append(f"{rebalance_date}: {error_msg}")
                else:
                    result["warnings"].append("MAが足りない初期期間（range扱い）")
            
            # 3. regime → params_id がポリシー通りに選ばれているか
            try:
                params_id = get_params_id_for_regime(regime)
                result["params_id"] = params_id
                
                # ポリシー確認
                expected_params_id = get_params_id_for_regime(regime)
                if params_id != expected_params_id:
                    error_msg = f"params_idがポリシーと一致しません: {params_id} != {expected_params_id}"
                    result["errors"].append(error_msg)
                    errors.append(f"{rebalance_date}: {error_msg}")
            except Exception as e:
                error_msg = f"params_id取得エラー: {str(e)}"
                result["errors"].append(error_msg)
                errors.append(f"{rebalance_date}: {error_msg}")
                params_id = None
            
            # 4. horizon_months が切り替わっているか
            if params_id:
                try:
                    registry_entry = get_registry_entry(params_id)
                    horizon_months = registry_entry.get("horizon_months")
                    result["horizon_months"] = horizon_months
                    
                    # カウント
                    horizon_months_counts[horizon_months] = horizon_months_counts.get(horizon_months, 0) + 1
                except Exception as e:
                    error_msg = f"horizon_months取得エラー: {str(e)}"
                    result["errors"].append(error_msg)
                    errors.append(f"{rebalance_date}: {error_msg}")
            
            # カウント
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
            if params_id:
                params_id_counts[params_id] = params_id_counts.get(params_id, 0) + 1
            
            results.append(result)
    
    # 結果サマリー
    print("=" * 80)
    print("【チェック結果サマリー】")
    print("=" * 80)
    
    # エラー数
    total_errors = sum(len(r["errors"]) for r in results)
    total_warnings = sum(len(r["warnings"]) for r in results)
    print(f"総エラー数: {total_errors}")
    print(f"総警告数: {total_warnings}")
    print()
    
    # レジーム分布
    print("レジーム分布:")
    for regime, count in sorted(regime_counts.items()):
        pct = (count / len(rebalance_dates)) * 100.0 if rebalance_dates else 0.0
        print(f"  {regime}: {count}回 ({pct:.1f}%)")
    print()
    
    # params_id分布
    print("params_id分布:")
    for params_id, count in sorted(params_id_counts.items()):
        pct = (count / len(rebalance_dates)) * 100.0 if rebalance_dates else 0.0
        print(f"  {params_id}: {count}回 ({pct:.1f}%)")
    print()
    
    # horizon_months分布
    print("horizon_months分布:")
    for horizon_months, count in sorted(horizon_months_counts.items()):
        pct = (count / len(rebalance_dates)) * 100.0 if rebalance_dates else 0.0
        print(f"  {horizon_months}M: {count}回 ({pct:.1f}%)")
    print()
    
    # エラー詳細
    if errors:
        print("=" * 80)
        print("【エラー詳細】")
        print("=" * 80)
        for error in errors[:20]:  # 最初の20件のみ表示
            print(f"  - {error}")
        if len(errors) > 20:
            print(f"  ... 他 {len(errors) - 20} 件のエラー")
        print()
    
    # 結果をJSONで出力
    output_data = {
        "summary": {
            "total_dates": len(rebalance_dates),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "regime_distribution": regime_counts,
            "params_id_distribution": params_id_counts,
            "horizon_months_distribution": horizon_months_counts,
        },
        "errors": errors,
        "results": results,
    }
    
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"結果を {output_path} に保存しました")
    else:
        # 標準出力にJSONを出力
        print("=" * 80)
        print("【JSON出力】")
        print("=" * 80)
        print(json.dumps(output_data, ensure_ascii=False, indent=2))
    
    print("=" * 80)
    
    return output_data


def main(
    start_date: str,
    end_date: str,
    output_path: str | None = None,
):
    """
    メイン処理
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        output_path: 出力パス（Noneの場合は標準出力）
    """
    result = check_regime_consistency(start_date, end_date, output_path)
    
    # エラーがある場合は終了コード1を返す
    if result["summary"]["total_errors"] > 0:
        return 1
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="レジーム切替整合性チェック",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 整合性チェックを実行
  python -m omanta_3rd.jobs.check_regime_consistency --start 2020-01-01 --end 2025-12-31
  
  # 結果をファイルに保存
  python -m omanta_3rd.jobs.check_regime_consistency --start 2020-01-01 --end 2025-12-31 --output outputs/consistency_check.json
        """
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
        "--output",
        type=str,
        dest="output_path",
        default=None,
        help="出力パス（Noneの場合は標準出力）",
    )
    
    args = parser.parse_args()
    
    sys.exit(main(
        start_date=args.start,
        end_date=args.end,
        output_path=args.output_path,
    ))

