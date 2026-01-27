# Walk-Forward検証 B案（評価終了年ベース）実行ガイド

現在（2026/1/3、価格データが2025年末まで）の状況では、**評価終了年ベースのホールドアウト（B案）**を使用することを推奨します。

## B案の概要

**評価終了年が2025になるリバランス日**をテストに使用します。

- 例：2024年のリバランス日 → 12M保有 → 2025年内で評価完了
- これなら2025年末までのデータで成立します

## 実行コマンド

### 12Mホライズン（推奨）

```powershell
# シンプル3分割
python walk_forward_longterm.py `
    --start 2020-01-01 `
    --end 2025-12-31 `
    --horizon 12 `
    --folds 1 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C `
    --holdout-eval-year 2025 `
    --fold-type simple `
    --seed 42

# ロール方式
python walk_forward_longterm.py `
    --start 2020-01-01 `
    --end 2025-12-31 `
    --horizon 12 `
    --folds 3 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C `
    --holdout-eval-year 2025 `
    --fold-type roll `
    --seed 42
```

### 24Mホライズン

```powershell
# 24Mホライズンで評価終了年2025 → 2023年のリバランス日が対象
python walk_forward_longterm.py `
    --start 2020-01-01 `
    --end 2025-12-31 `
    --horizon 24 `
    --folds 1 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C `
    --holdout-eval-year 2025 `
    --fold-type simple `
    --seed 42
```

### 36Mホライズン

```powershell
# 36Mホライズンで評価終了年2025 → 2022年のリバランス日が対象
python walk_forward_longterm.py `
    --start 2020-01-01 `
    --end 2025-12-31 `
    --horizon 36 `
    --folds 1 `
    --train-min-years 2.0 `
    --n-trials 50 `
    --study-type C `
    --holdout-eval-year 2025 `
    --fold-type simple `
    --seed 42
```

## パラメータ説明

- `--holdout-eval-year`: 評価終了年でホールドアウトを指定（例: 2025）
  - この年で評価が完了するリバランス日をテストに使用
  - 12Mホライズンなら2024年のリバランス日が対象
  - 24Mホライズンなら2023年のリバランス日が対象
  - 36Mホライズンなら2022年のリバランス日が対象

## 次のステップ

1. **Walk-Forward検証（B案）**: 上記コマンドで実行
2. **固定ホライズンseed耐性テスト（B案の定義で）**: `test_seed_robustness_fixed_horizon_extended.py`で再実行
3. **運用可能性の最終チェック**: 下位分位、最大ドローダウン、銘柄数・流動性制約、取引コスト感度

## 将来（2026年データが溜まったら）

2026年末まで価格が溜まったら、**A案（2025リバランス→12M評価）**が可能になります。

さらに2027/2028と進むと、24M/36Mも「ホールドアウト年=2025」で成立します。















