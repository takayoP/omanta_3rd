# 初期点投入機能の検証チェックリスト

## 目的

`--initial-params-json`機能が正しく動作しているかを確認するためのチェックリストです。

---

## A. 初期点の投入が正しく動くか

### A1. JSON構造の確認

- [ ] `--initial-params-json`から取り出したparamsが`best_trial.params`由来である
  - 確認方法: ログに「初期点として投入しました」と表示される
  - 実装確認: `initial_data.get("best_trial", {}).get("params", {})`を使用している

### A2. 方向パラメータの推論

- [ ] `rsi_direction`と`bb_direction`が正しく推論されている
  - 確認方法: ログに「RSI方向: reversal/momentum」「BB方向: reversal/momentum」と表示される
  - 1/21のJSONには方向パラメータが含まれていないため、推論が必要

### A3. enqueued trialの完走

- [ ] enqueued trialが**pruneされず完走**する
  - 確認方法: Optunaのログで、初期点のtrialが`COMPLETE`状態になる
  - 注意: 初期点だけはprune無効でもよい（実装次第）

### A4. 初期点のvalueが期待値と一致

- [ ] そのtrialのvalueが診断再評価値と概ね一致
  - 期待値: train≈4.108%、test≈4.072%
  - 許容範囲: ±0.5%ポイント程度の誤差は許容

---

## B. warm startが探索に"効いている"か（形跡確認）

### B1. 初期点近傍のサンプリング

- [ ] 初期点の後続trialで、初期点近傍が一定数サンプルされている
  - 確認方法: 後続のtrialのパラメータが初期点に近い値を持つ
  - 注意: 完全一致でなくてよい（近傍探索が行われていればOK）

### B2. best_valueの下限確保

- [ ] best_valueが「初期点のvalue未満」にならない
  - 確認方法: Optunaの`study.best_value`が初期点のvalue以上を維持
  - 注意: 少なくとも下限は確保されるべき

---

## C. 並列起因の再現性が壊れていないか

### C1. シングルスレッドでの再現性

- [ ] `n_jobs=1, bt_workers=1`で2回回した時にbest_valueが大きくズレない
  - 確認方法: 同じseedで2回実行し、best_valueの差が±0.5%ポイント以内
  - 注意: 完全一致は難しいが、大きくズレないことが重要

### C2. 方向パラメータのcategorical化確認

- [ ] 方向がcategorical化されている（trial番号依存を除去）
  - 確認方法: `objective_longterm`関数内で`trial.suggest_categorical("rsi_direction", ...)`を使用している
  - 実装確認: `trial.number % 2`を使用していない

---

## D. JSON構造の確認（実装詳細）

### D1. 正しいキーパスの使用

- [ ] `initial_data.get("best_trial", {}).get("params", {})`を使用している
  - ❌ 誤り: `initial_data.get("best_params")`（存在しない）
  - ❌ 誤り: `initial_data.get("normalized_params")`（派生値が混ざる可能性）

### D2. normalized_paramsの扱い

- [ ] `normalized_params`は使用していない
  - 理由: `normalized_params`は「派生値」も入っているため、trialのsuggest空間と一致しないキーが混ざる可能性がある

---

## 実行手順

### ステップ0: 最小限の確認（必須）

```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
  --n-trials 1 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 1 \
  --bt-workers 1 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

**確認項目**: A1, A2, A3, A4

### ステップ1: warm startの確認

```bash
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
  --n-trials 30 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 1 \
  --bt-workers 4 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

**確認項目**: B1, B2

### ステップ2: 再現性の確認

```bash
# 1回目
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
  --n-trials 50 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 1 \
  --bt-workers 1 \
  --random-seed 42 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json

# 2回目（同じseedで）
python -m omanta_3rd.jobs.optimize_longterm \
  --start 2018-01-31 \
  --end 2024-12-31 \
  --study-type A \
  --n-trials 50 \
  --train-end-date 2023-12-31 \
  --as-of-date 2024-12-31 \
  --horizon-months 24 \
  --lambda-penalty 0.00 \
  --objective-type mean \
  --n-jobs 1 \
  --bt-workers 1 \
  --random-seed 42 \
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

**確認項目**: C1

---

## トラブルシューティング

### 問題1: 初期点が投入されない

**原因**: JSONファイルのパスが間違っている、またはJSON構造が異なる

**対処**:
1. JSONファイルのパスを確認
2. JSONファイルの構造を確認（`best_trial.params`が存在するか）

### 問題2: 初期点のvalueが期待値と大きく異なる

**原因**: データ更新、評価窓の実装差、スコア/選定ロジックの変更

**対処**:
1. `scripts/reevaluate_best_params.py`で再評価を実行
2. 診断結果を確認（ケースA/Bの判定）

### 問題3: warm startが効いていない

**原因**: 探索範囲が広すぎる、TPEサンプラーの学習が不十分

**対処**:
1. ウォームアップ期間を延長（`n_trials`を増やす）
2. 探索範囲を初期点の近傍に絞る（実装が必要）

---

## 参考

- `docs/diagnosis_results.md`: 診断結果の詳細
- `docs/next_steps_after_diagnosis.md`: 次のステップのガイド
