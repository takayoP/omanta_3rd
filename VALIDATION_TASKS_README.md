# 検証タスク実行ガイド

ChatGPTの助言に基づいて、以下の2つの検証タスクを実行します。

## タスク1: データ量を増やしてテスト本数を増やす

現在、各seedでテストポートフォリオ数が7本しかないため、期間を伸ばして同じ検証を再実行します。

### 実行方法

```powershell
# より長い期間で12Mテストを実行（例: 2018-01-01 ～ 2024-12-31）
python test_seed_robustness_fixed_horizon_extended.py `
    --json-file optimization_result_optimization_longterm_studyC_20260102_205614.json `
    --start 2018-01-01 `
    --end 2024-12-31 `
    --horizon 12 `
    --n-seeds 20

# 24Mテスト
python test_seed_robustness_fixed_horizon_extended.py `
    --json-file optimization_result_optimization_longterm_studyC_20260102_205614.json `
    --start 2018-01-01 `
    --end 2024-12-31 `
    --horizon 24 `
    --n-seeds 20

# 36Mテスト
python test_seed_robustness_fixed_horizon_extended.py `
    --json-file optimization_result_optimization_longterm_studyC_20260102_205614.json `
    --start 2018-01-01 `
    --end 2024-12-31 `
    --horizon 36 `
    --n-seeds 20
```

### パラメータ説明

- `--json-file`: 最良パラメータを含むJSONファイル
- `--start`: 開始日（YYYY-MM-DD）
- `--end`: 終了日（YYYY-MM-DD）
- `--horizon`: ホライズン（月数: 12, 24, 36）
- `--n-seeds`: テストするseedの数（デフォルト: 20）
- `--train-ratio`: 学習データの割合（デフォルト: 0.8）
- `--cost-bps`: 取引コスト（bps、デフォルト: 0.0）
- `--cache-dir`: キャッシュディレクトリ（デフォルト: cache/features）
- `--n-jobs`: 並列数（-1で自動、デフォルト: -1）
- `--output`: 結果をJSONファイルに保存（Noneの場合は自動生成）

### 出力

- `seed_robustness_fixed_horizon_{horizon}M_extended.json`: テスト結果（JSON形式）

### 期待される改善

- テストポートフォリオ数が増加（7本 → 15本以上）
- より安定した統計結果
- より信頼性の高いseed耐性評価

---

## タスク2: Walk-Forward検証（時系列で外挿性確認）

ランダム分割seed耐性は確認できたので、最後に「前半最適化→後半評価」を複数区間で回して、実運用の外挿性を確認します。

**重要**: 2025年を最終ホールドアウトとして使用することを推奨します（`--use-2025-holdout`オプション）。

### 実行方法

#### 通常のWalk-Forward検証（2025年を含まない）

```powershell
# 12MホライズンでWalk-Forward検証（3fold、最小Train期間2年）
python walk_forward_longterm.py `
    --start 2018-01-01 `
    --end 2024-12-31 `
    --horizon 12 `
    --folds 3 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C
```

#### 2025年を最終ホールドアウトとして使用（推奨）

**案A: シンプル3分割**
- Train: 最初の年～最終年-2
- Validate: 最終年-1（パラメータ選定）
- Test（ホールドアウト）: 最終年（最後に1回）

```powershell
# 12Mホライズン（シンプル3分割、推奨）
python walk_forward_longterm.py `
    --start 2020-01-01 `
    --end 2025-12-31 `
    --horizon 12 `
    --folds 1 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C `
    --use-2025-holdout `
    --fold-type simple `
    --seed 42

# 24Mホライズン（シンプル3分割）
python walk_forward_longterm.py `
    --start 2020-01-01 `
    --end 2025-12-31 `
    --horizon 24 `
    --folds 1 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C `
    --use-2025-holdout `
    --fold-type simple `
    --seed 42

# ⚠️  36Mホライズンは2025年ホールドアウトには不適切
# 36Mホライズンで評価するには2028年末までのデータが必要
# 36Mを使う場合は --end 2028-12-31 まで伸ばすか、2025年ホールドアウトを使わない
```

**案B: ロール（複数スプリット）+ 最終年は最後に残す（より強い）**
- Split1: Train 最初の年～最終年-3 → Test 最終年-2
- Split2: Train 最初の年～最終年-2 → Test 最終年-1
- 最後: Train 最初の年～最終年-1 → Test 最終年

```powershell
# 12Mホライズン（ロール方式）
python walk_forward_longterm.py `
    --start 2020-01-01 `
    --end 2025-12-31 `
    --horizon 12 `
    --folds 3 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C `
    --use-2025-holdout `
    --fold-type roll `
    --seed 42

# 24Mホライズン（ロール方式）
python walk_forward_longterm.py `
    --start 2020-01-01 `
    --end 2025-12-31 `
    --horizon 24 `
    --folds 3 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C `
    --use-2025-holdout `
    --fold-type roll `
    --seed 42

# ⚠️  36Mホライズンは2025年ホールドアウトには不適切
# 36Mホライズンで評価するには2028年末までのデータが必要
```

### パラメータ説明

- `--start`: 開始日（YYYY-MM-DD）
- `--end`: 終了日（YYYY-MM-DD）
- `--horizon`: ホライズン（月数: 12, 24, 36）
- `--folds`: fold数（デフォルト: 3）
- `--train-min-years`: 最小Train期間（年、デフォルト: 2.0）
- `--n-trials`: 最適化の試行回数（デフォルト: 50）
- `--study-type`: スタディタイプ（A: BB寄り・低ROE、B: Value寄り・ROE高め、C: 統合・広範囲、デフォルト: C）
- `--seed`: 乱数シード（デフォルト: None、再現性を上げるには `--seed 42` を推奨）
- `--cache-dir`: キャッシュディレクトリ（デフォルト: cache/features）
- `--use-2025-holdout`: 2025年を最終ホールドアウトとして使用（デフォルト: False）
- `--fold-type`: foldタイプ（`roll`: ロール方式、`simple`: シンプル3分割、デフォルト: `roll`）
- `--output`: 結果をJSONファイルに保存（Noneの場合は自動生成）

### 出力

- `walk_forward_longterm_{horizon}M.json`: Walk-Forward検証結果（JSON形式）

### 検証内容

各foldで以下を実行：

1. **Train期間で最適化**: 前半期間でパラメータを最適化
2. **Test期間で評価**: 後半期間で固定パラメータでバックテスト
3. **複数foldで繰り返し**: 時系列順に複数のfoldで検証

### 期待される結果

- 各foldのTest期間での年率超過リターン
- 複数foldの平均・中央値・最小・最大
- 実運用での外挿性の確認

---

## 実行順序の推奨

1. **まずタスク1を実行**: より長い期間でのseed耐性テストで、テストポートフォリオ数を増やす
2. **次にタスク2を実行**: Walk-Forward検証で、時系列での外挿性を確認

---

## 注意事項

- データ範囲の確認: 実行前に、データベースに必要な期間のデータが存在することを確認してください
- 実行時間: 両方のタスクとも、並列化されていますが、長時間かかる可能性があります
- キャッシュ: 特徴量キャッシュが自動的に構築されますが、初回実行時は時間がかかります

---

## 結果の解釈

### タスク1（拡張版seed耐性テスト）

- **テストポートフォリオ数**: 7本 → 15本以上に増加しているか確認
- **統計の安定性**: 標準偏差やパーセンタイルがより安定しているか確認
- **合格判定**: 中央値 > 0 かつ 正の割合 ≥ 60%（12Mの場合）

### タスク2（Walk-Forward検証）

- **各foldの結果**: 各foldでTest期間の年率超過リターンが正の値か確認
- **fold間の一貫性**: 複数foldで一貫して良い結果が出ているか確認
- **外挿性**: Train期間で最適化したパラメータが、Test期間でも有効か確認
- **2025年ホールドアウト**: 2025年を最終ホールドアウトとして使用した場合、その結果が特に重要（実運用の緊張感に最も近い）

### 最終年ホールドアウトの重要性

ChatGPTのアドバイスに基づき、最終年を「絶対に最適化に触らせない」最終テストとして使用することを推奨します。

**注意点**:
- 最終年は一切チューニングに使わない
- 最終年より前の期間で最適化やパラメータ探索を行う
- 最終年は最後に1回だけ評価（ここで良ければかなり強い）

**⚠️ 重要な制約: ホライズンと終了日の関係**
- `--horizon 36`で`--end 2025-12-31`の場合、2025年を起点に36ヶ月の評価をするには**2028年末までの価格データが必要**です
- 2025年ホールドアウトを使う場合は、`--horizon 12`または`--horizon 24`を推奨
- 36Mホライズンで評価したい場合は、`--end 2028-12-31`まで伸ばすか、2025年ホールドアウトを使わない

**推奨コマンド**:
- 2025年ホールドアウト: `--horizon 12`または`--horizon 24`
- 36Mホライズン: `--end 2028-12-31`（データがある前提）または2025年ホールドアウトを使わない

**再現性の向上**:
- `--seed 42`を指定することで、Optunaの最適化結果が再現可能になります

