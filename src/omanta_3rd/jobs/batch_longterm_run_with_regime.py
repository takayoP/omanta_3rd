"""
長期保有型：レジーム切替対応のバッチポートフォリオ作成スクリプト

各リバランス日で市場レジームを判定し、レジームに応じたパラメータを使用して
ポートフォリオを作成します。

【注意】このスクリプトは長期保有型専用です。
月次リバランス型の運用には使用しません。

使用方法:
    python -m omanta_3rd.jobs.batch_longterm_run_with_regime --start 2020-01-01 --end 2025-12-31
    python -m omanta_3rd.jobs.batch_longterm_run_with_regime --start 2020-01-01 --end 2025-12-31 --fixed-params operational_24M
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import pandas as pd

from ..infra.db import connect_db
from ..jobs.longterm_run import build_features, select_portfolio, save_features, save_portfolio
from ..backtest.performance import calculate_portfolio_performance, save_performance_to_db
from ..jobs.batch_longterm_run import get_monthly_rebalance_dates
from ..market.regime import get_market_regime
from ..config.regime_policy import get_params_id_for_regime
from ..config.params_registry import load_params_by_id_longterm, get_registry_entry
from ..config.settings import PROJECT_ROOT
from ..jobs.params_utils import normalize_params


def save_regime_switch_log(
    log_data: Dict[str, Any],
    output_dir: Optional[Path] = None,
) -> Path:
    """
    レジーム切替ログをJSONL形式で保存
    
    Args:
        log_data: ログデータ
        output_dir: 出力ディレクトリ（Noneの場合はoutputs/longterm）
    
    Returns:
        保存先ファイルパス
    """
    if output_dir is None:
        output_dir = PROJECT_ROOT / "outputs" / "longterm"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "regime_switch_log.jsonl"
    
    # JSONL形式で追記
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_data, ensure_ascii=False) + '\n')
    
    return log_file


def run_monthly_portfolio_with_regime(
    rebalance_date: str,
    fixed_params_id: Optional[str] = None,
    calculate_performance: bool = True,
    as_of_date: Optional[str] = None,
    save_log: bool = True,
) -> dict:
    """
    レジーム切替対応の月次ポートフォリオ作成
    
    Args:
        rebalance_date: リバランス日（YYYY-MM-DD）
        fixed_params_id: 固定パラメータID（Noneの場合はレジーム切替、指定の場合は固定）
        calculate_performance: パフォーマンスを計算するか
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新）
        save_log: ログを保存するか
    
    Returns:
        実行結果の辞書
    """
    result = {
        "rebalance_date": rebalance_date,
        "portfolio_created": False,
        "performance_calculated": False,
        "error": None,
        "regime": None,
        "params_id": None,
    }
    
    try:
        with connect_db() as conn:
            # 1. レジーム判定とパラメータ決定
            if fixed_params_id:
                # 固定パラメータモード
                params_id = fixed_params_id
                regime_info = None
                regime = "fixed"
            else:
                # レジーム切替モード
                regime_info = get_market_regime(conn, rebalance_date)
                regime = regime_info["regime"]
                params_id = get_params_id_for_regime(regime)
            
            result["regime"] = regime
            result["params_id"] = params_id
            
            # 2. パラメータを読み込む
            params_dict = load_params_by_id_longterm(params_id)
            registry_entry = get_registry_entry(params_id)
            horizon_months = registry_entry.get("horizon_months")
            
            # パラメータ辞書をStrategyParamsとEntryScoreParamsに変換
            strategy_params, entry_params = normalize_params(params_dict)
            
            print(f"[{rebalance_date}] レジーム: {regime}, パラメータID: {params_id}, ホライズン: {horizon_months}M")
            
            # 3. 特徴量を構築（パラメータ対応）
            print(f"[{rebalance_date}] 特徴量を構築中...")
            feat = build_features(conn, rebalance_date, strategy_params=strategy_params, entry_params=entry_params)
            
            if feat.empty:
                result["error"] = "特徴量が空です"
                return result
            
            # 4. ポートフォリオを選択（パラメータ対応）
            print(f"[{rebalance_date}] ポートフォリオを選択中...")
            portfolio = select_portfolio(feat, strategy_params=strategy_params)
            
            if portfolio.empty:
                result["error"] = "ポートフォリオが空です"
                return result
            
            # 5. データベースに保存
            print(f"[{rebalance_date}] データベースに保存中...")
            save_features(conn, feat)
            save_portfolio(conn, portfolio)
            
            result["portfolio_created"] = True
            result["num_stocks"] = len(portfolio)
            
            # 6. パフォーマンスを計算
            if calculate_performance:
                print(f"[{rebalance_date}] パフォーマンスを計算中...")
                performance = calculate_portfolio_performance(rebalance_date, as_of_date)
                
                if "error" not in performance:
                    save_performance_to_db(performance)
                    result["performance_calculated"] = True
                    result["total_return_pct"] = performance.get("total_return_pct")
                else:
                    result["error"] = performance.get("error", "パフォーマンス計算エラー")
            
            # 7. ログを保存
            if save_log:
                log_data = {
                    "date": rebalance_date,
                    "regime": regime,
                    "params_id": params_id,
                    "horizon_months": horizon_months,
                    "regime_info": regime_info if regime_info else None,
                    "core_top80": feat.nlargest(80, "core_score")["code"].tolist() if len(feat) >= 80 else feat["code"].tolist(),
                    "final_selected": portfolio["code"].tolist(),
                    "num_stocks": len(portfolio),
                }
                log_file = save_regime_switch_log(log_data)
                result["log_file"] = str(log_file)
            
            print(f"[{rebalance_date}] ✅ 完了")
            return result
            
    except Exception as e:
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
        return result


def main(
    start_date: str,
    end_date: str,
    fixed_params_id: Optional[str] = None,
    calculate_performance: bool = True,
    as_of_date: Optional[str] = None,
    skip_existing: bool = True,
    save_log: bool = True,
):
    """
    メイン処理
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        fixed_params_id: 固定パラメータID（Noneの場合はレジーム切替）
        calculate_performance: パフォーマンスを計算するか
        as_of_date: 評価日（YYYY-MM-DD、Noneの場合は最新）
        skip_existing: 既存のポートフォリオをスキップするか
        save_log: ログを保存するか
    """
    print("=" * 80)
    print("レジーム切替対応バッチ月次ポートフォリオ作成")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    if fixed_params_id:
        print(f"モード: 固定パラメータ ({fixed_params_id})")
    else:
        print(f"モード: レジーム切替")
    print(f"パフォーマンス計算: {'有効' if calculate_performance else '無効'}")
    if as_of_date:
        print(f"評価日: {as_of_date}")
    else:
        print(f"評価日: 最新の価格データ")
    print("=" * 80)
    print()
    
    # 各月の最終営業日を取得
    print("各月の最終営業日を取得中...")
    rebalance_dates = get_monthly_rebalance_dates(start_date, end_date)
    print(f"✅ {len(rebalance_dates)}個のリバランス日を取得しました")
    print(f"   最初: {rebalance_dates[0] if rebalance_dates else 'N/A'}")
    print(f"   最後: {rebalance_dates[-1] if rebalance_dates else 'N/A'}")
    print()
    
    if not rebalance_dates:
        print("❌ リバランス日が見つかりませんでした")
        return 1
    
    # 既存のポートフォリオを確認
    if skip_existing:
        with connect_db() as conn:
            existing_dates_df = pd.read_sql_query(
                "SELECT DISTINCT rebalance_date FROM portfolio_monthly",
                conn
            )
            existing_dates = set(existing_dates_df["rebalance_date"].tolist()) if not existing_dates_df.empty else set()
            rebalance_dates = [d for d in rebalance_dates if d not in existing_dates]
            print(f"既存のポートフォリオをスキップ: {len(rebalance_dates)}個の日付を処理します")
            print()
    
    # 各日付でポートフォリオを作成
    results = []
    success_count = 0
    error_count = 0
    
    for i, rebalance_date in enumerate(rebalance_dates, 1):
        print(f"[{i}/{len(rebalance_dates)}] {rebalance_date} を処理中...")
        result = run_monthly_portfolio_with_regime(
            rebalance_date,
            fixed_params_id=fixed_params_id,
            calculate_performance=calculate_performance,
            as_of_date=as_of_date,
            save_log=save_log,
        )
        results.append(result)
        
        if result["error"]:
            error_count += 1
            print(f"  ❌ エラー: {result['error']}")
        else:
            success_count += 1
            if result["portfolio_created"]:
                print(f"  ✅ ポートフォリオ作成成功 ({result.get('num_stocks', 0)}銘柄)")
            if result["performance_calculated"]:
                return_pct = result.get("total_return_pct")
                if return_pct is not None:
                    print(f"  ✅ パフォーマンス計算成功 (リターン: {return_pct:.2f}%)")
        print()
    
    # 結果サマリー
    print("=" * 80)
    print("【実行結果サマリー】")
    print("=" * 80)
    print(f"総処理数: {len(rebalance_dates)}")
    print(f"成功: {success_count}")
    print(f"エラー: {error_count}")
    print()
    
    # レジーム分布
    if not fixed_params_id:
        regime_counts = {}
        for result in results:
            if result.get("regime"):
                regime = result["regime"]
                regime_counts[regime] = regime_counts.get(regime, 0) + 1
        if regime_counts:
            print("レジーム分布:")
            for regime, count in sorted(regime_counts.items()):
                print(f"  {regime}: {count}回")
            print()
    
    if error_count > 0:
        print("エラーが発生した日付:")
        for result in results:
            if result["error"]:
                print(f"  - {result['rebalance_date']}: {result['error']}")
        print()
    
    print("=" * 80)
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="レジーム切替対応のバッチ月次ポートフォリオ作成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # レジーム切替モード
  python -m omanta_3rd.jobs.batch_longterm_run_with_regime --start 2020-01-01 --end 2025-12-31
  
  # 固定パラメータモード
  python -m omanta_3rd.jobs.batch_longterm_run_with_regime --start 2020-01-01 --end 2025-12-31 --fixed-params operational_24M
  
  # パフォーマンス計算をスキップ
  python -m omanta_3rd.jobs.batch_longterm_run_with_regime --start 2020-01-01 --end 2025-12-31 --no-performance
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
        "--fixed-params",
        type=str,
        dest="fixed_params_id",
        default=None,
        help="固定パラメータID（指定しない場合はレジーム切替モード）",
    )
    parser.add_argument(
        "--as-of-date",
        type=str,
        dest="as_of_date",
        default=None,
        help="評価日（YYYY-MM-DD、Noneの場合は最新）",
    )
    parser.add_argument(
        "--no-performance",
        action="store_true",
        help="パフォーマンス計算をスキップ",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="既存のポートフォリオも再作成",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="ログを保存しない",
    )
    
    args = parser.parse_args()
    
    sys.exit(main(
        start_date=args.start,
        end_date=args.end,
        fixed_params_id=args.fixed_params_id,
        calculate_performance=not args.no_performance,
        as_of_date=args.as_of_date,
        skip_existing=not args.no_skip_existing,
        save_log=not args.no_log,
    ))

