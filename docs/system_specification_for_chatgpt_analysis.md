# システム仕様書（ChatGPT分析用）

## 概要

本システムは、日本株の長期保有型投資戦略のパラメータ最適化とバックテストを行うシステムです。Optunaを使用したハイパーパラメータ最適化により、最適なポートフォリオ選定パラメータを探索します。

**作成日**: 2026年1月12日  
**対象**: 長期保有型アルゴリズム（24Mホライズン）

---

## 1. システムアーキテクチャ

### 1.1 主要コンポーネント

1. **特徴量計算** (`build_features`)
   - 財務データ、価格データから特徴量を計算
   - `core_score`と`entry_score`を計算

2. **ポートフォリオ選択** (`_select_portfolio_with_params`)
   - スコアに基づいて銘柄を選定
   - セクターキャップを適用
   - **重みは等ウェイト**（選定ロジックはスコア比例）

3. **最適化** (`objective_longterm`)
   - Optunaを使用したハイパーパラメータ最適化
   - train期間でのパフォーマンスを最大化

4. **パフォーマンス評価** (`calculate_longterm_performance`)
   - 長期保有期間（24M）でのパフォーマンスを計算
   - TOPIXに対する超過リターンを計算

---

## 2. スコア計算ロジック（重点）

### 2.1 Core Score（基本評価スコア）

`core_score`は、中長期投資の基本評価スコアです。ファンダメンタル分析に基づき、銘柄の投資価値を総合的に評価します。

#### 計算式

```python
core_score = 
    w_quality × quality_score +      # 品質（ROE）
    w_value × value_score +          # バリュエーション（PER/PBR）
    w_growth × growth_score +        # 成長性
    w_record_high × record_high_score +  # 最高益フラグ
    w_size × size_score              # サイズ（時価総額）
```

#### 各要素の詳細

##### 1. Quality Score（品質スコア）

```python
quality_score = roe_score  # ROEのパーセンタイルランク
```

- **評価指標**: ROE（自己資本利益率）
- **計算方法**: 全銘柄中のROEのパーセンタイルランク（高いほど高スコア）
- **欠損値処理**: `fillna(0.0)`（ROEが欠損の場合は0.0）
- **意味**: ROEが高いほど高評価

##### 2. Value Score（バリュエーションスコア）

```python
forward_per_pct = groupby("sector33")["forward_per"].transform(
    lambda s: _pct_rank(s, ascending=True)  # 業種内でのパーセンタイルランク
)
pbr_pct = groupby("sector33")["pbr"].transform(
    lambda s: _pct_rank(s, ascending=True)  # 業種内でのパーセンタイルランク
)

value_score = 
    w_forward_per × (1.0 - forward_per_pct) +  # フォワードPER（低いほど高スコア）
    w_pbr × (1.0 - pbr_pct)                     # PBR（低いほど高スコア）
```

- **評価指標**: フォワードPER、PBR
- **計算方法**: 業種内（sector33）でのパーセンタイルランク（低いほど高スコア）
- **欠損値処理**: `fillna(0.5)`（中立的な値）
- **意味**: 割安なほど高評価（業種相対）

##### 3. Growth Score（成長性スコア）

```python
op_growth_score = _pct_rank(df["op_growth"], ascending=True).fillna(0.5)
profit_growth_score = _pct_rank(df["profit_growth"], ascending=True).fillna(0.5)
op_trend_score = _pct_rank(df["op_trend"], ascending=True).fillna(0.5)

growth_score = (
    0.4 × op_growth_score +          # 営業利益成長率
    0.4 × profit_growth_score +      # 当期純利益成長率
    0.2 × op_trend_score             # 営業利益トレンド（3年スロープ）
)
```

- **評価指標**: 営業利益成長率、利益成長率、営業利益トレンド
- **計算方法**: 全銘柄中のパーセンタイルランク（高いほど高スコア）
- **欠損値処理**: `fillna(0.5)`（中立的な値）
- **意味**: 成長性が高いほど高評価

##### 4. Record-High Score（最高益スコア）

```python
record_high_score = record_high_forecast_flag.astype(float)  # 0 or 1
```

- **評価指標**: 予想最高益フラグ
- **計算方法**: フラグが立っている場合は1.0、立っていない場合は0.0
- **欠損値処理**: `fillna(0.0)`
- **意味**: 予想最高益の場合は高評価

##### 5. Size Score（サイズスコア）

```python
log_mcap = market_cap.apply(_log_safe)  # 対数時価総額
size_score = _pct_rank(log_mcap, ascending=True)  # パーセンタイルランク
```

- **評価指標**: 時価総額（対数変換後）
- **計算方法**: 全銘柄中のパーセンタイルランク（小さいほど高スコア）
- **欠損値処理**: `fillna(0.5)`（中立的な値）
- **意味**: 小規模銘柄ほど高評価

#### 重みの正規化

```python
# 正規化（合計が1になるように）
total = w_quality + w_value + w_growth + w_record_high + w_size
w_quality /= total
w_value /= total
w_growth /= total
w_record_high /= total
w_size /= total
```

**注意**: 重みは正規化されており、合計が1.0になります。

---

### 2.2 Entry Score（エントリータイミングスコア）

`entry_score`は、エントリータイミングを評価するスコアです。テクニカル指標（BB、RSI）を使用して、買い時を判断します。

#### 計算式

```python
entry_score = bb_weight × bb_score + rsi_weight × rsi_score
```

#### 各要素の詳細

##### 1. BB Score（ボリンジャーバンドスコア）

```python
# 3つの期間（20, 60, 90日）で計算し、平均を取る
for n in (20, 60, 90):
    z = _bb_zscore(close, n)  # BB Z-score
    
    # 最小幅チェック
    bb_z_diff = bb_z_max - bb_z_base
    if abs(bb_z_diff) >= bb_z_min_width:  # デフォルト: 0.5
        # z=bb_z_baseのとき0、z=bb_z_maxのとき1になる線形変換
        raw_score = (z - bb_z_base) / bb_z_diff
        bb_score = np.clip(raw_score, 0.0, 1.0)
    else:
        bb_score = np.nan

bb_score = np.nanmean([bb_score_20, bb_score_60, bb_score_90])
```

- **評価指標**: BB Z-score（ボリンジャーバンドのZスコア）
- **計算方法**: 3つの期間（20, 60, 90日）で計算し、平均を取る
- **順張り/逆張り**: `bb_z_max > bb_z_base`の場合は順張り（zが高いほど高スコア）、`bb_z_max < bb_z_base`の場合は逆張り（zが低いほど高スコア）
- **最小幅制約**: `abs(bb_z_max - bb_z_base) >= bb_z_min_width`（デフォルト: 0.5）

##### 2. RSI Score（RSIスコア）

```python
# 3つの期間（20, 60, 90日）で計算し、平均を取る
for n in (20, 60, 90):
    rsi = _rsi_from_series(close, n)  # RSI
    
    # 最小幅チェック
    rsi_diff = rsi_max - rsi_base
    if abs(rsi_diff) >= rsi_min_width:  # デフォルト: 10.0
        # RSI=rsi_baseのとき0、RSI=rsi_maxのとき1になる線形変換
        raw_score = (rsi - rsi_base) / rsi_diff
        rsi_score = np.clip(raw_score, 0.0, 1.0)
    else:
        rsi_score = np.nan

rsi_score = np.nanmean([rsi_score_20, rsi_score_60, rsi_score_90])
```

- **評価指標**: RSI（相対力指数）
- **計算方法**: 3つの期間（20, 60, 90日）で計算し、平均を取る
- **順張り/逆張り**: `rsi_max > rsi_base`の場合は順張り（RSIが高いほど高スコア）、`rsi_max < rsi_base`の場合は逆張り（RSIが低いほど高スコア）
- **最小幅制約**: `abs(rsi_max - rsi_base) >= rsi_min_width`（デフォルト: 10.0）

#### 重みの正規化

```python
bb_weight + rsi_weight = 1.0  # 合計が1.0
```

---

### 2.3 スコア計算の実装場所

#### build_features関数（`longterm_run.py`）

```python
def build_features(
    conn: sqlite3.Connection,
    as_of_date: str,
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
) -> pd.DataFrame:
    """
    特徴量を計算し、core_scoreとentry_scoreを計算
    
    処理フロー:
    1. 財務データ、価格データを取得
    2. 各種特徴量を計算（ROE、PER、PBR、成長率など）
    3. core_scoreを計算（quality_score, value_score, growth_score, record_high_score, size_score）
    4. entry_scoreを計算（BB、RSI）
    5. 結果をDataFrameとして返す
    """
```

**重要なポイント**:
- `build_features`は`core_score`と`entry_score`の両方を計算する
- `_select_portfolio_with_params`内で`entry_score`が既に計算されている場合はスキップする（再計算を避ける）

---

## 3. ポートフォリオ選択ロジック（重点）

### 3.1 選択フロー

```python
def _select_portfolio_with_params(
    feat: pd.DataFrame,
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
) -> pd.DataFrame:
    """
    パラメータ化されたポートフォリオ選択
    
    処理フロー:
    1. entry_scoreが未計算の場合は計算（DBから価格データ取得）
    2. フィルタリング（流動性、ROE）
    3. サブスコア計算（value_score, size_score, quality_score, growth_score, record_high_score）
    4. core_score計算
    5. Pool selection（core_score上位N銘柄を選定）
    6. Final selection（entry_score + core_scoreでソート）
    7. Sector cap適用
    8. 重み付け（等ウェイト）
    """
```

### 3.2 フィルタリング

```python
# 1. 流動性フィルタ
if strategy_params.liquidity_quantile_cut > 0:
    q = df["liquidity_60d"].quantile(strategy_params.liquidity_quantile_cut)
    df = df[df["liquidity_60d"] >= q]

# 2. ROEフィルタ
df = df[df["roe"] >= strategy_params.roe_min]
```

### 3.3 Pool Selection

```python
# core_score上位N銘柄を選定
pool = df.nlargest(strategy_params.pool_size, "core_score")
```

### 3.4 Final Selection

```python
# entry_score + core_scoreでソート
if strategy_params.use_entry_score:
    pool = pool.sort_values(
        ["entry_score", "core_score"], ascending=[False, False]
    )
else:
    pool = pool.sort_values("core_score", ascending=False)
```

### 3.5 Sector Cap適用

```python
selected = []
sector_counts = {}
for _, row in pool.iterrows():
    sector = row["sector33"]
    if sector_counts.get(sector, 0) < strategy_params.sector_cap:
        selected.append(row)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= strategy_params.target_max:
            break

# 最小銘柄数に満たない場合はセクター制限を緩和
if len(selected) < strategy_params.target_min:
    # セクター制限を緩和して追加
    ...
```

### 3.6 重み付け（重要）

```python
# 等ウェイト（以前のスコア比例ウェイト戦略の選定ロジックを使用、重みは等ウェイト）
n = len(sel_df)
sel_df["weight"] = 1.0 / n
```

**重要なポイント**:
- **選定ロジック**: スコア比例（`core_score`と`entry_score`に基づいて選定）
- **重み付け**: **等ウェイト**（選定された銘柄に均等に重みを付ける）
- 以前はスコア比例ウェイト（`weight = core_score / total_score`）だったが、現在は等ウェイトに変更

---

## 4. 最適化ロジック（重点）

### 4.1 目的関数

```python
def objective_longterm(
    trial: optuna.Trial,
    train_dates: List[str],
    study_type: Literal["A", "B", "C"],
    ...
) -> float:
    """
    Optunaの目的関数（長期保有型）
    
    処理フロー:
    1. パラメータ提案（Optuna）
    2. StrategyParamsとEntryScoreParamsを構築
    3. train期間の各rebalance_dateでポートフォリオを選定
    4. パフォーマンスを計算
    5. 目的関数値を返す（年率超過リターン - λ × 下振れペナルティ）
    """
```

### 4.2 パラメータ探索空間

#### StrategyParamsのパラメータ

```python
# Core score weights（正規化される）
w_quality = trial.suggest_float("w_quality", 0.05, 0.50)
w_value = trial.suggest_float("w_value", 0.10, 0.60)  # Study C: 0.10-0.60
w_growth = trial.suggest_float("w_growth", 0.01, 0.30)
w_record_high = trial.suggest_float("w_record_high", 0.01, 0.20)
w_size = trial.suggest_float("w_size", 0.05, 0.40)

# Value mix
w_forward_per = trial.suggest_float("w_forward_per", 0.20, 0.90)
w_pbr = 1.0 - w_forward_per

# Filters
roe_min = trial.suggest_float("roe_min", 0.00, 0.20)  # Study C: 0.00-0.20
liquidity_quantile_cut = trial.suggest_float("liquidity_quantile_cut", 0.10, 0.30)

# Portfolio size
target_min = 12  # 固定
target_max = 12  # 固定
pool_size = 80   # 固定
sector_cap = 4   # 固定
```

#### EntryScoreParamsのパラメータ

```python
# RSI parameters（順張り/逆張りを対称に探索）
RSI_LOW, RSI_HIGH = 15.0, 85.0
rsi_min_width = 10.0

rsi_base = trial.suggest_float("rsi_base", RSI_LOW, RSI_HIGH)

# baseに対して制約を満たすmaxの範囲を計算
# 順張り: rsi_max >= rsi_base + rsi_min_width
# 逆張り: rsi_max <= rsi_base - rsi_min_width
if trial.number % 2 == 0:
    # 順張り方向
    rsi_max = trial.suggest_float("rsi_max", max(rsi_base + rsi_min_width, RSI_LOW), RSI_HIGH)
else:
    # 逆張り方向
    rsi_max = trial.suggest_float("rsi_max", RSI_LOW, min(rsi_base - rsi_min_width, RSI_HIGH))

# BB Z-score parameters（順張り/逆張りを対称に探索）
BB_LOW, BB_HIGH = -3.5, 3.5
bb_z_min_width = 0.5

bb_z_base = trial.suggest_float("bb_z_base", BB_LOW, BB_HIGH)

# baseに対して制約を満たすmaxの範囲を計算
# 順張り: bb_z_max >= bb_z_base + bb_z_min_width
# 逆張り: bb_z_max <= bb_z_base - bb_z_min_width
if trial.number % 2 == 0:
    # 順張り方向
    bb_z_max = trial.suggest_float("bb_z_max", max(bb_z_base + bb_z_min_width, BB_LOW), BB_HIGH)
else:
    # 逆張り方向
    bb_z_max = trial.suggest_float("bb_z_max", BB_LOW, min(bb_z_base - bb_z_min_width, BB_HIGH))

# BB/RSI weights
bb_weight = trial.suggest_float("bb_weight", 0.20, 0.95)  # Study C: 0.20-0.95
rsi_weight = 1.0 - bb_weight
```

**重要なポイント**:
- RSIとBBの順張り/逆張りは、trial番号の偶奇で決定（パラメータ空間を増やさない）
- 最小幅制約により、無意味なパラメータ組み合わせを排除

### 4.3 目的関数値の計算

```python
# train期間のパフォーマンスを計算
train_perf = calculate_longterm_performance(
    train_dates,
    strategy_params,
    entry_params,
    ...
)

# 目的関数値 = 年率超過リターン - λ × 下振れペナルティ
objective_value = train_perf["mean_annual_excess_return_pct"]
if lambda_penalty > 0:
    # 下振れペナルティ（P10超過リターンの負の値にペナルティ）
    p10_excess = train_perf.get("p10_excess_return_pct", 0.0)
    if p10_excess < 0:
        objective_value -= lambda_penalty * abs(p10_excess)

return objective_value
```

**重要なポイント**:
- 目的関数は`mean_annual_excess_return_pct`（年率超過リターンの平均）
- λペナルティがある場合は、P10超過リターンの負の値にペナルティを課す

---

## 5. パフォーマンス評価ロジック

### 5.1 長期保有パフォーマンス計算

```python
def calculate_longterm_performance(
    rebalance_dates: List[str],
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    horizon_months: int = 24,
    require_full_horizon: bool = True,
    as_of_date: Optional[str] = None,
    ...
) -> Dict[str, Any]:
    """
    長期保有パフォーマンスを計算
    
    処理フロー:
    1. 各rebalance_dateでポートフォリオを選定
    2. eval_end = rebalance_date + horizon_months
    3. require_full_horizon=Trueの場合、eval_end <= as_of_dateのもののみ評価
    4. 各ポートフォリオのリターンを計算
    5. 統計量を計算（平均、中央値、P10、勝率など）
    """
```

### 5.2 リターン計算

```python
# 各ポートフォリオのリターンを計算
for rebalance_date in rebalance_dates:
    eval_end = rebalance_date + relativedelta(months=horizon_months)
    
    if require_full_horizon and eval_end > as_of_date:
        # ホライズン未達の場合はスキップ
        continue
    
    # ポートフォリオのリターンを計算
    portfolio_return = calculate_portfolio_return(rebalance_date, eval_end)
    topix_return = calculate_topix_return(rebalance_date, eval_end)
    
    excess_return = portfolio_return - topix_return
    
    # 年率化
    holding_years = (eval_end - rebalance_date).days / 365.25
    annualized_excess_return = (1 + excess_return) ** (1 / holding_years) - 1
```

### 5.3 統計量の計算

```python
# 年率超過リターンの統計量
mean_annual_excess_return_pct = np.mean(annualized_excess_returns) * 100
median_annual_excess_return_pct = np.median(annualized_excess_returns) * 100
p10_excess_return_pct = np.percentile(annualized_excess_returns, 10) * 100
win_rate = np.mean(annualized_excess_returns > 0)
```

---

## 6. データフロー

### 6.1 最適化時のデータフロー

```
1. 特徴量の事前計算（FeatureCache）
   - build_featuresを各rebalance_dateで実行
   - features_dictに保存

2. 価格データの事前計算
   - prices_dictに保存

3. Optuna trial開始
   - パラメータ提案
   - objective_longterm実行
     - train期間の各rebalance_dateで:
       - build_features（features_dictから取得、なければ計算）
       - _select_portfolio_with_params（ポートフォリオ選定）
       - パフォーマンス計算
   - 目的関数値を返す

4. 最適化完了
   - best_paramsを取得
   - test期間で評価
```

### 6.2 データリーク防止

**重要なポイント**:
- `build_features`は`as_of_date`（リバランス日）以前のデータのみを使用
- 財務データは`disclosed_date <= as_of_date`のもののみ使用
- 価格データは`date <= as_of_date`のもののみ使用
- `entry_score`計算時も、`as_of_date`以前の価格データのみ使用

---

## 7. 確認すべきポイント（ChatGPT分析用）

### 7.1 スコア計算の整合性

1. **core_scoreの計算式が正しいか**
   - 各サブスコア（quality_score, value_score, growth_score, record_high_score, size_score）の計算が正しいか
   - 重みの正規化が正しく行われているか
   - 欠損値処理が適切か

2. **entry_scoreの計算式が正しいか**
   - BB Z-scoreとRSIの計算が正しいか
   - 順張り/逆張りのロジックが正しいか
   - 最小幅制約が適切か

3. **スコアの再計算が発生していないか**
   - `build_features`で計算したスコアが`_select_portfolio_with_params`で再計算されていないか
   - データリークが発生していないか

### 7.2 ポートフォリオ選択の整合性

1. **選定ロジックが正しいか**
   - Pool selection（core_score上位N銘柄）が正しく行われているか
   - Final selection（entry_score + core_scoreでソート）が正しく行われているか
   - Sector capが正しく適用されているか

2. **重み付けが正しいか**
   - 等ウェイトが正しく適用されているか
   - 以前のスコア比例ウェイトの痕跡が残っていないか

### 7.3 最適化ロジックの整合性

1. **パラメータ探索空間が適切か**
   - 探索範囲が広すぎないか、狭すぎないか
   - 制約（最小幅制約など）が適切か

2. **目的関数が正しいか**
   - `mean_annual_excess_return_pct`が正しく計算されているか
   - λペナルティが正しく適用されているか

3. **train/test分割が正しいか**
   - train期間とtest期間が重複していないか
   - 24Mホライズンの場合、test期間が適切に設定されているか

### 7.4 パフォーマンス評価の整合性

1. **リターン計算が正しいか**
   - 年率化が正しく行われているか
   - TOPIXとの比較が正しく行われているか

2. **ホライズン制約が正しく適用されているか**
   - `require_full_horizon=True`の場合、ホライズン未達のポートフォリオが除外されているか
   - `as_of_date`の制約が正しく適用されているか

---

## 8. 既知の問題点

### 8.1 train期間とtest期間の乖離

- **問題**: train期間では正の超過リターン（+4.20%）、test期間では負の超過リターン（-4.41%）
- **考えられる原因**:
  1. 過学習の可能性
  2. test期間のサンプル数が少ない（12期間のみ）
  3. 2021年の市場環境が不利だった可能性

### 8.2 スコア計算の重複

- **問題**: `build_features`で計算したスコアが`_select_portfolio_with_params`で再計算される可能性
- **現状**: `entry_score`が既に計算されている場合はスキップするロジックがあるが、`core_score`の再計算はチェックしていない

---

## 9. ファイル構成

### 9.1 主要ファイル

- `src/omanta_3rd/jobs/longterm_run.py`: 特徴量計算、ポートフォリオ選択（本番用）
- `src/omanta_3rd/jobs/optimize.py`: 最適化用のポートフォリオ選択（`_select_portfolio_with_params`）
- `src/omanta_3rd/jobs/optimize_longterm.py`: 長期保有型の最適化（`objective_longterm`）
- `src/omanta_3rd/jobs/compare_lambda_penalties.py`: λ比較スクリプト

### 9.2 データベーステーブル

- `features_monthly`: 特徴量スナップショット
- `portfolio_monthly`: ポートフォリオ（長期保有型用）
- `performance_monthly`: パフォーマンス結果

---

## 10. 参考情報

### 10.1 最近の変更履歴

1. **2026年1月12日**: スコア比例選定ロジックを採用（重みは等ウェイト）
2. **2026年1月12日**: 24Mホライズンのtest期間を2021年に設定
3. **2026年1月12日**: `test_dates`の再計算ロジックを追加

### 10.2 最適化結果

- **λ=0.00**: 平均超過 -5.00%, P10(超過) -11.00%, 勝率 25.0%, train超過 4.20%
- **λ=0.05**: 平均超過 -7.34%, P10(超過) -16.00%, 勝率 8.3%, train超過 4.77%

---

## 11. ChatGPTへの質問例

1. **スコア計算の整合性**: `core_score`と`entry_score`の計算式に問題がないか？
2. **ポートフォリオ選択の整合性**: 選定ロジックと重み付けが正しく実装されているか？
3. **最適化ロジックの整合性**: 目的関数とパラメータ探索空間が適切か？
4. **データリーク**: データリークが発生していないか？
5. **train/test乖離**: train期間とtest期間の乖離が大きい原因は何か？

---

**以上**

