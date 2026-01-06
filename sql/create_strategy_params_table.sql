-- =========================================================
-- strategy_params : 戦略パラメータテーブル
-- =========================================================
-- 運用パラメータと研究用パラメータを保存
CREATE TABLE IF NOT EXISTS strategy_params (
  param_id TEXT NOT NULL PRIMARY KEY,
  -- パラメータID（例: "operational_24M", "12M_momentum", "12M_reversal"）
  horizon_months INTEGER NOT NULL,
  -- ホライズン（12, 24, 36）
  strategy_type TEXT NOT NULL,
  -- "operational" または "research"
  portfolio_type TEXT NOT NULL,
  -- "longterm"（長期保有型）または "monthly_rebalance"（月次リバランス型）
  strategy_mode TEXT,
  -- "momentum"（順張り）, "reversal"（逆張り）, "mixed"（混合）
  source_fold TEXT,
  -- 元のfold（例: "fold1", "fold2"）
  source_test_period TEXT,
  -- 元のテスト期間（例: "2022-01-31 to 2022-12-30"）
  description TEXT,
  -- 説明
  recommended_for TEXT,
  -- "operational_use" または "regime_switching"
  -- パラメータ値
  w_quality REAL,
  w_growth REAL,
  w_record_high REAL,
  w_size REAL,
  w_value REAL,
  w_forward_per REAL,
  roe_min REAL,
  bb_weight REAL,
  liquidity_quantile_cut REAL,
  rsi_base REAL,
  rsi_max REAL,
  bb_z_base REAL,
  bb_z_max REAL,
  rsi_min_width REAL,
  bb_z_min_width REAL,
  -- メタデータ（JSON形式で保存）
  metadata_json TEXT,
  -- パフォーマンス情報（JSON形式で保存）
  performance_json TEXT,
  -- 横持ち評価結果（JSON形式で保存）
  cross_validation_json TEXT,
  -- JSONファイルの保存先パス
  json_file_path TEXT,
  -- 作成日時
  created_at TEXT NOT NULL,
  -- 更新日時
  updated_at TEXT NOT NULL,
  -- 有効フラグ
  is_active INTEGER DEFAULT 1
  -- 1: 有効, 0: 無効
);

-- インデックス
CREATE INDEX IF NOT EXISTS idx_strategy_params_type ON strategy_params(strategy_type);
CREATE INDEX IF NOT EXISTS idx_strategy_params_portfolio_type ON strategy_params(portfolio_type);
CREATE INDEX IF NOT EXISTS idx_strategy_params_horizon ON strategy_params(horizon_months);
CREATE INDEX IF NOT EXISTS idx_strategy_params_mode ON strategy_params(strategy_mode);
CREATE INDEX IF NOT EXISTS idx_strategy_params_active ON strategy_params(is_active);
CREATE INDEX IF NOT EXISTS idx_strategy_params_json_file ON strategy_params(json_file_path);

