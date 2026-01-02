# 長期保有型最適化ガイド

長期保有型のパラメータ最適化システムの使い方を説明します。

## 概要

長期保有型の最適化システムは、リバランス日基準でランダムに学習/テストデータを分割し、過学習を抑制します。

### 主な特徴

1. **学習/テスト分割**: リバランス日をランダムに分割（デフォルト: 80/20）
2. **過学習抑制**: 学習データで最適化、テストデータで評価
3. **評価指標**: 累積リターン、年率リターン、平均超過リターン、勝率
4. **月次リバランス型パラメータの再評価**: 月次リバランス型で最適化したパラメータを長期保有型で評価可能

## 使用方法

### 1. 長期保有型の最適化

**重要: 並列実行の制限**
- `--n-jobs 1`を推奨（Optuna試行の並列を切る）
- `--bt-workers`はCPUに合わせて設定可能（バックテスト側の並列はOK）
- 理由: DB書き込み競合を避けるため（将来的には改善予定）

**Windows PowerShellの場合:**
```powershell
# スモークテスト（5-10試行）
python -m omanta_3rd.jobs.optimize_longterm --start 2020-01-01 --end 2022-12-31 --study-type B --n-trials 10 --n-jobs 1 --bt-workers -1 --train-ratio 0.8 --random-seed 42

# 本番最適化（200試行）
python -m omanta_3rd.jobs.optimize_longterm --start 2020-01-01 --end 2022-12-31 --study-type B --n-trials 200 --n-jobs 1 --bt-workers -1 --train-ratio 0.8 --random-seed 42
```

**Linux/Macの場合:**
```bash
# スモークテスト（5-10試行）
python -m omanta_3rd.jobs.optimize_longterm \
    --start 2020-01-01 \
    --end 2022-12-31 \
    --study-type B \
    --n-trials 10 \
    --n-jobs 1 \
    --bt-workers -1 \
    --train-ratio 0.8 \
    --random-seed 42

# 本番最適化（200試行）
python -m omanta_3rd.jobs.optimize_longterm \
    --start 2020-01-01 \
    --end 2022-12-31 \
    --study-type B \
    --n-trials 200 \
    --n-jobs 1 \
    --bt-workers -1 \
    --train-ratio 0.8 \
    --random-seed 42
```

#### 主要オプション

- `--start`: 開始日（YYYY-MM-DD）
- `--end`: 終了日（YYYY-MM-DD）
- `--study-type`: Studyタイプ（A: BB寄り・低ROE閾値、B: Value寄り・ROE閾値やや高め）
- `--n-trials`: 試行回数（デフォルト: 200）
- `--train-ratio`: 学習データの割合（デフォルト: 0.8）
- `--random-seed`: ランダムシード（デフォルト: 42）
- `--cost-bps`: 取引コスト（bps、デフォルト: 0.0）
- `--n-jobs`: trial並列数（-1でCPU数）
- `--bt-workers`: trial内バックテストの並列数（-1で自動）

#### 実行例

```bash
# Study Aで最適化（50試行、スモークテスト）
python -m omanta_3rd.jobs.optimize_longterm \
    --start 2020-01-01 \
    --end 2022-12-31 \
    --study-type A \
    --n-trials 50 \
    --train-ratio 0.8 \
    --random-seed 42

# Study Bで最適化（200試行、本番）
python -m omanta_3rd.jobs.optimize_longterm \
    --start 2020-01-01 \
    --end 2022-12-31 \
    --study-type B \
    --n-trials 200 \
    --train-ratio 0.8 \
    --random-seed 42 \
    --cost-bps 10.0
```

### 2. 月次リバランス型パラメータの長期保有型評価

月次リバランス型で最適化したパラメータを長期保有型で再評価します。

```bash
# 全データで評価
python evaluate_monthly_params_on_longterm.py \
    --study-name optimization_timeseries_studyB_20251231_174014 \
    --start 2020-01-01 \
    --end 2024-12-31

# テストデータのみで評価
python evaluate_monthly_params_on_longterm.py \
    --study-name optimization_timeseries_studyB_20251231_174014 \
    --start 2020-01-01 \
    --end 2024-12-31 \
    --test-only \
    --train-ratio 0.8 \
    --random-seed 42

# 結果をJSONファイルに保存
python evaluate_monthly_params_on_longterm.py \
    --study-name optimization_timeseries_studyB_20251231_174014 \
    --start 2020-01-01 \
    --end 2024-12-31 \
    --output evaluation_result.json
```

#### 主要オプション

- `--study-name`: Optunaスタディ名（例: `optimization_timeseries_studyB_20251231_174014`）
- `--start`: 開始日（YYYY-MM-DD）
- `--end`: 終了日（YYYY-MM-DD）
- `--test-only`: テストデータのみで評価（デフォルト: False、全データで評価）
- `--train-ratio`: 学習データの割合（`--test-only`使用時、デフォルト: 0.8）
- `--random-seed`: ランダムシード（デフォルト: 42）
- `--output`: 結果をJSONファイルに保存

## 評価指標

長期保有型の最適化では、以下の評価指標を使用します：

1. **年率リターン**: 期間を年換算したリターン
2. **累積リターン**: 全ポートフォリオの平均リターン
3. **平均超過リターン**: TOPIXに対する平均超過リターン
4. **勝率**: 超過リターンが正のポートフォリオの割合

## 月次リバランス型との違い

| 項目 | 月次リバランス型 | 長期保有型 |
|------|----------------|-----------|
| 評価指標 | Sharpe ratio（年率化）、月次勝率 | 年率リターン、累積リターン、勝率 |
| データ分割 | なし（全期間で最適化） | あり（学習/テスト分割） |
| 過学習抑制 | なし | あり（テストデータで評価） |
| 目的関数 | Sharpe ratio | 年率リターン |

## 注意事項

1. **データ分割**: リバランス日をランダムに分割するため、同じ`random_seed`を使用すると同じ分割になります。
2. **最適化中のDB保存**: 最適化中は一時的にポートフォリオをDBに保存しますが、計算後に削除されます。
3. **評価指標**: 長期保有型では月次リバランス型の標準的な評価指標（Sharpe ratio等）は計算しません。
4. **並列実行の制限**: `--n-jobs 1`を推奨（Optuna試行の並列を切る）。DB書き込み競合を避けるため。`--bt-workers`はCPUに合わせて設定可能。

## 実行フロー

### 長期保有型の最適化

```
1. リバランス日を取得
2. 学習/テストに分割（ランダム）
3. 特徴量キャッシュを構築
4. 学習データで最適化（Optuna）
5. テストデータで評価
6. 結果を表示・保存
```

### 月次リバランス型パラメータの評価

```
1. Optunaスタディからパラメータを読み込み
2. リバランス日を取得
3. 評価用のリバランス日を決定（全データ or テストデータのみ）
4. 特徴量キャッシュを構築
5. 長期保有型で評価
6. 結果を表示・保存
```

## トラブルシューティング

### エラー: "No portfolios were generated"

- 特徴量が正しく計算されているか確認
- リバランス日の範囲が正しいか確認
- データベースに価格データが存在するか確認

### エラー: "No price data available"

- データベースに価格データが存在するか確認
- `--start`と`--end`の範囲が正しいか確認

### 最適化が遅い

- `--n-jobs`と`--bt-workers`を調整
- 特徴量キャッシュを事前に構築
- 試行回数を減らす（`--n-trials`）

## 関連ファイル

- `src/omanta_3rd/jobs/optimize_longterm.py`: 長期保有型の最適化システム
- `evaluate_monthly_params_on_longterm.py`: 月次リバランス型パラメータの評価
- `src/omanta_3rd/jobs/optimize_timeseries_clustered.py`: 月次リバランス型の最適化システム

