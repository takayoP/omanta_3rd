"""戦略パラメータ（ROE閾値、重み、業種上限等）"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class StrategyConfig:
    """投資戦略の設定パラメータ"""
    
    # スコアリング重み
    roe_weight: float = 0.3
    roe_trend_weight: float = 0.2
    profit_growth_weight: float = 0.2
    valuation_weight: float = 0.15  # PER/PBRの逆数
    record_high_weight: float = 0.15
    
    # フィルタリング閾値
    min_roe: float = 0.10  # 10%以上
    min_liquidity_60d: float = 100_000_000  # 1億円以上
    min_market_cap: float = 10_000_000_000  # 100億円以上
    max_per: Optional[float] = 30.0  # PER上限（Noneで無制限）
    max_pbr: Optional[float] = 3.0  # PBR上限（Noneで無制限）
    
    # ポートフォリオ構築
    target_stock_count: int = 25  # 目標銘柄数
    max_stocks_per_sector: int = 5  # 業種あたりの上限
    max_replacement_ratio: float = 0.3  # 入替上限（30%）
    
    # 市場フィルタ
    target_markets: list = None  # Noneで全市場、["プライム"]でプライムのみ
    
    def __post_init__(self):
        if self.target_markets is None:
            self.target_markets = ["プライム", "スタンダード", "グロース"]


# デフォルト設定インスタンス
default_strategy = StrategyConfig()


