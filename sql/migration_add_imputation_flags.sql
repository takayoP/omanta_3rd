-- =========================================================
-- Migration: Add imputation flags to fins_statements
-- =========================================================
-- 既存のfins_statementsテーブルに補完フラグカラムを追加
-- SQLiteでは、既存のテーブルにカラムを追加する場合はALTER TABLEを使用
-- ただし、SQLiteでは一度に複数のカラムを追加できないため、各カラムを個別に追加
-- 補完フラグカラムを追加（既に存在する場合はスキップ）
-- SQLiteではIF NOT EXISTSが使えないため、エラーを無視して実行
-- 営業利益の補完フラグ
ALTER TABLE fins_statements
ADD COLUMN imputed_op INTEGER DEFAULT 0;
-- 当期純利益の補完フラグ
ALTER TABLE fins_statements
ADD COLUMN imputed_profit INTEGER DEFAULT 0;
-- 純資産の補完フラグ
ALTER TABLE fins_statements
ADD COLUMN imputed_equity INTEGER DEFAULT 0;
-- EPSの補完フラグ
ALTER TABLE fins_statements
ADD COLUMN imputed_eps INTEGER DEFAULT 0;
-- BVPSの補完フラグ
ALTER TABLE fins_statements
ADD COLUMN imputed_bvps INTEGER DEFAULT 0;