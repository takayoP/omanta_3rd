# 候補パラメータ再最適化の概要（Step 1）

## 背景

以前の最適化では、以下の問題が指摘されました：

1. **未来参照リークの疑い**
   - 評価の終点が「ホライズン」ではなくDBの最新日になっていた
   - 2021年のリバランスを評価する際に、2026年までの情報で評価してしまう可能性

2. **学習/テスト分割が時系列ではない**
   - ランダムシャッフルによる分割で、trainが未来、testが過去になり得る
   - 時系列モデルとしては情報が混ざり、一般化性能の見積りが甘くなる

3. **評価窓の不一致**
   - 24Mと12Mで異なる期間数が評価される（24M=48期間、12M=60期間）
   - 比較可能性が損なわれる

## 修正内容

### Step 1: 固定ホライズン評価に統一

**修正前：**
- `calculate_longterm_performance()`内で`latest_date = MAX(date) FROM prices_daily`を取得
- 各リバランス日を`latest_date`まで評価
- 2021年のリバランスを2026年まで評価してしまう可能性

**修正後：**
- `as_of_date`パラメータを追加（評価の打ち切り日を明示的に指定、必須）
- `horizon_months`を必須パラメータに変更
- 各リバランス日の評価終了日を`eval_end_date = rebalance_date + horizon_months`で計算
- `require_full_horizon=True`の場合、`eval_end_date <= as_of_date`を満たさないものは除外
- **DBのMAX(date)は使用しない**（未来参照リーク対策）
- **`as_of_date`が未指定の場合は`end_date`を使用**（DB MAX(date)は使わない）

**ログ出力：**
各リバランス日について以下を出力：
- `rebalance_date`: リバランス日
- `eval_end_date`: 評価終了日（`rebalance_date + horizon_months`）
- `holding_years`: 保有期間（年）

### Step 2: 時系列分割をデフォルトに

**修正前：**
- `split_rebalance_dates()`がランダムシャッフルで80/20分割
- trainが未来、testが過去になり得る

**修正後：**
- `time_series_split=True`をデフォルトに設定
- 時系列順にソートして、前80%をtrain、後20%をtestに分割
- ランダム分割は研究用途のみ（`time_series_split=False`で有効化可能）

**推奨分割：**
- train: 2020-01-01 ～ 2022-12-31
- val: 2023-01-01 ～ 2023-12-31
- holdout: 2024-01-01 ～ 2025-12-31

### Step 3: 24Mと12Mで異なるend_dateを使用

**問題：**
- 24Mと12Mを同じ期間（2020-2025）で最適化すると、24Mは後半が未達で除外される
- 有効サンプル数がズレる（24M=48期間、12M=60期間）

**解決策：**
- 24Mの最適化は、24Mホライズンが完走できるように`rebalance_end_date`を自動調整
  - `rebalance_end_date_24m = end_date - 24ヶ月`（リバランス日の取得範囲）
  - `as_of_date = end_date`（評価の打ち切り日、元のend_dateを使用）
  - 例：`end_date=2025-12-31` → `rebalance_end_date_24m=2023-12-31`, `as_of_date=2025-12-31`
  - **重要**: `rebalance_end_date_24m`と`as_of_date`を分離して渡す（混同防止）
- 12Mはそのまま`end_date`を使用（`rebalance_end_date=end_date`, `as_of_date=end_date`）

## 実行方法

### 基本コマンド

```bash
python -m omanta_3rd.jobs.reoptimize_all_candidates \
  --start 2020-01-01 \
  --end 2025-12-31 \
  --n-trials 200
```

### オプション

- `--as-of-date YYYY-MM-DD`: 評価の打ち切り日（指定しない場合は`end_date`を使用）
- `--train-end-date YYYY-MM-DD`: 学習期間の終了日（指定しない場合は2022-12-31）
- `--skip-24m`: 24Mの最適化をスキップ
- `--skip-12m`: 12Mの最適化をスキップ
- `--version VERSION`: バージョン（指定しない場合は自動生成：YYYYMMDD形式）

### 実行内容

1. **operational_24M**（24Mホライズン）を最適化
   - Studyタイプ: C（広範囲探索）
   - `end_date`を自動調整（24Mホライズン完走のため）

2. **12M_momentum**（12Mホライズン、momentumモード）を最適化
   - Studyタイプ: A（BB寄り・低ROE閾値）

3. **12M_reversal**（12Mホライズン、reversalモード）を最適化
   - Studyタイプ: B（Value寄り・ROE閾値やや高め）

4. 各パラメータを`params_*.json`形式で保存
5. レジストリ（`config/params_registry_longterm.json`）を更新

## 出力ファイル

- `optimization_result_{params_id}_{version}.json`: 最適化結果（詳細）
- `params_{params_id}_{version}.json`: パラメータファイル（運用用）
- `config/params_registry_longterm.json`: レジストリ（更新）

## 確認ポイント

### 未来参照リークの確認

実行ログで以下を確認：

```
[calculate_longterm_performance] 2020-01-31 → eval_end=2022-01-31 (holding=2.00年, horizon=24M)
[calculate_longterm_performance] 2020-02-28 → eval_end=2022-02-28 (holding=2.00年, horizon=24M)
...
```

**確認事項：**
- `eval_end_date`が常に`rebalance_date + horizon_months`になっているか
- `eval_end_date <= as_of_date`を満たしているか
- DBの最新日（2026-01-08など）が使われていないか
- `as_of_date`が`end_date`（CLIの`--end`）になっているか（DB MAX(date)ではない）
- 24M最適化で`rebalance_end_date_24m`と`as_of_date`が分離されているか

### 時系列分割の確認

実行ログで以下を確認：

```
学習データ: XX日 (80.0%)
  最初: 2020-01-31
  最後: 2022-XX-XX
テストデータ: XX日 (20.0%)
  最初: 2023-01-31
  最後: 2023-XX-XX
```

**確認事項：**
- trainの最後の日付 < testの最初の日付 になっているか
- 時系列順に分割されているか

### 評価窓の確認

**24M最適化：**
- `rebalance_end_date_24m = end_date - 24ヶ月`（リバランス日の取得範囲）
- `as_of_date = end_date`（評価の打ち切り日、元のend_dateを使用）
- 例：`end_date=2025-12-31` → `rebalance_end_date_24m=2023-12-31`, `as_of_date=2025-12-31`
- すべてのリバランス日が24Mホライズン完走可能か
- `rebalance_end_date_24m`と`as_of_date`が分離されているか

**12M最適化：**
- `end_date`をそのまま使用
- すべてのリバランス日が12Mホライズン完走可能か

## 期待される改善

1. **未来参照リークの排除**
   - 各リバランス日が固定ホライズンで評価される
   - DBの最新日が使われない

2. **時系列リークの排除**
   - train/testが時系列順に分割される
   - より現実的な一般化性能の見積り

3. **比較可能性の向上**
   - 24Mと12Mで有効サンプル数を揃える
   - 公平な比較が可能

## 次のステップ

再最適化完了後：

1. **Step 2: A-1比較を共通のrebalance_date集合で再集計**
   - 24Mを含める比較 → 全戦略が評価できる月（積集合）だけで集計
   - 12Mだけの比較 → 12M同士で比較

2. **Step 3: レジームポリシーのrangeを見直す**
   - range → 12M_momentum
   - range → 前回のparams_idを維持（ヒステリシス）
   - range → 24Mのまま（現状）

## 注意事項

- 最適化には時間がかかります（各候補で200試行 × 3 = 600試行）
- すべて`require_full_horizon=True`で実行されます
- 時系列分割がデフォルトで使用されます
- 24Mの最適化は自動的に`end_date`が調整されます
