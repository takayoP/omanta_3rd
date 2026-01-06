#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
運用パラメータを保存するスクリプト

24M Fold1パラメータを運用用として保存し、
12Mのパラメータをモード別（順張り/逆張り）に保存します。
"""

import json
from datetime import datetime
from pathlib import Path

def determine_strategy_mode(rsi_base: float, rsi_max: float, bb_z_base: float, bb_z_max: float) -> str:
    """パラメータから戦略モード（順張り/逆張り）を判定"""
    rsi_momentum = rsi_max > rsi_base
    bb_momentum = bb_z_max > bb_z_base
    
    if rsi_momentum and bb_momentum:
        return "momentum"  # 順張り
    elif not rsi_momentum and not bb_momentum:
        return "reversal"  # 逆張り
    else:
        return "mixed"  # 混合

def save_params_with_metadata(params: dict, output_path: str, metadata: dict):
    """パラメータとメタデータを保存"""
    output = {
        "metadata": metadata,
        "params": params
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"保存しました: {output_path}")

def main():
    # 24M Fold1パラメータ（運用用・安定型）
    params_24M_fold1 = {
        "w_quality": 0.3336411960139006,
        "w_growth": 0.10761729711447666,
        "w_record_high": 0.03244604445645113,
        "w_size": 0.3390732598504549,
        "w_value": 0.18722220256471678,
        "w_forward_per": 0.8286818642376064,
        "roe_min": 0.0602348864668037,
        "bb_weight": 0.6244678637750611,
        "liquidity_quantile_cut": 0.19643160022923523,
        "rsi_base": 51.99741274474254,
        "rsi_max": 71.57699842062665,
        "bb_z_base": -2.1997465928485593,
        "bb_z_max": 2.0840378956404764,
        "rsi_min_width": 10.0,
        "bb_z_min_width": 0.5
    }
    
    mode_24M = determine_strategy_mode(
        params_24M_fold1["rsi_base"],
        params_24M_fold1["rsi_max"],
        params_24M_fold1["bb_z_base"],
        params_24M_fold1["bb_z_max"]
    )
    
    metadata_24M = {
        "horizon_months": 24,
        "strategy_type": "operational",
        "portfolio_type": "longterm",
        "strategy_mode": mode_24M,
        "source_fold": "fold1",
        "source_test_period": "2022-01-31 to 2022-12-30",
        "source_performance": {
            "ann_excess_mean": 2.37,
            "win_rate": 0.583,
            "n_portfolios": 12
        },
        "cross_validation_performance": {
            "2022": {"ann_excess_mean": 2.37, "win_rate": 0.583},
            "2023": {"ann_excess_mean": 2.89, "win_rate": 0.667}
        },
        "description": "24Mホライズン・安定型パラメータ。2022/2023の両年でプラス超過リターンを達成。運用パラメータとして推奨。",
        "created_at": datetime.now().isoformat(),
        "recommended_for": "operational_use"
    }
    
    save_params_with_metadata(
        params_24M_fold1,
        "params_operational_24M.json",
        metadata_24M
    )
    
    # 12M Fold1パラメータ（順張りモード）
    params_12M_fold1 = {
        "w_quality": 0.04749467563061696,
        "w_growth": 0.10882868476612413,
        "w_record_high": 0.049246938953340834,
        "w_size": 0.3577232095672914,
        "w_value": 0.4367064910826267,
        "w_forward_per": 0.5356374083004061,
        "roe_min": 0.03539232972417195,
        "bb_weight": 0.40925705855117955,
        "liquidity_quantile_cut": 0.1570819242432306,
        "rsi_base": 27.00503581329634,
        "rsi_max": 65.90500751446345,
        "bb_z_base": -0.7108023247173709,
        "bb_z_max": 2.460822216946905,
        "rsi_min_width": 10.0,
        "bb_z_min_width": 0.5
    }
    
    mode_12M_fold1 = determine_strategy_mode(
        params_12M_fold1["rsi_base"],
        params_12M_fold1["rsi_max"],
        params_12M_fold1["bb_z_base"],
        params_12M_fold1["bb_z_max"]
    )
    
    metadata_12M_fold1 = {
        "horizon_months": 12,
        "strategy_type": "research",
        "portfolio_type": "longterm",
        "strategy_mode": mode_12M_fold1,
        "source_fold": "fold1",
        "source_test_period": "2022-01-31 to 2022-12-30",
        "source_performance": {
            "ann_excess_mean": 3.93,
            "win_rate": 0.917,
            "n_portfolios": 12
        },
        "cross_validation_performance": {
            "2022": {"ann_excess_mean": 3.93, "win_rate": 0.917},
            "2023": {"ann_excess_mean": -5.20, "win_rate": 0.25},
            "2024": {"ann_excess_mean": -1.82, "win_rate": 0.333}
        },
        "description": "12Mホライズン・順張りモード。2022で高パフォーマンスだが、他年への移植では性能低下。レジーム切替前提で使用。",
        "created_at": datetime.now().isoformat(),
        "recommended_for": "regime_switching"
    }
    
    save_params_with_metadata(
        params_12M_fold1,
        "params_12M_momentum.json",
        metadata_12M_fold1
    )
    
    # 12M Fold2パラメータ（逆張りモード）
    params_12M_fold2 = {
        "w_quality": 0.24829361837771735,
        "w_growth": 0.06061290087001123,
        "w_record_high": 0.053514907641641296,
        "w_size": 0.24392265504320823,
        "w_value": 0.3936559180674219,
        "w_forward_per": 0.2733758456653447,
        "roe_min": 0.037250058697410444,
        "bb_weight": 0.4390542442912585,
        "liquidity_quantile_cut": 0.17620220894585936,
        "rsi_base": 52.276455638555156,
        "rsi_max": 18.480612012013168,
        "bb_z_base": -1.1991191634115483,
        "bb_z_max": -3.16997379898768,
        "rsi_min_width": 10.0,
        "bb_z_min_width": 0.5
    }
    
    mode_12M_fold2 = determine_strategy_mode(
        params_12M_fold2["rsi_base"],
        params_12M_fold2["rsi_max"],
        params_12M_fold2["bb_z_base"],
        params_12M_fold2["bb_z_max"]
    )
    
    metadata_12M_fold2 = {
        "horizon_months": 12,
        "strategy_type": "research",
        "portfolio_type": "longterm",
        "strategy_mode": mode_12M_fold2,
        "source_fold": "fold2",
        "source_test_period": "2023-01-31 to 2023-12-29",
        "source_performance": {
            "ann_excess_mean": 12.27,
            "win_rate": 0.917,
            "n_portfolios": 12
        },
        "cross_validation_performance": {
            "2022": {"ann_excess_mean": -2.96, "win_rate": 0.25},
            "2023": {"ann_excess_mean": 12.27, "win_rate": 0.917},
            "2024": {"ann_excess_mean": 2.53, "win_rate": 0.50}
        },
        "description": "12Mホライズン・逆張りモード。2023で高パフォーマンス。2024でもプラスだが、2022ではマイナス。レジーム切替前提で使用。",
        "created_at": datetime.now().isoformat(),
        "recommended_for": "regime_switching"
    }
    
    save_params_with_metadata(
        params_12M_fold2,
        "params_12M_reversal.json",
        metadata_12M_fold2
    )
    
    print("\n" + "=" * 80)
    print("パラメータ保存完了")
    print("=" * 80)
    print("\n保存されたファイル:")
    print("  1. params_operational_24M.json - 運用パラメータ（24M・安定型）")
    print("  2. params_12M_momentum.json - 研究用（12M・順張りモード）")
    print("  3. params_12M_reversal.json - 研究用（12M・逆張りモード）")
    print("\n各ファイルには、パラメータとメタデータ（性能、横持ち評価結果など）が含まれています。")

if __name__ == "__main__":
    main()

