# entry_score計算ロジックの具体例

## 概要

`entry_score`は、RSI（相対力指数）とBB Z-score（ボリンジャーバンドZスコア）を組み合わせて、エントリータイミングを評価するスコアです。

## 計算の流れ

### ステップ1: パラメータの取得（Optunaから）

Optunaが最適化するパラメータ：
- `rsi_base`, `rsi_max`: RSIの基準値と上限値
- `bb_z_base`, `bb_z_max`: BB Z-scoreの基準値と上限値
- `bb_weight`, `rsi_weight`: BBとRSIの重み

**例1: 順張りパラメータ**
```
rsi_base = 50.0
rsi_max = 80.0  （rsi_max > rsi_base → 順張り）
bb_z_base = 0.0
bb_z_max = 3.0  （bb_z_max > bb_z_base → 順張り）
bb_weight = 0.6
rsi_weight = 0.4
```

**例2: 逆張りパラメータ**
```
rsi_base = 70.0
rsi_max = 40.0  （rsi_max < rsi_base → 逆張り）
bb_z_base = 2.0
bb_z_max = -1.0  （bb_z_max < bb_z_base → 逆張り）
bb_weight = 0.6
rsi_weight = 0.4
```

### ステップ2: 各期間（20日、60日、90日）での計算

各期間で以下を計算：
1. RSIとBB Z-scoreを取得
2. BBスコアとRSIスコアを計算
3. 重み付き平均で期間スコアを計算
4. 3期間の最大値を最終スコアとする

---

## 具体例1: 順張りパラメータの場合

### パラメータ
```
rsi_base = 50.0, rsi_max = 80.0  （順張り）
bb_z_base = 0.0, bb_z_max = 3.0  （順張り）
bb_weight = 0.6, rsi_weight = 0.4
```

### 銘柄Aのデータ（20日）
```
RSI = 75.0  （高い = 買われている）
BB Z-score = 2.5  （高い = 上昇トレンド）
```

### BBスコアの計算

**ステップ1: 線形変換（raw_score）**
```
bb_z_diff = bb_z_max - bb_z_base = 3.0 - 0.0 = 3.0
raw_score = (bb_z - bb_z_base) / bb_z_diff
          = (2.5 - 0.0) / 3.0
          = 2.5 / 3.0
          = 0.8333
```
- `raw_score = 0.0` → `bb_z = bb_z_base`（基準値）
- `raw_score = 1.0` → `bb_z = bb_z_max`（上限値）
- `raw_score = 0.8333` → `bb_z = 2.5`（上限に近い）

**ステップ2: Sigmoid化**
```
k = 3.0  （スケーリング係数）
sigmoid_score = 1.0 / (1.0 + exp(-k * (raw_score - 0.5)))
              = 1.0 / (1.0 + exp(-3.0 * (0.8333 - 0.5)))
              = 1.0 / (1.0 + exp(-3.0 * 0.3333))
              = 1.0 / (1.0 + exp(-1.0))
              = 1.0 / (1.0 + 0.3679)
              = 1.0 / 1.3679
              = 0.731
```
- Sigmoid化により、0/1への張り付きを防止
- 滑らかな分布で銘柄の並びが安定

### RSIスコアの計算

**ステップ1: 線形変換（raw_score）**
```
rsi_diff = rsi_max - rsi_base = 80.0 - 50.0 = 30.0
raw_score = (rsi - rsi_base) / rsi_diff
          = (75.0 - 50.0) / 30.0
          = 25.0 / 30.0
          = 0.8333
```

**ステップ2: Sigmoid化**
```
sigmoid_score = 1.0 / (1.0 + exp(-3.0 * (0.8333 - 0.5)))
              = 0.731（BBと同じ計算）
```

### 期間スコア（20日）の計算

```
period_score_20d = (bb_weight * bb_score + rsi_weight * rsi_score) / (bb_weight + rsi_weight)
                  = (0.6 * 0.731 + 0.4 * 0.731) / 1.0
                  = 0.731
```

### 60日、90日も同様に計算

```
period_score_60d = 0.650
period_score_90d = 0.580
```

### 最終スコア

```
entry_score = max(period_score_20d, period_score_60d, period_score_90d)
            = max(0.731, 0.650, 0.580)
            = 0.731
```

**解釈**: 20日が最も「買われている」状態なので、そのスコアを採用

---

## 具体例2: 逆張りパラメータの場合

### パラメータ
```
rsi_base = 70.0, rsi_max = 40.0  （逆張り: rsi_max < rsi_base）
bb_z_base = 2.0, bb_z_max = -1.0  （逆張り: bb_z_max < bb_z_base）
bb_weight = 0.6, rsi_weight = 0.4
```

### 銘柄Bのデータ（20日）
```
RSI = 35.0  （低い = 売られすぎ）
BB Z-score = -2.0  （低い = 下振れ）
```

### BBスコアの計算

**ステップ1: 線形変換（raw_score）**
```
bb_z_diff = bb_z_max - bb_z_base = -1.0 - 2.0 = -3.0  （負の値！）
raw_score = (bb_z - bb_z_base) / bb_z_diff
          = (-2.0 - 2.0) / (-3.0)
          = -4.0 / -3.0
          = 1.3333
```
- **重要なポイント**: 分母が負なので、`bb_z`が低いほど`raw_score`が大きくなる
- `raw_score = 0.0` → `bb_z = bb_z_base = 2.0`（基準値）
- `raw_score = 1.0` → `bb_z = bb_z_max = -1.0`（下限値）
- `raw_score = 1.3333` → `bb_z = -2.0`（下限よりさらに低い = 高スコア）

**ステップ2: Sigmoid化**
```
sigmoid_score = 1.0 / (1.0 + exp(-3.0 * (1.3333 - 0.5)))
              = 1.0 / (1.0 + exp(-3.0 * 0.8333))
              = 1.0 / (1.0 + exp(-2.5))
              = 1.0 / (1.0 + 0.0821)
              = 1.0 / 1.0821
              = 0.924  （高いスコア！）
```

### RSIスコアの計算

**ステップ1: 線形変換（raw_score）**
```
rsi_diff = rsi_max - rsi_base = 40.0 - 70.0 = -30.0  （負の値！）
raw_score = (rsi - rsi_base) / rsi_diff
          = (35.0 - 70.0) / (-30.0)
          = -35.0 / -30.0
          = 1.1667
```
- **重要なポイント**: 分母が負なので、`rsi`が低いほど`raw_score`が大きくなる

**ステップ2: Sigmoid化**
```
sigmoid_score = 1.0 / (1.0 + exp(-3.0 * (1.1667 - 0.5)))
              = 1.0 / (1.0 + exp(-3.0 * 0.6667))
              = 1.0 / (1.0 + exp(-2.0))
              = 1.0 / (1.0 + 0.1353)
              = 1.0 / 1.1353
              = 0.881  （高いスコア！）
```

### 期間スコア（20日）の計算

```
period_score_20d = (0.6 * 0.924 + 0.4 * 0.881) / 1.0
                  = 0.907
```

### 最終スコア

```
entry_score = max(period_score_20d, period_score_60d, period_score_90d)
            = 0.907
```

**解釈**: 逆張りパラメータでは、売られすぎた銘柄（低いRSI、低いBB Z-score）が高スコアになる

## 重要なポイント

### 1. 順張り vs 逆張りの違い

#### 順張り（rsi_max > rsi_base, bb_z_max > bb_z_base）

**計算式**:
```
raw_score = (value - base) / (max - base)
```
- 分母が**正**（max > base）
- `value`が大きいほど`raw_score`が大きくなる
- **上昇トレンドを追う**

**例**:
- `rsi_base = 50`, `rsi_max = 80`（順張り）
- `rsi = 75` → `raw_score = (75-50)/(80-50) = 0.833`（高いスコア）
- `rsi = 40` → `raw_score = (40-50)/(80-50) = -0.333`（低いスコア）

#### 逆張り（rsi_max < rsi_base, bb_z_max < bb_z_base）

**計算式**:
```
raw_score = (value - base) / (max - base)
```
- 分母が**負**（max < base）
- `value`が小さいほど`raw_score`が大きくなる（符号が反転）
- **下落局面で買う**

**例**:
- `rsi_base = 70`, `rsi_max = 40`（逆張り）
- `rsi = 35` → `raw_score = (35-70)/(40-70) = -35/-30 = 1.167`（高いスコア）
- `rsi = 75` → `raw_score = (75-70)/(40-70) = 5/-30 = -0.167`（低いスコア）

### 2. Sigmoid化の効果

#### クリップ処理（以前の実装）

```python
bb_score = np.clip(raw_score, 0.0, 1.0)
```

**問題点**:
- `raw_score > 1.0` → すべて`1.0`に張り付く
- `raw_score < 0.0` → すべて`0.0`に張り付く
- 銘柄の並びが不安定（同じスコアが大量発生）
- ノイズで順位が入れ替わる

**例**:
```
銘柄A: raw_score = 1.5 → bb_score = 1.0
銘柄B: raw_score = 2.0 → bb_score = 1.0  （区別できない！）
銘柄C: raw_score = 0.5 → bb_score = 0.5
```

#### Sigmoid化（現在の実装）

```python
k = 3.0  # スケーリング係数
sigmoid_score = 1.0 / (1.0 + exp(-k * (raw_score - 0.5)))
```

**効果**:
- 0/1への張り付きを防止
- 滑らかな分布で銘柄の並びが安定
- ノイズに対する耐性が向上

**例**:
```
銘柄A: raw_score = 1.5 → sigmoid_score = 0.952
銘柄B: raw_score = 2.0 → sigmoid_score = 0.998  （区別できる！）
銘柄C: raw_score = 0.5 → sigmoid_score = 0.500
```

**Sigmoid関数の特性**:
- `raw_score = 0.5` → `sigmoid_score = 0.5`（中心）
- `raw_score → +∞` → `sigmoid_score → 1.0`（上限に漸近）
- `raw_score → -∞` → `sigmoid_score → 0.0`（下限に漸近）
- `k`が大きいほど急峻（k=3.0で適度な滑らかさ）

### 3. 最小幅制約の重要性

```python
rsi_min_width = 5.0
if abs(rsi_max - rsi_base) < rsi_min_width:
    raise optuna.TrialPruned("RSI width too small")
```

**目的**: 分母が0に近くなるのを防ぐ

**問題のあるケース**:
```
rsi_base = 50.0
rsi_max = 52.0
rsi_diff = 52.0 - 50.0 = 2.0  （小さい！）

rsi = 51.0 の場合:
raw_score = (51.0 - 50.0) / 2.0 = 0.5

rsi = 51.1 の場合:
raw_score = (51.1 - 50.0) / 2.0 = 0.55  （わずかな差で大きく変動）
```

**最小幅制約により**:
- `rsi_base = 50.0`, `rsi_max = 52.0` → 幅=2.0 < 5.0 → **prune**（スキップ）
- `rsi_base = 50.0`, `rsi_max = 60.0` → 幅=10.0 >= 5.0 → **OK**（計算続行）

**BB Z-scoreも同様**:
```
bb_z_min_width = 0.3
if abs(bb_z_max - bb_z_base) < bb_z_min_width:
    raise optuna.TrialPruned("BB width too small")
```

### 4. 3期間の最大値を採用

```python
scores = [period_score_20d, period_score_60d, period_score_90d]
entry_score = max(scores)
```

**理由**: 最も売られすぎている（または買われすぎている）期間を採用

**例**:
```
period_score_20d = 0.731  （20日が最も買われている）
period_score_60d = 0.650
period_score_90d = 0.580

entry_score = max(0.731, 0.650, 0.580) = 0.731
```

**設計思想**:
- 短期（20日）で急騰 → 高スコア
- 中期（60日）で上昇トレンド → 高スコア
- 長期（90日）で上昇トレンド → 高スコア
- **いずれかが高ければエントリー推奨**

## 計算例のまとめ

### 順張りパラメータの場合

| 銘柄 | RSI | BB Z | raw_score (RSI) | raw_score (BB) | sigmoid (RSI) | sigmoid (BB) | period_score | entry_score |
|------|-----|------|-----------------|----------------|---------------|--------------|--------------|-------------|
| A | 75.0 | 2.5 | 0.833 | 0.833 | 0.731 | 0.731 | 0.731 | 0.731 |
| B | 60.0 | 1.5 | 0.333 | 0.500 | 0.377 | 0.500 | 0.452 | 0.452 |
| C | 40.0 | -1.0 | -0.333 | -0.333 | 0.119 | 0.119 | 0.119 | 0.119 |

**解釈**: 高いRSI/BB Z-scoreの銘柄が高スコア

### 逆張りパラメータの場合

| 銘柄 | RSI | BB Z | raw_score (RSI) | raw_score (BB) | sigmoid (RSI) | sigmoid (BB) | period_score | entry_score |
|------|-----|------|-----------------|----------------|---------------|--------------|--------------|-------------|
| D | 35.0 | -2.0 | 1.167 | 1.333 | 0.881 | 0.924 | 0.907 | 0.907 |
| E | 50.0 | 0.0 | 0.667 | 0.667 | 0.622 | 0.622 | 0.622 | 0.622 |
| F | 75.0 | 2.0 | -0.167 | -0.667 | 0.378 | 0.119 | 0.215 | 0.215 |

**解釈**: 低いRSI/BB Z-scoreの銘柄が高スコア（逆張り）

## 探索範囲の対称性

### 実装方式

**baseとmaxを同じ範囲から独立にサンプル**:
```python
RSI_LOW, RSI_HIGH = 30.0, 85.0
rsi_base = trial.suggest_float("rsi_base", RSI_LOW, RSI_HIGH)
rsi_max = trial.suggest_float("rsi_max", RSI_LOW, RSI_HIGH)
```

### 対称性の確認

**RSI**:
- `rsi_base`: 30.0-85.0（独立にサンプル）
- `rsi_max`: 30.0-85.0（独立にサンプル）
- **結果**: `rsi_max > rsi_base`（順張り）と`rsi_max < rsi_base`（逆張り）が**同確率**

**BB Z-score**:
- `bb_z_base`: -3.0-4.5（独立にサンプル）
- `bb_z_max`: -3.0-4.5（独立にサンプル）
- **結果**: `bb_z_max > bb_z_base`（順張り）と`bb_z_max < bb_z_base`（逆張り）が**同確率**

### 探索例

**Trial 1**:
- `rsi_base = 50.0`, `rsi_max = 80.0` → 順張り（幅=30.0）
- `bb_z_base = 0.0`, `bb_z_max = 3.0` → 順張り（幅=3.0）

**Trial 2**:
- `rsi_base = 70.0`, `rsi_max = 40.0` → 逆張り（幅=30.0）
- `bb_z_base = 2.0`, `bb_z_max = -1.0` → 逆張り（幅=3.0）

**Trial 3**:
- `rsi_base = 60.0`, `rsi_max = 45.0` → 逆張り（幅=15.0）
- `bb_z_base = -1.0`, `bb_z_max = 2.0` → 順張り（幅=3.0）（混合）

**Trial 4**:
- `rsi_base = 55.0`, `rsi_max = 57.0` → 順張り（幅=2.0 < 5.0）→ **prune**（最小幅制約違反）

Optunaはこれらの組み合わせを探索し、最適な方向性を見つけます。

## 実際の探索例

**Trial 1**:
- `rsi_base = 50.0`, `rsi_max = 80.0` → 順張り
- `bb_z_base = 0.0`, `bb_z_max = 3.0` → 順張り

**Trial 2**:
- `rsi_base = 70.0`, `rsi_max = 40.0` → 逆張り
- `bb_z_base = 2.0`, `bb_z_max = -1.0` → 逆張り

**Trial 3**:
- `rsi_base = 60.0`, `rsi_max = 45.0` → 逆張り
- `bb_z_base = -1.0`, `bb_z_max = 2.0` → 順張り（混合）

Optunaはこれらの組み合わせを探索し、最適な方向性を見つけます。

