# omanta_3rd — Claude 引き継ぎドキュメント

## プロジェクト概要

J-Quants API（日本株データ）と SQLite を使った**個人向け投資アルゴリズム**。
長期保有型（月次リバランス）のポートフォリオ自動選定・バックテスト・最適化を行う。

- データソース：J-Quants API（価格・財務・上場情報）
- DB：SQLite（`data/db/jquants.sqlite`）
- 言語：Python 3.9+

---

## セットアップ

```bash
# 依存インストール
pip install -e ".[dev]"

# 環境変数（.env をコピーして編集）
cp .env.example .env
# → JQUANTS_API_KEY, DB_PATH を設定

# DB初期化
python -m omanta_3rd.jobs.init_db

# テスト
python -m pytest tests/ -v
```

### 必要な環境変数（.env）

```
JQUANTS_API_KEY=...         # J-Quants APIキー
DB_PATH=data/db/jquants.sqlite
LOG_DIR=data/logs
# EXECUTION_DATE=2024-01-31  # バックテスト用（省略時は当日）
```

---

## アーキテクチャ（レイヤー構造）

依存は必ず **下位層 → 上位層** の一方向。逆方向の import は禁止。

```
config/         設定（環境変数・戦略パラメータ・レジームポリシー）
    ↓
infra/          DB接続・J-Quants APIクライアント
    ↓
ingest/         ETL（API → DB）
    ↓
features/       特徴量計算（純粋関数 + DBローダー）
market/         市場レジーム判定（TOPIX移動平均）
    ↓
strategy/       スコアリング・ポートフォリオ選定
    ↓
backtest/       パフォーマンス計算・評価指標
portfolio/      保有銘柄管理（実運用用）
reporting/      CSV/JSON/HTML出力
    ↓
jobs/           実行エントリーポイント（CLI スクリプト群）
```

### 重要な例外
- `backtest/feature_cache.py` が `jobs/longterm_run.py` を import している
  （最適化の高速化のため意図的な設計。循環ではない）

---

## 主要コマンド

```bash
# ETL（市場データ更新）
python -m omanta_3rd.jobs.etl_update

# 月次ポートフォリオ構築
python -m omanta_3rd.jobs.longterm_run --asof 2025-01-31

# バックテスト（全期間）
python -m omanta_3rd.jobs.backtest

# パラメータ最適化（長期保有型）
python -m omanta_3rd.jobs.optimize_longterm --params-id operational_24M

# バッチ実行（複数月）
python -m omanta_3rd.jobs.batch_longterm_run --start 2020-01-01 --end 2025-12-31

# テスト
python -m pytest tests/ -v
```

---

## モジュール別 公開API

各パッケージの `__init__.py` に `__all__` が定義されている。

```python
from omanta_3rd.features import calculate_roe, rsi_from_series, bb_zscore
from omanta_3rd.strategy import calculate_core_score, select_portfolio
from omanta_3rd.backtest import calculate_max_drawdown, calculate_sharpe_ratio
from omanta_3rd.infra import connect_db, JQuantsClient
from omanta_3rd.market import get_market_regime
```

---

## 戦略パラメータ

### `StrategyParams`（`jobs/longterm_run.py`）
長期保有型のコアパラメータ。最適化結果で上書きされる。
- `roe_min`: ROEフィルタ下限（デフォルト 6.21%）
- `w_value`: バリュースコア重み（最も重要、39.08%）
- `sector_cap`: 同一業種の上限銘柄数（4）
- 最適化結果は `config/params_registry_longterm.json` で管理

### `StrategyConfig`（`config/strategy.py`）
`strategy/` モジュール用の設定クラス（`StrategyParams` とは別物）。

---

## 設計上の重要な制約

### 先読みバイアス防止（最重要）
- 全クエリは `disclosed_date <= rebalance_date` または `date <= as_of_date` を必ず付ける
- `as_of_date` は必須引数として明示的に渡す設計（`None` にしない）
- 未来の価格・財務データを参照しないことが正確なバックテストの前提

### 日付の扱い
- 日付は常に文字列 `"YYYY-MM-DD"` で扱う
- 翌営業日取得: `_get_next_trading_day(conn, date, max_date=as_of_date)`
- 株式分割の補正: `_split_multiplier_between(conn, code, start_date, end_date)`

### DB接続
- `connect_db()` はコンテキストマネージャ（`with connect_db() as conn:`）
- 直接 `sqlite3.connect()` を使わない

---

## テスト

```
tests/
  test_features.py   # 純粋計算関数（DB不要）: ROE, PER, RSI, BB, utils
  test_metrics.py    # バックテスト指標（DB不要）: Sharpe, MaxDD, CAGR
  test_scoring.py    # スコアリング（インメモリSQLite）
  test_selection.py  # ポートフォリオ選定（インメモリSQLite）
```

- 合計 88 テスト、全 PASS
- DB依存テストはインメモリSQLiteを使用（`sqlite3.connect(":memory:")`）
- `backtest/performance.py` と `timeseries.py` はテスト未整備（実DB依存が深い）

---

## 今後の課題（優先度順）

### 中優先
- `backtest/performance.py` / `timeseries.py` のテスト追加
  （関数が内部で `connect_db()` を呼ぶため、`unittest.mock.patch` か `conn` 引数追加が必要）

### 低優先
- `jobs/` 内の26ファイルをサブパッケージで整理（optimize/, analysis/ など）
- `_daterange` 関数が `ingest/prices.py` と `ingest/fins.py` に重複（`ingest/utils.py` に統合可能）
- `config/__init__.py` に `__all__` を追加

---

## コードベースの健全性メモ

このコードベースは一連のリファクタリングで整理済み（2026年3月）：
- 循環依存を解消（`ProgressWindow` を `progress_window.py` に分離）
- デッドコード・重複実装を削除（約400行削減）
- 全モジュールに `__all__` を定義
- ユニットテスト88件を追加

総合評価 **B+**（個人開発としては上位水準）。
