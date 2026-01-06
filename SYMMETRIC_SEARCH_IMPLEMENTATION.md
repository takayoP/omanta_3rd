# 対称な探索範囲の実装（修正版）

## 問題点（修正前）

以前の実装（「中心±半幅」方式）には以下の問題がありました：

1. **境界で非対称**: `max()`/`min()`でクリップしているため、端に寄ったときに片側が削れて対称にならない
2. **例の数値が成立しない**: `rsi_base=50`の場合、`rsi_max`は`max(30.0, 50-35.0)=30`から`min(85.0, 50+35.0)=85`の範囲になり、15にはならない
3. **中心が実質固定**: BBで`half_range=全レンジ/2`を使うと、中心が特定の値（例：0.75）に実質固定される

## 修正内容（修正後）

### 実装方式：baseとmaxを同じ範囲から独立にサンプル

**RSIパラメータ**:
```python
RSI_LOW, RSI_HIGH = 30.0, 85.0
rsi_base = trial.suggest_float("rsi_base", RSI_LOW, RSI_HIGH)
rsi_max = trial.suggest_float("rsi_max", RSI_LOW, RSI_HIGH)
```

**BB Z-scoreパラメータ**:
```python
BB_LOW, BB_HIGH = -3.0, 4.5
bb_z_base = trial.suggest_float("bb_z_base", BB_LOW, BB_HIGH)
bb_z_max = trial.suggest_float("bb_z_max", BB_LOW, BB_HIGH)
```

### 最小幅制約

```python
rsi_min_width = 5.0
if abs(rsi_max - rsi_base) < rsi_min_width:
    raise optuna.TrialPruned("RSI width too small")

bb_z_min_width = 0.3
if abs(bb_z_max - bb_z_base) < bb_z_min_width:
    raise optuna.TrialPruned("BB width too small")
```

## 効果

1. **完全に対称**: `rsi_max > rsi_base`（順張り）と`rsi_max < rsi_base`（逆張り）が同確率で探索される
2. **境界問題なし**: クリップがないため、端でも対称が保たれる
3. **中心固定問題なし**: 半幅を固定しないため、任意の中心で探索可能

## ログ出力

順張り/逆張りの方向と幅をログに記録：

```python
trial.set_user_attr("rsi_direction", "順張り" if rsi_max > rsi_base else "逆張り")
trial.set_user_attr("bb_direction", "順張り" if bb_z_max > bb_z_base else "逆張り")
trial.set_user_attr("rsi_width", abs(rsi_max - rsi_base))
trial.set_user_attr("bb_z_width", abs(bb_z_max - bb_z_base))
```

最適化結果の表示でも方向と幅を表示：

```
entry_score方向:
  RSI: 逆張り (rsi_base=55.26, rsi_max=45.00, width=10.26)
  BB: 順張り (bb_z_base=-0.02, bb_z_max=4.21, width=4.23)
```

## 修正ファイル

1. **`src/omanta_3rd/jobs/optimize_longterm.py`**
   - RSI/BBパラメータを独立サンプル方式に変更
   - 方向と幅のログ出力を追加

2. **`src/omanta_3rd/jobs/optimize_timeseries.py`**
   - RSI/BBパラメータを独立サンプル方式に変更
   - 方向と幅のログ出力を追加

## 比較の公平性

- **RSI**: 30.0-85.0の範囲から独立にサンプル（対称）
- **BB**: -3.0-4.5の範囲から独立にサンプル（対称）
- **その他のパラメータ**: すべて以前と同じ範囲

これにより、RSIとBBの順張り/逆張り対応がパフォーマンスに与える影響を正確に評価できます。









