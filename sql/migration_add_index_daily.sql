-- =========================================================
-- Migration: Add index_daily table
-- =========================================================
-- 指数データ（日経平均指数など）を保存するテーブルを作成
-- SQLiteでは CREATE TABLE IF NOT EXISTS を使用するため、既に存在する場合はスキップされる

CREATE TABLE IF NOT EXISTS index_daily (
  date TEXT NOT NULL,
  -- YYYY-MM-DD
  index_code TEXT NOT NULL,
  -- 指数コード（例: "N225" は日経平均指数）
  open REAL,
  -- 始値
  high REAL,
  -- 高値
  low REAL,
  -- 安値
  close REAL,
  -- 終値
  PRIMARY KEY (date, index_code)
);

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_index_date_code ON index_daily (date, index_code);

