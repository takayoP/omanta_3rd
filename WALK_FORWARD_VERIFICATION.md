# Walk-Forward検証の動作確認

## 確認結果

### 1. JSON読み込みの有無
✅ **既存の最適化結果（JSONファイル）は使用していません**
- `walk_forward_longterm.py`内に`load_best_params`や`optimization_result_*.json`の読み込みは存在しません
- `build_params_from_json`は、最適化結果の`best_params`を`StrategyParams`/`EntryScoreParams`に変換するためだけに使用（外部JSONファイルの読み込みではない）

### 2. Optuna Studyの扱い
✅ **各foldで新規に最適化を実行しています**
- `study_name`: 毎回タイムスタンプで生成（`wfa_longterm_fold_{YYYYMMDD_HHMMSS}`）
- `load_if_exists=False`: 既存studyを読み込まない（新規作成）
- `storage`: 毎回新しいファイル名（`sqlite:///optuna_{study_name}.db`）

### 3. ログ出力（追加済み）
各foldで以下のログを出力します：

```
Train期間で最適化を実行中... (n_trials=50, study_type=C)
⚠️  注意: 既存の最適化結果は使用せず、このfoldのTrain期間で新たに最適化を実行します
Study名: wfa_longterm_fold_20260103_123456 (新規作成)
乱数シード: 42 (再現性あり)
✓ Optunaスタディを作成しました (load_if_exists=False)
最適化を開始します (n_trials=50)...
✓ 最適化完了
  Best trial number: 23
  Best value: 2.3456
  Best params:
    bb_weight: 0.654321
    bb_z_base: -1.234567
    ...
```

## 動作の確認方法

実行時に以下のログを確認してください：

1. **各foldで「最適化を開始します」が表示されるか**
   - 表示されれば、新規最適化を実行している

2. **Best trial numberがfoldごとに異なるか**
   - 異なれば、各foldで独立して最適化している

3. **Study名がfoldごとに異なるか**
   - 異なれば、各foldで新規studyを作成している

4. **「既存の最適化結果は使用せず」という警告が表示されるか**
   - 表示されれば、既存JSONファイルを使っていないことが明確

## 設計の意味

### Walk-Forward検証（`walk_forward_longterm.py`）
- **目的**: 「運用ルール＝定期的に再最適化する戦略」の外挿性評価
- **動作**: 各foldでTrain期間のデータを使って新たに最適化 → Test期間で評価
- **意味**: 実運用で定期的に再最適化する場合の性能を評価

### Seed耐性テスト（`test_seed_robustness_fixed_horizon.py`）
- **目的**: 「Study Cで見つけた固定パラメータが2025でも通用するか」を確認
- **動作**: 既存の最適化結果（JSONファイル）を固定パラメータとして使用
- **意味**: 一度最適化したパラメータを固定して運用する場合の性能を評価

## 補足：固定パラメータモード（将来の拡張案）

「Study Cで見つけた固定パラメータが2025でも通用するか」を見たい場合は、別モードとして以下を用意すると整理が綺麗です：

- `--use-fixed-params --json-file optimization_result_*.json`オプション
- この場合、各foldで最適化せず、指定したJSONファイルのパラメータを固定して使用

現時点では実装していませんが、将来的に追加する価値があります。











