# ファイル名変更サマリー

## 変更内容

月次リバランス型と紛らわしい命名を修正しました。

### リネームされたファイル

1. **`monthly_run.py`** → **`longterm_run.py`**
   - 長期保有型の単一実行スクリプト
   - 特徴量構築とポートフォリオ選択を行う

2. **`batch_monthly_run.py`** → **`batch_longterm_run.py`**
   - 長期保有型のバッチ実行スクリプト
   - 複数のリバランス日でポートフォリオを作成

3. **`batch_monthly_run_with_regime.py`** → **`batch_longterm_run_with_regime.py`**
   - 長期保有型のレジーム切替対応バッチ実行スクリプト
   - 各リバランス日でレジームを判定し、パラメータを自動選択

## 更新されたインポート

以下のファイルでインポート文を更新しました：

### `src/omanta_3rd/jobs/`内
- `optimize.py`
- `optimize_longterm.py`
- `optimize_timeseries.py`
- `optimize_timeseries_clustered.py`
- `robust_optimize_timeseries.py`
- `holdout_eval_timeseries.py`
- `walk_forward_timeseries.py`
- `params_utils.py`
- `batch_longterm_run.py`
- `batch_longterm_run_with_regime.py`

### `src/omanta_3rd/backtest/`内
- `feature_cache.py`

### ルートディレクトリのスクリプト
- `walk_forward_longterm.py`
- `cross_validate_params.py`
- `cross_validate_params_24M.py`
- `analyze_worst_seed.py`
- `analyze_entry_score_components.py`
- `check_feature_direction.py`
- `test_split_seed_robustness.py`
- `test_seed_robustness_fixed_horizon.py`
- `test_seed_robustness_fixed_horizon_extended.py`
- `evaluate_candidates_holdout.py`
- `evaluate_monthly_params_on_longterm.py`
- `check_optimization_readiness.py`
- `create_and_calculate_performance.py`
- `create_portfolio_from_optimization.py`
- `recalculate_portfolio_performance.py`
- `run_optimized_backtest.py`
- `fetch_all_listed_info.py`
- `investigate_rebalance_issue.py`
- `test_next_trading_day.py`
- `check_rebalance_dates.py`
- `analyze_missing_values.py`

## 使用方法の変更

### 変更前
```bash
python -m omanta_3rd.jobs.monthly_run --asof 2025-12-12
python -m omanta_3rd.jobs.batch_monthly_run --start 2020-01-01 --end 2025-12-31
python -m omanta_3rd.jobs.batch_monthly_run_with_regime --start 2020-01-01 --end 2025-12-31
```

### 変更後
```bash
python -m omanta_3rd.jobs.longterm_run --asof 2025-12-12
python -m omanta_3rd.jobs.batch_longterm_run --start 2020-01-01 --end 2025-12-31
python -m omanta_3rd.jobs.batch_longterm_run_with_regime --start 2020-01-01 --end 2025-12-31
```

## 注意事項

- `get_monthly_rebalance_dates`関数は`batch_longterm_run.py`に残っていますが、この関数は月次リバランス型でも使用されるため、関数名は変更していません（機能は「月次の最終営業日を取得する」という意味で適切です）
- すべてのインポート文を更新済みです
- 既存のコードとの互換性はありません（インポートエラーが発生します）が、すべて更新済みです













