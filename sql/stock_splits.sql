-- 株式分割情報テーブル
CREATE TABLE IF NOT EXISTS stock_splits (
    code TEXT NOT NULL,
    split_date TEXT NOT NULL,
    -- 株式分割日（YYYY-MM-DD）
    split_ratio REAL NOT NULL,
    -- 分割比率（例: 1→3株なら3.0）
    description TEXT,
    -- 説明（例: "1株→3株"）
    PRIMARY KEY (code, split_date)
);
-- インデックス
CREATE INDEX IF NOT EXISTS idx_stock_splits_code_date ON stock_splits(code, split_date);