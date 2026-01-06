# 投資アルゴリズムシステム 全体ロジック仕様書

## 概要

本資料は、投資アルゴリズムシステムの全体ロジックを説明するものです。ChatGPTによる評価・分析のために、システムの動作原理、データフロー、計算ロジックを詳細に記載しています。

---

## 1. システムアーキテクチャ

### 1.1 システム構成

```
omanta_3rd/
├── src/omanta_3rd/
│   ├── infra/          # インフラ層（DB接続、APIクライアント）
│   ├── ingest/         # データ取り込み（J-Quants API → SQLite）
│   ├── features/       # 特徴量計算（財務指標、テクニカル指標）
│   ├── strategy/       # 投資戦略（スコアリング、ポートフォリオ選定）
│   ├── backtest/       # バックテスト（パフォーマンス計算）
│   ├── jobs/           # ジョブ実行（月次実行、最適化）
│   └── config/         # 設定管理（戦略パラメータ）
├── data/               # データベースファイル（SQLite）
├── sql/                # スキーマ定義
└── tests/              # テストコード
```

### 1.2 データフロー

```
【データ取得】
J-Quants API
    ↓
[ingest層] データ取得・正規化
    ↓
SQLite データベース
    ├── listed_info        (銘柄情報)
    ├── prices_daily       (価格データ)
    ├── fins_statements    (財務データ)
    └── index_daily        (指数データ)

【特徴量計算】
データベース
    ↓
[features層] 特徴量計算
    ├── 財務指標計算 (ROE, PER, PBR等)
    ├── 成長率計算
    ├── トレンド分析
    └── テクニカル指標 (RSI, ボリンジャーバンド)
    ↓
features_monthly テーブル

【ポートフォリオ構築】
features_monthly
    ↓
[strategy層] スコアリング・選定
    ├── core_score計算
    ├── entry_score計算
    ├── フィルタリング
    └── ポートフォリオ選定
    ↓
portfolio_monthly テーブル

【バックテスト】
portfolio_monthly + prices_daily
    ↓
[backtest層] パフォーマンス計算
    ├── リターン計算
    ├── リスク指標計算
    └── TOPIX比較
    ↓
backtest_performance テーブル
```

---

## 2. データベーススキーマ

### 2.1 listed_info（銘柄情報）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| date | TEXT | 日付（YYYY-MM-DD） |
| code | TEXT | 銘柄コード（4桁） |
| company_name | TEXT | 会社名 |
| market_name | TEXT | 市場区分（プライム、スタンダード、グロース、旧：東証一部等） |
| sector17 | TEXT | 17業種分類 |
| sector33 | TEXT | 33業種分類 |
| **PRIMARY KEY** | (date, code) | |

### 2.2 prices_daily（日次価格データ）

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

### 2.3 fins_statements（財務データ）

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

### 2.4 features_monthly（月次特徴量スナップショット）

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

### 2.5 portfolio_monthly（月次ポートフォリオ）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| rebalance_date | TEXT | リバランス日（YYYY-MM-DD） |
| code | TEXT | 銘柄コード |
| weight | REAL | ポートフォリオ内の重み（1/N、等加重） |
| core_score | REAL | 総合スコア |
| entry_score | REAL | エントリースコア |
| reason | TEXT | 採用理由（JSON形式） |
| **PRIMARY KEY** | (rebalance_date, code) | |

---

## 3. 特徴量計算ロジック

### 3.1 財務指標計算の基本方針

1. **評価日時点の株価**と**その時点の株数ベースの1株指標**で計算
2. **株式分割・併合は株数側で補正**（`adjustment_factor`を使用）
3. **EPS/BPS/予想EPSは自前で再計算**（`profit`/`equity`/`forecast_profit`と補正後株数から）

### 3.2 PER/PBR/Forward PER計算フロー

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

### 3.3 その他の財務指標

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

#### 流動性（60日平均売買代金）
```python
liquidity_60d = average(turnover_value, last_60_trading_days)
```

### 3.4 テクニカル指標

#### RSI（Relative Strength Index）
```python
def _rsi_from_series(close: pd.Series, n: int) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    
    avg_gain = gain.rolling(n).mean().iloc[-1]
    avg_loss = loss.rolling(n).mean().iloc[-1]
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi)
```

#### ボリンジャーバンド Z-score
```python
def _bb_zscore(close: pd.Series, n: int) -> float:
    window = close.iloc[-n:]
    mu = window.mean()
    sd = window.std(ddof=0)
    
    if sd == 0:
        return np.nan
    
    z = (window.iloc[-1] - mu) / sd
    return float(z)
```

---

## 4. スコアリングロジック

### 4.1 Core Score（総合スコア）

Core Scoreは、中長期投資の基本評価スコアです。ファンダメンタル分析に基づき、銘柄の投資価値を総合的に評価します。

#### 計算式

```python
core_score = (
    w_quality × quality_score +      # 品質スコア（ROE）
    w_value × value_score +          # バリュースコア（PER/PBR）
    w_growth × growth_score +        # 成長スコア
    w_record_high × record_high_score +  # 最高益スコア
    w_size × size_score              # サイズスコア（時価総額）
)
```

#### 最適化後の重み（n=70最適化結果）

| パラメータ | 値 | 割合 | 解釈 |
|-----------|-----|------|------|
| **w_value** | **0.3908** | **39.08%** | **最重要** - バリュー投資を重視 |
| w_size | 0.2448 | 24.48% | 大型株を重視 |
| w_quality | 0.1519 | 15.19% | 品質（ROE）を重視 |
| w_growth | 0.1120 | 11.20% | 成長性は控えめに評価 |
| w_record_high | 0.0364 | 3.64% | 最高値更新予想は補助的 |

#### 各サブスコアの計算

**1. Quality Score（品質スコア）**

```python
roe_score = percentile_rank(roe, ascending=True)  # ROEのパーセンタイル順位
quality_score = roe_score
```

- 評価指標: ROE（自己資本利益率）
- 計算方法: 全銘柄中のROEのパーセンタイルランク（高いほど高スコア）
- 意味: ROEが高いほど高評価

**2. Value Score（バリュースコア）**

```python
forward_per_pct = percentile_rank(forward_per, by_sector33, ascending=True)
pbr_pct = percentile_rank(pbr, by_sector33, ascending=True)
value_score = w_forward_per × (1 - forward_per_pct) + w_pbr × (1 - pbr_pct)
```

- 評価指標: フォワードPER、PBR
- 計算方法: **業種内**でのパーセンタイルランク（低いほど高スコア）
- 意味: 業種内で割安なほど高評価
- 最適化後の重み: `w_forward_per = 0.4977` (49.77%), `w_pbr = 0.5023` (50.23%)

**3. Growth Score（成長スコア）**

```python
op_growth_score = percentile_rank(op_growth, ascending=True)
profit_growth_score = percentile_rank(profit_growth, ascending=True)
op_trend_score = percentile_rank(op_trend, ascending=True)
growth_score = 0.4 × op_growth_score + 0.4 × profit_growth_score + 0.2 × op_trend_score
```

- 評価指標: 営業利益成長率、利益成長率、営業利益トレンド
- 計算方法: 全銘柄中のパーセンタイルランク（高いほど高スコア）
- 意味: 成長性が高いほど高評価

**4. Record High Score（最高益スコア）**

```python
record_high_score = record_high_forecast_flag  # 0 or 1
```

- 評価指標: 予想営業利益が過去最高かどうか
- 計算方法: フラグ（0 or 1）
- 意味: 最高益予想がある銘柄を高評価

**5. Size Score（サイズスコア）**

```python
log_mcap = log(market_cap)  # market_cap > 0 の場合のみ
size_score = percentile_rank(log_mcap, ascending=True)  # 小さいほど高スコア
```

- 評価指標: 時価総額（対数）
- 計算方法: 全銘柄中の対数時価総額のパーセンタイルランク（**小さいほど高スコア**）
- 意味: **時価総額が小さいほど高評価**（注意: これは最適化結果と矛盾する可能性があるため、実装を確認する必要がある）

**注意**: 実装では`ascending=True`となっているが、これは「小さいほど高スコア」を意味します。しかし、最適化結果では`w_size = 0.2448`（24.48%）と大型株を重視しているため、実装と意図が一致していない可能性があります。実際の実装では、`ascending=False`（大きいほど高スコア）が正しい可能性があります。

### 4.2 Entry Score（エントリースコア）

Entry Scoreは、エントリータイミングを評価するスコアです。テクニカル指標（RSI、ボリンジャーバンド）に基づき、モメンタムを評価します。

#### 計算式

各期間（20日、60日、90日）で以下を計算し、**最大値を採用**：

```python
# ボリンジャーバンドスコア
bb_score = clip((BB_Z-score - bb_z_base) / (bb_z_max - bb_z_base), 0, 1)

# RSIスコア
rsi_score = clip((RSI - rsi_base) / (rsi_max - rsi_base), 0, 1)

# 期間ごとのエントリースコア
entry_score_period = (bb_weight × bb_score + rsi_weight × rsi_score) / (bb_weight + rsi_weight)

# 最終エントリースコア（最大値）
entry_score = max(entry_score_20d, entry_score_60d, entry_score_90d)
```

#### 最適化後のパラメータ（n=70最適化結果）

| パラメータ | 値 | 解釈 |
|-----------|-----|------|
| **bb_weight** | **0.5527 (55.27%)** | **ボリンジャーバンドを重視** |
| rsi_weight | 0.4473 (44.73%) | RSIは補助的 |
| rsi_base | 51.18 | RSIが51.18以上でスコア開始 |
| rsi_max | 73.58 | RSIが73.58で最大スコア |
| bb_z_base | -0.57 | BB Z-scoreが-0.57以上でスコア開始 |
| bb_z_max | 2.16 | BB Z-scoreが2.16で最大スコア |

#### 解釈

**順張り戦略（モメンタム）**:
- RSIが51.18以上（中立的な強気相場）でスコアが始まる
- RSIが73.58（強気相場）で最大スコア
- BB Z-scoreが-0.57以上（下位バンドより上）でスコアが始まる
- BB Z-scoreが2.16（上位バンド付近）で最大スコア

**選ばれる銘柄の特徴**:
- 価格が上昇トレンドにある（BB Z-score > -0.57、できれば > 0）
- モメンタムがある（RSI > 51.18、できれば > 60）
- **「割安で、上昇トレンドにある大型株」**を選ぶ

---

## 5. ポートフォリオ選定プロセス

### 5.1 選定フロー

```
1. ユニバース: プライム市場（旧：東証一部）の銘柄を対象
   - 市場区分マッピング: 「プライム」「Prime」「東証一部」を同一視

2. 流動性フィルタ: 売買代金60日平均の下位15.09%を除外
   - liquidity_quantile_cut = 0.1509（最適化結果）

3. ROEフィルタ: ROE >= 6.21% の銘柄のみ
   - roe_min = 0.0621（最適化結果）

4. プール選定: core_score上位80銘柄をプール
   - pool_size = 80

5. Entry Scoreで再ソート
   - Entry Score → Core Score の順でソート
   - 上昇トレンドにある銘柄を優先

6. セクター上限: 33業種あたり最大4銘柄まで
   - sector_cap = 4

7. 最終選定: 12銘柄を選定
   - target_min = 12, target_max = 12（最適化結果）

8. 等加重: 選定銘柄は等加重（weight = 1/12）
```

### 5.2 選ばれる銘柄の特徴

**基本要件**:
- ✅ ROE 6.21%以上
- ✅ 流動性が中位以上（下位15.09%を除外）
- ✅ 業種内で割安（forward_per、pbrが低い）
- ✅ 時価総額が大きい（大型株）

**追加要件（Entry Score）**:
- ✅ 価格が上昇トレンド（BB Z-score > -0.57、できれば > 0）
- ✅ モメンタムがある（RSI > 51.18、できれば > 60）

**選定される銘柄のイメージ**:
- 大型のバリュー株で、上昇トレンドにある銘柄
- 例：業種内で割安な大型株で、最近価格が上昇している銘柄

---

## 6. バックテストロジック

### 6.1 パフォーマンス計算フロー

```python
def calculate_portfolio_performance(rebalance_date, as_of_date):
    """
    指定されたrebalance_dateのポートフォリオのパフォーマンスを計算
    """
    # 1. リバランス日のポートフォリオを取得
    portfolio = get_portfolio(rebalance_date)
    
    # 2. リバランス日の翌営業日の価格を取得（購入価格）
    purchase_prices = get_prices(rebalance_date_next_day, portfolio.codes)
    
    # 3. 評価日の価格を取得（売却価格）
    evaluation_prices = get_prices(as_of_date, portfolio.codes)
    
    # 4. 各銘柄のリターンを計算（株式分割を考慮）
    returns = []
    for code in portfolio.codes:
        purchase_price = purchase_prices[code]
        evaluation_price = evaluation_prices[code]
        
        # 株式分割を考慮した株数倍率
        split_mult = _split_multiplier_between(
            conn, code, 
            rebalance_date_next_day, 
            as_of_date
        )
        
        # リターン計算（分割を考慮）
        return_pct = (evaluation_price / purchase_price - 1.0) * 100.0
        returns.append(return_pct)
    
    # 5. ポートフォリオ全体の加重平均リターンを計算
    portfolio_return = sum(weight * return_pct 
                           for weight, return_pct 
                           in zip(portfolio.weights, returns))
    
    # 6. TOPIXとの比較
    topix_return = calculate_topix_return(rebalance_date, as_of_date)
    excess_return = portfolio_return - topix_return
    
    return {
        "total_return_pct": portfolio_return,
        "excess_return_pct": excess_return,
        "num_stocks": len(portfolio.codes),
        "returns": returns,  # 個別銘柄のリターン
    }
```

### 6.2 株式分割の処理

株式分割は、**株数側で補正**します：

```python
def _split_multiplier_between(conn, code, start_date, end_date):
    """
    指定期間内の分割・併合による株数倍率を計算
    
    (start_date, end_date] の期間に発生したAdjustmentFactorから、
    株数倍率 = ∏(1 / adjustment_factor) を計算します。
    
    例: 1:3分割（adjustment_factor = 0.333333）の場合、
    株数倍率 = 1 / 0.333333 ≈ 3.0
    """
    # start_dateより後、end_date以下のAdjustmentFactorを取得
    df = pd.read_sql_query(
        """
        SELECT date, adjustment_factor
        FROM prices_daily
        WHERE code = ?
          AND date > ?
          AND date <= ?
          AND adjustment_factor IS NOT NULL
          AND adjustment_factor != 1.0
        ORDER BY date ASC
        """,
        conn,
        params=(code, start_date, end_date),
    )
    
    # 株数倍率を計算: split_mult = ∏(1 / adjustment_factor)
    mult = 1.0
    for _, row in df.iterrows():
        adj_factor = row["adjustment_factor"]
        mult *= (1.0 / float(adj_factor))
    
    return mult
```

**重要**: 価格は調整前終値（`close`）を使用し、分割は株数側で補正します。これにより、バックテスト時の価格データが将来の分割情報に汚染されません。

### 6.3 TOPIXとの比較

```python
def calculate_topix_return(start_date, end_date):
    """
    TOPIXのリターンを計算
    """
    start_price = get_topix_price(start_date)
    end_price = get_topix_price(end_date)
    
    return (end_price / start_price - 1.0) * 100.0
```

---

## 7. 最適化ロジック

### 7.1 最適化フレームワーク

- **フレームワーク**: Optuna（Bayesian Optimization）
- **並列計算**: マルチプロセス（CPU数に応じて自動調整）
- **データ分割**: 時系列データのため、train/test分割は実施せず、全期間で最適化

### 7.2 目的関数

```python
objective_value = (
    mean_excess_return * 0.7      # 平均超過リターン（TOPIX比）: 70%
    + win_rate * 10.0 * 0.2       # 勝率（10倍してスケール調整）: 20%
    + sharpe_ratio * 0.1          # シャープレシオ: 10%
)
```

**評価指標**:
- **平均超過リターン**: TOPIXに対する超過リターン（%）
- **勝率**: ポートフォリオ内の銘柄で正のリターンを獲得した割合
- **シャープレシオ**: リスク調整後リターン

### 7.3 最適化対象パラメータ

**最適化対象パラメータ数**: 13個

1. **Core Score重み**: 5個
   - `w_quality`, `w_value`, `w_growth`, `w_record_high`, `w_size`
   - 制約: 合計 = 1.0（正規化）

2. **Value Score重み**: 1個
   - `w_forward_per`（`w_pbr`は自動計算: `1.0 - w_forward_per`）

3. **Entry Scoreパラメータ**: 5個
   - `rsi_base`, `rsi_max`, `bb_z_base`, `bb_z_max`, `bb_weight`
   - 制約: `rsi_max > rsi_base`, `bb_z_max > bb_z_base`, `bb_weight + rsi_weight = 1.0`

4. **フィルタ条件**: 2個
   - `roe_min`, `liquidity_quantile_cut`

### 7.4 最適化の進化

**第1回（n=50）から第2回（n=70）への改善**:
- 試行回数を40%増加（50 → 70）
- パラメータ探索範囲を第1回の最適値周辺に絞り込み
- 目的関数値が70%向上（4.8551 → 8.2627）

---

## 8. 重要な設計判断

### 8.1 価格データの扱い

- **使用**: `close`（調整前終値）
- **理由**: 評価日時点の市場価格に一致し、バックテストでも将来の分割が混入しにくい
- **分割対応**: 株数側で補正（`adjustment_factor`を使用）

### 8.2 EPS/BPSの計算

- **方針**: J-Quantsの`eps`/`bvps`は参考用
- **実装**: `profit`/`equity`と補正後株数から再計算
- **理由**: 株数基準の一貫性を保つため

### 8.3 予想データの扱い

- **優先順位**: FY予想 > 四半期予想（3Q > 2Q > 1Q）
- **補完**: FYデータに予想値がない場合のみ四半期データを使用
- **注意**: 予想値は参考情報として扱う

### 8.4 欠損値の扱い

- **スコアリング**: 欠損値はデフォルト値（0.5または0.0）を使用
- **フィルタリング**: 主要指標が欠損している銘柄は除外
- **ログ出力**: 欠損率と影響度を可視化

### 8.5 市場区分の扱い

- **旧区分の対応**: 「東証一部」を「プライム」として扱う
- **市場区分マッピング**: 旧区分を新区分にマッピングして処理

---

## 9. 月次実行ジョブ

### 9.1 monthly_run.py

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

### 9.2 最適化ジョブ

**実行方法**:
```bash
python -m omanta_3rd.jobs.optimize --start 2021-01-02 --end 2025-12-26 --n-trials 70
```

---

## 10. 戦略の特徴

### 10.1 戦略のタイプ

**「バリュー×モメンタム」戦略**:
- バリュー投資（39.08%）を基盤に
- モメンタム（Entry Score）でタイミングを最適化
- 大型株（24.48%）で安定性を確保

### 10.2 最適化結果の意味

**バックテスト結果**（n=70最適化パラメータ適用後）:
- 平均リターン（ポートフォリオ平均）: 58.21%
- 年率リターン: 9.96%
- 平均超過リターン（個別銘柄ベース）: 6.82%
- 勝率（ポートフォリオ平均）: 86.02%
- シャープレシオ（ポートフォリオ平均）: 0.9622
- ソルティノレシオ（ポートフォリオ平均）: 164.9488

**この戦略が有効な理由**:
1. **バリュー投資**: 割安な銘柄を選ぶことで、下振れリスクを抑制
2. **モメンタム**: 上昇トレンドにある銘柄を選ぶことで、タイミングを最適化
3. **大型株**: 流動性と安定性を確保
4. **品質**: ROEが高い銘柄を選ぶことで、収益性を確保

---

## 11. 注意事項

### 11.1 過学習のリスク

- 最適化は2021-2025年のデータに基づいている
- 将来の市場環境が変わると、パフォーマンスが低下する可能性がある
- 時系列データのため、train/test分割を実施していない

### 11.2 市場環境への依存

- この戦略は「バリュー×モメンタム」が有効な市場環境で機能する
- 市場環境が変わると、パラメータの再最適化が必要になる可能性がある

### 11.3 継続的なモニタリング

- 定期的にパフォーマンスを確認し、必要に応じてパラメータを調整
- 市場環境の変化に応じて、戦略を見直す

---

## 12. まとめ

本システムは、以下の特徴を持つ投資アルゴリズムです：

1. **ファンダメンタル分析を主軸**: Core Scoreでバリュー、品質、成長性を評価
2. **テクニカル分析でタイミング最適化**: Entry Scoreでモメンタムを評価
3. **業種相対評価**: Value Scoreは業種内での相対評価
4. **大型株重視**: 流動性と安定性を確保
5. **等加重ポートフォリオ**: シンプルで再現性が高い

**最適化結果**:
- バリュー投資（39.08%）を最重要視
- 大型株（24.48%）を重視
- モメンタム（Entry Score）でタイミング最適化
- 12銘柄の等加重ポートフォリオ

**懸念事項**:
- 過学習のリスク（2021-2025年のデータに特化している可能性）
- 異常に良好なバックテスト結果（勝率86%、ソルティノレシオ165など）
- 将来の市場環境での有効性が不明

---

**最終更新日**: 2025-12-29  
**バージョン**: 1.0















