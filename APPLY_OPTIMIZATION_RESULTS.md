# 最適化結果の適用方法

## 最適化結果の確認

最適化結果は以下のJSONファイルに保存されています：
- `optimization_result_optimization_20251229_140924.json`

最良値: **+4.8551**（「優秀」評価を大きく上回る）

## 最良パラメータ

### StrategyParams（core_scoreの重み）
- `w_quality`: 0.2245（22.45%）
- `w_value`: 0.3008（30.08%）← 最も重要
- `w_growth`: 0.1006（10.06%）
- `w_record_high`: 0.0609（6.09%）
- `w_size`: 0.1604（16.04%）
- `w_forward_per`: 0.4825（48.25%）
- `w_pbr`: 0.5175（51.75%）
- `roe_min`: 0.0711（7.11%）
- `liquidity_quantile_cut`: 0.2642（26.42%）

### EntryScoreParams（順張り戦略）
- `rsi_base`: 44.64（RSIが44.64以上で高スコア）
- `rsi_max`: 78.72（RSIが78.72で最大スコア）
- `bb_z_base`: -1.41（BB Z-scoreが-1.41以上で高スコア）
- `bb_z_max`: 2.50（BB Z-scoreが2.50で最大スコア）
- `bb_weight`: 0.62（BBとRSIの重み、BB側が62%）
- `rsi_weight`: 0.38（RSI側が38%）

## 適用方法

### 方法1: StrategyParamsを直接更新（推奨）

`src/omanta_3rd/jobs/monthly_run.py`の`StrategyParams`クラスを更新：

```python
@dataclass(frozen=True)
class StrategyParams:
    target_min: int = 20
    target_max: int = 30
    pool_size: int = 80

    # Hard filters
    roe_min: float = 0.0711  # 最適化結果: 0.0711
    liquidity_quantile_cut: float = 0.2642  # 最適化結果: 0.2642

    # Sector cap (33-sector)
    sector_cap: int = 4

    # Scoring weights
    w_quality: float = 0.2245  # 最適化結果: 0.2245
    w_value: float = 0.3008   # 最適化結果: 0.3008
    w_growth: float = 0.1006  # 最適化結果: 0.1006
    w_record_high: float = 0.0609  # 最適化結果: 0.0609
    w_size: float = 0.1604    # 最適化結果: 0.1604

    # Value mix
    w_forward_per: float = 0.4825  # 最適化結果: 0.4825
    w_pbr: float = 0.5175  # 最適化結果: 1.0 - 0.4825

    # Entry score (BB/RSI)
    use_entry_score: bool = True
```

### 方法2: entry_scoreのパラメータを更新

現在の`_entry_score`関数は固定値を使用していますが、最適化結果を反映するには、`optimize.py`の`_entry_score_with_params`関数のロジックを参考に、`monthly_run.py`の`_entry_score`関数を更新する必要があります。

ただし、現在の実装では`_entry_score`は固定値を使用しているため、最適化結果を反映するには、`_entry_score`関数をパラメータ化するか、`optimize.py`の`_entry_score_with_params`を使用する必要があります。

**注意**: 現在の`monthly_run.py`の`_entry_score`は固定値（rsi_base=50, rsi_max=80, bb_z_base=0, bb_z_max=3）を使用しています。最適化結果を完全に反映するには、この関数をパラメータ化する必要があります。

## 適用後の確認

最適化結果を適用した後、以下のコマンドでポートフォリオを生成し、パフォーマンスを確認してください：

```bash
# ポートフォリオを生成
python -m omanta_3rd.jobs.monthly_run --asof 2025-12-29

# パフォーマンスを確認
python -m omanta_3rd.backtest.performance --rebalance-date 2025-12-29
```

## 注意事項

1. **過学習のリスク**: バックテスト期間に最適化されているため、実運用では異なる結果になる可能性があります
2. **期間による変動**: 異なる期間でバックテストを実行し、結果の安定性を確認してください
3. **リスク管理**: リターンだけでなく、リスク（ボラティリティ、最大ドローダウン）も考慮してください







