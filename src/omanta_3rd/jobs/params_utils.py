"""
パラメータユーティリティ関数

JSONから読み込んだパラメータ辞書をStrategyParamsとEntryScoreParamsに変換します。
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .longterm_run import StrategyParams
    from .optimize import EntryScoreParams


def build_strategy_params_from_dict(params_dict: Dict[str, Any]):
    """
    JSONから読み込んだパラメータ辞書からStrategyParamsを構築
    
    Args:
        params_dict: パラメータ辞書
    
    Returns:
        StrategyParamsインスタンス
    """
    # 遅延インポートで循環参照を回避
    from .longterm_run import StrategyParams
    
    # デフォルト値を取得
    defaults = {
        field.name: field.default
        for field in StrategyParams.__dataclass_fields__.values()
    }
    
    # パラメータ辞書から値を取得（存在しない場合はデフォルト値を使用）
    kwargs = {}
    for field_name in defaults.keys():
        if field_name in params_dict:
            kwargs[field_name] = params_dict[field_name]
        elif field_name in defaults:
            kwargs[field_name] = defaults[field_name]
    
    return StrategyParams(**kwargs)


def build_entry_params_from_dict(params_dict: Dict[str, Any]):
    """
    JSONから読み込んだパラメータ辞書からEntryScoreParamsを構築
    
    Args:
        params_dict: パラメータ辞書
    
    Returns:
        EntryScoreParamsインスタンス
    """
    # 遅延インポートで循環参照を回避
    from .optimize import EntryScoreParams
    
    # デフォルト値を取得
    defaults = {
        field.name: field.default
        for field in EntryScoreParams.__dataclass_fields__.values()
    }
    
    # パラメータ辞書から値を取得（存在しない場合はデフォルト値を使用）
    kwargs = {}
    for field_name in defaults.keys():
        if field_name in params_dict:
            kwargs[field_name] = params_dict[field_name]
        elif field_name in defaults:
            kwargs[field_name] = defaults[field_name]
    
    return EntryScoreParams(**kwargs)


def normalize_params(
    params_dict: Dict[str, Any]
):
    """
    パラメータ辞書を正規化してStrategyParamsとEntryScoreParamsに変換
    
    Args:
        params_dict: パラメータ辞書（JSONから読み込んだ形式）
    
    Returns:
        (StrategyParams, EntryScoreParams)のタプル
    """
    strategy_params = build_strategy_params_from_dict(params_dict)
    entry_params = build_entry_params_from_dict(params_dict)
    
    return strategy_params, entry_params

