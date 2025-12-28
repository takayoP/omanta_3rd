-- =========================================================
-- Indexes（性能が効く）
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_listed_code_date ON listed_info (code, date);
CREATE INDEX IF NOT EXISTS idx_prices_code_date ON prices_daily (code, date);
CREATE INDEX IF NOT EXISTS idx_fins_code_date ON fins_statements (code, disclosed_date);
CREATE INDEX IF NOT EXISTS idx_feat_date_score ON features_monthly (as_of_date, core_score);
CREATE INDEX IF NOT EXISTS idx_backtest_rebalance ON backtest_performance (rebalance_date);
CREATE INDEX IF NOT EXISTS idx_backtest_asof ON backtest_performance (as_of_date);
CREATE INDEX IF NOT EXISTS idx_backtest_stock_rebalance ON backtest_stock_performance (rebalance_date, as_of_date);
CREATE INDEX IF NOT EXISTS idx_index_date_code ON index_daily (date, index_code);
CREATE INDEX IF NOT EXISTS idx_holdings_code ON holdings (code);
CREATE INDEX IF NOT EXISTS idx_holdings_purchase_date ON holdings (purchase_date);
CREATE INDEX IF NOT EXISTS idx_holdings_sell_date ON holdings (sell_date);
CREATE INDEX IF NOT EXISTS idx_holdings_active ON holdings (sell_date) WHERE sell_date IS NULL;
CREATE INDEX IF NOT EXISTS idx_holdings_summary_date ON holdings_summary (as_of_date);