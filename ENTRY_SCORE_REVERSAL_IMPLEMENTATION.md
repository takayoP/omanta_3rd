# entry_scoreの順張り/逆張り両対応実装

## 実装概要

ChatGPTのアドバイスに基づき、`entry_score`の計算で順張り/逆張り両方を探索できるように実装を改善しました。

## 実装内容

### 1. 順序制約の撤廃

**変更前**:
- `bb_z_base`: -3.0 ～ 0.0（負の値のみ）
- `bb_z_max`: 1.0 ～ 4.5（正の値のみ、`bb_z_base + 0.5`以上）
- `rsi_base`: 30.0 ～ 70.0
- `rsi_max`: 70.0 ～ 85.0（`rsi_base + 5.0`以上）

**変更後**:
- `bb_z_base`: -3.0 ～ 3.0（範囲を拡張）
- `bb_z_max`: -3.0 ～ 4.5（順序制約なし）
- `rsi_base`: 30.0 ～ 70.0
- `rsi_max`: 30.0 ～ 85.0（順序制約なし）

### 2. 最小幅制約の追加

分母が0に近くなるのを防ぐため、最小幅制約を追加：

```python
# RSI
rsi_min_width = 5.0
if abs(rsi_max - rsi_base) < rsi_min_width:
    raise optuna.TrialPruned("RSI最小幅制約違反")

# BB Z-score
bb_z_min_width = 0.3
if abs(bb_z_max - bb_z_base) < bb_z_min_width:
    raise optuna.TrialPruned("BB Z-score最小幅制約違反")
```

### 3. Sigmoid化による張り付き対策

クリップ処理（0-1に制限）の代わりに、sigmoid関数を使用して滑らかに：

```python
# 変更前: クリップ処理
bb_score = np.clip((z - bb_z_base) / (bb_z_max - bb_z_base), 0.0, 1.0)

# 変更後: sigmoid化
raw_score = (z - bb_z_base) / (bb_z_max - bb_z_base)
k = 3.0  # スケーリング係数
sigmoid_score = 1.0 / (1.0 + np.exp(-k * (raw_score - 0.5)))
bb_score = sigmoid_score
```

**効果**:
- 0/1への張り付きを防ぐ
- 銘柄の並びが安定
- ノイズに対する耐性が向上

### 4. 順張り/逆張りの判定とログ出力

最適化時に方向を判定し、ログに記録：

```python
rsi_direction = "順張り" if rsi_max > rsi_base else "逆張り"
bb_direction = "順張り" if bb_z_max > bb_z_base else "逆張り"
trial.set_user_attr("rsi_direction", rsi_direction)
trial.set_user_attr("bb_direction", bb_direction)
```

最適化結果の表示でも方向を表示：

```
entry_score方向:
  RSI: 逆張り (rsi_base=55.26, rsi_max=45.00)
  BB: 順張り (bb_z_base=-0.02, bb_z_max=4.21)
```

## 修正ファイル

1. **`src/omanta_3rd/jobs/optimize.py`**
   - `EntryScoreParams`に`rsi_min_width`と`bb_z_min_width`を追加
   - `_entry_score_with_params`で最小幅チェックとsigmoid化を実装

2. **`src/omanta_3rd/jobs/optimize_longterm.py`**
   - パラメータ範囲を変更（順序制約を外す）
   - 最小幅制約を追加
   - 順張り/逆張りのログ出力を追加

3. **`src/omanta_3rd/jobs/optimize_timeseries.py`**
   - 同様の修正を適用

## 期待される効果

### 1. 逆張りの探索が可能に

- 2022-2023で崩壊したFoldで、最適化が逆張り（`bb_z_max < bb_z_base`）を選ぶ可能性
- 順張りが効かない市場環境でも適応可能

### 2. スコアの安定性向上

- Sigmoid化により、0/1への張り付きを防止
- 銘柄の並びが安定し、rollでの極端な崩れを抑制

### 3. パラメータの有効性向上

- 最小幅制約により、分母が0に近くなる問題を防止
- より安定したスコア計算が可能

## 検証方法

### 1. 最適化結果の確認

```bash
python walk_forward_longterm.py --fold-type roll --n-trials 30
```

最適化結果で以下を確認：
- `bb_z_max < bb_z_base`が選ばれるか（逆張り）
- `rsi_max < rsi_base`が選ばれるか（逆張り）
- ログに「逆張り」と表示されるか

### 2. スコア分布の確認

最適化後に`bb_score`の分布を確認：
- 0/1に張り付き過ぎていないか
- 上位銘柄の差が出ているか

### 3. 2022-2023期間での検証

rollで崩壊した2022-2023のFoldで：
- 逆張りが選ばれるか
- パフォーマンスが改善するか

## 注意点

1. **最小幅制約の値**
   - `rsi_min_width = 5.0`: RSIの最小幅（探索してもOK）
   - `bb_z_min_width = 0.3`: BB Z-scoreの最小幅（探索してもOK）
   - 必要に応じて調整可能

2. **Sigmoidのスケーリング係数**
   - `k = 3.0`: 現在の値（大きいほど急峻）
   - 必要に応じて調整可能

3. **後方互換性**
   - 既存の最適化結果とは互換性がない
   - 新しい最適化を実行する必要がある

## 次のステップ

1. ✅ 実装完了
2. ⏳ 最適化の再実行（rollテスト）
3. ⏳ 結果の確認（逆張りが選ばれるか）
4. ⏳ パフォーマンスの改善確認









