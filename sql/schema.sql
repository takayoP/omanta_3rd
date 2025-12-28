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
  open REAL,
  -- 始値（調整前）
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
  topix_return_pct REAL,
  -- TOPIXリターン（%）
  excess_return_pct REAL,
  -- 超過リターン（%）= ポートフォリオリターン - TOPIXリターン
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
  -- リバランス日の翌営業日の始値（購入価格）
  current_price REAL,
  -- 評価日時点の終値（評価価格）
  split_multiplier REAL,
  -- リバランス日の翌営業日以降の分割倍率
  adjusted_current_price REAL,
  -- 分割を考慮した調整済み評価価格（current_price * split_multiplier）
  return_pct REAL,
  -- リターン（%）
  investment_amount REAL,
  -- 投資金額（比較用の仮想金額）
  topix_return_pct REAL,
  -- TOPIXリターン（%）
  excess_return_pct REAL,
  -- 超過リターン（%）= 銘柄リターン - TOPIXリターン
  PRIMARY KEY (rebalance_date, as_of_date, code)
);
-- -----------------------
-- 8) holdings : 実際の保有銘柄
-- -----------------------
CREATE TABLE IF NOT EXISTS holdings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  purchase_date TEXT NOT NULL,
  -- 購入日（YYYY-MM-DD）
  code TEXT NOT NULL,
  -- 銘柄コード
  company_name TEXT,
  -- 社名（購入日時点の最新の社名）
  shares REAL NOT NULL,
  -- 株数
  purchase_price REAL NOT NULL,
  -- 購入単価
  broker TEXT,
  -- 証券会社名（例: "SBI証券", "大和証券"）
  current_price REAL,
  -- 現在価格（最新の終値、更新時に計算）
  adjustment_factor REAL,
  -- 調整係数（株式分割・併合による株数倍率、購入日から評価日までの分割倍率）
  -- 例: 1:3分割の場合、adjustment_factor = 3.0
  -- 購入日から評価日までの分割倍率 = ∏(1 / prices_daily.adjustment_factor)
  unrealized_pnl REAL,
  -- 含み損益（保有中の場合、更新時に計算）
  return_pct REAL,
  -- リターン（%）、更新時に計算
  sell_date TEXT,
  -- 売却日（YYYY-MM-DD、NULLの場合は保有中）
  sell_price REAL,
  -- 売却単価（NULLの場合は保有中）
  realized_pnl REAL,
  -- 実現損益（売却時のみ、更新時に計算）
  topix_return_pct REAL,
  -- TOPIXリターン（%）、更新時に計算
  excess_return_pct REAL,
  -- 超過リターン（%）= リターン - TOPIXリターン、更新時に計算
  created_at TEXT,
  -- 作成日時（YYYY-MM-DD HH:MM:SS）
  updated_at TEXT,
  -- 更新日時（YYYY-MM-DD HH:MM:SS）
  UNIQUE(purchase_date, code, shares, purchase_price)
  -- 同じ購入日・銘柄・株数・単価の重複を防ぐ
);
-- -----------------------
-- 9) holdings_summary : 保有銘柄全体のパフォーマンスサマリー
-- -----------------------
CREATE TABLE IF NOT EXISTS holdings_summary (
  as_of_date TEXT NOT NULL,
  -- 評価日（YYYY-MM-DD）
  total_investment REAL,
  -- 総投資額（保有中の銘柄のみ）
  total_unrealized_pnl REAL,
  -- 総含み損益（保有中の銘柄のみ）
  total_realized_pnl REAL,
  -- 総実現損益（売却済み銘柄のみ）
  portfolio_return_pct REAL,
  -- ポートフォリオ全体のリターン（%）
  topix_return_pct REAL,
  -- TOPIXリターン（%）
  excess_return_pct REAL,
  -- 超過リターン（%）= ポートフォリオリターン - TOPIXリターン
  num_holdings INTEGER,
  -- 保有中銘柄数
  num_sold INTEGER,
  -- 売却済み銘柄数
  created_at TEXT,
  -- 作成日時（YYYY-MM-DD HH:MM:SS）
  updated_at TEXT,
  -- 更新日時（YYYY-MM-DD HH:MM:SS）
  PRIMARY KEY (as_of_date)
);
-- -----------------------
-- 10) earnings_calendar : 決算発表予定日
-- -----------------------
CREATE TABLE IF NOT EXISTS earnings_calendar (
  code TEXT NOT NULL,
  -- 銘柄コード
  announcement_date TEXT NOT NULL,
  -- 決算発表予定日（YYYY-MM-DD）
  period_type TEXT,
  -- 期間種別（FY / 1Q / 2Q / 3Q）
  period_end TEXT,
  -- 当期末日（YYYY-MM-DD）
  created_at TEXT,
  -- 作成日時（YYYY-MM-DD HH:MM:SS）
  updated_at TEXT,
  -- 更新日時（YYYY-MM-DD HH:MM:SS）
  PRIMARY KEY (code, announcement_date, period_type, period_end)
);
-- -----------------------
-- 11) index_daily : 指数データ（TOPIXなど）
-- -----------------------
CREATE TABLE IF NOT EXISTS index_daily (
  date TEXT NOT NULL,
  -- YYYY-MM-DD
  index_code TEXT NOT NULL,
  -- 指数コード（例: "0000" はTOPIX指数）
  open REAL,
  -- 始値
  high REAL,
  -- 高値
  low REAL,
  -- 安値
  close REAL,
  -- 終値
  PRIMARY KEY (date, index_code)
);