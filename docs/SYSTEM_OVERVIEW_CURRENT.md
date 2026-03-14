# 現状システム構成概要

**作成日**: 2025-03-14  
**目的**: システムの複雑化を把握し、最小化・整理のための現状資料として利用する。

---

## 1. システムの目的と概要

### 1.1 目的

- **日本株**を対象に、**ファンダメンタル指標中心の銘柄スクリーニング（ランキング）** を行う
- その結果を用いて **2つの運用スタイル** を併存運用する基盤
  - **(A) 長期保有型（NISA想定）**: 積立・買い増し、低頻度入替
  - **(B) 月次リバランス型**: 月次で上位銘柄に入れ替え、超過リターン（vs TOPIX）を狙う
- ベンチマークは **TOPIX**（J-Quants API 経由）

### 1.2 技術スタック

| 項目 | 内容 |
|------|------|
| データソース | J-Quants API |
| DB | SQLite（`%LocalAppData%\omanta_3rd\db\jquants.sqlite`） |
| 言語 | Python 3.9+ |
| 最適化 | Optuna |
| 主依存 | pandas, numpy, optuna, requests, python-dotenv |

---

## 2. 2つの運用スタイルの整理

| 項目 | 長期保有型 | 月次リバランス型 |
|------|-----------|------------------|
| **目的** | NISA想定の長期積立・買い増し | 時系列の超過リターン（vs TOPIX） |
| **入替頻度** | 低（月次〜四半期の点検） | 高（月次で全入れ替え） |
| **意思決定** | スクリーニング結果を参考に手動 | 最適化パラメータで自動選定 |
| **主な実行** | `longterm_run`（月次実行）、`backtest` | `optimize_timeseries`、Holdout/WFA |
| **ポートフォリオ保存** | `portfolio_monthly`（参考/一時） | `monthly_rebalance_portfolio` 等 |
| **テーブル接頭辞** | なし | `monthly_rebalance_` |

**注意**: 長期保有型用の最適化として **`optimize_longterm.py`** が別途存在し、固定ホライズン（12M/24M/36M）で train/test 分割してパラメータ探索を行う。月次リバランス型の `optimize_timeseries.py` とは目的・評価指標が異なる。

---

## 3. ディレクトリ・モジュール構成

### 3.1 リポジトリルート直下の主な役割

```
omanta_3rd/
├── src/omanta_3rd/     # メインパッケージ（コアロジック）
├── sql/                # スキーマ・マイグレーション
├── scripts/            # 実行用・分析用スクリプト群
├── docs/               # 設計・検証・議事メモ
├── memo/               # メモ
├── *.py                # ルート直下に多数のスタンドアロンスクリプト（検証・可視化・DB保存等）
├── *.ps1 / *.bat       # 実行用シェル（最適化・WFA・評価）
└── README.md, SYSTEM_SPECIFICATION.md 等
```

### 3.2 パッケージ `src/omanta_3rd/` の構成

| ディレクトリ | 役割 | 主なファイル例 |
|-------------|------|----------------|
| **backtest/** | バックテスト・指標計算 | `timeseries.py`（時系列P/L）, `metrics.py`, `performance.py`, `eval_common.py`, `feature_cache.py` |
| **config/** | 設定・パラメータ | `settings.py`, `strategy.py`, `params_registry.py`, `regime_policy.py` |
| **features/** | 特徴量 | `fundamentals.py`, `valuation.py`, `technicals.py`, `universe.py` |
| **infra/** | DB・API | `db.py`, `jquants.py` |
| **ingest/** | データ取り込み | `listed.py`, `prices.py`, `fins.py`, `indices.py`, `earnings_calendar.py` |
| **jobs/** | ジョブ・最適化（**多数**） | 下記「4. ジョブ・最適化一覧」参照 |
| **market/** | レジーム等 | `regime.py` |
| **portfolio/** | 保有管理（長期保有） | `holdings.py` |
| **strategy/** | スコア・選定 | `scoring.py`, `select.py` |
| **reporting/** | 出力 | `export.py` |

### 3.3 ルート直下のスクリプト（例・一部）

- **データ・検証**: `update_all_data.py`, `verify_*.py`, `sanity_check_timeseries.py`
- **評価・分析**: `evaluate_candidates_holdout.py`, `evaluate_cost_sensitivity.py`, `cross_validate_params.py`, `analyze_*.py`
- **可視化**: `visualize_holdings_details.py`, `visualize_equity_curve_and_holdings.py`, `visualize_optimization.py`
- **DB保存・運用**: `save_final_candidates_to_db.py`, `save_performance_time_series_to_db.py`, `save_params_to_db.py`, `select_candidates_for_2025.py`
- **Walk-Forward等**: `run_walk_forward_analysis.py`, `run_walk_forward_analysis_roll.py`, `walk_forward_longterm.py`

---

## 4. ジョブ・最適化一覧（複雑性の中心）

### 4.1 最適化系（Optuna 利用）

| ファイル | 運用スタイル | 計算方式 | 備考 |
|---------|-------------|----------|------|
| **optimize.py** | 月次リバランス（旧） | 累積リターン（ti→最終日） | 非推奨・互換用。ポートフォリオ選定ロジックは他から参照される |
| **optimize_timeseries.py** | 月次リバランス | 月次リターン（ti→ti+1）、open-close | **推奨**。Sharpe_excess 等を目的関数 |
| **optimize_longterm.py** | 長期保有型 | 固定ホライズン（12M/24M/36M）、train/test 分割 | 約2200行。長期用評価指標（年率リターン・MaxDD等） |
| **robust_optimize_timeseries.py** | 月次リバランス | WFA 複数 fold で安定性重視 | 過学習抑制用 |
| **optimize_timeseries_clustered.py** | 月次リバランス | クラスタリング付き時系列 | 派生版 |
| **optimize_monthly_rebalance.py** | 月次リバランス | 月次リバランス専用の最適化 | 別入口 |

### 4.2 評価・検証系

| ファイル | 役割 |
|---------|------|
| **walk_forward_timeseries.py** | WFA（fold ごとに train 最適化 → test 評価） |
| **holdout_eval_timeseries.py** | Train/Holdout 分割で OOS 評価 |
| **compare_lambda_penalties.py** | λ（ペナルティ）比較。optimize_longterm の test_dates を利用 |
| **compare_regime_switching.py** | レジーム切替ポリシー比較 |
| **compare_range_policies.py** | レンジポリシー比較 |
| **reoptimize_all_candidates.py** | 候補の一括再最適化 |

### 4.3 実行・バッチ系

| ファイル | 役割 |
|---------|------|
| **longterm_run.py** | 長期保有型の月次実行（特徴量計算＋ポートフォリオ選定）。約2000行超 |
| **batch_longterm_run.py** | 長期保有型の期間一括実行（リバランス日リスト生成含む） |
| **batch_longterm_run_with_regime.py** | レジーム考慮版バッチ |
| **backtest.py** | バックテスト実行（長期保有型向け等） |
| **etl_update.py** | ETL（listed / prices / fins / indices 等） |
| **init_db.py** | DB 初期化 |
| **calculate_all_performance.py** | パフォーマンス一括計算 |
| **add_holding.py** / **sell_holding.py** / **update_holdings.py** | 保有の追加・売却・更新 |

### 4.4 ユーティリティ・分析

| ファイル | 役割 |
|---------|------|
| **params_utils.py** | パラメータの構築・正規化（他ジョブから共通利用） |
| **verify_strategy_mode.py** | 戦略モード（momentum/reversal）検証 |
| **check_regime_consistency.py** | レジーム一貫性チェック |
| **analyze_optimization_detail.py** | 最適化結果の分析 |
| **recover_optimization_result.py** | 最適化結果の復旧 |

**複雑性の要因**: 最適化が「長期用」と「月次リバランス用」で分かれ、さらに「旧形式」「時系列」「Robust」「Clustered」「月次リバランス専用」等が並存している。また `optimize_longterm` が `optimize_timeseries` の `_select_portfolio_for_rebalance_date` を参照するなど、モジュール間の依存が入り組んでいる。

---

## 5. データベース構成（概要）

### 5.1 共通テーブル

| テーブル | 説明 |
|---------|------|
| listed_info | 銘柄属性（日付・コード・市場・セクター等） |
| prices_daily | 日足（open/close/adj_close/volume 等） |
| fins_statements | 財務（開示日・実績・予想） |
| features_monthly | 月次特徴量（core_score, entry_score 等） |
| index_daily | 指数（TOPIX） |
| stock_splits | 株式分割情報 |

### 5.2 長期保有型関連

| テーブル | 説明 |
|---------|------|
| portfolio_monthly | 月次ポートフォリオ（参考/最適化時の一時保存） |
| holdings | 実際の保有銘柄 |
| backtest_performance | バックテスト結果 |
| backtest_stock_performance | 銘柄別パフォーマンス |

### 5.3 月次リバランス型関連（接頭辞 `monthly_rebalance_`）

| テーブル | 説明 |
|---------|------|
| monthly_rebalance_portfolio | 確定ポートフォリオ |
| monthly_rebalance_final_selected_candidates | 最終選定候補とパラメータ |
| monthly_rebalance_candidate_performance | 候補のパフォーマンス指標 |
| monthly_rebalance_candidate_monthly_returns | 月次超過リターン時系列 |
| monthly_rebalance_candidate_detailed_metrics | 詳細メトリクス |

その他、strategy_params 用テーブルやマイグレーションで追加されたカラム・テーブルあり（`sql/` 参照）。

---

## 6. 主な実行エントリポイント

### 6.1 パッケージ経由（例）

```bash
# DB・データ
python -m omanta_3rd.jobs.init_db
python -m omanta_3rd.jobs.etl_update --target listed --date 2025-12-13

# 長期保有型
python -m omanta_3rd.jobs.longterm_run --asof 2025-12-19
python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19 --save-to-db

# 月次リバランス型・最適化（推奨）
python -m omanta_3rd.jobs.optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 20 --study-name xxx --n-jobs 4

# 長期保有型・最適化
python -m omanta_3rd.jobs.optimize_longterm --start 2020-01-01 --end 2022-12-31 --study-type B --n-trials 50 --train-ratio 0.8

# WFA・Holdout
python -m omanta_3rd.jobs.walk_forward_timeseries --start 2021-01-01 --end 2025-12-31 --folds 3 --n-trials 50
python -m omanta_3rd.jobs.holdout_eval_timeseries --train-start 2021-01-01 --train-end 2023-12-31 --holdout-start 2024-01-01 --holdout-end 2025-12-31
```

### 6.2 ルート直下スクリプト・シェル

- **データ更新**: `update_all_data.py --target indices` 等
- **Holdout 評価**: `evaluate_candidates_holdout.py`（候補 JSON を指定）
- **Walk-Forward**: `run_walk_forward_analysis.ps1`, `run_walk_forward_analysis_roll.ps1`, `run_walk_forward_analysis_roll_n100_24M_36M.ps1` 等
- **最適化**: `run_optimization_with_cache_rebuild.ps1`
- **その他**: `run_fixed_horizon_tests.ps1`, `run_seed_robustness_test.ps1`, `run_2025_live_evaluation.ps1` 等

---

## 7. データフロー（簡略）

```
J-Quants API
    → etl_update / update_all_data
    → listed_info, prices_daily, fins_statements, index_daily

DB（上記＋features_monthly）
    → longterm_run.build_features / select_portfolio
    → features_monthly, portfolio_monthly（長期用）

同じく DB
    → optimize_timeseries / optimize_longterm 等
    → 各最適化は「パラメータ → ポートフォリオ選定 → バックテスト → 指標」のループ

バックテスト
    → backtest/timeseries.py, performance.py, metrics.py
    → 時系列リターン or 累積リターン → Sharpe/MaxDD/CAGR 等
```

---

## 8. 複雑化・整理の観点で見た現状の課題

1. **最適化経路が多すぎる**  
   旧形式・時系列・長期用・Robust・Clustered・月次リバランス専用が並存し、どれを本流にするかが分かりにくい。

2. **コードの重複と依存**  
   - ポートフォリオ選定: `optimize.py` の `_select_portfolio_with_params` と、`optimize_timeseries` の `_select_portfolio_for_rebalance_date` が存在。長期用は時系列側の関数を利用。
   - スコア・エントリー計算が `longterm_run` と `optimize` / `optimize_timeseries` に分散。

3. **巨大ファイル**  
   - `optimize_longterm.py`: 約 2200 行  
   - `longterm_run.py`: 約 2000 行超  
   単一ファイルに責務が集中している。

4. **ルート直下のスクリプト過多**  
   検証・可視化・DB 保存・分析用がルートに多数あり、どこから実行するかが分かりにくい。

5. **ドキュメント・履歴の分散**  
   `docs/` に多数の md があり、修正履歴・設計判断がファイル名・日付ベースで散在している。

6. **2つの運用スタイルの共有と分離**  
   特徴量・DB は共有しているが、最適化・評価・テーブルが分かれており、「長期だけ」「月次リバランスだけ」に絞る場合の最小セットが明文化されていない。

---

## 9. 関連ドキュメント（既存）

- **README.md** - プロジェクト概要・クイックスタート
- **SYSTEM_SPECIFICATION.md** - システム仕様（構成・データフロー・コマンド・DB）
- **OPTIMIZATION_SYSTEM_OVERVIEW.md** - 最適化システム全体像（旧形式・時系列・Robust・WFA・Holdout）
- **PERFORMANCE_CALCULATION_METHODS.md** - パフォーマンス計算方法の比較
- **TIMESERIES_REFINEMENT_PLAN.md** - 時系列バックテストの設計・改善履歴

---

**以上が現状のシステム構成の概要である。最小化・整理の際は、運用スタイルをどちらに絞るか（または両方維持するか）、最適化をどの 1 本に集約するかを決めた上で、ジョブとルートスクリプトの削減・統合を進めるとよい。**
