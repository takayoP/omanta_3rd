# train期間の超過リターンが低い問題：検証結果まとめ

## 確認項目と結果

### 1. Optunaの方向とbest_valueの整合性確認 ✅

**現在の結果（2026-01-12）**:
- `direction: 2` (maximize)
- `best_value: 1.4449622060373972%` (Trial 156)
- 上位trial（トップ5）: 1.4450%, 1.4293%, 1.3692%, 1.2818%, 1.2313%
- **結論**: Optunaは正しく動作している。`best_value`は最大値と一致。

**以前の結果（2026-01-11）**:
- `direction: 2` (maximize)
- `best_value: 13.487045443783238%` (Trial 185)
- 上位trial（トップ5）: 13.4870%, 13.2348%, 11.5701%, 11.5575%, 11.4592%
- **結論**: Optunaは正しく動作している。`best_value`は最大値と一致。

### 2. train_datesの範囲と件数の確認 ✅

**両方の結果で同じ**:
- `train_dates_first: 2018-01-31`
- `train_dates_last: 2020-12-30`
- `num_train_periods: 36`

**結論**: `train_dates`は同じなので、`as_of_date`の違いが直接的な原因では**ない**。

### 3. 確認が必要な項目

#### 3.1. trainでn_used_datesとmax_eval_end_usedを確認

実際のログファイルまたは最適化実行時の出力を確認する必要があります：
- `n_input_dates`（入力されたrebalance_dates数）: 36のはず
- `n_used_dates`（実際に使用されたrebalance_dates数）: 36であることを確認
- `max_eval_end_used`（使用されたポートフォリオの最大eval_end）: 2022-12-30近辺であることを確認
- `excluded_due_to_incomplete_horizon`（`eval_end > as_of_date`で落ちた件数）: 0であることを確認

#### 3.2. 旧best paramsを今の等ウェイト実装で再評価

同じtrain_dates（36本）に対して：
1. 現在のbest params（train=1.44%）
2. 以前のbest params（train=13.49%だったやつ）

を、今のコード（等ウェイト統一後）で固定評価して、trainの`mean_annual_excess_return_pct`を出す。

**解釈**:
- 旧paramsを等ウェイトで再評価しても**10%超が再現**する場合:
  → 現optimizerがその近辺を見つけられていない可能性
  → direction/探索空間/サンプリング/制約/バグを疑うべき
- 旧paramsを等ウェイトで再評価しても**1〜2%程度**の場合:
  → 13.49%は「別戦略/別算出」の数字だった可能性が高い
  → 今の1.44%は「現実」

## 次のステップ

1. **実際のログを確認**: `calculate_longterm_performance`のログから、除外件数と最大eval_endを確認（`max_eval_end_used`の出力を追加済み）
2. **旧best paramsの再評価**: `re_evaluate_old_params.py`を実行して、旧paramsを等ウェイト実装で再評価
3. **原因特定**: 上記の情報から「splitが想定通りか／as_ofで落ちてるか／以前は条件が違っていたか」を判定



