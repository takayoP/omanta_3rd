# ChatGPT Pro向け バックテストパフォーマンス計算検証プロンプト

以下のプロンプトをChatGPT Proにコピー&ペーストして使用してください。

---

## プロンプト本文

```
以下のバックテストパフォーマンス計算の実装コードとサンプルデータを提供します。
計算ロジックが正しく実装されているか、詳細に検証してください。

【検証の重点項目】
1. 分割処理の正確性（split_multiplierの計算）
2. 価格調整方式の妥当性（adjusted_current_price = current_price × split_multiplier）
3. リターン計算式の正確性
4. ポートフォリオ全体のリターン計算（weight加重平均）の正確性
5. TOPIX比較のタイミングと計算の正確性
6. エッジケースの処理（価格データなし、分割複数回など）

【実装コード】

```python
# ファイル: src/omanta_3rd/backtest/performance.py

def _split_multiplier_between(conn, code: str, start_date: str, end_date: str) -> float:
    """
    指定期間内の分割・併合による株数倍率を計算
    
    (start_date, end_date] の期間に発生したAdjustmentFactorから、
    株数倍率 = ∏(1 / adjustment_factor) を計算します。
    
    例: 1:3分割（adjustment_factor = 0.333333）の場合、
    株数倍率 = 1 / 0.333333 ≈ 3.0
    """
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
    
    if df.empty:
        return 1.0
    
    # 株数倍率を計算: split_mult = ∏(1 / adjustment_factor)
    mult = 1.0
    for _, row in df.iterrows():
        adj_factor = row["adjustment_factor"]
        if pd.notna(adj_factor) and adj_factor > 0:
            mult *= (1.0 / float(adj_factor))
    
    return mult


def calculate_portfolio_performance(
    rebalance_date: str,
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    指定されたrebalance_dateのポートフォリオのパフォーマンスを計算
    """
    with connect_db() as conn:
        # ポートフォリオを取得
        portfolio = pd.read_sql_query(
            """
            SELECT code, weight, core_score, entry_score
            FROM portfolio_monthly
            WHERE rebalance_date = ?
            """,
            conn,
            params=(rebalance_date,),
        )
        
        # リバランス日の翌営業日を取得
        next_trading_day = _get_next_trading_day(conn, rebalance_date)
        
        # 各銘柄のリバランス日の翌営業日の始値を取得（購入価格）
        rebalance_prices = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT open
                FROM prices_daily
                WHERE code = ? AND date = ?
                """,
                conn,
                params=(code, next_trading_day),
            )
            if not price_row.empty and price_row["open"].iloc[0] is not None:
                rebalance_prices.append({
                    "code": code,
                    "rebalance_price": price_row["open"].iloc[0],
                })
        
        rebalance_prices_df = pd.DataFrame(rebalance_prices)
        portfolio = portfolio.merge(rebalance_prices_df, on="code", how="left")
        
        # 各銘柄の現在価格を取得（終値を使用）
        current_prices = []
        split_multipliers = []
        for code in portfolio["code"]:
            price_row = pd.read_sql_query(
                """
                SELECT close
                FROM prices_daily
                WHERE code = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                conn,
                params=(code, as_of_date),
            )
            if not price_row.empty and price_row["close"].iloc[0] is not None:
                current_prices.append({
                    "code": code,
                    "current_price": price_row["close"].iloc[0],
                })
                # リバランス日の翌営業日以後の分割倍率を計算
                split_mult = _split_multiplier_between(conn, code, next_trading_day, as_of_date)
                split_multipliers.append({
                    "code": code,
                    "split_multiplier": split_mult,
                })
        
        current_prices_df = pd.DataFrame(current_prices)
        portfolio = portfolio.merge(current_prices_df, on="code", how="left")
        
        split_multipliers_df = pd.DataFrame(split_multipliers)
        portfolio = portfolio.merge(split_multipliers_df, on="code", how="left")
        portfolio["split_multiplier"] = portfolio["split_multiplier"].fillna(1.0)
        
        # 損益率を計算（分割を考慮）
        # バックテストでは仮想的な保有なので、価格を調整する方法を使用
        # 分割が発生した場合、購入価格を分割後の基準に調整して比較
        portfolio["adjusted_current_price"] = portfolio["current_price"] * portfolio["split_multiplier"]
        portfolio["return_pct"] = (
            (portfolio["adjusted_current_price"] - portfolio["rebalance_price"]) 
            / portfolio["rebalance_price"] 
            * 100.0
        )
        
        # ポートフォリオ全体の損益を計算（weightを考慮）
        portfolio["weighted_return"] = portfolio["weight"] * portfolio["return_pct"]
        total_return = portfolio["weighted_return"].sum()
        
        # TOPIX比較: 購入日と評価日のTOPIX価格を取得
        topix_buy_price = _get_topix_price(conn, next_trading_day, use_open=True)
        topix_sell_price = _get_topix_price(conn, as_of_date, use_open=False)
        
        # TOPIXリターンの計算
        topix_return_pct = None
        if topix_buy_price is not None and topix_sell_price is not None and topix_buy_price > 0:
            topix_return_pct = (topix_sell_price - topix_buy_price) / topix_buy_price * 100.0
        
        # 超過リターン
        excess_return_pct = None
        if not pd.isna(total_return) and topix_return_pct is not None:
            excess_return_pct = total_return - topix_return_pct
        
        return {
            "rebalance_date": rebalance_date,
            "as_of_date": as_of_date,
            "total_return_pct": float(total_return) if not pd.isna(total_return) else None,
            "topix_return_pct": float(topix_return_pct) if topix_return_pct is not None else None,
            "excess_return_pct": float(excess_return_pct) if excess_return_pct is not None else None,
            "stocks": portfolio[
                ["code", "weight", "rebalance_price", "current_price", "split_multiplier", 
                 "adjusted_current_price", "return_pct"]
            ].to_dict("records"),
        }
```

【サンプルデータ - ポートフォリオ全体のパフォーマンス】
```
リバランス日: 2022-01-31
評価日: 2025-12-26
total_return_pct: 79.40597%
topix_return_pct: 79.492208%
excess_return_pct: -0.086238%
num_stocks: 30
avg_return_pct: 81.009605%
min_return_pct: -74.200206%
max_return_pct: 443.103448%
```

【サンプルデータ - 銘柄別パフォーマンス（分割なしの例）】
```
銘柄コード: 5706
weight: 0.030669
rebalance_price（購入価格）: 3190.0円（2022-02-01の始値）
current_price（評価価格）: 17325.0円（2025-12-26の終値）
split_multiplier: 1.0（分割なし）
adjusted_current_price: 17325.0円
return_pct: 443.103448%

手動計算検証:
  リターン = (17325.0 - 3190.0) / 3190.0 × 100 = 443.10%
  ✓ データベースの値と一致
```

【サンプルデータ - 分割が発生した銘柄の例1】
```
銘柄コード: 5021
weight: 0.038154
rebalance_price: 2293.0円
current_price: 4170.0円
split_multiplier: 2.0（1:2分割が発生）
adjusted_current_price: 8340.0円（4170.0 × 2.0）
return_pct: 263.715656%

手動計算検証:
  調整後評価価格 = 4170.0 × 2.0 = 8340.0円
  リターン = (8340.0 - 2293.0) / 2293.0 × 100 = 263.72%
  ✓ データベースの値（263.715656%）とほぼ一致（丸め誤差）
```

【サンプルデータ - 分割が発生した銘柄の例2（複数回分割）】
```
銘柄コード: 9432
weight: 0.038352
rebalance_price: 3262.0円
current_price: 158.8円
split_multiplier: 25.0（複数回の分割により合計25倍）
adjusted_current_price: 3970.0円（158.8 × 25.0）
return_pct: 21.704476%

手動計算検証:
  調整後評価価格 = 158.8 × 25.0 = 3970.0円
  リターン = (3970.0 - 3262.0) / 3262.0 × 100 = 21.70%
  ✓ データベースの値と一致
```

【サンプルデータ - ポートフォリオ全体のweight合計】
```
total_weight: 1.0（30銘柄の合計）
min_weight: 0.029826
max_weight: 0.038964
✓ weightの合計が1.0で正しい
```

【質問事項】

1. **分割処理の正確性**: `split_multiplier = ∏(1 / adjustment_factor)` という計算式は正しいか？1:3分割でadjustment_factor=0.333333の場合、split_multiplier=3.0になるのは正しいか？

2. **価格調整方式の妥当性**: `adjusted_current_price = current_price × split_multiplier` という方式は正しいか？これにより、分割が発生しても正しいリターンが計算できるか？

3. **期間の範囲**: 分割履歴の取得で `date > start_date` と `date <= end_date` を使用しているが、これは正しいか？購入日の分割は除外し、評価日までの分割を含めるのは適切か？

4. **リターン計算式**: `return_pct = (adjusted_current_price - rebalance_price) / rebalance_price × 100` は正しいか？

5. **ポートフォリオ全体の計算**: `total_return = Σ(weight × return_pct)` というweight加重平均による計算は正しいか？

6. **購入価格のタイミング**: リバランス日の翌営業日の始値を使用することは適切か？

7. **評価価格のタイミング**: 評価日の終値を使用することは適切か？

8. **TOPIX比較**: 個別株と同じタイミング（翌営業日始値で購入、評価日終値で評価）を使用することは適切か？

9. **エッジケース**: 
   - 価格データがない銘柄の処理は適切か？
   - 分割倍率が0や負の値になる可能性はないか？
   - 評価日が営業日でない場合の処理は適切か？

10. **潜在的な問題点**: 現在の実装に問題や改善点はあるか？

上記の項目について、詳細に検証し、問題があれば指摘してください。
特に、分割処理の計算式と価格調整方式が正しいかどうかを重点的に検証してください。
```

---

## 使用方法

1. 上記のプロンプト本文をコピー
2. ChatGPT Proに貼り付け
3. 検証結果を確認
4. 指摘された問題があれば修正

## 補足情報

必要に応じて、以下の情報も追加してください：

- `BACKTEST_PERFORMANCE_VERIFICATION.md` の詳細説明
- 実際のデータベースクエリの結果
- 特定の銘柄についての詳細な分割履歴







