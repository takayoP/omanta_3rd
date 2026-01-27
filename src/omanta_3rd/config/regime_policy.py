"""
レジーム→パラメータIDのポリシー管理

市場レジームに応じて使用するパラメータIDを決定します。
"""

import json
from pathlib import Path
from typing import Dict, Optional

from ..config.settings import PROJECT_ROOT


def load_regime_policy() -> Dict[str, str]:
    """
    レジームポリシーを読み込む
    
    Returns:
        レジーム→パラメータIDのマッピング
        {
            "up": "12M_momentum",
            "down": "12M_reversal",
            "range": "operational_24M"
        }
    """
    policy_path = PROJECT_ROOT / "config" / "regime_policy_longterm.json"
    if not policy_path.exists():
        raise FileNotFoundError(f"レジームポリシーファイルが見つかりません: {policy_path}")
    
    with open(policy_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_params_id_for_regime(regime: str) -> str:
    """
    レジームからパラメータIDを取得
    
    Args:
        regime: レジーム（"up", "down", "range"）
    
    Returns:
        パラメータID
    
    Raises:
        KeyError: レジームがポリシーに存在しない場合
    """
    policy = load_regime_policy()
    
    if regime not in policy:
        available_regimes = list(policy.keys())
        raise KeyError(
            f"レジーム '{regime}' がポリシーに見つかりません。"
            f"利用可能なレジーム: {available_regimes}"
        )
    
    return policy[regime]













