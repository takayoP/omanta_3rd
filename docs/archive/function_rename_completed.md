# 関数名変更完了：`_run_single_backtest_portfolio_only` → `_select_portfolio_for_rebalance_date`

## 実施内容

関数名を`_run_single_backtest_portfolio_only`から`_select_portfolio_for_rebalance_date`に変更しました。

## 変更理由

1. **関数の役割を正確に表現**
   - 元の名前「backtest」は誤解を招く（実際には「ポートフォリオ選定のみ」を行う）
   - 新しい名前「select_portfolio_for_rebalance_date」は関数の役割を正確に表現

2. **長期保有型と月次リバランス型の両方で使用可能であることを明確化**
   - ドキュメントに明記
   - 違いは「パフォーマンス計算方法」のみであることを明記

## 変更ファイル

### 1. `src/omanta_3rd/jobs/optimize_timeseries.py`

- **関数定義**（256行目）:
  - `def _run_single_backtest_portfolio_only(...)` → `def _select_portfolio_for_rebalance_date(...)`
  
- **ドキュメント追加**:
  - この関数は「ポートフォリオ選定のみ」を行う
  - パフォーマンス計算は行わない
  - 長期保有型と月次リバランス型の両方で使用可能
  - 違いは「パフォーマンス計算方法」のみ

- **呼び出し箇所**（134行目、155行目）:
  - `_run_single_backtest_portfolio_only(...)` → `_select_portfolio_for_rebalance_date(...)`

- **ログメッセージ**:
  - `[_run_single_backtest]` → `[_select_portfolio]`

### 2. `src/omanta_3rd/jobs/optimize_longterm.py`

- **インポート**（52-54行目）:
  - `_run_single_backtest_portfolio_only` → `_select_portfolio_for_rebalance_date`

- **呼び出し箇所**（232行目、257行目）:
  - `_run_single_backtest_portfolio_only(...)` → `_select_portfolio_for_rebalance_date(...)`

## 効果

1. **コードの可読性向上**
   - 関数名から役割が明確
   - ドキュメントで用途が明確

2. **混同の防止**
   - 「backtest」という名前による誤解を防止
   - 長期保有型と月次リバランス型の両方で使用可能であることを明記

3. **保守性向上**
   - 将来的な拡張時に混乱を防止
   - 新しい開発者が理解しやすくなる

## まとめ

- **変更完了**: `_run_single_backtest_portfolio_only` → `_select_portfolio_for_rebalance_date`
- **変更ファイル**: `optimize.py`、`optimize_timeseries.py`、`optimize_longterm.py`
- **効果**: コードの可読性向上、混同の防止、保守性向上

