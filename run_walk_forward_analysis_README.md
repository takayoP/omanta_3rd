# Walk-Forward Analysis実行スクリプト

## 概要

長期保有型のWalk-Forward検証を実行するためのPythonスクリプトです。

## スクリプト一覧

### 1. `run_walk_forward_analysis.py`
**評価終了年2025をホールドアウトとして使用する推奨設定**

- ホライズン: 12ヶ月
- Fold数: 1（simple型）
- 評価終了年ホールドアウト: 2025年
- Fold間並列化: 自動（fold数が1のため効果なし）

**実行方法:**
```bash
python run_walk_forward_analysis.py
```

### 2. `run_walk_forward_analysis_roll.py`
**複数foldでWalk-Forward検証を実行（fold間並列化あり）**

- ホライズン: 12ヶ月
- Fold数: 3（roll型）
- Fold間並列化: 自動（fold数とCPU数の最小値）

**実行方法:**
```bash
python run_walk_forward_analysis_roll.py
```

## パラメータ説明

### 基本パラメータ
- `--start`: 開始日（YYYY-MM-DD）
- `--end`: 終了日（YYYY-MM-DD）
- `--horizon`: ホライズン（月数: 12, 24, 36）
- `--folds`: fold数（1: simple, 3: roll）
- `--train-min-years`: 最小Train期間（年）

### 最適化パラメータ
- `--n-trials`: 最適化試行回数（デフォルト: 50）
- `--study-type`: スタディタイプ（A/B/C、デフォルト: C）
- `--seed`: 乱数シード（再現性のため、デフォルト: 42）

### Walk-Forwardパラメータ
- `--holdout-eval-year`: 評価終了年でホールドアウトを指定（例: 2025）
- `--fold-type`: foldタイプ（simple/roll、デフォルト: roll）
- `--n-jobs-fold`: fold間の並列数（-1: 自動, 1: 逐次実行）

## 推奨設定

### 評価終了年2025をホールドアウトとして使用（推奨）
```bash
python walk_forward_longterm.py \
    --start 2020-01-01 \
    --end 2025-12-31 \
    --horizon 12 \
    --folds 1 \
    --train-min-years 2.0 \
    --n-trials 50 \
    --study-type C \
    --holdout-eval-year 2025 \
    --fold-type simple \
    --seed 42 \
    --n-jobs-fold 1
```

### 複数foldでWalk-Forward検証（fold間並列化あり）
```bash
python walk_forward_longterm.py \
    --start 2020-01-01 \
    --end 2025-12-31 \
    --horizon 12 \
    --folds 3 \
    --train-min-years 2.0 \
    --n-trials 50 \
    --study-type C \
    --fold-type roll \
    --seed 42 \
    --n-jobs-fold -1
```

## 注意事項

1. **並列化について**
   - `--n-jobs-fold -1`で自動設定（fold数とCPU数の最小値）
   - fold数が1の場合は並列化の効果なし
   - 各fold内での並列化は無効（プロセス数の爆発を防ぐため）

2. **評価終了年ベースのホールドアウト**
   - `--holdout-eval-year 2025`を指定すると、評価終了年が2025年になるリバランス日のみをテストに使用
   - 12Mホライズンの場合、2024年のリバランス日が対象（2024年リバランス → 12M保有 → 2025年で評価完了）

3. **実行時間**
   - fold間の並列化により、複数foldの場合に実行時間が短縮されます
   - ただし、各fold内での最適化は逐次実行のため、全体の実行時間は最適化試行回数に比例します

## 出力

実行結果は以下の形式でJSONファイルとして保存されます：
- `walk_forward_longterm_YYYYMMDD_HHMMSS.json`

結果には以下が含まれます：
- 各foldの最適化結果（best_params, best_value）
- 各foldのテスト期間パフォーマンス（年率超過リターン、勝率等）
- 全体の集計結果

