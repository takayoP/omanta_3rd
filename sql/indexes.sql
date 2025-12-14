-- =========================================================
-- Indexes（性能が効く）
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_listed_code_date ON listed_info (code, date);
CREATE INDEX IF NOT EXISTS idx_prices_code_date ON prices_daily (code, date);
CREATE INDEX IF NOT EXISTS idx_fins_code_date   ON fins_statements (code, disclosed_date);
CREATE INDEX IF NOT EXISTS idx_feat_date_score  ON features_monthly (as_of_date, core_score);


