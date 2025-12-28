-- =========================================================
-- Migration: Add company_name column to holdings table
-- =========================================================
-- 保有銘柄に社名を追加

ALTER TABLE holdings ADD COLUMN company_name TEXT;
-- 社名（購入日時点の最新の社名）

