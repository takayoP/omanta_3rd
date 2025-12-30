# 時系列P/L計算の洗練計画

## 概要

時系列版の実装は完了していますが、レビューで指摘された問題点を修正し、信頼性を向上させます。

---

## 1. 優先度の高い改善項目

### 1.1 売買タイミングの定義を明確化（最優先） ✅ 完了

**実装方針**:
- **open-close方式**を採用（実際の現金余力がないとポジションの引継ぎができないため）
  - 意思決定: リバランス日 `t` の引けでシグナル確定（`t`までの情報で計算）
  - 購入執行: 翌営業日 `t+1` の寄り成（open）で購入
  - 売却執行: 次のリバランス日 `t_next` の引け成（close）で売却
  - リターン: `open(t+1)` → `close(t_next)` の期間
- TOPIXも同じタイミング（購入: open、売却: close）で統一

**実装**:
- `timeseries.py` の `calculate_timeseries_returns()` を修正
- 購入価格: リバランス日の翌営業日 `t+1` の始値
- 売却価格: 次のリバランス日 `t_next` の終値
- TOPIXも同じタイミングで取得

### 1.2 価格取得ロジックの改善

**現状の問題**:
- `_get_price()` が `date <= ? ORDER BY date DESC LIMIT 1` を使用
- データ欠損時に「直前日」を拾ってしまい、意図せず有利/不利になる

**改善方針**:
- 原則は **`date = ?` の完全一致**
- 欠損したら「その銘柄を当月は取引できない」として扱い、ログに残す
- 補完が必要な場合は `missing_policy="ffill"` を明示してオプション化

**実装**:
- `_get_price()` を修正して完全一致を要求
- 欠損時の処理を明文化（drop_and_renormalize or cash）

### 1.3 欠損銘柄のウェイト設計を明文化

**現状の問題**:
- 価格が取れない銘柄を `continue` で落とすため、投資比率が100%未満になる
- 月によって現金比率が変動し、リターンが歪む

**改善方針**:
- **drop_and_renormalize（推奨）** を採用
  - 欠損銘柄は除外し、残り銘柄でウェイトを再正規化（常にフルインベスト）
- ログに欠損銘柄を記録

**実装**:
- `calculate_timeseries_returns()` で欠損銘柄を除外後、ウェイトを再正規化
- 欠損銘柄の情報を `portfolio_details` に記録

### 1.4 取引コストをターンオーバー連動に

**現状の問題**:
- `cost_bps` を毎月固定で引いている
- 入替が激しいほど有利という最適化バイアスが残る

**改善方針**:
- **turnover（入替率）** を計算
- `cost = turnover × cost_bps`（片道/往復は定義次第）

**実装**:
- ターンオーバー計算関数を追加
- 取引コストをターンオーバー連動に変更

### 1.5 指標定義の洗練

**現状の問題**:
- Sortino: 負のリターンだけを抜き出して標準偏差（負け月が少ないと過大になりやすい）
- Profit Factor: 月次リターン（%）の正負を単純合計（複利・資産額の変化が反映されない）

**改善方針**:
- **Sortino**: `downside = min(0, r - target)` を全期間に適用し、`std(downside)` を下方偏差にする
- **Profit Factor**: `pnl_t = equity_{t-1} * r_t` を作り、`sum(pnl_positive) / abs(sum(pnl_negative))`

**実装**:
- `metrics.py` の `calculate_sortino_ratio()` を修正
- `calculate_profit_factor_timeseries()` を修正

### 1.6 目的関数の洗練

**現状の問題**:
- 勝率項が支配的になりやすい設計
- 時系列版に直した後はスケールが変わるので、再調整が必要

**改善方針**:
- ベース: **情報比（IR）＝Sharpe（超過リターン版）** を主軸にする
- 追加: 平均超過は入れるなら小さく、勝率はさらに小さく（または撤去）

**実装**:
- `optimize_timeseries.py` の `objective_timeseries()` を修正

---

## 2. 実装順序

### Phase 1: 売買タイミングと価格取得の改善（最優先） ✅ 完了

1. ✅ 売買タイミングをopen-close方式に統一
2. ✅ 価格取得ロジックを完全一致に変更
3. ✅ 欠損銘柄のウェイト設計を明文化（drop_and_renormalize）
4. ✅ ドキュメントに売買タイミングの定義を明記

### Phase 2: 取引コストと指標定義の改善 ⏳ 未実装

1. ⏳ ターンオーバー計算を追加
2. ⏳ 取引コストをターンオーバー連動に変更
3. ⏳ SortinoとProfit Factorの定義を洗練

### Phase 3: 目的関数の洗練 ⏳ 未実装

1. ⏳ 目的関数を情報比ベースに変更
2. ⏳ 勝率の係数を調整（または撤去）

### Phase 4: サニティチェックの実行 ✅ 完了

1. ✅ サニティチェックスクリプトを作成
2. ✅ サニティチェックスクリプトを実行
3. ✅ 結果を確認して問題があれば修正

### Phase 5: OOS/WFA 自動化 ✅ 完了

1. ✅ Walk-Forward Analysisスクリプトを作成
2. ✅ ホールドアウト評価スクリプトを作成
3. ✅ メトリクス計算の共通化
4. ✅ レポート生成機能

---

## 3. 実装詳細

### 3.1 売買タイミングの統一（open-close方式） ✅ 実装済み

```python
# 実装内容
purchase_date = _get_next_trading_day(conn, rebalance_date)  # リバランス日の翌営業日
purchase_price = _get_price(conn, code, purchase_date, use_open=True)  # 始値（完全一致）
sell_date = next_rebalance_date  # 次のリバランス日
sell_price = _get_price(conn, code, sell_date, use_open=False)  # 終値（完全一致）

# TOPIXも同じタイミング
topix_purchase = _get_topix_price_exact(conn, purchase_date, use_open=True)  # 始値
topix_sell = _get_topix_price_exact(conn, sell_date, use_open=False)  # 終値
```

### 3.2 価格取得ロジックの改善

```python
def _get_price(conn, code: str, date: str, use_open: bool = False) -> Optional[float]:
    """
    指定日の価格を取得（完全一致）
    
    Args:
        conn: データベース接続
        code: 銘柄コード
        date: 日付（YYYY-MM-DD、完全一致を要求）
        use_open: Trueの場合は始値、Falseの場合は終値を取得
    
    Returns:
        価格、存在しない場合はNone
    """
    price_column = "open" if use_open else "close"
    price_df = pd.read_sql_query(
        f"""
        SELECT {price_column}
        FROM prices_daily
        WHERE code = ? AND date = ?
        """,
        conn,
        params=(code, date),
    )
    
    if price_df.empty or pd.isna(price_df[price_column].iloc[0]):
        return None
    
    return float(price_df[price_column].iloc[0])
```

### 3.3 欠損銘柄のウェイト再正規化

```python
# 欠損銘柄を除外
valid_stock_returns = []
missing_codes = []

for _, row in portfolio.iterrows():
    code = row["code"]
    weight = row["weight"]
    
    purchase_price = _get_price(conn, code, purchase_date, use_open=True)
    sell_price = _get_price(conn, code, sell_date, use_open=False)
    
    if purchase_price is None or sell_price is None:
        missing_codes.append(code)
        continue
    
    # リターン計算...
    valid_stock_returns.append({...})

# ウェイトを再正規化
if valid_stock_returns:
    total_weight = sum(r["weight"] for r in valid_stock_returns)
    if total_weight > 0:
        for r in valid_stock_returns:
            r["weight"] = r["weight"] / total_weight  # 再正規化
```

### 3.4 ターンオーバー計算

```python
def calculate_turnover(
    current_portfolio: pd.DataFrame,
    previous_portfolio: Optional[pd.DataFrame],
) -> float:
    """
    ターンオーバー（入替率）を計算
    
    Args:
        current_portfolio: 現在のポートフォリオ（code, weight列）
        previous_portfolio: 前回のポートフォリオ（code, weight列、Noneの場合は初回）
    
    Returns:
        ターンオーバー（0.0-1.0、1.0 = 100%入替）
    """
    if previous_portfolio is None:
        return 1.0  # 初回は100%入替
    
    # 現在のポートフォリオの銘柄セット
    current_codes = set(current_portfolio["code"].tolist())
    previous_codes = set(previous_portfolio["code"].tolist())
    
    # 入替銘柄の割合
    new_codes = current_codes - previous_codes
    removed_codes = previous_codes - current_codes
    
    # 簡易版: 入替銘柄の割合（等金額の場合）
    turnover = (len(new_codes) + len(removed_codes)) / (2 * len(current_codes))
    
    return min(1.0, turnover)
```

---

## 4. サニティチェック項目

1. **TOPIX月次の分布**が常識的（±数%中心、極端値が連発しない）
2. **個別銘柄の月次リターン**に +300% が頻発しない
3. **equity curve が上下**し、MaxDDが0にならない
4. **Sharpe/Sortinoが極端に発散しない**

---

## 5. 実装状況

### 完了した実装

- ✅ **売買タイミングの統一（open-close方式）**
  - 意思決定: リバランス日 `t` の引けでシグナル確定
  - 購入価格: リバランス日の翌営業日 `t+1` の始値
  - 売却価格: 次のリバランス日 `t_next` の終値
  - TOPIXも同じタイミング（購入: open、売却: close）で統一

- ✅ **価格取得ロジックの改善（完全一致）**
  - `_get_price()`: `date = ?` の完全一致を要求
  - `_get_topix_price_exact()`: TOPIX価格も完全一致
  - 欠損時はNoneを返し、その銘柄を当月の取引から除外

- ✅ **欠損銘柄のウェイト設計（drop_and_renormalize）**
  - 欠損銘柄は除外
  - 残り銘柄でウェイトを再正規化（常にフルインベスト）
  - 欠損銘柄の情報を `portfolio_details` に記録

- ✅ **サニティチェックスクリプトの作成**
  - `sanity_check_timeseries.py` を作成
  - TOPIX月次リターン分布のチェック
  - 個別銘柄の異常リターンチェック
  - エクイティカーブのチェック
  - 指標（Sharpe、Sortino）のチェック

### 完了した実装（Phase 2-5）

- ✅ **ターンオーバー計算とコストモデル**
  - 実売買ベースのターンオーバー（executed_turnover = 2.0）
  - 買い・売りコストを分離可能に
  - 参考値としてpaper turnoverも計算

- ✅ **SortinoとProfit Factorの標準定義**
  - Sortino: `downside = min(0, r - target)` を全期間に適用
  - Profit Factor: `pnl_t = equity_{t-1} * r_t`（通貨建て損益）

- ✅ **目的関数の洗練**
  - Sharpe_excess（=IR）を主軸に変更
  - 勝率項を撤去

- ✅ **サニティチェック**
  - 全チェックをパス
  - レポート生成機能

- ✅ **OOS/WFA 自動化**
  - Walk-Forward Analysisスクリプト（`walk_forward_timeseries.py`）
  - ホールドアウト評価スクリプト（`holdout_eval_timeseries.py`）
  - メトリクス計算の共通化（`eval_common.py`）
  - レポート生成（Markdown + JSON）

---

**最終更新日**: 2025-12-30  
**バージョン**: 1.2

---

## 6. Phase 5: OOS/WFA 自動化

### 6.1 実装ファイル

- `src/omanta_3rd/backtest/eval_common.py`
  - `calculate_metrics_from_timeseries_data()`: メトリクス計算の共通関数
  
- `src/omanta_3rd/jobs/walk_forward_timeseries.py`
  - Walk-Forward Analysisの実行
  - foldごとにtrain期間で最適化→test期間で固定評価
  
- `src/omanta_3rd/jobs/holdout_eval_timeseries.py`
  - ホールドアウト評価の実行
  - Train期間で最適化→Holdout期間で固定評価

### 6.2 使用方法

#### Walk-Forward Analysis
```bash
python -m omanta_3rd.jobs.walk_forward_timeseries \
  --start 2021-01-01 \
  --end 2025-12-31 \
  --folds 3 \
  --train-min-years 2.0 \
  --n-trials 50 \
  --buy-cost 10.0 \
  --sell-cost 10.0 \
  --seed 42
```

#### ホールドアウト評価
```bash
python -m omanta_3rd.jobs.holdout_eval_timeseries \
  --train-start 2021-01-01 \
  --train-end 2023-12-31 \
  --holdout-start 2024-01-01 \
  --holdout-end 2025-12-31 \
  --n-trials 50 \
  --buy-cost 10.0 \
  --sell-cost 10.0 \
  --seed 42
```

### 6.3 出力

- `reports/wfa_timeseries_YYYYMMDD_HHMMSS.md`: WFAレポート（Markdown）
- `reports/holdout_timeseries_YYYYMMDD_HHMMSS.md`: ホールドアウトレポート（Markdown）
- `artifacts/wfa_timeseries_YYYYMMDD_HHMMSS.json`: WFA生データ（JSON）
- `artifacts/holdout_timeseries_YYYYMMDD_HHMMSS.json`: ホールドアウト生データ（JSON）
- `artifacts/best_params_foldX_YYYYMMDD_HHMMSS.json`: foldごとの最良パラメータ
- `artifacts/best_params_holdout_YYYYMMDD_HHMMSS.json`: ホールドアウトの最良パラメータ

### 6.4 重要な実装要件

- **Leak防止**: test期間のデータが最適化に混入しない構造（期間指定を明確に分離）
- **単一ソース**: `eval_common.py`でメトリクス計算を共通化
- **メタデータ**: 出力JSONにconfig（start/end/cost/timing/missing_policy/commit hash）を保存

