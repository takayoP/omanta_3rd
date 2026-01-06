-- =========================================================
-- strategy_paramsテーブルにJSONファイルパスカラムを追加
-- =========================================================
-- JSONファイルの保存先を記録するカラムを追加
ALTER TABLE strategy_params ADD COLUMN json_file_path TEXT;

-- インデックス（必要に応じて）
CREATE INDEX IF NOT EXISTS idx_strategy_params_json_file ON strategy_params(json_file_path);

