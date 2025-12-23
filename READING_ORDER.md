# プロジェクト全体の推奨読む順番

このドキュメントは、`omanta_3rd`プロジェクトのコードを理解するための推奨読む順番をまとめたものです。

---

## フェーズ1: プロジェクト概要の把握（必須・30分）

### 1. ドキュメントファイル
```
1. README.md                    # プロジェクトの目的と方針
2. SPECIFICATION.md              # システム仕様書（詳細）
3. ARCHITECTURE.md               # アーキテクチャ設計（参考）
4. CALCULATION_LOGIC_STANDARD.md # 計算ロジック仕様
5. pyproject.toml                # プロジェクト設定と依存関係
```

**目的**: プロジェクトの全体像、目的、設計思想を理解する

---

## フェーズ2: データベース構造の理解（30分）

### 2. スキーマ定義
```
1. sql/schema.sql                # データベーススキーマ（全テーブル定義）
2. sql/indexes.sql               # インデックス定義
3. sql/migration_*.sql           # マイグレーション（必要に応じて）
```

**目的**: データベースの構造とテーブル間の関係を理解する

---

## フェーズ3: インフラ層（基盤・1時間）

### 3. 設定管理
```
1. src/omanta_3rd/config/settings.py    # アプリケーション設定（DBパス、API設定）
   - 行1-30: 基本設定
   - 行31-35: その他の設定

2. src/omanta_3rd/config/strategy.py   # 戦略パラメータ（参考用、実際はmonthly_run.py内で定義）
```

**目的**: アプリケーションの設定と環境変数の扱いを理解する

### 4. データベース接続
```
1. src/omanta_3rd/infra/db.py           # データベース接続・操作ユーティリティ
   - 行1-39: connect_db関数（接続管理）
   - 行41-60: init_db関数（初期化）
   - 行62-106: upsert関数（UPSERT操作）
```

**目的**: データベース接続の管理方法とUPSERT操作を理解する

### 5. APIクライアント
```
1. src/omanta_3rd/infra/jquants.py     # J-Quants APIクライアント
   - 行1-50: クラス定義と初期化
   - 行55-66: リフレッシュトークン取得
   - 行68-82: IDトークン取得
   - 行84-87: トークン管理
   - 行89-128: get関数（APIリクエスト）
   - 行130-166: get_all_pages関数（ページネーション対応）
```

**目的**: J-Quants APIとの通信方法と認証処理を理解する

---

## フェーズ4: データ取り込み層（1時間）

### 6. データ取り込みモジュール
```
1. src/omanta_3rd/ingest/listed.py     # 銘柄情報取り込み
   - 行1-22: コード正規化
   - 行25-45: データ取得と変換
   - 行48-52: 保存
   - 行56-62: メイン関数

2. src/omanta_3rd/ingest/prices.py     # 価格データ取り込み
   - 行1-26: コード正規化とユーティリティ
   - 行43-49: データ取得
   - 行52-81: データマッピング
   - 行84-91: 保存
   - 行94-134: メイン関数

3. src/omanta_3rd/ingest/fins.py       # 財務データ取り込み
   - 行1-49: ユーティリティ関数
   - 行52-85: データマッピング
   - 行148-222: 重複レコードマージ（重要）
   - 行225-247: 保存
   - 行250-292: メイン関数
```

**目的**: APIから取得したデータをどのように加工してデータベースに保存するかを理解する

**重要ポイント**:
- コード正規化（5桁→4桁）
- フィールド名変換（PascalCase → snake_case）
- 重複レコードのマージ処理（財務データのみ）

---

## フェーズ5: 特徴量計算層（参考用）

### 7. 特徴量モジュール（参考）
```
1. src/omanta_3rd/features/universe.py      # ユニバース定義（参考）
2. src/omanta_3rd/features/fundamentals.py   # 財務指標計算（参考）
3. src/omanta_3rd/features/valuation.py      # バリュエーション指標（参考）
4. src/omanta_3rd/features/technicals.py     # テクニカル指標（参考）
```

**注意**: 実際の実装は`monthly_run.py`内にあります。これらのファイルは参考用です。

---

## フェーズ6: 投資戦略層（参考用）

### 8. 戦略モジュール（参考）
```
1. src/omanta_3rd/strategy/scoring.py  # スコアリング（参考）
2. src/omanta_3rd/strategy/select.py  # 銘柄選定（参考）
```

**注意**: 実際の実装は`monthly_run.py`内にあります。

---

## フェーズ7: ジョブ実行層（核心・3-4時間）

### 9. データベース初期化
```
1. src/omanta_3rd/jobs/init_db.py      # DB初期化ジョブ
   - 全体を読む（短いファイル）
```

### 10. ETL更新ジョブ
```
1. src/omanta_3rd/jobs/etl_update.py   # データ更新ジョブ
   - 行1-50: メイン関数とヘルパー
   - 行52-150: 各データ更新処理
```

### 11. 月次実行ジョブ（最重要・長いファイル）

**ファイル**: `src/omanta_3rd/jobs/monthly_run.py` (1858行)

#### 【読む順番】:

##### ステップ1: ファイルヘッダーと設定（10分）
```
1. 行1-60: ファイルヘッダーと設定
   - 行1-10: ファイル説明
   - 行31-59: StrategyParams（戦略パラメータ）
```

##### ステップ2: ユーティリティ関数（20分）
```
2. 行66-163: ユーティリティ関数
   - 行66-76: _safe_div（安全な除算）
   - 行79-82: _clip01（0-1にクリップ）
   - 行85-86: _pct_rank（パーセンタイル順位）
   - 行89-92: _log_safe（安全な対数）
   - 行95-103: _calc_slope（傾き計算）
   - 行106-121: _rsi_from_series（RSI計算）
   - 行124-133: _bb_zscore（ボリンジャーバンドZスコア）
   - 行136-161: _entry_score（エントリースコア）
```

##### ステップ3: 日付スナップと基本データ取得（15分）
```
3. 行547-600: 日付スナップと基本データ取得
   - 行547-555: _snap_price_date（評価日を営業日にスナップ）
   - 行558-569: _snap_listed_date（銘柄情報の日付をスナップ）
   - 行572-584: _load_universe（銘柄情報取得）
   - 行587-600: _load_prices_window（価格データ取得）
```

##### ステップ4: 株式分割・株数計算（理解が難しい部分・1時間）
```
4. 行232-545: 株式分割・株数計算
   - 行232-309: _split_multiplier_between（分割倍率計算）★重要
   - 行312-358: _get_shares_at_date（指定日の株数取得）
   - 行361-429: _get_latest_basis_shares（最新株数ベース計算、非推奨関数を使用）
   - 行432-545: _get_shares_adjustment_factor（株数調整係数）
   
   注意: この部分は複雑ですが、EPS/BPS計算の基礎となる重要な部分です。
```

##### ステップ5: 財務データ取得（1時間）
```
5. 行668-1071: 財務データ取得
   - 行668-878: _load_latest_fy（最新FY実績データ）★重要・長い
     - 行685-708: SQLクエリ（最新期の選定）
     - 行718-753: SQLクエリ（レコード取得）
     - 行765-850: 相互補完処理
     - 行857-877: 実績値優先の選定
   - 行881-971: _load_fy_history（過去FY履歴データ）
   - 行974-1071: _load_latest_forecast（最新予想データ）
```

##### ステップ6: build_features関数（核心部分・1.5時間）
```
6. 行1078-1725: build_features関数（核心部分）
   - 行1078-1093: 初期化と基本データ取得
   - 行1095-1125: 財務データ取得
   - 行1127-1165: データマージと補完
   - 行1185-1186: ROE計算
   - 行1188-1208: FY期末のネット株数計算
   - 行1210-1248: 分割倍率計算
   - 行1250-1260: 評価日時点のネット株数計算
   - 行1262-1336: EPS/BPS/予想EPS計算
   - 行1338-1358: PER/PBR/Forward PER計算
   - 行1360-1366: 時価総額計算
   - 行1374-1389: 成長率・最高益フラグ計算
   - 行1391-1405: 営業利益トレンド計算
   - 行1407-1461: ROEトレンド計算
   - 行1511-1516: エントリースコア計算
   - 行1518-1553: 各種スコア計算（value, growth, quality等）
   - 行1567-1710: 欠損値影響分析
```

##### ステップ7: ポートフォリオ選定（30分）
```
7. 行1732-1804: select_portfolio関数
   - 行1736-1747: フィルタリング（流動性、ROE）
   - 行1754-1756: プール選定（core_score上位）
   - 行1758-1760: エントリースコアでソート
   - 行1762-1777: セクター上限適用
   - 行1783-1799: 理由生成
```

##### ステップ8: データ保存（10分）
```
8. 行1811-1826: 保存関数
   - 行1811-1815: save_features（特徴量保存）
   - 行1818-1826: save_portfolio（ポートフォリオ保存）
```

##### ステップ9: メイン関数（10分）
```
9. 行1833-1857: main関数
   - 行1833-1850: メイン処理（build_features → select_portfolio → save）
   - 行1853-1857: コマンドライン引数処理
```

---

## フェーズ8: バックテスト機能（1時間）

### 12. バックテストジョブ
```
1. src/omanta_3rd/backtest/performance.py  # パフォーマンス計算
   - 行13-128: calculate_portfolio_performance（ポートフォリオパフォーマンス計算）
   - 行131-159: calculate_all_portfolios_performance（全ポートフォリオ計算）
   - 行162-208: save_performance_to_db（DB保存）

2. src/omanta_3rd/jobs/backtest.py         # バックテスト実行
   - 行18-91: main関数
   - 行94-132: コマンドライン引数処理
```

**目的**: バックテストの実行方法とパフォーマンス計算ロジックを理解する

---

## フェーズ9: その他のモジュール（30分）

### 13. レポート・エクスポート
```
1. src/omanta_3rd/reporting/export.py  # データエクスポート（必要に応じて）
```

### 14. スクリプトファイル
```
1. update_all_data.py                  # データ一括更新スクリプト
2. UPDATE_DATA_README.md               # データ更新の説明
```

### 15. テストファイル（理解を深めるために）
```
1. tests/test_scoring.py               # スコアリングテスト
2. tests/test_selection.py             # 選定ロジックテスト
```

---

## 推奨読む順番のまとめ（優先度順）

### 第1段階: 全体像把握（30分）
```
1. README.md
2. SPECIFICATION.md（全体を流し読み）
3. sql/schema.sql
4. src/omanta_3rd/config/settings.py
```

### 第2段階: インフラ層理解（1時間）
```
1. src/omanta_3rd/infra/db.py
2. src/omanta_3rd/infra/jquants.py
```

### 第3段階: データ取り込み理解（1時間）
```
1. src/omanta_3rd/ingest/listed.py
2. src/omanta_3rd/ingest/prices.py
3. src/omanta_3rd/ingest/fins.py（特に重複マージ処理）
```

### 第4段階: 核心部分理解（3-4時間）
```
1. src/omanta_3rd/jobs/monthly_run.py（上記の順番で読む）
   - 特にbuild_features関数（行1078-1725）を重点的に
```

### 第5段階: その他の機能（1時間）
```
1. src/omanta_3rd/jobs/etl_update.py
2. src/omanta_3rd/backtest/performance.py
3. src/omanta_3rd/jobs/backtest.py
```

---

## 読む際のポイント

### 重要度の高いファイル（必須）
1. **`monthly_run.py`** - システムの核心（最も重要）
2. **`fins.py`** - 財務データの取り込みとマージ
3. **`db.py`** - データベース操作の基礎
4. **`jquants.py`** - API通信の基礎

### 理解が難しい部分（時間をかけて）
1. `monthly_run.py`の株式分割処理（行232-545）
2. `monthly_run.py`のbuild_features関数（行1078-1725）
3. `fins.py`の重複レコードマージ（行148-222）

### 参考用ファイル（後回し可）
- `features/`配下のファイル（実際の実装は`monthly_run.py`内）
- `strategy/`配下のファイル（実際の実装は`monthly_run.py`内）

---

## 効率的な読み方のコツ

### 1. 全体像から詳細へ
- まずドキュメントとスキーマで全体像を把握
- 次にデータフローを追う（API → DB → 特徴量 → 選定）
- 最後に詳細な実装を理解

### 2. データフローを意識する
```
J-Quants API
    ↓
[ingest層] データ取得・正規化
    ↓
SQLite データベース
    ↓
[monthly_run.py] 特徴量計算・スコアリング
    ↓
[monthly_run.py] ポートフォリオ選定
    ↓
データベース保存
```

### 3. コメントを活用
- 各セクションの区切りコメント（`# -----------------------------`）で構造を把握
- 関数のdocstringで目的を理解
- 重要な処理には詳細なコメントがある

### 4. 段階的に理解する
- 最初は流れだけ理解する（細部は後回し）
- 2回目で詳細を理解する
- 3回目で最適化や改善点を考える

---

## 各ファイルの重要度マップ

### ★★★★★ 最重要（必ず読む）
- `src/omanta_3rd/jobs/monthly_run.py`
- `src/omanta_3rd/ingest/fins.py`
- `src/omanta_3rd/infra/db.py`
- `src/omanta_3rd/infra/jquants.py`

### ★★★★☆ 重要（理解を深めるために読む）
- `src/omanta_3rd/ingest/prices.py`
- `src/omanta_3rd/ingest/listed.py`
- `src/omanta_3rd/backtest/performance.py`
- `src/omanta_3rd/jobs/etl_update.py`

### ★★★☆☆ 参考（必要に応じて読む）
- `src/omanta_3rd/jobs/backtest.py`
- `src/omanta_3rd/jobs/init_db.py`
- `src/omanta_3rd/reporting/export.py`

### ★★☆☆☆ 参考用（実際の実装はmonthly_run.py内）
- `src/omanta_3rd/features/*.py`
- `src/omanta_3rd/strategy/*.py`

---

## 時間配分の目安

| フェーズ | 時間 | 内容 |
|---------|------|------|
| フェーズ1 | 30分 | ドキュメント・概要 |
| フェーズ2 | 30分 | データベース構造 |
| フェーズ3 | 1時間 | インフラ層 |
| フェーズ4 | 1時間 | データ取り込み |
| フェーズ7 | 3-4時間 | 月次実行ジョブ（核心） |
| フェーズ8 | 1時間 | バックテスト |
| フェーズ9 | 30分 | その他 |
| **合計** | **7-8時間** | **全体理解** |

---

## トラブルシューティング

### 理解が難しい場合
1. **SPECIFICATION.md**を再度読む（仕様を確認）
2. **sql/schema.sql**を確認（データ構造を確認）
3. **monthly_run.py**の`main`関数から読む（全体の流れを把握）

### 特定の機能を理解したい場合
- **データ取り込み**: `ingest/`配下のファイル
- **特徴量計算**: `monthly_run.py`の`build_features`関数
- **ポートフォリオ選定**: `monthly_run.py`の`select_portfolio`関数
- **バックテスト**: `backtest/performance.py`

---

**最終更新日**: 2025-01-XX
**バージョン**: 1.0

