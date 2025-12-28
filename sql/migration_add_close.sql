-- =========================================================
-- Migration: Add close column to prices_daily
-- =========================================================
-- 既存のprices_dailyテーブルにcloseカラム（調整前終値）を追加
ALTER TABLE prices_daily
ADD COLUMN close REAL;








