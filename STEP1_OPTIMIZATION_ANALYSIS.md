# Step 1: 追加トライアル実行と分析

## 目的

**"bestが再現するか"**を確認する。

## 実行手順

### 1. 最適化の実行

```bash
# 20トライアルで実行（同一期間: 2021-01-01 ～ 2024-12-31）
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2024-12-31 \
  --n-trials 20 \
  --study-name optimization_timeseries_20251230_phase1 \
  --no-progress-window
```

**注意**: 実行には時間がかかります（20トライアル × 各バックテスト時間）。

### 2. 結果の分析

最適化が完了したら、以下のコマンドで結果を分析します：

```bash
python analyze_optimization_results.py \
  --study-name optimization_timeseries_20251230_phase1 \
  --output analysis_result_phase1.json
```

## 評価指標

### 1. Sharpe_excessの分布

見るべき指標:
- **best**: 最良値
- **p95**: 95パーセンタイル
- **median**: 中央値

### 2. 上位5 trialのパラメータ分布

各パラメータの範囲比（max/min）を確認:
- **範囲比 > 2.0**: ❌ 極端にブレ
- **範囲比 1.5-2.0**: ⚠️ ややブレ
- **範囲比 < 1.5**: ✅ 安定

### 3. missing_countの分析

**注意**: 現在の実装では、missing_countは最適化結果に保存されていません。
最適化実行時のログを確認するか、最適化スクリプトを修正してuser_attrsに保存する必要があります。

## 合格ライン（目安）

### 良好なケース
- **bestが0.44付近でも、p95が0.30前後、medianが0.10-0.20** → ✅ **普通にあり得る上振れ**
- 上位5 trialのパラメータが安定（範囲比 < 1.5）

### 問題のあるケース
- **bestだけ0.44で、他が0近辺** → ❌ **当たりの可能性が高い**
- 上位5 trialのパラメータが極端にブレ（範囲比 > 2.0）

## 判定基準

### p95とbestの関係
- **p95 ≥ best × 0.68** (約0.30/0.44) → ✅ 再現性良好
- **p95 ≥ best × 0.50** → ⚠️ やや上振れの可能性
- **p95 < best × 0.50** → ❌ 当たりの可能性が高い

### medianとbestの関係
- **medianが0.10-0.20の範囲** (best=0.44の場合、best×0.23-0.45) → ✅ 普通にあり得る上振れ
- **median ≥ best × 0.10** → ⚠️ やや上振れの可能性
- **median < best × 0.10** → ❌ 当たりの可能性が高い

## 次のステップ

### Step 1が合格した場合
→ **Step 2: Holdout検証**に進む

### Step 1が不合格の場合
- パラメータ範囲の見直し
- 目的関数の調整
- データ品質の確認

## 参考

- **1トライアル結果**: Sharpe_excess = 0.4448
- **サニティチェック**: Sharpe_excess ≈ 0.23
- **最適化スクリプト**: `src/omanta_3rd/jobs/optimize_timeseries.py`
- **分析スクリプト**: `analyze_optimization_results.py`















