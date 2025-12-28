-- =========================================================
-- Migration: Add holdings_summary table for portfolio performance summary
-- =========================================================
-- 保有銘柄全体のTOPIXとのパフォーマンス比較結果を保存するテーブル

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

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_holdings_summary_date ON holdings_summary (as_of_date);

