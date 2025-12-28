-- =========================================================
-- Migration: Add earnings calendar table for announcement dates
-- =========================================================
-- 決算発表予定日を管理するテーブルを作成

CREATE TABLE IF NOT EXISTS earnings_calendar (
  code TEXT NOT NULL,
  -- 銘柄コード
  announcement_date TEXT NOT NULL,
  -- 決算発表予定日（YYYY-MM-DD）
  period_type TEXT,
  -- 期間種別（FY / 1Q / 2Q / 3Q）
  period_end TEXT,
  -- 当期末日（YYYY-MM-DD）
  created_at TEXT,
  -- 作成日時（YYYY-MM-DD HH:MM:SS）
  updated_at TEXT,
  -- 更新日時（YYYY-MM-DD HH:MM:SS）
  PRIMARY KEY (code, announcement_date, period_type, period_end)
);

-- インデックスの作成
CREATE INDEX IF NOT EXISTS idx_earnings_calendar_date ON earnings_calendar (announcement_date);
CREATE INDEX IF NOT EXISTS idx_earnings_calendar_code ON earnings_calendar (code);

