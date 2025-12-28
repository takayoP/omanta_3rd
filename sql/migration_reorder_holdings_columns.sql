-- =========================================================
-- Migration: Reorder holdings table columns to put company_name after code
-- =========================================================
-- company_nameカラムをcodeカラムの直後に移動

-- 一時テーブルを作成（新しい順序で）
CREATE TABLE IF NOT EXISTS holdings_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  purchase_date TEXT NOT NULL,
  -- 購入日（YYYY-MM-DD）
  code TEXT NOT NULL,
  -- 銘柄コード
  company_name TEXT,
  -- 社名（購入日時点の最新の社名）
  shares REAL NOT NULL,
  -- 株数
  purchase_price REAL NOT NULL,
  -- 購入単価
  broker TEXT,
  -- 証券会社名（例: "SBI証券", "大和証券"）
  current_price REAL,
  -- 現在価格（最新の終値、更新時に計算）
  unrealized_pnl REAL,
  -- 含み損益（保有中の場合、更新時に計算）
  return_pct REAL,
  -- リターン（%）、更新時に計算
  sell_date TEXT,
  -- 売却日（YYYY-MM-DD、NULLの場合は保有中）
  sell_price REAL,
  -- 売却単価（NULLの場合は保有中）
  realized_pnl REAL,
  -- 実現損益（売却時のみ、更新時に計算）
  topix_return_pct REAL,
  -- TOPIXリターン（%）、更新時に計算
  excess_return_pct REAL,
  -- 超過リターン（%）= リターン - TOPIXリターン、更新時に計算
  created_at TEXT,
  -- 作成日時（YYYY-MM-DD HH:MM:SS）
  updated_at TEXT,
  -- 更新日時（YYYY-MM-DD HH:MM:SS）
  UNIQUE(purchase_date, code, shares, purchase_price)
  -- 同じ購入日・銘柄・株数・単価の重複を防ぐ
);

-- 既存のデータを新しいテーブルにコピー
INSERT INTO holdings_new (
  id, purchase_date, code, company_name, shares, purchase_price, broker,
  current_price, unrealized_pnl, return_pct, sell_date, sell_price, realized_pnl,
  topix_return_pct, excess_return_pct, created_at, updated_at
)
SELECT 
  id, purchase_date, code, company_name, shares, purchase_price, broker,
  current_price, unrealized_pnl, return_pct, sell_date, sell_price, realized_pnl,
  topix_return_pct, excess_return_pct, created_at, updated_at
FROM holdings;

-- 古いテーブルを削除
DROP TABLE holdings;

-- 新しいテーブルをholdingsにリネーム
ALTER TABLE holdings_new RENAME TO holdings;

-- インデックスを再作成
CREATE INDEX IF NOT EXISTS idx_holdings_code ON holdings (code);
CREATE INDEX IF NOT EXISTS idx_holdings_purchase_date ON holdings (purchase_date);
CREATE INDEX IF NOT EXISTS idx_holdings_sell_date ON holdings (sell_date);
CREATE INDEX IF NOT EXISTS idx_holdings_active ON holdings (sell_date) WHERE sell_date IS NULL;

