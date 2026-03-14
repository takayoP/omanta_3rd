-- V1 スリム化: features_monthly に ref score 用カラムを追加
-- 既存の core_score / entry_score は上書きしない（legacy 比較用に維持）

-- score_profile: どの固定式で作ったスコアか (例: v1_ref)
ALTER TABLE features_monthly ADD COLUMN score_profile TEXT;

-- core_score_ref: v1_ref による固定 core スコア
ALTER TABLE features_monthly ADD COLUMN core_score_ref REAL;

-- entry_score_ref: v1_ref による固定 entry スコア
ALTER TABLE features_monthly ADD COLUMN entry_score_ref REAL;
