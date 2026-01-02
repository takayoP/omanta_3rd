-- =========================================================
-- Migration: Add open column to prices_daily
-- =========================================================
-- 既存のprices_dailyテーブルにopenカラム（始値）を追加
ALTER TABLE prices_daily
ADD COLUMN open REAL;














