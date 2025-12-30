# 最適化実行例（並列化・高速化対応版）

## 概要

`optimize_timeseries.py`に以下の改善を実装しました：

1. **並列化制御の改善**
   - `--parallel-mode`: trial/backtest/hybrid の選択
   - `--n-jobs`: trial並列数
   - `--bt-workers`: trial内バックテストの並列数

2. **BLASスレッド制御**
   - プロセス並列時の過負荷を防ぐため、BLASスレッドを1に固定

3. **時間計測ログ**
   - 各trialのデータ取得時間、保存時間、時系列計算時間、指標計算時間を計測

4. **サマリーレポート**
   - best/p95/medianのSharpe_excess分布
   - 上位5 trialのパラメータ分布

## 実行例

### Step 1: 追加トライアル（10〜20）を回す（同一期間）

**目的**: bestが再現するかを確認

**見るべき指標**:
- best / p95 / median の Sharpe_excess
- 上位5 trial のパラメータ分布（極端にブレるか）
- missing_count が上位に偏ってないか（欠損が都合よく効いていないか）

**合格ライン（目安）**:
- bestが0.44付近でも、p95が0.30前後、medianが0.10〜0.20なら「普通にあり得る上振れ」
- bestだけ0.44で、他が0近辺なら「当たりの可能性が高い」

#### SQLiteストレージ（推奨：まずはこれ）

```bash
# Windows PowerShell
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:OPENBLAS_NUM_THREADS="1"
$env:NUMEXPR_NUM_THREADS="1"
python -m omanta_3rd.jobs.optimize_timeseries `
  --start 2021-01-01 `
  --end 2024-12-31 `
  --n-trials 20 `
  --study-name optimization_timeseries_20251230_phase1 `
  --parallel-mode trial `
  --n-jobs 4 `
  --bt-workers 1 `
  --no-progress-window
```

```bash
# Linux/Mac
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2024-12-31 \
  --n-trials 20 \
  --study-name optimization_timeseries_20251230_phase1 \
  --parallel-mode trial \
  --n-jobs 4 \
  --bt-workers 1 \
  --no-progress-window
```

#### Postgresストレージ（可能なら：高速化しやすい）

```bash
# Windows PowerShell
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:OPENBLAS_NUM_THREADS="1"
$env:NUMEXPR_NUM_THREADS="1"
python -m omanta_3rd.jobs.optimize_timeseries `
  --start 2021-01-01 `
  --end 2024-12-31 `
  --n-trials 50 `
  --study-name optimization_timeseries_20251230_phase1 `
  --storage postgresql://user:pass@host/db `
  --parallel-mode trial `
  --n-jobs -1 `
  --bt-workers 1 `
  --no-progress-window
```

### Step 2: Holdout（1年）で"崩れ方"を見る

**推奨分割**:
- Train: 2021-2023
- Holdout: 2024

**判定の勘所**:
- Holdout Sharpe_excess が Train の **50〜70%**残るならかなり良い
- 0付近〜マイナスなら、過学習か、相場局面依存が強い

#### Train期間で最適化

```bash
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2023-12-31 \
  --n-trials 50 \
  --study-name optimization_timeseries_train \
  --parallel-mode trial \
  --n-jobs 4 \
  --bt-workers 1 \
  --no-progress-window
```

#### Holdout期間で検証

最適化結果JSONからパラメータを読み込んで、Holdout期間で実行します。
`create_portfolio_from_optimization.py`を参考に、最適化結果JSONを読み込んで実行してください。

### Step 3: WFA / Robust（fold=3）へ

最後にWFA/Robustで「時間方向の安定性」を確認。

```bash
python -m omanta_3rd.jobs.robust_optimize_timeseries \
  --start 2021-01-01 \
  --end 2024-12-31 \
  --n-trials 30 \
  --folds 3 \
  --train-min-years 2.0 \
  --stability-weight 0.3
```

## 並列化モードの説明

### `--parallel-mode trial`（推奨）

- Optuna trialを並列化
- trial内バックテストは逐次（`--bt-workers 1`）
- SQLite環境では`--n-jobs 2〜4`を推奨
- Postgres環境では`--n-jobs -1`（自動）も可能

### `--parallel-mode backtest`

- Optuna trialは逐次
- trial内バックテストを並列化（`--bt-workers`で指定）
- 価格データを事前にメモリにロードしている場合に有効

### `--parallel-mode hybrid`

- 二重並列（trial並列 × trial内並列）
- `n_jobs * bt_workers <= physical_cores`を厳守
- SQLite競合が増える可能性があるため、原則"最後の手段"

## パラメータ説明

- `--n-jobs`: trial並列数（-1で自動、parallel-mode='trial'の場合に使用）
- `--bt-workers`: trial内バックテストの並列数（デフォルト: 1）
- `--parallel-mode`: 並列化モード（trial/backtest/hybrid）
- `--storage`: Optunaストレージ（Noneの場合はSQLite、例: 'postgresql://...'）
- `--no-progress-window`: 進捗ウィンドウを表示しない（推奨）

## 出力される情報

### 各trialのログ例

```
[Trial 0] objective=0.4448, excess_return=0.4210%, win_rate=0.5000, sharpe=0.4448 | time=12.34s (data=8.90s, save=0.50s, timeseries=2.50s, metrics=0.44s)
```

### 最適化終了時のサマリー

```
================================================================================
【最適化サマリー】
================================================================================
完了試行数: 20
Sharpe_excess分布:
  best: 0.4448
  p95: 0.3200 (72.0% of best)
  median: 0.1500 (33.7% of best)

上位5 trialのパラメータ範囲:
  w_value: 0.3500 ~ 0.4100 (range: 0.0600)
  w_forward_per: 0.6000 ~ 0.6500 (range: 0.0500)
  ...
```

## 注意事項

1. **BLASスレッド制御**: 環境変数は自動設定されますが、手動で設定することも可能です
2. **SQLiteの並列数**: 多数並列書き込みはロック待ちが増えるため、`--n-jobs 2〜4`を推奨
3. **Postgresストレージ**: 可能ならOptunaストレージだけPostgresにすると並列スケールが改善しやすい
4. **CPU利用率**: 理論上「1/8」などの線形短縮は、IO/DB競合で崩れることが多い。まずは「総処理時間が減るか」「trial/秒が上がるか」をKPIにする

