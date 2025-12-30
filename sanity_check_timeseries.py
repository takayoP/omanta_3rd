"""
時系列P/L計算のサニティチェックスクリプト

時系列版のバックテスト結果が妥当かどうかを検証します。
"""

from __future__ import annotations

import sys
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

from omanta_3rd.backtest.timeseries import calculate_timeseries_returns
from omanta_3rd.backtest.metrics import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_volatility_timeseries,
)
from omanta_3rd.infra.db import connect_db


def check_topix_monthly_returns(
    timeseries_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    TOPIXの月次リターン分布をチェック
    
    Args:
        timeseries_data: calculate_timeseries_returns()の戻り値
    
    Returns:
        チェック結果の辞書
    """
    portfolio_details = timeseries_data.get("portfolio_details", [])
    
    if not portfolio_details:
        return {
            "status": "ERROR",
            "message": "ポートフォリオ詳細がありません",
        }
    
    topix_returns = [
        detail["topix_return"] * 100.0  # %換算
        for detail in portfolio_details
        if detail.get("topix_return") is not None
    ]
    
    if not topix_returns:
        return {
            "status": "ERROR",
            "message": "TOPIXリターンが計算されていません",
        }
    
    topix_array = np.array(topix_returns)
    mean_return = np.mean(topix_array)
    std_return = np.std(topix_array, ddof=1)
    min_return = np.min(topix_array)
    max_return = np.max(topix_array)
    
    # 詳細統計（percentile）
    p1 = np.percentile(topix_array, 1)
    median = np.median(topix_array)
    p99 = np.percentile(topix_array, 99)
    
    # チェック基準
    checks = []
    
    # 1. 平均が常識的か（±数%/月）
    if abs(mean_return) > 10.0:
        checks.append({
            "check": "平均リターンが異常",
            "value": f"{mean_return:.2f}%",
            "expected": "±数%/月",
            "status": "WARNING",
        })
    else:
        checks.append({
            "check": "平均リターン",
            "value": f"{mean_return:.2f}%",
            "expected": "±数%/月",
            "status": "OK",
        })
    
    # 2. 最小値がリーマン級（-20%/月）以下でないか
    if min_return < -20.0:
        checks.append({
            "check": "最小リターンが異常",
            "value": f"{min_return:.2f}%",
            "expected": ">-20%/月（リーマン級）",
            "status": "WARNING",
        })
    else:
        checks.append({
            "check": "最小リターン",
            "value": f"{min_return:.2f}%",
            "expected": ">-20%/月",
            "status": "OK",
        })
    
    # 3. 最大値が+20%/月以下か
    if max_return > 20.0:
        checks.append({
            "check": "最大リターンが異常",
            "value": f"{max_return:.2f}%",
            "expected": "<+20%/月",
            "status": "WARNING",
        })
    else:
        checks.append({
            "check": "最大リターン",
            "value": f"{max_return:.2f}%",
            "expected": "<+20%/月",
            "status": "OK",
        })
    
    # 4. 標準偏差が常識的か（月次で5-10%程度）
    if std_return > 15.0:
        checks.append({
            "check": "標準偏差が異常に大きい",
            "value": f"{std_return:.2f}%",
            "expected": "5-10%/月程度",
            "status": "WARNING",
        })
    else:
        checks.append({
            "check": "標準偏差",
            "value": f"{std_return:.2f}%",
            "expected": "5-10%/月程度",
            "status": "OK",
        })
    
    overall_status = "OK" if all(c["status"] == "OK" for c in checks) else "WARNING"
    
    return {
        "status": overall_status,
        "summary": {
            "count": len(topix_returns),
            "mean": mean_return,
            "std": std_return,
            "min": min_return,
            "p1": p1,
            "median": median,
            "p99": p99,
            "max": max_return,
        },
        "checks": checks,
    }


def check_individual_stock_returns(
    timeseries_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    個別銘柄の月次リターンをチェック
    
    Args:
        timeseries_data: calculate_timeseries_returns()の戻り値
    
    Returns:
        チェック結果の辞書
    """
    portfolio_details = timeseries_data.get("portfolio_details", [])
    
    if not portfolio_details:
        return {
            "status": "ERROR",
            "message": "ポートフォリオ詳細がありません",
        }
    
    # 各ポートフォリオの詳細から個別銘柄のリターンを抽出
    # 注意: 現状のtimeseries.pyでは個別銘柄のリターンは返していないため、
    # ここではポートフォリオ全体のリターンをチェック
    portfolio_returns = [
        detail["portfolio_return_net"] * 100.0  # %換算
        for detail in portfolio_details
        if detail.get("portfolio_return_net") is not None
    ]
    
    if not portfolio_returns:
        return {
            "status": "ERROR",
            "message": "ポートフォリオリターンが計算されていません",
        }
    
    returns_array = np.array(portfolio_returns)
    
    # 異常値チェック（+200%以上 or <-80%）
    extreme_positive = returns_array[returns_array > 200.0]
    extreme_negative = returns_array[returns_array < -80.0]
    
    checks = []
    
    if len(extreme_positive) > 0:
        # 上位10件を取得
        top_10 = np.sort(extreme_positive)[-10:][::-1]  # 降順
        checks.append({
            "check": "異常に大きなリターンが検出",
            "value": f"{len(extreme_positive)}件（最大: {np.max(extreme_positive):.2f}%）",
            "expected": "0件（+200%/月は異常）",
            "status": "ERROR",
            "message": "株式分割・併合・データ欠損・調整前価格を疑う",
            "top_10": top_10.tolist(),
        })
    else:
        checks.append({
            "check": "異常に大きなリターン",
            "value": "0件",
            "expected": "0件",
            "status": "OK",
        })
    
    # 負の異常値チェック（-80%以下）
    if len(extreme_negative) > 0:
        # 下位10件を取得
        bottom_10 = np.sort(extreme_negative)[:10]  # 昇順
        checks.append({
            "check": "異常に大きな損失が検出",
            "value": f"{len(extreme_negative)}件（最小: {np.min(extreme_negative):.2f}%）",
            "expected": "0件（-80%/月は異常）",
            "status": "WARNING",
            "bottom_10": bottom_10.tolist(),
        })
    else:
        checks.append({
            "check": "異常に大きな損失",
            "value": "0件",
            "expected": "0件",
            "status": "OK",
        })
    
    overall_status = "OK"
    if any(c["status"] == "ERROR" for c in checks):
        overall_status = "ERROR"
    elif any(c["status"] == "WARNING" for c in checks):
        overall_status = "WARNING"
    
    return {
        "status": overall_status,
        "summary": {
            "mean": float(np.mean(returns_array)),
            "std": float(np.std(returns_array, ddof=1)),
            "min": float(np.min(returns_array)),
            "max": float(np.max(returns_array)),
            "count": len(portfolio_returns),
            "extreme_positive_count": len(extreme_positive),
            "extreme_negative_count": len(extreme_negative),
        },
        "checks": checks,
    }


def check_missing_stocks(
    timeseries_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    欠損銘柄をチェック
    
    Args:
        timeseries_data: calculate_timeseries_returns()の戻り値
    
    Returns:
        チェック結果の辞書
    """
    portfolio_details = timeseries_data.get("portfolio_details", [])
    
    if not portfolio_details:
        return {
            "status": "ERROR",
            "message": "ポートフォリオ詳細がありません",
        }
    
    # 期間別の欠損銘柄数
    missing_by_period = []
    missing_codes_all = []
    
    for detail in portfolio_details:
        num_missing = detail.get("num_missing_stocks", 0)
        missing_codes = detail.get("missing_codes", [])
        missing_by_period.append({
            "rebalance_date": detail.get("rebalance_date"),
            "num_missing": num_missing,
            "missing_codes": missing_codes,
        })
        missing_codes_all.extend(missing_codes)
    
    # 銘柄別の欠損回数
    from collections import Counter
    missing_by_code = Counter(missing_codes_all)
    
    total_missing_periods = sum(1 for p in missing_by_period if p["num_missing"] > 0)
    total_missing_count = sum(p["num_missing"] for p in missing_by_period)
    
    checks = []
    
    if total_missing_count > 0:
        checks.append({
            "check": "欠損銘柄の総数",
            "value": f"{total_missing_count}件（{total_missing_periods}期間）",
            "expected": "0件（理想）",
            "status": "INFO" if total_missing_count < 100 else "WARNING",
        })
        
        # 最も欠損が多い銘柄（上位10件）
        top_missing_codes = missing_by_code.most_common(10)
        checks.append({
            "check": "欠損が多い銘柄（上位10件）",
            "value": f"{len(top_missing_codes)}件",
            "expected": "確認",
            "status": "INFO",
            "top_missing_codes": [{"code": code, "count": count} for code, count in top_missing_codes],
        })
    else:
        checks.append({
            "check": "欠損銘柄",
            "value": "0件",
            "expected": "0件",
            "status": "OK",
        })
    
    return {
        "status": "OK" if total_missing_count == 0 else "INFO",
        "summary": {
            "total_missing_count": total_missing_count,
            "total_missing_periods": total_missing_periods,
            "unique_missing_codes": len(missing_by_code),
        },
        "checks": checks,
        "missing_by_period": missing_by_period[:20],  # 最初の20期間
        "missing_by_code": dict(missing_by_code.most_common(20)),  # 上位20銘柄
    }


def check_equity_curve(
    timeseries_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    エクイティカーブをチェック
    
    Args:
        timeseries_data: calculate_timeseries_returns()の戻り値
    
    Returns:
        チェック結果の辞書
    """
    equity_curve = timeseries_data.get("equity_curve", [])
    
    if not equity_curve or len(equity_curve) < 2:
        return {
            "status": "ERROR",
            "message": "エクイティカーブがありません",
        }
    
    equity_array = np.array(equity_curve)
    
    # チェック
    checks = []
    
    # 1. MaxDDが0になっていないか
    max_dd = calculate_max_drawdown(equity_curve)
    
    if max_dd == 0.0:
        checks.append({
            "check": "最大ドローダウン",
            "value": "0.0%",
            "expected": "0以外（通常は負の値）",
            "status": "ERROR",
            "message": "エクイティカーブが単調増加している可能性があります",
        })
    else:
        checks.append({
            "check": "最大ドローダウン",
            "value": f"{max_dd*100:.2f}%",
            "expected": "0以外",
            "status": "OK",
        })
    
    # 2. エクイティカーブが上下しているか
    # 単調増加/減少のチェック
    is_monotonic_increasing = np.all(equity_array[1:] >= equity_array[:-1])
    is_monotonic_decreasing = np.all(equity_array[1:] <= equity_array[:-1])
    
    if is_monotonic_increasing:
        checks.append({
            "check": "エクイティカーブの変動",
            "value": "単調増加",
            "expected": "上下変動",
            "status": "WARNING",
            "message": "損失月が存在しない可能性があります",
        })
    elif is_monotonic_decreasing:
        checks.append({
            "check": "エクイティカーブの変動",
            "value": "単調減少",
            "expected": "上下変動",
            "status": "WARNING",
            "message": "利益月が存在しない可能性があります",
        })
    else:
        checks.append({
            "check": "エクイティカーブの変動",
            "value": "上下変動あり",
            "expected": "上下変動",
            "status": "OK",
        })
    
    # 3. 最終値が初期値より大きいか（総リターンが正か）
    total_return = (equity_array[-1] / equity_array[0] - 1.0) * 100.0
    
    checks.append({
        "check": "総リターン",
        "value": f"{total_return:.2f}%",
        "expected": "任意",
        "status": "INFO",
    })
    
    overall_status = "OK"
    if any(c["status"] == "ERROR" for c in checks):
        overall_status = "ERROR"
    elif any(c["status"] == "WARNING" for c in checks):
        overall_status = "WARNING"
    
    return {
        "status": overall_status,
        "summary": {
            "initial_value": float(equity_array[0]),
            "final_value": float(equity_array[-1]),
            "min_value": float(np.min(equity_array)),
            "max_value": float(np.max(equity_array)),
            "total_return": total_return,
            "max_drawdown": max_dd * 100.0,
            "num_periods": len(equity_curve) - 1,
        },
        "checks": checks,
    }


def check_metrics(
    timeseries_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    指標（Sharpe、Sortino）をチェック
    
    Args:
        timeseries_data: calculate_timeseries_returns()の戻り値
    
    Returns:
        チェック結果の辞書
    """
    monthly_returns = timeseries_data.get("monthly_returns", [])
    monthly_excess_returns = timeseries_data.get("monthly_excess_returns", [])
    
    if not monthly_returns:
        return {
            "status": "ERROR",
            "message": "月次リターンがありません",
        }
    
    # 指標を計算
    sharpe = calculate_sharpe_ratio(
        monthly_returns,
        monthly_excess_returns,
        risk_free_rate=0.0,
        annualize=True,
    )
    sortino = calculate_sortino_ratio(
        monthly_returns,
        monthly_excess_returns,
        risk_free_rate=0.0,
        annualize=True,
    )
    
    checks = []
    
    # 1. Sharpe_excessが極端に大きくないか
    if sharpe is not None:
        if abs(sharpe) > 10.0:
            checks.append({
                "check": "シャープレシオ（超過）",
                "value": f"{sharpe:.2f}",
                "expected": "|Sharpe| < 10.0（通常は0-3程度）",
                "status": "WARNING",
                "message": "指標定義または欠損の扱いを確認してください",
            })
        else:
            checks.append({
                "check": "シャープレシオ（超過）",
                "value": f"{sharpe:.2f}",
                "expected": "|Sharpe| < 10.0",
                "status": "OK",
            })
    else:
        checks.append({
            "check": "シャープレシオ（超過）",
            "value": "計算不可",
            "expected": "数値",
            "status": "ERROR",
        })
    
    # 2. Sortino_excessが極端に大きくないか
    if sortino is not None:
        if abs(sortino) > 50.0:
            checks.append({
                "check": "ソルティノレシオ（超過）",
                "value": f"{sortino:.2f}",
                "expected": "|Sortino| < 50.0（通常は0-10程度）",
                "status": "WARNING",
                "message": "指標定義または欠損の扱いを確認してください",
            })
        else:
            checks.append({
                "check": "ソルティノレシオ（超過）",
                "value": f"{sortino:.2f}",
                "expected": "|Sortino| < 50.0",
                "status": "OK",
            })
    else:
        checks.append({
            "check": "ソルティノレシオ（超過）",
            "value": "計算不可",
            "expected": "数値",
            "status": "OK",  # 負のリターンがない場合はNoneが正常
        })
    
    overall_status = "OK"
    if any(c["status"] == "ERROR" for c in checks):
        overall_status = "ERROR"
    elif any(c["status"] == "WARNING" for c in checks):
        overall_status = "WARNING"
    
    return {
        "status": overall_status,
        "summary": {
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
        },
        "checks": checks,
    }


def run_sanity_check(
    start_date: str,
    end_date: str,
    cost_bps: float = 0.0,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    サニティチェックを実行
    
    Args:
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        cost_bps: 取引コスト（bps）
        output_path: 出力ファイルパス（Markdown形式、Noneの場合は標準出力）
    
    Returns:
        チェック結果の辞書
    """
    print("=" * 80)
    print("時系列P/L計算のサニティチェック")
    print("=" * 80)
    print(f"期間: {start_date} ～ {end_date}")
    print(f"取引コスト: {cost_bps} bps")
    print()
    
    # 時系列P/Lを計算
    print("時系列P/Lを計算中...")
    timeseries_data = calculate_timeseries_returns(
        start_date=start_date,
        end_date=end_date,
        rebalance_dates=None,
        cost_bps=cost_bps,
    )
    
    print(f"リバランス日数: {len(timeseries_data.get('dates', []))}")
    print(f"月次リターン数: {len(timeseries_data.get('monthly_returns', []))}")
    print()
    
    # 各チェックを実行
    print("チェックを実行中...")
    results = {
        "topix_check": check_topix_monthly_returns(timeseries_data),
        "stock_returns_check": check_individual_stock_returns(timeseries_data),
        "missing_stocks_check": check_missing_stocks(timeseries_data),
        "equity_curve_check": check_equity_curve(timeseries_data),
        "metrics_check": check_metrics(timeseries_data),
    }
    
    # 結果をMarkdown形式で出力
    markdown_output = generate_markdown_report(results, start_date, end_date, cost_bps)
    
    if output_path:
        Path(output_path).write_text(markdown_output, encoding="utf-8")
        print(f"結果を {output_path} に保存しました")
    else:
        print(markdown_output)
    
    return results


def generate_markdown_report(
    results: Dict[str, Any],
    start_date: str,
    end_date: str,
    cost_bps: float,
) -> str:
    """
    Markdown形式のレポートを生成
    
    Args:
        results: チェック結果の辞書
        start_date: 開始日
        end_date: 終了日
        cost_bps: 取引コスト
    
    Returns:
        Markdown形式の文字列
    """
    lines = []
    lines.append("# 時系列P/L計算のサニティチェック結果")
    lines.append("")
    lines.append(f"**実行日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**期間**: {start_date} ～ {end_date}")
    lines.append(f"**取引コスト**: {cost_bps} bps")
    lines.append("")
    
    # 各チェック結果
    status_icons = {
        "OK": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "INFO": "ℹ️",
    }
    
    for check_name, check_result in results.items():
        status = check_result.get("status", "UNKNOWN")
        icon = status_icons.get(status, "❓")
        
        lines.append(f"## {icon} {check_name.replace('_', ' ').title()}")
        lines.append("")
        
        if "message" in check_result:
            lines.append(f"**メッセージ**: {check_result['message']}")
            lines.append("")
        
        if "summary" in check_result:
            lines.append("### サマリー")
            lines.append("")
            for key, value in check_result["summary"].items():
                if isinstance(value, float):
                    lines.append(f"- **{key}**: {value:.4f}")
                elif isinstance(value, (list, dict)):
                    # リストや辞書は簡潔に表示
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict):
                            lines.append(f"- **{key}**:")
                            for item in value[:10]:  # 最大10件
                                lines.append(f"  - {item}")
                        else:
                            lines.append(f"- **{key}**: {value[:10]}")  # 最大10件
                    else:
                        lines.append(f"- **{key}**: {value}")
                else:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")
        
        if "checks" in check_result:
            lines.append("### チェック項目")
            lines.append("")
            lines.append("| チェック | 値 | 期待値 | ステータス |")
            lines.append("|---------|-----|--------|----------|")
            
            for check in check_result["checks"]:
                check_name = check.get("check", "")
                value = check.get("value", "")
                expected = check.get("expected", "")
                status = check.get("status", "UNKNOWN")
                icon = status_icons.get(status, "❓")
                
                lines.append(f"| {check_name} | {value} | {expected} | {icon} {status} |")
                
                if "message" in check:
                    lines.append(f"| → {check['message']} | | | |")
                
                # 追加情報（top_10, bottom_10, top_missing_codesなど）
                if "top_10" in check:
                    lines.append(f"| → 上位10件: {check['top_10'][:5]}... | | | |")
                if "bottom_10" in check:
                    lines.append(f"| → 下位10件: {check['bottom_10'][:5]}... | | | |")
                if "top_missing_codes" in check:
                    lines.append(f"| → 欠損が多い銘柄: {check['top_missing_codes'][:5]}... | | | |")
            
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # 全体のステータス
    overall_status = "OK"
    if any(r.get("status") == "ERROR" for r in results.values()):
        overall_status = "ERROR"
    elif any(r.get("status") == "WARNING" for r in results.values()):
        overall_status = "WARNING"
    
    icon = status_icons.get(overall_status, "❓")
    lines.append(f"## {icon} 全体ステータス: {overall_status}")
    lines.append("")
    
    return "\n".join(lines)


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="時系列P/L計算のサニティチェック")
    parser.add_argument("--start", type=str, required=True, help="開始日（YYYY-MM-DD）")
    parser.add_argument("--end", type=str, required=True, help="終了日（YYYY-MM-DD）")
    parser.add_argument("--cost", type=float, default=0.0, help="取引コスト（bps、デフォルト: 0.0）")
    parser.add_argument("--output", type=str, help="出力ファイルパス（Markdown形式）")
    
    args = parser.parse_args()
    
    results = run_sanity_check(
        start_date=args.start,
        end_date=args.end,
        cost_bps=args.cost,
        output_path=args.output,
    )
    
    # 全体のステータスを確認
    overall_status = "OK"
    if any(r.get("status") == "ERROR" for r in results.values()):
        overall_status = "ERROR"
    elif any(r.get("status") == "WARNING" for r in results.values()):
        overall_status = "WARNING"
    
    if overall_status == "ERROR":
        print("\n❌ エラーが検出されました。詳細を確認してください。")
        sys.exit(1)
    elif overall_status == "WARNING":
        print("\n⚠️ 警告が検出されました。詳細を確認してください。")
        sys.exit(0)
    else:
        print("\n✅ すべてのチェックをパスしました。")
        sys.exit(0)


if __name__ == "__main__":
    main()

