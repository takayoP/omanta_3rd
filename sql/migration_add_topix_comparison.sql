-- =========================================================
-- Migration: Add TOPIX comparison columns to backtest tables
-- =========================================================
-- TOPIX比較結果を保存するためのカラムを追加

-- backtest_performance テーブルにTOPIX比較カラムを追加
ALTER TABLE backtest_performance ADD COLUMN topix_return_pct REAL;
-- TOPIXリターン（%）

ALTER TABLE backtest_performance ADD COLUMN excess_return_pct REAL;
-- 超過リターン（%）= ポートフォリオリターン - TOPIXリターン

-- backtest_stock_performance テーブルにTOPIX比較カラムを追加
ALTER TABLE backtest_stock_performance ADD COLUMN investment_amount REAL;
-- 投資金額（比較用の仮想金額）

ALTER TABLE backtest_stock_performance ADD COLUMN topix_return_pct REAL;
-- TOPIXリターン（%）

ALTER TABLE backtest_stock_performance ADD COLUMN excess_return_pct REAL;
-- 超過リターン（%）= 銘柄リターン - TOPIXリターン

