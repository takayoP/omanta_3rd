# 投資アルゴリズム プロジェクト構成案

## フォルダ構成

```
omanta_3rd/
├── config/                    # 設定ファイル
│   ├── __init__.py
│   ├── settings.py           # アプリケーション設定（DBパス、API設定など）
│   └── strategy_config.py    # 戦略パラメータ（ROE閾値、重み付けなど）
│
├── data/                      # データベース関連（既存）
│   ├── __init__.py
│   ├── schema.sql            # データベーススキーマ（既存）
│   ├── db_utils.py           # DB接続・ユーティリティ（既存）
│   ├── init_db.py            # DB初期化（既存）
│   └── Sample/               # サンプルデータ（既存）
│
├── api/                       # J-Quants API層
│   ├── __init__.py
│   ├── client.py             # APIクライアント（認証、リクエスト管理）
│   ├── endpoints.py          # エンドポイント定義
│   └── data_fetchers.py      # データ取得モジュール（価格、財務、銘柄情報など）
│
├── models/                    # データモデル
│   ├── __init__.py
│   ├── stock.py              # 銘柄情報モデル
│   ├── price.py              # 価格データモデル
│   ├── financial.py          # 財務データモデル
│   └── portfolio.py          # ポートフォリオモデル
│
├── features/                  # 特徴量エンジニアリング
│   ├── __init__.py
│   ├── calculators.py        # 財務指標計算（ROE、PER、PBR、成長率など）
│   ├── aggregators.py        # 集計処理（トレンド、平均など）
│   └── validators.py         # データ品質チェック
│
├── strategy/                  # 投資戦略層
│   ├── __init__.py
│   ├── scoring.py            # スコアリングロジック（core_score, entry_score）
│   ├── filters.py            # フィルタリング（流動性、時価総額など）
│   ├── portfolio_builder.py  # ポートフォリオ構築（リバランス、重み付け）
│   └── rules.py              # 投資ルール定義
│
├── backtest/                  # バックテスト層
│   ├── __init__.py
│   ├── engine.py             # バックテストエンジン
│   ├── metrics.py            # パフォーマンス指標計算
│   └── report.py             # レポート生成
│
├── pipeline/                  # データパイプライン
│   ├── __init__.py
│   ├── ingest.py             # データ取り込み（API → DB）
│   ├── transform.py          # データ変換・特徴量生成
│   └── scheduler.py          # 定期実行スケジューラ
│
├── utils/                     # ユーティリティ
│   ├── __init__.py
│   ├── logging_config.py     # ロギング設定
│   ├── date_utils.py         # 日付処理ユーティリティ
│   └── validators.py         # 共通バリデーション
│
├── scripts/                   # 実行スクリプト
│   ├── fetch_data.py         # データ取得スクリプト
│   ├── calculate_features.py # 特徴量計算スクリプト
│   ├── run_strategy.py       # 戦略実行スクリプト
│   ├── backtest.py           # バックテスト実行
│   └── rebalance.py          # リバランス実行
│
├── tests/                     # テスト
│   ├── __init__.py
│   ├── test_api/
│   ├── test_features/
│   ├── test_strategy/
│   └── test_backtest/
│
├── notebooks/                 # Jupyter Notebook（分析・検証用）
│   └── analysis/
│
├── requirements.txt           # Python依存関係
├── README.md                  # プロジェクト説明（既存）
└── ARCHITECTURE.md            # このファイル
```

## 責務分離の原則

### 1. **API層 (`api/`)**
**責務**: J-Quants APIとの通信のみ
- 認証管理
- HTTPリクエスト/レスポンス処理
- エラーハンドリング（API側）
- レート制限管理

**依存関係**: `config/`（API設定）

---

### 2. **データ層 (`data/`)**
**責務**: データベース操作のみ
- スキーマ定義
- 接続管理
- CRUD操作
- トランザクション管理

**依存関係**: なし（他の層から依存される）

---

### 3. **モデル層 (`models/`)**
**責務**: データ構造の定義
- Pydantic/Dataclassモデル
- 型安全性の確保
- バリデーション

**依存関係**: なし

---

### 4. **特徴量層 (`features/`)**
**責務**: 財務指標・特徴量の計算
- ROE、PER、PBR、成長率などの計算
- トレンド分析
- データ品質チェック

**依存関係**: `models/`, `data/`

---

### 5. **戦略層 (`strategy/`)**
**責務**: 投資ロジックの実装
- スコアリング（core_score, entry_score）
- フィルタリング（流動性、時価総額など）
- ポートフォリオ構築・リバランス

**依存関係**: `features/`, `models/`, `config/`

---

### 6. **バックテスト層 (`backtest/`)**
**責務**: 戦略の検証
- 時系列シミュレーション
- パフォーマンス指標計算
- レポート生成

**依存関係**: `strategy/`, `data/`, `models/`

---

### 7. **パイプライン層 (`pipeline/`)**
**責務**: データフローのオーケストレーション
- API → DB の取り込み
- 特徴量生成の実行
- 定期実行のスケジューリング

**依存関係**: `api/`, `data/`, `features/`, `strategy/`

---

### 8. **ユーティリティ層 (`utils/`)**
**責務**: 共通機能
- ロギング
- 日付処理
- バリデーション

**依存関係**: なし（他の層から依存される）

---

## 依存関係の方向性

```
scripts/
  └─> pipeline/ ──> strategy/ ──> features/ ──> models/
                    └─> backtest/              └─> data/
  └─> api/ ──────────────────────────────────> config/
  └─> utils/ (どこからでも利用可能)
```

**原則**: 
- 上位層は下位層に依存可能
- 下位層は上位層に依存しない
- 横方向の依存は最小化

---

## 実装のベストプラクティス

### 1. **設定管理**
- 環境変数と設定ファイルの分離
- 開発/本番環境の切り替え
- 機密情報（APIキー）の安全な管理

### 2. **エラーハンドリング**
- 各層で適切な例外を定義
- ロギングによる追跡可能性
- リトライロジック（API層）

### 3. **テスト容易性**
- 依存性注入の活用
- モック可能なインターフェース
- 単体テストと統合テストの分離

### 4. **データ整合性**
- トランザクション管理
- データ品質チェック
- バリデーションの階層化

### 5. **パフォーマンス**
- データベースインデックスの活用
- バッチ処理の最適化
- キャッシュ戦略

---

## 次のステップ

1. この構成に基づいてフォルダ構造を作成
2. 各層のインターフェースを定義
3. 設定ファイルのテンプレート作成
4. 基本的なデータフロー（API → DB → 特徴量）の実装
5. 単体テストの作成


