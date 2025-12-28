-- =========================================================
-- Migration: Add broker column to holdings table
-- =========================================================
-- 保有銘柄に証券会社の情報を追加

ALTER TABLE holdings ADD COLUMN broker TEXT;
-- 証券会社名（例: "SBI証券", "大和証券"）

