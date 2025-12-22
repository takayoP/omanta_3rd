-- =========================================================
-- J-Quants SQLite Schema (Pandas + SQLite)
-- =========================================================
-- -----------------------
-- 1) listed_info : 銘柄属性
-- -----------------------
CREATE TABLE IF NOT EXISTS listed_info (
  date TEXT NOT NULL,
  -- YYYY-MM-DD
  code TEXT NOT NULL,
  -- 銘柄コード（4桁推奨に統一）
  company_name TEXT,
  market_name TEXT,
  -- "プライム" 等
  sector17 TEXT,
  sector33 TEXT,
  PRIMARY KEY (date, code)
);
-- -----------------------
-- 2) prices_daily : 日足
-- -----------------------
CREATE TABLE IF NOT EXISTS prices_daily (
  date TEXT NOT NULL,
  -- YYYY-MM-DD
  code TEXT NOT NULL,
  close REAL,
  -- 調整前終値
  adj_close REAL,
  -- 調整済終値
  adj_volume REAL,
  -- 調整済出来高
  turnover_value REAL,
  -- 売買代金
  adjustment_factor REAL,
  -- 調整係数（株式分割等の調整係数、1:2分割なら0.5）
  PRIMARY KEY (date, code)
);
-- -----------------------
-- 3) fins_statements : 財務（開示ベース）
--    ※数値はAPIでは文字列なので、DBではREALで持つ
-- -----------------------
CREATE TABLE IF NOT EXISTS fins_statements (
  disclosed_date TEXT NOT NULL,
  -- YYYY-MM-DD（開示日）
  disclosed_time TEXT,
  -- HH:MM:SS など（あれば）
  code TEXT NOT NULL,
  -- 銘柄コード
  type_of_current_period TEXT,
  -- FY / 1Q / 2Q / 3Q / ...
  current_period_end TEXT,
  -- YYYY-MM-DD（当期末）
  -- 実績（FYを中心に使う）
  operating_profit REAL,
  -- 営業利益
  profit REAL,
  -- 当期純利益
  equity REAL,
  -- 純資産
  eps REAL,
  -- EPS（実績）
  bvps REAL,
  -- BVPS
  -- 予想（会社予想）
  forecast_operating_profit REAL,
  forecast_profit REAL,
  forecast_eps REAL,
  next_year_forecast_operating_profit REAL,
  next_year_forecast_profit REAL,
  next_year_forecast_eps REAL,
  -- 株数（取れるなら時価総額に使う）
  shares_outstanding REAL,
  -- 期末発行済株式数（自己株含む）
  treasury_shares REAL,
  -- 期末自己株式数
  PRIMARY KEY (
    disclosed_date,
    code,
    type_of_current_period,
    current_period_end
  )
);
-- -----------------------
-- 4) features_monthly : 月次特徴量（スナップショット）
--    as_of_date＝月末営業日
-- -----------------------
CREATE TABLE IF NOT EXISTS features_monthly (
  as_of_date TEXT NOT NULL,
  -- YYYY-MM-DD
  code TEXT NOT NULL,
  sector33 TEXT,
  liquidity_60d REAL,
  -- 売買代金60営業日平均
  market_cap REAL,
  -- 時価総額（推定でも可）
  -- 実績ベース
  roe REAL,
  roe_trend REAL,
  -- バリュエーション
  per REAL,
  pbr REAL,
  forward_per REAL,
  -- フォワードPER（予想EPS）
  -- 予想成長率
  op_growth REAL,
  profit_growth REAL,
  -- 最高益（実績/予想で立てる）
  record_high_flag INTEGER,
  record_high_forecast_flag INTEGER,
  core_score REAL,
  entry_score REAL,
  PRIMARY KEY (as_of_date, code)
);
-- -----------------------
-- 5) portfolio_monthly : 月次ポートフォリオ（確定結果）
-- -----------------------
CREATE TABLE IF NOT EXISTS portfolio_monthly (
  rebalance_date TEXT NOT NULL,
  code TEXT NOT NULL,
  weight REAL NOT NULL,
  core_score REAL,
  entry_score REAL,
  reason TEXT,
  -- JSON文字列など（採用理由）
  PRIMARY KEY (rebalance_date, code)
);
-- -----------------------
-- 6) backtest_performance : バックテストパフォーマンス結果
-- -----------------------
CREATE TABLE IF NOT EXISTS backtest_performance (
  rebalance_date TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  total_return_pct REAL,
  -- ポートフォリオ全体の総リターン（%）
  num_stocks INTEGER,
  -- 銘柄数
  num_stocks_with_price INTEGER,
  -- 価格データがある銘柄数
  avg_return_pct REAL,
  -- 平均リターン（%）
  min_return_pct REAL,
  -- 最小リターン（%）
  max_return_pct REAL,
  -- 最大リターン（%）
  created_at TEXT,
  -- 作成日時（YYYY-MM-DD HH:MM:SS）
  PRIMARY KEY (rebalance_date, as_of_date)
);
-- -----------------------
-- 7) backtest_stock_performance : バックテスト銘柄別パフォーマンス
-- -----------------------
CREATE TABLE IF NOT EXISTS backtest_stock_performance (
  rebalance_date TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  code TEXT NOT NULL,
  weight REAL NOT NULL,
  rebalance_price REAL,
  -- リバランス日時点の価格
  current_price REAL,
  -- 評価日時点の価格
  return_pct REAL,
  -- リターン（%）
  PRIMARY KEY (rebalance_date, as_of_date, code)
);