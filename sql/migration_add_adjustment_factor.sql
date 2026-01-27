-- =========================================================
-- Migration: Add adjustment_factor column to prices_daily
-- =========================================================
-- 既存のprices_dailyテーブルにadjustment_factorカラムを追加
-- SQLiteでは、既存のテーブルにカラムを追加する場合はALTER TABLEを使用
-- カラムが既に存在する場合はエラーになるが、マイグレーションスクリプトでエラーハンドリングする
ALTER TABLE prices_daily
ADD COLUMN adjustment_factor REAL;


























