"""
パラメータ台帳（registry）の読み込みと管理

長期保有型のパラメータをIDで管理し、JSONファイルから読み込む機能を提供します。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

from ..config.settings import PROJECT_ROOT


def load_registry() -> Dict[str, Any]:
    """パラメータ台帳を読み込む"""
    registry_path = PROJECT_ROOT / "config" / "params_registry_longterm.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"パラメータ台帳が見つかりません: {registry_path}")
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_params_by_id_longterm(params_id: str) -> Dict[str, Any]:
    """
    パラメータIDからパラメータを読み込む
    
    Args:
        params_id: パラメータID（例: "operational_24M", "12M_momentum", "12M_reversal"）
    
    Returns:
        パラメータ辞書（JSONファイルの"params"キーの内容）
    
    Raises:
        KeyError: params_idが台帳に存在しない場合
        FileNotFoundError: パラメータファイルが見つからない場合
    """
    registry = load_registry()
    
    if params_id not in registry:
        available_ids = list(registry.keys())
        raise KeyError(
            f"パラメータID '{params_id}' が見つかりません。"
            f"利用可能なID: {available_ids}"
        )
    
    entry = registry[params_id]
    params_file_path = entry.get("params_file_path")
    
    if not params_file_path:
        raise ValueError(f"パラメータID '{params_id}' にparams_file_pathが設定されていません")
    
    # 相対パスの場合はPROJECT_ROOTからのパスとして扱う
    if not Path(params_file_path).is_absolute():
        params_file_path = PROJECT_ROOT / params_file_path
    else:
        params_file_path = Path(params_file_path)
    
    if not params_file_path.exists():
        raise FileNotFoundError(
            f"パラメータファイルが見つかりません: {params_file_path}"
        )
    
    with open(params_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # "params"キーの内容を返す
    if "params" not in data:
        raise ValueError(f"パラメータファイルに'params'キーがありません: {params_file_path}")
    
    return data["params"]


def get_registry_entry(params_id: str) -> Dict[str, Any]:
    """
    パラメータIDから台帳エントリを取得する
    
    Args:
        params_id: パラメータID
    
    Returns:
        台帳エントリ（horizon_months, role, mode, source, params_file_path, notes）
    """
    registry = load_registry()
    
    if params_id not in registry:
        available_ids = list(registry.keys())
        raise KeyError(
            f"パラメータID '{params_id}' が見つかりません。"
            f"利用可能なID: {available_ids}"
        )
    
    return registry[params_id]













