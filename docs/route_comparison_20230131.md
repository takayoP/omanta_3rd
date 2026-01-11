# 2023-01-31の結果突き合わせ（両ルート比較）

## 目的

`test_mean_excess_return_pct`（optimize側）と`avg_annualized_excess_return_pct`（compare側）の差の原因を特定するため、2023-01-31の1本だけで両ルートの結果を突き合わせました。

## 実行条件

- **パラメータID**: `operational_24M_lambda0.00`
- **リバランス日**: 2023-01-31
- **評価日**: 2025-12-31
- **ホライズン**: 24M

## 結果

### ポートフォリオ生成結果

**選定銘柄**: 12銘柄（等権重8.33%ずつ）

- 銘柄コード: 1661, 512, 1425, 503, 1418, 1304, 1420, 137, 338, 895, 819, 793

**日付情報**:
- リバランス日（入口日）: 2023-01-31
- eval_end_raw: 2025-01-31
- eval_end_snapped: 2025-01-31
- as_of_date: 2025-12-31
- 保有期間: 2.0014年（731日）

### パフォーマンス結果

**基本指標**:
- total_return_pct: **24.61%**
- topix_return_pct: **40.55%**
- excess_return_pct: **-15.94%**
- as_of_date: 2025-01-31

**年率化指標**（`avg_annualized_excess_return_pct`の計算方法）:
- annualized_total_return_pct: **11.62%**
- annualized_topix_return_pct: **18.54%**
- annualized_excess_return_pct: **-6.92%**

## 重要な発見

### 両ルートは同じロジックを使用

**確認結果**:
- 両ルート（optimize側とcompare側）は、同じ`build_features`と`select_portfolio`を使用
- 同じパラメータで実行すれば、同じポートフォリオが生成されるはず

**実装の確認**:
- **optimize側**（`calculate_longterm_performance`）: `_run_single_backtest_portfolio_only`を使用 → 内部で`build_features`と`select_portfolio`を呼び出し
- **compare側**（`run_backtest_with_params_file`）: 直接`build_features`と`select_portfolio`を呼び出し

### この日付の結果

2023-01-31のポートフォリオ:
- 選定銘柄: 12銘柄（等権重）
- 累積超過リターン: -15.94%
- 年率超過リターン: -6.92%

## 次のステップ

### 比較すべき情報

ChatGPTの指摘に基づき、以下の情報を比較する必要があります：

1. **optimize側（calculate_longterm_performance）での2023-01-31の結果**
   - 選定銘柄リスト（上位数本でも可）
   - 重み
   - 入口価格日、出口価格日
   - その窓のtotal_return / topix_return

2. **compare側（run_backtest_with_params_file）での2023-01-31の結果**
   - 選定銘柄リスト（上位数本でも可）
   - 重み
   - 入口価格日、出口価格日
   - その窓のtotal_return / topix_return

### 期待される結果

**ここが一致するなら**:
- 「差の原因は集約（指標定義の違い）」で、バグではない
- `test_mean_excess_return_pct`は「各窓を個別に年率化してから平均」
- `avg_annualized_excess_return_pct`も「各窓を個別に年率化してから平均」
- 理論的には同じ値になるはずだが、実際には集約方法が異なる可能性がある

**一致しないなら**:
- 「ポートフォリオ生成の差」が原因
- 実装を一本化する必要がある

## 注意事項

現在のスクリプト（`compare_routes_single_date.py`）は、compare側のルートを再現しています。
optimize側の詳細な結果（個別ポートフォリオの情報）を取得するには、`calculate_longterm_performance`の内部実装を確認する必要があります。

ただし、両方とも同じ`build_features`と`select_portfolio`を使用しているため、同じパラメータで実行すれば同じポートフォリオが生成されるはずです。

もし差が残る場合は、以下の可能性があります：
1. **ポートフォリオ生成のタイミングが異なる**（データの状態が変わる可能性）
2. **集約方法が異なる**（指標定義の違い）

