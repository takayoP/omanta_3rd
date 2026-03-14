-- V1 スリム化: run 単位の新テーブル（長期/月次を mode で区別）

-- strategy_runs: 実行メタデータ
CREATE TABLE IF NOT EXISTS strategy_runs (
  run_id TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  run_type TEXT NOT NULL,
  score_profile TEXT,
  params_json TEXT,
  asof TEXT,
  start_date TEXT,
  end_date TEXT,
  objective_name TEXT,
  objective_value REAL,
  parent_run_id TEXT,
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- portfolio_snapshots: リバランス日ごとの選定結果
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  run_id TEXT NOT NULL,
  rebalance_date TEXT NOT NULL,
  code TEXT NOT NULL,
  rank INTEGER,
  weight REAL,
  total_score REAL,
  core_score_ref REAL,
  entry_score_ref REAL,
  bucket TEXT,
  action TEXT,
  detail_json TEXT,
  PRIMARY KEY (run_id, rebalance_date, code),
  FOREIGN KEY (run_id) REFERENCES strategy_runs(run_id)
);

-- performance_series: 日付ごとの時系列
CREATE TABLE IF NOT EXISTS performance_series (
  run_id TEXT NOT NULL,
  date TEXT NOT NULL,
  nav REAL,
  return REAL,
  benchmark_return REAL,
  excess_return REAL,
  drawdown REAL,
  turnover REAL,
  PRIMARY KEY (run_id, date),
  FOREIGN KEY (run_id) REFERENCES strategy_runs(run_id)
);

-- performance_summary: run 単位の集計指標
CREATE TABLE IF NOT EXISTS performance_summary (
  run_id TEXT PRIMARY KEY,
  cagr REAL,
  sharpe REAL,
  maxdd REAL,
  calmar REAL,
  avg_turnover REAL,
  hit_ratio REAL,
  detail_json TEXT,
  FOREIGN KEY (run_id) REFERENCES strategy_runs(run_id)
);

-- live_holdings: 実保有（既存 holdings の v2 として optional）
CREATE TABLE IF NOT EXISTS live_holdings (
  asof_date TEXT NOT NULL,
  code TEXT NOT NULL,
  shares REAL,
  avg_cost REAL,
  market_value REAL,
  status TEXT,
  PRIMARY KEY (asof_date, code)
);

CREATE INDEX IF NOT EXISTS ix_portfolio_snapshots_run_rebalance ON portfolio_snapshots(run_id, rebalance_date);
CREATE INDEX IF NOT EXISTS ix_performance_series_run_date ON performance_series(run_id, date);
