# 最適化結果の解釈と次のステップ

## TL;DR

**1トライアル結果**: Sharpe_excess = 0.4448（サニティチェック0.23より高い）

**重要なポイント**:
- 1トライアルでは上振れ判定不能。再現性（複数trial）とOOS（Out-of-Sample）で確認が必要
- 勝率50%は補助指標。重要なのはSharpe_excess/MaxDD/mean_excess_return
- パラメータ特徴: バリュー重視(40.9%)、Forward PER重視(64.5%)、BB重視(63.9%)

**次のステップ**:
1. **追加20トライアル**: best/p95/medianのSharpe_excessを確認
2. **Holdout検証**: Train期間で最適化→Holdout期間で検証（HoldoutがTrainの50-70%残れば良好）
3. **WFA/Robust最適化**: 複数foldで時系列的な安定性を評価

---

## 1トライアル結果の概要

### パフォーマンス指標

| 指標 | 値 | 評価 |
|------|-----|------|
| **Sharpe_excess (IR)** | **0.4448** | サニティチェック(0.23)より高い |
| **平均超過リターン** | 0.4210% | 月次で約0.42%の超過リターン |
| **勝率** | 0.5000 (50%) | 補助指標（重要なのはSharpe_excess/MaxDD/mean_excess） |
| **Sharpe** | 0.4448 | IRと同じ（超過リターン系列のSharpe） |

### サニティチェックとの比較

- **サニティチェック結果**: Sharpe_excess ≈ 0.23, MaxDD ≈ -18%
- **1トライアル結果**: Sharpe_excess = 0.4448
- **評価**: 1トライアルでは上振れ判定不能。再現性（複数trial）とOOS（Out-of-Sample）で確認が必要

---

## 最良パラメータの解釈

### Core Score重み（正規化後）

| パラメータ | 値 | デフォルト | 解釈 |
|-----------|-----|-----------|------|
| `w_quality` | 0.2508 (25.1%) | 0.35 (35%) | **品質重視がやや低い** |
| `w_value` | 0.4090 (40.9%) | 0.25 (25%) | **バリュー重視が大幅に高い** |
| `w_growth` | 0.1349 (13.5%) | 0.15 (15%) | 成長性は標準的 |
| `w_record_high` | 0.0325 (3.3%) | 0.15 (15%) | **最高益フラグの重みが非常に低い** |
| `w_size` | 0.1729 (17.3%) | 0.10 (10%) | サイズ重視がやや高い |

**解釈**:
- **バリュー重視**: 40.9%と最も高い重み。割安銘柄を重視する戦略。
- **品質重視**: 25.1%とデフォルトより低い。ROEの重要度がやや下がる。
- **最高益フラグ**: 3.3%と非常に低い。予想最高益の効果が限定的。

### Value Score内訳

| パラメータ | 値 | デフォルト | 解釈 |
|-----------|-----|-----------|------|
| `w_forward_per` | 0.6455 (64.5%) | 0.50 (50%) | **Forward PERを重視** |
| `w_pbr` | 0.3545 (35.5%) | 0.50 (50%) | PBRの重みは低い |

**解釈**: Forward PER（予想PER）をPBRより重視する戦略。

### フィルタリング閾値

| パラメータ | 値 | デフォルト | 解釈 |
|-----------|-----|-----------|------|
| `roe_min` | 0.0839 (8.39%) | 0.10 (10%) | **ROE閾値がやや緩い** |
| `liquidity_quantile_cut` | 0.2845 (28.5%) | 0.20 (20%) | **流動性フィルタがやや緩い** |

**解釈**: 
- ROE閾値が8.39%とデフォルト(10%)より低い。より多くの銘柄を候補に含める。
- 流動性フィルタが28.5%とデフォルト(20%)より緩い。やや流動性の低い銘柄も含める。

### Entry Scoreパラメータ

| パラメータ | 値 | 解釈 |
|-----------|-----|------|
| `rsi_base` | 56.03 | RSI=56以下でスコアが付き始める |
| `rsi_max` | 74.95 | RSI=75以上で最大スコア |
| `bb_z_base` | -0.6510 | BB Z-score=-0.65以下でスコアが付き始める |
| `bb_z_max` | 3.0404 | BB Z-score=3.0以上で最大スコア |
| `bb_weight` | 0.6388 (63.9%) | **BBをRSIより重視** |

**解釈**:
- **BB重視**: 63.9%とRSIより高い。ボリンジャーバンドのZ-scoreを重視。
- **RSI範囲**: 56-75の範囲でスコアが変化。中立的な範囲。
- **BB範囲**: -0.65から3.0の範囲。下位バンドより上でもスコアが付く。

---

## パラメータの特徴まとめ

### 1. バリュー重視戦略
- Core Scoreの40.9%がバリュー（デフォルト25%より高い）
- Forward PERをPBRより重視（64.5% vs 35.5%）

### 2. 品質・成長性は標準的
- 品質: 25.1%（デフォルト35%より低い）
- 成長性: 13.5%（デフォルト15%とほぼ同じ）

### 3. 最高益フラグの効果が限定的
- 重みが3.3%と非常に低い
- 予想最高益の効果が限定的と判断

### 4. エントリータイミングはBB重視
- BB Z-scoreを63.9%重視
- RSIは補助的な役割

### 5. フィルタリングはやや緩い
- ROE閾値: 8.39%（デフォルト10%より低い）
- 流動性: 28.5%カット（デフォルト20%より緩い）

---

## 次のステップの提案

### フェーズ1: 追加トライアル実行（推奨）

**目的**: 再現性を確認し、パラメータの安定性を評価

**推奨アクション**:
```bash
# 20トライアルで追加実行
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2024-12-31 \
  --n-trials 20 \
  --study-name optimization_timeseries_20251230_phase1
```

**評価ポイント**:
1. **Sharpe_excessの分布**: best/p95/medianの値を確認
2. **パラメータの分散**: 最良パラメータが複数トライアルで安定しているか
3. **パラメータ重要度**: Optunaの`plot_param_importances`で重要パラメータを確認

**判断基準（数値で明確化）**:
- **best Sharpe_excess**: 0.4-0.5の範囲で安定 → 次のフェーズへ
- **p95 Sharpe_excess**: bestの80%以上 → 再現性良好
- **median Sharpe_excess**: bestの60%以上 → 中央値も良好
- **best Sharpe_excess > 0.6 かつ 分散が大きい** → 過学習の可能性、WFA/holdoutを検討

---

### フェーズ2: Holdout検証（推奨）

**目的**: 最適化期間とは独立した期間（OOS）でパフォーマンスを検証

**推奨アクション**:
1. **Train期間**: 2021-01-01 ～ 2023-12-31（3年）
2. **Holdout期間**: 2024-01-01 ～ 2024-12-31（1年）

```bash
# 1. Train期間で最適化
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2023-12-31 \
  --n-trials 50 \
  --study-name optimization_timeseries_train

# 2. Holdout期間で検証（最良パラメータを固定）
# create_portfolio_from_optimization.pyを参考に、最適化結果JSONからパラメータを読み込んで実行
# 注意: create_portfolio_from_optimization.pyのmain()関数内で、
#       start_dateとend_dateをHoldout期間（2024-01-01 ～ 2024-12-31）に変更し、
#       result_fileを"optimization_result_optimization_timeseries_train.json"に変更して実行

# または、以下の手順で手動実行:
# a) 最適化結果JSONを読み込む（load_optimization_result）
# b) Holdout期間でポートフォリオを作成（create_portfolio_with_optimized_params）
# c) 時系列P/Lを計算（calculate_timeseries_returns）
# d) メトリクスを計算（calculate_metrics_from_timeseries_data または calculate_sharpe_ratio）
```

**評価ポイント（数値で明確化）**:
1. **Holdout Sharpe_excess**: Train期間の最良値と比較
   - **HoldoutがTrainの70%以上** → 良好（例: Train=0.44 → Holdout≥0.31）
   - **HoldoutがTrainの50-70%** → 許容範囲（例: Train=0.44 → Holdout=0.22-0.31）
   - **HoldoutがTrainの50%以下** → 過学習の可能性（例: Train=0.44 → Holdout<0.22）
2. **パフォーマンスの安定性**: Holdout期間の月次リターン分布を確認
3. **MaxDD**: Holdout期間のMaxDDが-20%以内なら許容範囲

---

### フェーズ3: Walk Forward Analysis (WFA)（推奨）

**目的**: 時系列的に分割して、各期間で最適化→検証を繰り返す

**推奨アクション**:
```bash
# WFA最適化（robust_optimize_timeseries.pyを使用）
python -m omanta_3rd.jobs.robust_optimize_timeseries \
  --start 2021-01-01 \
  --end 2024-12-31 \
  --n-trials 30 \
  --folds 3 \
  --train-min-years 2.0 \
  --stability-weight 0.3
```

**評価ポイント**:
1. **各FoldのSharpe_excess**: 3つのfoldで安定しているか
2. **安定性指標**: 標準偏差が小さいほど良い
3. **最悪ケース**: 最小Sharpe_excessが負でないか

**メリット**:
- 過学習を避けられる
- 時系列的な安定性を評価できる
- 複数のfoldで安定したパラメータを選べる

---

### フェーズ4: Robust最適化（オプション）

**目的**: WFAの複数foldで安定したパフォーマンスを示すパラメータを探索

**推奨アクション**:
```bash
# Robust最適化（既に実装済み）
python -m omanta_3rd.jobs.robust_optimize_timeseries \
  --start 2021-01-01 \
  --end 2024-12-31 \
  --n-trials 50 \
  --folds 3 \
  --train-min-years 2.0 \
  --stability-weight 0.3
```

**評価ポイント**:
1. **平均Sharpe_excess**: 複数foldの平均値
2. **安定性ペナルティ**: 標準偏差が小さいほど良い
3. **最悪ケース**: 最小Sharpe_excessが負でないか

---

## 推奨される実行順序

### ステップ1: 追加トライアル（即座に実行可能）
- **期間**: 20トライアル
- **目的**: 再現性を確認（best/p95/medianのSharpe_excess）
- **判断基準**:
  - best Sharpe_excess: 0.4-0.5の範囲で安定
  - p95 Sharpe_excess: bestの80%以上
  - median Sharpe_excess: bestの60%以上

### ステップ2: Holdout検証（ステップ1の後）
- **期間**: Train 3年 + Holdout 1年
- **目的**: OOS（Out-of-Sample）でのパフォーマンスを確認
- **判断基準**:
  - Holdout Sharpe_excessがTrainの70%以上 → 良好
  - Holdout Sharpe_excessがTrainの50-70% → 許容範囲
  - Holdout Sharpe_excessがTrainの50%以下 → 過学習の可能性

### ステップ3: WFA/Robust最適化（ステップ2の後）
- **期間**: 全期間を3-5 foldに分割
- **目的**: 時系列的な安定性を評価
- **判断**: 複数foldで安定したパラメータを選ぶ

---

## 注意事項

### 1. 再現性とOOS検証の重要性
- **1トライアルのみ**: 上振れ判定不能。再現性（複数trial）とOOSで確認が必要
- **Sharpe_excess = 0.44**: サニティチェック(0.23)より約2倍高いが、1トライアルでは判断不可
- **対策**: 追加20トライアルでbest/p95/medianを確認、Holdout検証、WFAを実施

### 2. パラメータの解釈
- **バリュー重視**: 40.9%と高いが、Forward PER重視（64.5%）
- **最高益フラグ**: 3.3%と非常に低い（効果が限定的）
- **BB重視**: 63.9%と高い（エントリータイミング重視）

### 3. データ欠損の影響
- 警告: 3期間で価格データが欠損（8090, 4423, 2309）
- 影響は限定的だが、データ品質の確認が必要

---

## 次のアクション

### 即座に実行可能
1. **追加トライアル実行**: 10-20トライアルでパラメータの安定性を確認
2. **パラメータ重要度の可視化**: `plot_param_importances`で重要パラメータを確認

### 短期（1-2日）
3. **Holdout検証**: Train/Holdout分割で過学習を確認
4. **WFA実行**: 3-5 foldで時系列的な安定性を評価

### 中期（1週間）
5. **Robust最適化**: 複数foldで安定したパラメータを探索
6. **最終パラメータの決定**: 検証結果を踏まえて最適パラメータを選定

---

## 参考情報

- **サニティチェック**: Sharpe_excess ≈ 0.23, MaxDD ≈ -18%
- **1トライアル結果**: Sharpe_excess = 0.4448
- **最適化スクリプト**: `src/omanta_3rd/jobs/optimize_timeseries.py`
- **Robust最適化**: `src/omanta_3rd/jobs/robust_optimize_timeseries.py`
- **WFA実装**: `src/omanta_3rd/jobs/walk_forward_timeseries.py`

