# 最適化システム全体概要

このドキュメントでは、本リポジトリで利用可能な最適化システムの全体像を説明します。

**最終更新日**: 2025-12-30  
**バージョン**: 1.0

---

## 目次

1. [最適化システムの分類](#1-最適化システムの分類)
2. [旧形式の最適化（累積リターン版）](#2-旧形式の最適化累積リターン版)
3. [時系列最適化（open-close方式）](#3-時系列最適化open-close方式)
4. [信頼性向上型最適化](#4-信頼性向上型最適化)
5. [OOS/WFA評価システム](#5-ooswfa評価システム)
6. [使い分けガイド](#6-使い分けガイド)
7. [推奨ワークフロー](#7-推奨ワークフロー)

---

## 1. 最適化システムの分類

本リポジトリには、以下の最適化システムが実装されています：

| システム | ファイル | 計算方法 | 用途 |
|---------|---------|---------|------|
| **旧形式最適化** | `optimize.py` | 累積リターン（ti→最終日） | 既存システムとの互換性 |
| **時系列最適化** | `optimize_timeseries.py` | 月次リターン（ti→ti+1） | **推奨**：標準的なバックテスト指標 |
| **信頼性向上型最適化** | `robust_optimize_timeseries.py` | WFAの複数foldで評価 | 過学習を避けた安定パラメータ探索 |
| **WFA評価** | `walk_forward_timeseries.py` | foldごとにtrain/test分割 | 過学習検証 |
| **ホールドアウト評価** | `holdout_eval_timeseries.py` | train/holdout分割 | 過学習検証 |

### 計算方法の違い

#### 旧形式（累積リターン版）
```
リバランス日 t0 → 最終評価日（例: 2025-12-31）
リバランス日 t1 → 最終評価日
リバランス日 t2 → 最終評価日
...
```
- **問題点**: 各ポートフォリオの期間が異なるため、時系列指標として解釈できない
- **用途**: 既存システムとの互換性維持

#### 時系列版（open-close方式）✅ 推奨
```
リバランス日 t0 → リバランス日 t1（月次リターン）
リバランス日 t1 → リバランス日 t2（月次リターン）
リバランス日 t2 → リバランス日 t3（月次リターン）
...
```
- **売買タイミング**: 
  - 購入: リバランス日の翌営業日 `t+1` の寄り成（open）
  - 売却: 次のリバランス日 `t_next` の引け成（close）
  - 期間リターン: `open(t+1) → close(t_next)`
- **利点**: 標準的なバックテスト指標（Sharpe、Sortino、MaxDD）として解釈可能

---

## 2. 旧形式の最適化（累積リターン版）

### ファイル
- `src/omanta_3rd/jobs/optimize.py`

### 計算方法
各リバランス日から**最終評価日**までの累積リターンを計算します。

### 特徴
- **用途**: 既存システムとの互換性維持
- **期間**: 各ポートフォリオごとに異なる期間
- **指標**: 銘柄間の平均・分散（時系列指標ではない）
- **問題点**: 時系列指標（Sharpe、Sortino、MaxDD）として解釈できない

### 使用方法
```bash
python -m omanta_3rd.jobs.optimize \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --n-trials 50 \
  --cost 0.0
```

### 出力
- `optimization_result_{study_name}.json`: 最適化結果
- `optimization_history_{study_name}.png`: 最適化履歴
- `param_importances_{study_name}.png`: パラメータ重要度

### 注意点
- **非推奨**: 時系列指標として解釈できないため、新規最適化には使用しないことを推奨
- **用途**: 既存の最適化結果との比較・互換性維持のみ

---

## 3. 時系列最適化（open-close方式）✅ 推奨

### ファイル
- `src/omanta_3rd/jobs/optimize_timeseries.py`

### 計算方法
各リバランス日から**次のリバランス日**までの月次リターンを計算します。

### 特徴
- **用途**: 標準的なバックテスト指標を計算する最適化
- **期間**: 各ポートフォリオは1ヶ月間（ti→ti+1）
- **指標**: 時系列リターン系列から標準的な指標を計算
- **売買タイミング**: open-close方式（実運用に近い）

### 目的関数
```python
objective_value = sharpe_ratio  # Sharpe_excess（=IR）を主軸に
```

### 使用方法
```bash
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --n-trials 50 \
  --cost 0.0 \
  --n-jobs -1
```

### パラメータ
- `--start`: 開始日（YYYY-MM-DD）
- `--end`: 終了日（YYYY-MM-DD）
- `--n-trials`: 試行回数（デフォルト: 50）
- `--cost`: 取引コスト（bps、デフォルト: 0.0）
- `--n-jobs`: 並列実行数（-1でCPU数、デフォルト: -1）
- `--study-name`: スタディ名（オプション）
- `--no-progress-window`: 進捗ウィンドウを表示しない

### 出力
- `optimization_result_{study_name}.json`: 最適化結果
- `optimization_history_{study_name}.png`: 最適化履歴
- `param_importances_{study_name}.png`: パラメータ重要度
- `optuna_{study_name}.db`: Optunaスタディデータベース

### 計算される指標
- **Sharpe_excess**: 月次超過リターン系列のSharpe（年率化）= IR
- **平均超過リターン**: 月次超過リターン系列の平均
- **勝率**: 月次超過リターンが正の割合

### 利点
- 標準的なバックテスト指標として解釈可能
- エクイティカーブからMaxDDを計算可能
- 月次リバランス戦略としてのパフォーマンスを評価可能

---

## 4. 信頼性向上型最適化

### ファイル
- `src/omanta_3rd/jobs/robust_optimize_timeseries.py`

### 計算方法
WFAの複数foldで各パラメータ候補を評価し、安定性を重視します。

### 特徴
- **用途**: 過学習を避け、複数のfoldで安定したパフォーマンスを示すパラメータを探索
- **評価方法**: 各trialでWFAの全foldを実行し、test期間のパフォーマンスを評価
- **目的関数**: `平均Sharpe_excess - 安定性ペナルティ（標準偏差）`

### 目的関数
```python
objective_value = mean_sharpe + stability_penalty + min_penalty
```
- `mean_sharpe`: 全foldのtest期間のSharpe_excessの平均
- `stability_penalty`: 標準偏差が大きいほどペナルティ（安定性重視）
- `min_penalty`: 最悪ケース（負のSharpe）を避けるペナルティ

### 使用方法
```bash
python -m omanta_3rd.jobs.robust_optimize_timeseries \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --n-trials 20 \
  --folds 3 \
  --train-min-years 2.0 \
  --buy-cost 10.0 \
  --sell-cost 10.0 \
  --stability-weight 0.3 \
  --seed 42
```

### パラメータ
- `--start`: 開始日（YYYY-MM-DD）
- `--end`: 終了日（YYYY-MM-DD）
- `--n-trials`: 試行回数（デフォルト: 50、**推奨: 10-20**）
- `--folds`: WFAのfold数（デフォルト: 3）
- `--train-min-years`: 最小Train期間（年、デフォルト: 2.0）
- `--buy-cost`: 購入コスト（bps、デフォルト: 0.0）
- `--sell-cost`: 売却コスト（bps、デフォルト: 0.0）
- `--stability-weight`: 安定性の重み（0.0-1.0、デフォルト: 0.3）
  - 0.0: 平均Sharpe_excessのみ重視
  - 1.0: 安定性のみ重視
- `--seed`: 乱数シード（オプション）
- `--study-name`: スタディ名（オプション）

### 出力
- `artifacts/robust_optimization_result_{timestamp}.json`: 最適化結果

### 注意点
- **計算時間**: 各trialでWFAの全foldを実行するため、計算時間がかかります
- **推奨**: 少数trial（10-20）から始めることを推奨
- **用途**: 通常の最適化で候補を絞った後、信頼性を向上させる段階で使用

---

## 5. OOS/WFA評価システム

### 5.1 Walk-Forward Analysis（WFA）

#### ファイル
- `src/omanta_3rd/jobs/walk_forward_timeseries.py`

#### 目的
過学習の有無を検証するため、foldごとにtrain期間で最適化→test期間で固定評価を繰り返します。

#### 使用方法
```bash
python -m omanta_3rd.jobs.walk_forward_timeseries \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --folds 3 \
  --train-min-years 2.0 \
  --n-trials 50 \
  --buy-cost 10.0 \
  --sell-cost 10.0 \
  --seed 42
```

#### 出力
- `reports/wfa_timeseries_{timestamp}.md`: WFAレポート（Markdown）
- `artifacts/wfa_timeseries_{timestamp}.json`: WFA生データ（JSON）
- `artifacts/best_params_foldX_{timestamp}.json`: foldごとの最良パラメータ

#### レポート内容
- foldごとの詳細メトリクス（CAGR, MaxDD, Sharpe_excess, Sortino_excess, TotalReturn）
- 集計結果（TestのSharpe_excess平均・標準偏差）
- Train vs Test のギャップ（過学習サイン）

### 5.2 ホールドアウト評価

#### ファイル
- `src/omanta_3rd/jobs/holdout_eval_timeseries.py`

#### 目的
Train期間で最適化→Holdout期間で固定評価を行い、過学習の有無を検証します。

#### 使用方法
```bash
python -m omanta_3rd.jobs.holdout_eval_timeseries \
  --train-start 2021-01-01 \
  --train-end 2023-12-31 \
  --holdout-start 2024-01-01 \
  --holdout-end 2025-12-31 \
  --n-trials 50 \
  --buy-cost 10.0 \
  --sell-cost 10.0 \
  --seed 42
```

#### 出力
- `reports/holdout_timeseries_{timestamp}.md`: ホールドアウトレポート（Markdown）
- `artifacts/holdout_timeseries_{timestamp}.json`: ホールドアウト生データ（JSON）
- `artifacts/best_params_holdout_{timestamp}.json`: 最良パラメータ

#### レポート内容
- Train vs Holdout の比較（Sharpe_excess, CAGR, MaxDD）
- ギャップ（過学習サイン）
- 詳細メトリクス

---

## 6. 使い分けガイド

### 6.1 最適化システムの選択

| 用途 | 推奨システム | 理由 |
|------|------------|------|
| **新規最適化** | `optimize_timeseries.py` | 標準的なバックテスト指標として解釈可能 |
| **既存システムとの互換性** | `optimize.py` | 累積リターン版（非推奨） |
| **過学習を避けた安定パラメータ探索** | `robust_optimize_timeseries.py` | WFAの複数foldで評価 |
| **過学習検証** | `walk_forward_timeseries.py` または `holdout_eval_timeseries.py` | OOS評価 |

### 6.2 評価システムの選択

| 用途 | 推奨システム | 理由 |
|------|------------|------|
| **複数期間での安定性確認** | `walk_forward_timeseries.py` | 複数のfoldで評価 |
| **単一期間での検証** | `holdout_eval_timeseries.py` | シンプルなtrain/holdout分割 |

---

## 7. 推奨ワークフロー

### 7.1 基本的な最適化ワークフロー

#### Step 1: 時系列最適化で候補を絞る
```bash
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --n-trials 100 \
  --cost 0.0
```

**目的**: 広い探索空間から候補パラメータを絞り込む

#### Step 2: WFAで過学習を検証
```bash
python -m omanta_3rd.jobs.walk_forward_timeseries \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --folds 3 \
  --train-min-years 2.0 \
  --n-trials 50 \
  --buy-cost 10.0 \
  --sell-cost 10.0
```

**目的**: 最適化結果が過学習していないか確認

#### Step 3: 信頼性向上型最適化（オプション）
```bash
python -m omanta_3rd.jobs.robust_optimize_timeseries \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --n-trials 20 \
  --folds 3 \
  --train-min-years 2.0 \
  --stability-weight 0.3
```

**目的**: 過学習を避け、安定したパラメータを探索

### 7.2 実運用前の最終検証ワークフロー

#### Step 1: ホールドアウト評価
```bash
python -m omanta_3rd.jobs.holdout_eval_timeseries \
  --train-start 2021-01-01 \
  --train-end 2023-12-31 \
  --holdout-start 2024-01-01 \
  --holdout-end 2025-12-31 \
  --n-trials 50 \
  --buy-cost 10.0 \
  --sell-cost 10.0
```

**目的**: 実運用に近い期間で最終検証

#### Step 2: サニティチェック
```bash
python sanity_check_timeseries.py \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --cost 0.0 \
  --output reports/sanity_check_timeseries_YYYYMMDD.md
```

**目的**: データの異常や計算エラーを検出

---

## 8. 計算時間の目安

| システム | 計算時間の目安 | 備考 |
|---------|--------------|------|
| `optimize_timeseries.py` | 1 trialあたり 1-5分 | 並列実行可能（`--n-jobs -1`） |
| `robust_optimize_timeseries.py` | 1 trialあたり 10-30分 | 各trialでWFAの全foldを実行 |
| `walk_forward_timeseries.py` | 全foldで 30-120分 | fold数 × 最適化時間 |
| `holdout_eval_timeseries.py` | 30-60分 | 1回の最適化 + バックテスト |

**注意**: 計算時間はデータ量、期間、試行回数によって大きく異なります。

---

## 9. パラメータの解釈

### 9.1 最適化パラメータ

すべての最適化システムで、以下のパラメータを探索します：

#### StrategyParams
- `w_quality`, `w_value`, `w_growth`, `w_record_high`, `w_size`: Core Scoreの重み
- `w_forward_per`, `w_pbr`: Value Scoreの重み
- `roe_min`: ROEの最小値
- `liquidity_quantile_cut`: 流動性の分位点カット

#### EntryScoreParams
- `rsi_base`, `rsi_max`: RSIの基準値と最大値
- `bb_z_base`, `bb_z_max`: ボリンジャーバンドZスコアの基準値と最大値
- `bb_weight`, `rsi_weight`: BBとRSIの重み

### 9.2 最適化結果の解釈

- **best_value**: 目的関数の値（Sharpe_excessまたは信頼性向上型のスコア）
- **best_params**: 正規化後の最良パラメータ
- **best_params_raw**: 正規化前の最良パラメータ（参考用）

---

## 10. トラブルシューティング

### 10.1 よくある問題

#### 問題: 最適化が終わらない
- **原因**: 試行回数が多すぎる、または計算時間が長い
- **解決策**: `--n-trials`を減らす、または`--n-jobs 1`で逐次実行

#### 問題: WFAのfoldが生成されない
- **原因**: 期間が短すぎる、または`train_min_years`が大きすぎる
- **解決策**: 期間を延ばす、または`--train-min-years`を減らす

#### 問題: ポートフォリオが生成されない
- **原因**: 特徴量データが不足、またはフィルタ条件が厳しすぎる
- **解決策**: データ更新を確認、またはフィルタ条件を緩和

### 10.2 ログの確認

各システムは詳細なログを出力します。以下を確認してください：
- リバランス日数
- ポートフォリオ生成数
- エラーメッセージ

---

## 11. 関連ドキュメント

- `TIMESERIES_REFINEMENT_PLAN.md`: 時系列P/L計算の洗練計画
- `PERFORMANCE_CALCULATION_METHODS.md`: パフォーマンス計算方法の比較
- `OPTIMIZATION_README.md`: 最適化システムの詳細（既存）

---

## 12. まとめ

### 推奨される最適化フロー

1. **時系列最適化**（`optimize_timeseries.py`）で候補を絞る
2. **WFA評価**（`walk_forward_timeseries.py`）で過学習を検証
3. **信頼性向上型最適化**（`robust_optimize_timeseries.py`）で安定パラメータを探索（オプション）
4. **ホールドアウト評価**（`holdout_eval_timeseries.py`）で最終検証
5. **サニティチェック**でデータ異常を確認

### 重要なポイント

- ✅ **時系列最適化**を新規最適化の標準として使用
- ✅ **WFA/holdout評価**で過学習を必ず検証
- ✅ **信頼性向上型最適化**は計算時間を考慮して使用
- ❌ **旧形式最適化**は既存システムとの互換性維持のみ

---

**最終更新日**: 2025-12-30  
**バージョン**: 1.0





