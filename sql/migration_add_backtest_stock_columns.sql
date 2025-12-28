-- =========================================================
-- Migration: Add split_multiplier and adjusted_current_price columns to backtest_stock_performance
-- =========================================================
-- 既存のbacktest_stock_performanceテーブルに分割倍率と調整済み価格カラムを追加
ALTER TABLE backtest_stock_performance
ADD COLUMN split_multiplier REAL;

ALTER TABLE backtest_stock_performance
ADD COLUMN adjusted_current_price REAL;








