# V1 スリム化実装サマリ

**実施日**: 2025-03-14  
ChatGPT 案に沿った「1つのランキングエンジン＋2ポリシー・最適化は月次だけ」の実装を追加した。

---

## 追加・変更したファイル

### 設定

| ファイル | 内容 |
|----------|------|
| `src/omanta_3rd/config/score_profile.py` | `ScoreProfile`（凍結）, `PolicyParams`（探索）, `get_v1_ref_score_profile()`, `get_default_policy_params()` |

### 単一の真実（純粋関数）

| ファイル | 内容 |
|----------|------|
| `src/omanta_3rd/strategy/snapshot.py` | `build_snapshot(conn, asof)` — 指定日の features_monthly を読むだけ |
| `src/omanta_3rd/strategy/scoring_engine.py` | `score_candidates(snapshot, score_profile, policy_params)` — total_score 付与 |
| `src/omanta_3rd/strategy/policy.py` | `select_portfolio(scored_df, policy_params, rebalance_date, prev_portfolio)` — 選定 |
| `src/omanta_3rd/backtest/evaluator.py` | `evaluate_portfolio(portfolios, start_date, end_date, cost_bps, lambda_turnover)` — 指標・目的関数 |

### DB

| ファイル | 内容 |
|----------|------|
| `sql/migration_add_ref_scores_to_features.sql` | features_monthly に score_profile, core_score_ref, entry_score_ref 追加 |
| `sql/migration_add_strategy_runs_tables.sql` | strategy_runs, portfolio_snapshots, performance_series, performance_summary, live_holdings 作成 |

### リポジトリ層

| ファイル | 内容 |
|----------|------|
| `src/omanta_3rd/infra/repositories/features_repo.py` | `upsert_features(conn, feat)` |
| `src/omanta_3rd/infra/repositories/run_repo.py` | `save_run(...)`, `save_portfolio_snapshots(...)` |

### ジョブ

| ファイル | 内容 |
|----------|------|
| `src/omanta_3rd/jobs/prepare_features.py` | 特徴量＋ref score を v1_ref で計算して features_monthly に保存。`--asof` または `--start / --end` |
| `src/omanta_3rd/jobs/run_strategy.py` | 選定のみ。`--mode longterm|monthly`, `--asof` または `--start / --end`。新テーブルに保存可 |
| `src/omanta_3rd/jobs/optimize_strategy.py` | 月次のみ Optuna。PolicyParams 6 パラメータ探索。snapshot キャッシュで trial 内は pure 関数のみ |

### Legacy 明示

| ファイル | 内容 |
|----------|------|
| `legacy/README.md` | optimize_longterm / compare_lambda_penalties は legacy。mainline は optimize_strategy + run_strategy。ファイルは移動していない。 |

---

## 実行手順（最小）

1. **マイグレーション**（初回のみ）  
   - `sql/migration_add_ref_scores_to_features.sql` を実行  
   - `sql/migration_add_strategy_runs_tables.sql` を実行  

2. **特徴量・ref score の準備**  
   ```bash
   python -m omanta_3rd.jobs.prepare_features --asof 2024-12-31
   # または期間一括
   python -m omanta_3rd.jobs.prepare_features --start 2021-01-01 --end 2024-12-31
   ```

3. **選定の実行**  
   ```bash
   python -m omanta_3rd.jobs.run_strategy --mode monthly --asof 2024-12-31
   python -m omanta_3rd.jobs.run_strategy --mode monthly --start 2021-01-01 --end 2024-12-31
   ```

4. **月次最適化**  
   ```bash
   python -m omanta_3rd.jobs.optimize_strategy --start 2021-01-01 --end 2024-12-31 --n-trials 20 --study-name v1_study
   ```

---

## 注意

- **features_monthly の ref 列**: マイグレーションで追加した列が無いと prepare_features の保存でエラーになる。先にマイグレーションを実行すること。
- **strategy_runs / portfolio_snapshots**: 新テーブルが無いと run_strategy の `--no-save-new` なしでエラーになる。マイグレーションで作成すること。
- **既存の longterm_run / optimize_timeseries**: そのまま利用可能。V1 の mainline は prepare_features → run_strategy → optimize_strategy の流れ。
- **optimize_longterm / compare_lambda_penalties**: ファイルは移動していない。既存スクリプトの import はそのまま。新機能では使わない（legacy として扱う）。
