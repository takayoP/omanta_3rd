# Walk-Forward検証の改善点

## 1. 並列化について

現在の実装では、**fold間は逐次実行**されています。各fold内の最適化も逐次実行（`n_jobs=1`）です。

### 並列化の現状
- **Fold間**: 逐次実行（並列化なし）
- **各fold内の最適化**: 逐次実行（`n_jobs=1`）
- **特徴量キャッシュ構築**: 並列化済み（`n_jobs=-1`）

### 並列化の検討
- Fold間の並列化は、Optunaのストレージ競合の可能性があるため、現状は逐次実行が安全
- 各fold内の最適化は、Optunaの`n_jobs`パラメータで並列化可能だが、WFAでは逐次実行を推奨

## 2. 評価終了年ベースの分割（修正済み）

### 問題点
以前の実装では、Train/Validate/Testの分割が**リバランス年ベース**になっていました。これでは、ValidateとTestが同じリバランス年で衝突する可能性がありました。

### 修正内容
- **Train/Validate/Testの分割を評価終了年ベースに変更**
- 各リバランス日の評価終了年を計算し、それに基づいて分類
- Disjointチェックを追加（train ∩ val = ∅, train ∩ test = ∅, val ∩ test = ∅）

### 正しい対応表（holdout-eval-year=2025固定）

#### 12Mホライズン
- **Test（eval_end_year=2025）**: rebalance 2024
- **Val（eval_end_year=2024）**: rebalance 2023
- **Train（<=2023）**: rebalance <=2022

#### 24Mホライズン
- **Test（=2025）**: rebalance 2023
- **Val（=2024）**: rebalance 2022
- **Train（<=2023）**: rebalance <=2021

#### 36Mホライズン
- **Test（=2025）**: rebalance 2022
- **Val（=2024）**: rebalance 2021
- **Train（<=2023）**: rebalance <=2020

## 3. Disjointチェック（追加済み）

### 実装内容
- Train/Validate/Testの交差チェックを追加
- 重複がある場合は`ValueError`を発生
- 評価終了年ベースの確認ログを追加（デバッグ用）

### チェック項目
- `train_ids ∩ val_ids == ∅`
- `train_ids ∩ test_ids == ∅`
- `val_ids ∩ test_ids == ∅`

## 4. 実行後の確認ポイント

12Mの結果が出たら、次の3つを確認：

1. **fold内の train/val/test のサンプル数**
   - 特にtestが極端に少なくないか
   - ログで確認可能

2. **train/val/test が disjoint**
   - 実行時に自動チェック（エラーで停止）
   - ログで確認可能

3. **test（eval_end_year=2025）の中身が rebalance 2024だけになっているか（12Mの場合）**
   - 評価終了年ベースの確認ログで確認可能

## 5. 今後の改善案（オプション）

### Embargo（間引き）
- Testに使うサンプルの評価開始直前〜一定期間のサンプルを train/val から除外
- 12Mなら 1〜3ヶ月でも効果的
- 現時点では実装していない（まずはWFが破綻なく回ることを優先）

### 評価窓の重なり検知
- 各サンプルが持つ評価窓（start, end）で重なりも検知
- 独立性の弱さを定量化
- 現時点では実装していない















