# システム仕様書

## 1. 概要

本システムは、日本株を対象にした投資アルゴリズムの基盤システムです。  
ファンダメンタル指標を中心とした銘柄スクリーニングを行い、**2つの運用スタイル**（長期保有型と月次リバランス型）を併存して運用できます。

### 1.1 投資方針（共通）

- **Quality（収益力・持続性）**: ROE、利益成長の一貫性、過去最高益
- **Value（バリュー指標）**: PER、PBR
- **ベンチマーク**: TOPIX（J-Quants API経由）

### 1.2 2つの運用スタイル

| 項目 | 長期保有型 | 月次リバランス型 |
|------|-----------|-----------------|
| 目的 | NISA想定の長期積立・買い増し | 時系列の超過リターン（vs TOPIX） |
| 入替頻度 | 頻繁に行わず、定期点検（月次〜四半期） | 月次で全入れ替え |
| 主なテーブル | `holdings` | `portfolio_monthly`、`monthly_rebalance_*` |
| 実行スクリプト | `monthly_run.py`（スクリーニング結果を参考） | `optimize_timeseries.py`、`evaluate_candidates_holdout.py` |

---

## 2. システム構成

### 2.1 ディレクトリ構成

```
omanta_3rd/
├── src/omanta_3rd/          # メインパッケージ
│   ├── backtest/            # バックテスト関連
│   │   ├── timeseries.py    # 時系列リターン計算
│   │   ├── metrics.py       # パフォーマンス指標計算
│   │   ├── eval_common.py   # 評価共通処理
│   │   └── feature_cache.py # 特徴量キャッシュ
│   ├── config/              # 設定ファイル
│   │   ├── settings.py      # データベースパス等
│   │   └── strategy.py      # 戦略パラメータ
│   ├── features/            # 特徴量計算
│   │   ├── fundamentals.py  # ファンダメンタル指標
│   │   ├── valuation.py     # バリュエーション指標
│   │   ├── technicals.py    # テクニカル指標
│   │   └── universe.py      # ユニバース定義
│   ├── infra/               # インフラ層
│   │   ├── db.py            # データベース接続
│   │   └── jquants.py       # J-Quants API
│   ├── ingest/              # データ取り込み
│   │   ├── listed.py        # 銘柄情報
│   │   ├── prices.py        # 価格データ
│   │   ├── fins.py          # 財務データ
│   │   └── indices.py       # 指数データ（TOPIX）
│   ├── jobs/                # ジョブスクリプト
│   │   ├── monthly_run.py   # 月次実行（特徴量計算+ポートフォリオ選定）
│   │   ├── optimize_timeseries.py  # 時系列最適化（月次リバランス用）
│   │   ├── evaluate_candidates_holdout.py  # Holdout検証（月次リバランス用）
│   │   ├── backtest.py      # バックテスト実行
│   │   └── etl_update.py    # ETL更新
│   ├── portfolio/           # ポートフォリオ管理（長期保有用）
│   │   └── holdings.py      # 保有銘柄管理
│   ├── strategy/            # 戦略ロジック
│   │   ├── scoring.py       # スコアリング
│   │   └── select.py        # 銘柄選定
│   └── reporting/           # レポート出力
│       └── export.py        # エクスポート機能
├── sql/                     # データベーススキーマ
│   └── schema.sql           # テーブル定義
├── evaluate_candidates_holdout.py  # Holdout検証スクリプト
├── evaluate_cost_sensitivity.py    # コスト感度分析
├── visualize_holdings_details.py   # 保有銘柄詳細可視化
└── README.md                # このファイル

```

### 2.2 データベース構成

データベースパス: `C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite`

#### 2.2.1 共通テーブル（両方の運用スタイルで使用）

| テーブル名 | 説明 | 主な用途 |
|-----------|------|---------|
| `listed_info` | 銘柄属性（会社名、セクター等） | 共通 |
| `prices_daily` | 日足価格データ | 共通 |
| `fins_statements` | 財務データ（開示ベース） | 共通 |
| `features_monthly` | 月次特徴量（スナップショット） | 共通 |
| `index_daily` | 指数データ（TOPIX） | 共通 |
| `stock_splits` | 株式分割情報 | 共通 |

#### 2.2.2 長期保有型専用テーブル

| テーブル名 | 説明 | 主な用途 |
|-----------|------|---------|
| `holdings` | 実際の保有銘柄 | 長期保有型の実際の保有状況を管理 |
| `backtest_performance` | バックテストパフォーマンス結果 | 長期保有型のパフォーマンス評価 |
| `backtest_stock_performance` | バックテスト銘柄別パフォーマンス | 長期保有型の個別銘柄評価 |

#### 2.2.3 月次リバランス型専用テーブル（`monthly_rebalance_`接頭辞）

| テーブル名 | 説明 | 主な用途 |
|-----------|------|---------|
| `portfolio_monthly` | 月次ポートフォリオ（確定結果） | 月次リバランス型のポートフォリオ選定結果 |
| `monthly_rebalance_final_selected_candidates` | 最終選定候補（基本情報とパラメータ） | 月次リバランス型の最適化結果 |
| `monthly_rebalance_candidate_performance` | 最終選定候補のパフォーマンス指標 | 月次リバランス型のパフォーマンス集計 |
| `monthly_rebalance_candidate_monthly_returns` | 月次超過リターン時系列 | 月次リバランス型の時系列データ |
| `monthly_rebalance_candidate_detailed_metrics` | 詳細パフォーマンス指標 | 月次リバランス型の詳細メトリクス |

**命名規則**: 月次リバランス型のテーブルには `monthly_rebalance_` という接頭辞を付けます。  
これにより、長期保有型と月次リバランス型のデータを明確に区別できます。

---

## 3. データフロー

### 3.1 データ取り込みフロー

```
J-Quants API
    ↓
[ETL更新スクリプト]
    ├── listed_info (銘柄情報)
    ├── prices_daily (価格データ)
    ├── fins_statements (財務データ)
    └── index_daily (TOPIXデータ)
```

### 3.2 特徴量計算フロー

```
[データベース]
    ↓
[features_monthly 計算]
    ├── ROE、ROEトレンド
    ├── PER、PBR、フォワードPER
    ├── 利益成長率
    ├── 過去最高益フラグ
    ├── core_score（ファンダメンタルスコア）
    └── entry_score（エントリースコア：BB/RSI）
```

### 3.3 長期保有型の運用フロー

```
[月次実行: monthly_run.py]
    ↓
[特徴量計算 + スクリーニング]
    ↓
[候補銘柄リスト（参考情報）]
    ↓
[手動判断 or 定期点検]
    ↓
[holdings テーブルに追加/更新]
    ↓
[backtest.py でパフォーマンス評価]
    ↓
[backtest_performance, backtest_stock_performance に保存]
```

### 3.4 月次リバランス型の運用フロー

```
[最適化: optimize_timeseries.py]
    ↓
[Optuna によるハイパーパラメータ最適化]
    ↓
[最適化結果（候補パラメータ）]
    ↓
[Holdout検証: evaluate_candidates_holdout.py]
    ↓
[最終選定候補の決定]
    ↓
[portfolio_monthly にポートフォリオ保存]
    ↓
[パフォーマンス評価]
    ↓
[monthly_rebalance_* テーブルに保存]
```

---

## 4. 主要スクリプトと実行コマンド

### 4.1 データベース初期化

```bash
python -m omanta_3rd.jobs.init_db
```

### 4.2 データ更新（ETL）

```bash
# 銘柄情報更新
python -m omanta_3rd.jobs.etl_update --target listed --date 2025-12-13

# 価格データ更新（日付範囲指定）
python -m omanta_3rd.jobs.etl_update --target prices --start 2025-09-01 --end 2025-12-13

# 財務データ更新
python -m omanta_3rd.jobs.etl_update --target fins --start 2025-09-01 --end 2025-12-13

# TOPIXデータ更新
python update_all_data.py --target indices
```

### 4.3 長期保有型の運用

#### 4.3.1 月次実行（特徴量計算 + スクリーニング）

```bash
# 最新日で実行
python -m omanta_3rd.jobs.monthly_run

# 特定日付で実行
python -m omanta_3rd.jobs.monthly_run --asof 2025-12-19
```

このスクリプトは以下を実行します：
- 指定日の特徴量を計算し、`features_monthly` に保存
- スクリーニング結果を `portfolio_monthly` に保存（参考情報として）

#### 4.3.2 バックテスト実行

```bash
# 特定のリバランス日のポートフォリオの損益を確認
python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19

# 評価日を指定する場合
python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19 --as-of-date 2025-12-20

# すべてのポートフォリオの損益を確認
python -m omanta_3rd.jobs.backtest

# 結果をDBに保存
python -m omanta_3rd.jobs.backtest --save-to-db
```

### 4.4 月次リバランス型の運用

#### 4.4.1 最適化実行

```bash
# Windows PowerShell
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:OPENBLAS_NUM_THREADS="1"
$env:NUMEXPR_NUM_THREADS="1"
python -m omanta_3rd.jobs.optimize_timeseries `
  --start 2021-01-01 `
  --end 2024-12-31 `
  --n-trials 200 `
  --study-name optimization_timeseries_studyB `
  --parallel-mode trial `
  --n-jobs 4 `
  --bt-workers 1 `
  --no-progress-window
```

主要パラメータ：
- `--parallel-mode`: 並列化モード（`trial`/`backtest`/`hybrid`）
- `--n-jobs`: trial並列数（-1で自動、SQLite環境では2〜4を推奨）
- `--bt-workers`: trial内バックテストの並列数

#### 4.4.2 Holdout検証

```bash
python evaluate_candidates_holdout.py `
  --candidates candidates_studyB_20251231_174014.json `
  --holdout-start 2023-01-01 `
  --holdout-end 2024-12-31 `
  --cost-bps 0.0 `
  --output holdout_results_with_holdings.json `
  --use-cache
```

このスクリプトは以下を実行します：
- 候補パラメータでHoldout期間を評価
- ポートフォリオ情報と保有銘柄詳細をJSONに保存
- 詳細メトリクス（年別Sharpe、CAGR、MaxDD、ターンオーバー等）を計算

#### 4.4.3 コスト感度分析

```bash
python evaluate_cost_sensitivity.py `
  --candidates candidates_studyB_20251231_174014.json `
  --holdout-start 2023-01-01 `
  --holdout-end 2024-12-31 `
  --cost-levels 0 10 20 30 `
  --output cost_sensitivity_analysis.json
```

#### 4.4.4 可視化

```bash
# 保有銘柄の詳細情報を可視化
python visualize_holdings_details.py

# 資産曲線と保有銘柄の推移を可視化
python visualize_equity_curve_and_holdings.py
```

### 4.5 データベースへの結果保存（月次リバランス型）

```bash
# 最終選定候補のパラメータとパフォーマンスをDBに保存
python save_final_candidates_to_db.py

# パフォーマンス時系列データをDBに保存
python save_performance_time_series_to_db.py
```

---

## 5. データベーススキーマ詳細

### 5.1 共通テーブル

#### `features_monthly`
月次特徴量のスナップショット。両方の運用スタイルで使用されます。

主要カラム：
- `as_of_date`: 評価日（YYYY-MM-DD）
- `code`: 銘柄コード
- `core_score`: ファンダメンタルスコア
- `entry_score`: エントリースコア（BB/RSI）

#### `portfolio_monthly`
月次ポートフォリオの確定結果。**月次リバランス型で使用**されます。

主要カラム：
- `rebalance_date`: リバランス日（YYYY-MM-DD）
- `code`: 銘柄コード
- `weight`: ウェイト
- `core_score`: スコア
- `entry_score`: エントリースコア

### 5.2 長期保有型テーブル

#### `holdings`
実際の保有銘柄を管理します。

主要カラム：
- `purchase_date`: 購入日
- `code`: 銘柄コード
- `shares`: 株数
- `purchase_price`: 購入単価

### 5.3 月次リバランス型テーブル（`monthly_rebalance_`接頭辞）

#### `monthly_rebalance_final_selected_candidates`
最終選定候補の基本情報とパラメータを保存します。

主要カラム：
- `trial_number`: トライアル番号
- `params`: パラメータ（JSON形式）

#### `monthly_rebalance_candidate_performance`
最終選定候補のパフォーマンス指標を集計して保存します。

主要カラム：
- `trial_number`: トライアル番号
- `evaluation_period`: 評価期間（`holdout_2023_2024`、`holdout_2025`等）
- `sharpe_excess`: 超過Sharpe比
- `cagr_excess`: 超過CAGR
- `max_drawdown`: 最大ドローダウン

#### `monthly_rebalance_candidate_monthly_returns`
月次超過リターンの時系列データを保存します。

主要カラム：
- `trial_number`: トライアル番号
- `evaluation_period`: 評価期間
- `period_date`: 期間日（YYYY-MM-DD）
- `excess_return`: 超過リターン（小数）

#### `monthly_rebalance_candidate_detailed_metrics`
詳細パフォーマンス指標を保存します。

主要カラム：
- `trial_number`: トライアル番号
- `evaluation_period`: 評価期間
- 年別Sharpe、CAGR、MaxDD、ターンオーバー等

---

## 6. 運用スタイルの比較

### 6.1 目的の違い

| 項目 | 長期保有型 | 月次リバランス型 |
|------|-----------|-----------------|
| 主な目的 | NISA想定の長期積立 | 時系列の超過リターン |
| 入替頻度 | 低頻度（月次〜四半期の定期点検） | 高頻度（月次で全入れ替え） |
| 意思決定 | スクリーニング結果を参考に手動判断 | 最適化されたパラメータで自動選定 |

### 6.2 データ管理の違い

| 項目 | 長期保有型 | 月次リバランス型 |
|------|-----------|-----------------|
| ポートフォリオ保存先 | `portfolio_monthly`（参考情報） | `portfolio_monthly`（確定結果） |
| パフォーマンス保存先 | `backtest_performance` | `monthly_rebalance_candidate_performance` |
| テーブル命名規則 | 接頭辞なし | `monthly_rebalance_`接頭辞 |

### 6.3 評価方法の違い

| 項目 | 長期保有型 | 月次リバランス型 |
|------|-----------|-----------------|
| 評価指標 | 累積リターン、保有期間 | Sharpe比、CAGR、MaxDD、ターンオーバー |
| 評価方法 | 単一時点での評価 | 時系列での評価（Holdout検証、WFA） |
| 最適化 | 手動パラメータ調整 | Optunaによる自動最適化 |

---

## 7. 注意事項

### 7.1 データベーステーブルの命名規則

- **月次リバランス型のテーブルには `monthly_rebalance_` という接頭辞を付けます**
- これにより、長期保有型と月次リバランス型のデータを明確に区別できます
- 新しい月次リバランス型のテーブルを作成する際は、必ずこの接頭辞を使用してください

### 7.2 並列実行時の注意

- SQLite環境では、並列書き込みがロック待ちを引き起こす可能性があります
- 最適化実行時は `--n-jobs 2〜4` を推奨します
- BLASスレッドは自動で1に設定されますが、手動で環境変数を設定することも可能です

### 7.3 データ更新のタイミング

- 財務データは決算発表後に更新されます
- 予想値は会社予想の更新タイミングに依存します
- データ遅延を考慮した運用が必要です

---

## 8. 関連ドキュメント

- `README.md`: プロジェクト概要とクイックスタート
- `OPTIMIZATION_SYSTEM_OVERVIEW.md`: 最適化システム全体像
- `OPTIMIZATION_RESULT_INTERPRETATION.md`: 最適化結果の解釈
- `OPTIMIZATION_EXECUTION_EXAMPLES.md`: 最適化実行例
- `PERFORMANCE_CALCULATION_METHODS.md`: パフォーマンス計算方法
- `TIMESERIES_REFINEMENT_PLAN.md`: 時系列バックテストの設計
- `TRADING_COST_DOCUMENTATION.md`: 取引コストの扱い
- `FINAL_SELECTED_CANDIDATES.md`: 最終選定候補の情報

