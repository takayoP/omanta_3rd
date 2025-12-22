# 投資アルゴリズムシステム 仕様書

## 1. システム概要

### 1.1 目的
中長期の株式投資において、ROEの水準と成長性、利益成長の一貫性を重視したファンダメンタル主導の戦略を構築する。

### 1.2 基本方針
- **データソース**: J-Quants API
- **データベース**: SQLite（将来PostgreSQL移行を想定）
- **アプローチ**: ファンダメンタル分析を主軸とし、テクニカル指標は補助的に使用
- **設計思想**: 過学習を避け、解釈可能性を重視
- **予測値の扱い**: 将来予測値は参考情報として扱う

### 1.3 システム構成
```
omanta_3rd/
├── src/omanta_3rd/
│   ├── infra/          # インフラ層（DB接続、APIクライアント）
│   ├── ingest/         # データ取り込み（API → DB）
│   ├── features/       # 特徴量計算
│   ├── strategy/       # 投資戦略（スコアリング、選定）
│   ├── backtest/       # バックテスト
│   ├── jobs/           # ジョブ実行（月次実行、ETL更新）
│   └── config/         # 設定管理
├── data/               # データベースファイル
├── sql/                # スキーマ定義
└── tests/              # テストコード
```

---

## 2. データフロー

### 2.1 データ取得フロー
```
J-Quants API
    ↓
[ingest層] データ取得・正規化
    ↓
SQLite データベース
    ├── listed_info        (銘柄情報)
    ├── prices_daily       (価格データ)
    └── fins_statements    (財務データ)
```

### 2.2 特徴量計算フロー
```
データベース
    ↓
[features層] 特徴量計算
    ├── 財務指標計算 (ROE, PER, PBR等)
    ├── 成長率計算
    └── トレンド分析
    ↓
features_monthly テーブル
```

### 2.3 ポートフォリオ構築フロー
```
features_monthly
    ↓
[strategy層] スコアリング・選定
    ├── core_score計算
    ├── entry_score計算
    ├── フィルタリング
    └── ポートフォリオ選定
    ↓
portfolio_monthly テーブル
```

---

## 3. データベーススキーマ

### 3.1 listed_info（銘柄情報）
| カラム名 | 型 | 説明 |
|---------|-----|------|
| date | TEXT | 日付（YYYY-MM-DD） |
| code | TEXT | 銘柄コード（4桁） |
| company_name | TEXT | 会社名 |
| market_name | TEXT | 市場区分（プライム等） |
| sector17 | TEXT | 17業種分類 |
| sector33 | TEXT | 33業種分類 |
| **PRIMARY KEY** | (date, code) | |

### 3.2 prices_daily（日次価格データ）
| カラム名 | 型 | 説明 |
|---------|-----|------|
| date | TEXT | 日付（YYYY-MM-DD） |
| code | TEXT | 銘柄コード（4桁） |
| close | REAL | **調整前終値**（主要指標計算に使用） |
| adj_close | REAL | 調整済終値（参考用） |
| adj_volume | REAL | 調整済出来高 |
| turnover_value | REAL | 売買代金 |
| adjustment_factor | REAL | 調整係数（株式分割等、1:2分割なら0.5） |
| **PRIMARY KEY** | (date, code) | |

**重要**: PER/PBR計算では`close`（調整前終値）を使用。株式分割は株数側で補正。

### 3.3 fins_statements（財務データ）
| カラム名 | 型 | 説明 |
|---------|-----|------|
| disclosed_date | TEXT | 開示日（YYYY-MM-DD） |
| disclosed_time | TEXT | 開示時刻 |
| code | TEXT | 銘柄コード（4桁） |
| type_of_current_period | TEXT | 期間種別（FY/1Q/2Q/3Q） |
| current_period_end | TEXT | 期末日（YYYY-MM-DD） |
| **実績値** | | |
| operating_profit | REAL | 営業利益 |
| profit | REAL | 当期純利益 |
| equity | REAL | 純資産 |
| eps | REAL | EPS（参考用、再計算推奨） |
| bvps | REAL | BPS（参考用、再計算推奨） |
| **予想値** | | |
| forecast_operating_profit | REAL | 予想営業利益 |
| forecast_profit | REAL | 予想利益 |
| forecast_eps | REAL | 予想EPS（参考用） |
| next_year_forecast_* | REAL | 翌年度予想値 |
| **株数** | | |
| shares_outstanding | REAL | 発行済み株式数（自己株含む） |
| treasury_shares | REAL | 自己株式数 |
| **PRIMARY KEY** | (disclosed_date, code, type_of_current_period, current_period_end) | |

### 3.4 features_monthly（月次特徴量スナップショット）
| カラム名 | 型 | 説明 |
|---------|-----|------|
| as_of_date | TEXT | 評価日（YYYY-MM-DD） |
| code | TEXT | 銘柄コード |
| sector33 | TEXT | 33業種分類 |
| liquidity_60d | REAL | 売買代金60営業日平均 |
| market_cap | REAL | 時価総額 |
| roe | REAL | ROE（自己資本利益率） |
| roe_trend | REAL | ROEトレンド（現在ROE - 過去4期平均ROE） |
| per | REAL | 実績PER |
| pbr | REAL | 実績PBR |
| forward_per | REAL | 予想PER（Forward PER） |
| op_growth | REAL | 営業利益成長率（予想/実績 - 1） |
| profit_growth | REAL | 利益成長率（予想/実績 - 1） |
| record_high_forecast_flag | INTEGER | 予想営業利益が過去最高フラグ |
| op_trend | REAL | 営業利益トレンド（5年スロープ） |
| core_score | REAL | 総合スコア（0-1） |
| entry_score | REAL | エントリースコア（BB/RSIベース、0-1） |
| **PRIMARY KEY** | (as_of_date, code) | |

### 3.5 portfolio_monthly（月次ポートフォリオ）
| カラム名 | 型 | 説明 |
|---------|-----|------|
| rebalance_date | TEXT | リバランス日（YYYY-MM-DD） |
| code | TEXT | 銘柄コード |
| weight | REAL | ポートフォリオ内の重み（1/N） |
| core_score | REAL | 総合スコア |
| entry_score | REAL | エントリースコア |
| reason | TEXT | 採用理由（JSON形式） |
| **PRIMARY KEY** | (rebalance_date, code) | |

---

## 4. データ取り込み処理

### 4.1 APIデータの加工
APIから取得したデータは、以下の軽微な加工のみ実施：

1. **フィールド名変換**: PascalCase → snake_case
2. **コード正規化**: 5桁コード（例: `72030`）→ 4桁（`7203`）
3. **型変換**: 文字列数値 → float
4. **重複レコードマージ**: 財務データで同じ主キーのレコードをマージ（実績値優先）

**重要**: 計算や集計などの値の変更は行わない。APIの値をそのまま保存。

### 4.2 取り込み対象データ
- **listed_info**: 銘柄情報（日次更新）
- **prices_daily**: 価格データ（日次更新）
- **fins_statements**: 財務データ（開示日ベースで更新）

---

## 5. 財務指標計算ロジック

### 5.1 基本方針
1. **評価日時点の株価**と**その時点の株数ベースの1株指標**で計算
2. **株式分割・併合は株数側で補正**（adjustment_factorを使用）
3. **EPS/BPS/予想EPSは自前で再計算**（profit/equity/forecast_profitと補正後株数から）

### 5.2 PER/PBR/Forward PER計算フロー

#### ステップ1: 評価日の確定
```python
price_date = _snap_price_date(conn, asof)  # 営業日にスナップ
```

#### ステップ2: 価格データの取得
```python
# 未調整終値（close）を使用
px_today = prices_win[prices_win["date"] == price_date][["code", "close"]]
```

#### ステップ3: 最新FY実績データの取得
- `disclosed_date <= 評価日` かつ `type_of_current_period = 'FY'`
- 銘柄ごとに最新の`current_period_end`を取得
- 取得項目: `profit`, `equity`, `shares_outstanding`, `treasury_shares`

#### ステップ4: 最新予想データの取得
- FYデータを優先、次に四半期データ（3Q → 2Q → 1Q）
- 取得項目: `forecast_profit`（第一優先）、`forecast_eps`（フォールバック）

#### ステップ5: 分割・併合を株数に反映
```python
# FY期末のネット株数
net_shares_fy = shares_outstanding - treasury_shares

# FY期末→評価日までの分割倍率
split_mult = _split_multiplier_between(conn, code, fy_end, price_date)
# = ∏(1 / adjustment_factor)  for date in (fy_end, price_date]

# 評価日時点のネット株数（補正後）
net_shares_at_price = net_shares_fy * split_mult
```

#### ステップ6: 標準EPS/BPS/予想EPSの計算
```python
# 標準EPS（実績）
eps_std = profit / net_shares_at_price  # profit > 0 の場合のみ

# 標準BPS（実績）
bps_std = equity / net_shares_at_price  # equity > 0 の場合のみ

# 標準予想EPS（予想）
forecast_eps_std = forecast_profit / net_shares_at_price  # 第一優先
# フォールバック: forecast_eps（J-Quants）を使用
```

#### ステップ7: PER/PBR/Forward PERの計算
```python
# 実績PER（Trailing PER）
per = price / eps_std  # eps_std > 0 の場合のみ

# 実績PBR
pbr = price / bps_std  # bps_std > 0 の場合のみ

# 予想PER（Forward PER）
forward_per = price / forecast_eps_std  # forecast_eps_std > 0 の場合のみ
```

### 5.3 その他の財務指標

#### ROE（自己資本利益率）
```python
roe = profit / equity  # equity > 0 の場合のみ
```

#### ROEトレンド
```python
roe_trend = current_roe - average(past_4_periods_roe)
```

#### 成長率
```python
op_growth = forecast_operating_profit / operating_profit - 1.0
profit_growth = forecast_profit / profit - 1.0
```

#### 営業利益トレンド
```python
op_trend = slope(operating_profit, last_5_years)  # 線形回帰の傾き
```

#### 時価総額
```python
market_cap = price * net_shares_at_price
```

---

## 6. 投資戦略

### 6.1 戦略パラメータ（デフォルト値）

```python
@dataclass
class StrategyParams:
    # ポートフォリオサイズ
    target_min: int = 20      # 最小銘柄数
    target_max: int = 30      # 最大銘柄数
    pool_size: int = 80      # プールサイズ
    
    # ハードフィルタ
    roe_min: float = 0.10     # ROE最低10%
    liquidity_quantile_cut: float = 0.20  # 流動性下位20%を除外
    
    # セクター上限
    sector_cap: int = 4       # 33業種あたり最大4銘柄
    
    # スコアリング重み
    w_quality: float = 0.35      # 品質スコア（ROE）
    w_value: float = 0.25        # バリュースコア（PER/PBR）
    w_growth: float = 0.15        # 成長スコア（成長率・トレンド）
    w_record_high: float = 0.15   # 最高益フラグ
    w_size: float = 0.10          # サイズスコア（時価総額）
    
    # バリューミックス
    w_forward_per: float = 0.5    # Forward PERの重み
    w_pbr: float = 0.5             # PBRの重み
    
    # エントリースコア
    use_entry_score: bool = True   # BB/RSIベースのエントリースコアを使用
```

### 6.2 スコアリングロジック

#### core_score（総合スコア）
```python
core_score = (
    w_quality * quality_score +
    w_value * value_score +
    w_growth * growth_score +
    w_record_high * record_high_score +
    w_size * size_score
)
```

#### 各サブスコアの計算

**quality_score（品質スコア）**
```python
roe_score = percentile_rank(roe, ascending=True)  # ROEのパーセンタイル順位
quality_score = roe_score
```

**value_score（バリュースコア）**
```python
forward_per_pct = percentile_rank(forward_per, by_sector33, ascending=True)
pbr_pct = percentile_rank(pbr, by_sector33, ascending=True)
value_score = w_forward_per * (1 - forward_per_pct) + w_pbr * (1 - pbr_pct)
```

**growth_score（成長スコア）**
```python
op_growth_score = percentile_rank(op_growth, ascending=True)
profit_growth_score = percentile_rank(profit_growth, ascending=True)
op_trend_score = percentile_rank(op_trend, ascending=True)
growth_score = 0.4 * op_growth_score + 0.4 * profit_growth_score + 0.2 * op_trend_score
```

**record_high_score（最高益スコア）**
```python
record_high_score = record_high_forecast_flag  # 0 or 1
```

**size_score（サイズスコア）**
```python
log_mcap = log(market_cap)  # market_cap > 0 の場合のみ
size_score = percentile_rank(log_mcap, ascending=True)  # 小さいほど高スコア
```

**entry_score（エントリースコア）**
```python
# BB（ボリンジャーバンド）とRSIから計算
# 複数期間（20日、60日、90日）のスコアの最大値
entry_score = max(
    bb_zscore_score(close, n=20),
    rsi_score(close, n=20),
    ...
)
```

### 6.3 ポートフォリオ選定フロー

1. **ユニバース**: プライム市場の銘柄を対象
2. **流動性フィルタ**: 売買代金60日平均の下位20%を除外
3. **ROEフィルタ**: ROE >= 10% の銘柄のみ
4. **プール選定**: core_score上位80銘柄をプール
5. **セクター上限**: 33業種あたり最大4銘柄まで
6. **最終選定**: 20-30銘柄を選定（entry_scoreも考慮）
7. **等加重**: 選定銘柄は等加重（weight = 1/N）

---

## 7. 月次実行ジョブ

### 7.1 monthly_run.py
月次で実行されるメインジョブ：

1. **特徴量構築**: `build_features(conn, asof)`
   - 評価日を確定
   - 価格データ、財務データを取得
   - 財務指標を計算
   - スコアリング
   - `features_monthly`テーブルに保存

2. **ポートフォリオ選定**: `select_portfolio(feat)`
   - フィルタリング
   - スコアリング
   - セクター上限適用
   - `portfolio_monthly`テーブルに保存

**実行方法**:
```bash
python -m omanta_3rd.jobs.monthly_run --asof 2025-12-12
```

### 7.2 etl_update.py
データ更新ジョブ：

- `listed_info`: 銘柄情報を更新
- `prices_daily`: 価格データを更新
- `fins_statements`: 財務データを更新

---

## 8. バックテスト

### 8.1 パフォーマンス計算
```python
calculate_portfolio_performance(rebalance_date, as_of_date)
```

**計算内容**:
1. リバランス日のポートフォリオを取得
2. リバランス日時点の価格を取得
3. 評価日時点の価格を取得
4. 各銘柄のリターンを計算
5. ポートフォリオ全体の加重平均リターンを計算

**出力項目**:
- `total_return_pct`: ポートフォリオ全体の総リターン（%）
- `num_stocks`: 銘柄数
- `num_stocks_with_price`: 価格データがある銘柄数
- `avg_return_pct`: 平均リターン（%）
- `min_return_pct`: 最小リターン（%）
- `max_return_pct`: 最大リターン（%）

### 8.2 バックテストテーブル
- `backtest_performance`: ポートフォリオ全体のパフォーマンス
- `backtest_stock_performance`: 銘柄別パフォーマンス

---

## 9. 重要な設計判断

### 9.1 価格データの扱い
- **使用**: `close`（調整前終値）
- **理由**: 評価日時点の市場価格に一致し、バックテストでも将来の分割が混入しにくい
- **分割対応**: 株数側で補正（`adjustment_factor`を使用）

### 9.2 EPS/BPSの計算
- **方針**: J-Quantsの`eps`/`bvps`は参考用
- **実装**: `profit`/`equity`と補正後株数から再計算
- **理由**: 株数基準の一貫性を保つため

### 9.3 予想データの扱い
- **優先順位**: FY予想 > 四半期予想（3Q > 2Q > 1Q）
- **補完**: FYデータに予想値がない場合のみ四半期データを使用
- **注意**: 予想値は参考情報として扱う

### 9.4 欠損値の扱い
- **スコアリング**: 欠損値はデフォルト値（0.5または0.0）を使用
- **フィルタリング**: 主要指標が欠損している銘柄は除外
- **ログ出力**: 欠損率と影響度を可視化

---

## 10. 技術スタック

- **言語**: Python 3.x
- **データベース**: SQLite（将来PostgreSQL移行を想定）
- **主要ライブラリ**:
  - `pandas`: データ処理
  - `numpy`: 数値計算
  - `sqlite3`: データベース接続
  - `requests`: HTTPリクエスト（J-Quants API）

---

## 11. 実行コマンド例

### データ更新
```bash
# 全データを更新
python update_all_data.py

# 特定のデータのみ更新
python update_all_data.py --target prices
python update_all_data.py --target fins
python update_all_data.py --target listed
```

### 月次実行
```bash
# 指定日の月次実行
python -m omanta_3rd.jobs.monthly_run --asof 2025-12-12
```

### バックテスト
```bash
# 特定のリバランス日のパフォーマンスを計算
python -m omanta_3rd.jobs.backtest --rebalance-date 2025-01-01 --as-of-date 2025-12-31
```

---

## 12. 注意事項

1. **データ品質**: APIから取得したデータは基本的に加工せず保存。計算時点で整合性チェックを実施。

2. **株式分割・併合**: 分割は株数側で補正。増資や自己株取得は`fins_statements`の更新粒度次第で取り切れない場合がある。

3. **予想値の信頼性**: 会社予想は参考情報として扱い、機械的最適化は行わない。

4. **過学習の回避**: 解釈可能性を重視し、シンプルなスコアリングロジックを採用。

5. **欠損値の影響**: 欠損値が多い銘柄はスコアが不完全になる可能性がある。ログで可視化している。

---

## 13. 今後の拡張予定

- PostgreSQLへの移行
- より詳細なバックテスト機能
- レポート生成機能の強化
- リアルタイム監視機能

---

**最終更新日**: 2025-01-XX
**バージョン**: 1.0

