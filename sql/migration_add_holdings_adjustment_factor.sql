-- =========================================================
-- Migration: Add adjustment_factor column to holdings table
-- =========================================================
-- 保有銘柄テーブルにadjustment_factorカラムを追加
-- 購入日から評価日までの株式分割・併合による株数倍率を保存

ALTER TABLE holdings
ADD COLUMN adjustment_factor REAL;
-- 調整係数（株式分割・併合による株数倍率）
-- 例: 1:3分割の場合、adjustment_factor = 3.0
-- 購入日から評価日までの分割倍率 = ∏(1 / prices_daily.adjustment_factor)

