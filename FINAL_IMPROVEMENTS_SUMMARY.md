# バックテストパフォーマンス計算の最終改善まとめ

## 修正日: 2025-12-28

## 完了した改善内容

### ✅ 1. 評価日が非営業日のときのズレ問題を修正

**問題**: 評価日が非営業日の場合、価格と分割の基準日がズレる可能性

**修正**: 
- 現在価格取得時に`date`も取得し、`effective_asof_date`を保持
- 分割倍率計算時に`effective_asof_date`を使用

**状態**: ✅ 完了

---

### ✅ 2. ポートフォリオ全体のリターン計算での欠損値処理を改善

**問題**: 
- `sum()`が全部NaNでも0を返すリスク
- 欠損銘柄が暗黙に無視される

**修正**:
- `sum(min_count=1)`を使用: 全部NaNならNaNを維持
- `weight_coverage`を計算して返却
- 欠損値の警告を詳細化

**状態**: ✅ 完了

---

### ✅ 3. 分割倍率の不正値検出と警告

**問題**: `adjustment_factor <= 0`を黙殺している

**修正**:
- 不正値（NULL、0、負の値）を検出し、警告を出力
- 不正値は無視して計算を続行（既存の挙動を維持）

**状態**: ✅ 完了

---

### ✅ 4. as_of_date=NoneのときのSQL問題を修正

**問題**: `as_of_date=None`のときSQLが空になり得る

**修正**:
- `as_of_date=None`の場合は最新の価格データの日付を使用
- 型チェックを追加: `as_of_date`が文字列であることを保証

**状態**: ✅ 完了

---

### ✅ 5. TOPIX比較の挙動確認

**確認**: `_get_topix_price`の非営業日・欠損時の挙動が個別株と一致しているか

**結果**: 
- 個別株と同じく「`date <= ? ORDER BY date DESC LIMIT 1`」で直近営業日の価格を取得
- 非営業日・欠損時の挙動が一致していることを確認
- コメントで明示

**状態**: ✅ 確認完了

---

## 実装済みの改善

### 1. 分割倍率の不正値検出

```python
if adj_factor <= 0:
    invalid_factors.append((split_date, f"invalid_value={adj_factor}"))
    print(f"警告: 銘柄{code}の分割データに不正値があります。日付={split_date}, adjustment_factor={adj_factor}")
    continue
```

### 2. 欠損価格の警告

```python
if missing_buy_prices:
    print(f"警告: {len(missing_buy_prices)}銘柄で購入価格が取得できませんでした。")

if missing_sell_prices:
    print(f"警告: {len(missing_sell_prices)}銘柄で評価価格が取得できませんでした。")
```

### 3. 欠損値の品質管理

```python
# sum(min_count=1)を使用: 全部NaNならNaNを維持（誤った0%を防ぐ）
total_return = portfolio["weighted_return"].sum(min_count=1)

# 欠損値の警告（品質管理）
if coverage < MIN_COVERAGE:
    print(
        f"警告: ポートフォリオの品質が低い可能性があります。"
        f"欠損銘柄数={missing_count}/{num_total}, "
        f"欠損weight={missing_weight:.4f}/{total_weight:.4f}, "
        f"coverage={coverage:.4f}"
    )
```

### 4. as_of_dateの型保証

```python
# 型チェック: as_of_dateが文字列であることを保証（SQLクエリで使用するため）
if not isinstance(as_of_date, str):
    as_of_date = str(as_of_date)
```

---

## 検証済みの計算式

### ✅ split_multiplier = ∏(1 / adjustment_factor)
**回答**: 正しい
- `adjustment_factor`が「価格を分割後基準に合わせる係数」で、イベント日にのみ立つ前提なら正しい
- 1:3分割で0.333333なら3.0は正しい

### ✅ adjusted_current_price = current_price × split_multiplier
**回答**: 正しい
- 分割・併合のみを考える限り、株数調整と等価で正しい
- サンプルデータでも整合性を確認

### ✅ 期間範囲 date > start_date と date <= end_date
**回答**: 妥当
- 購入日の分割を除外し、評価日まで含めるのは一般に妥当
- 非営業日評価では「価格が取れた日」をend_dateに合わせる方が安全（実装済み）

### ✅ return_pct 式
**回答**: 正しい
- 分割調整後の単純リターンとして正しい

### ✅ total_return = Σ(weight × return_pct)
**回答**: 単一期間の買い持ちなら正しい
- ただし欠損銘柄があると結果が暗黙に歪むため、coverage/方針が必要（実装済み）

### ✅ 購入価格：翌営業日始値
**回答**: 適切
- リバランス日終値で選定→翌日寄りで執行、という想定として合理的
- ルックアヘッドも避けやすい

### ✅ 評価価格：評価日終値
**回答**: 妥当
- 非営業日は直近営業日の終値を拾う設計も良い
- ただし分割終端も合わせる（実装済み）

### ✅ TOPIX比較：同タイミング
**回答**: 適切
- `_get_topix_price`の「非営業日・欠損時の挙動」が個別株と一致していることを確認済み

---

## 改善効果

1. **堅牢性の向上**: 不正値や欠損値を検出し、警告を出力
2. **正確性の向上**: 評価日が非営業日でも、価格と分割の基準日が必ず一致
3. **品質管理の向上**: `weight_coverage`により、欠損値の影響を可視化
4. **エラー検出の向上**: 全部NaNの場合はNaNを返すことで、誤った結果を防ぐ
5. **型安全性の向上**: `as_of_date`が文字列であることを保証

---

## 実装ファイル

- `src/omanta_3rd/backtest/performance.py`: メインの実装
- `sql/migration_add_backtest_coverage.sql`: データベースマイグレーション（実行済み）
- `PERFORMANCE_FIX_SUMMARY.md`: 詳細な修正内容
- `BACKTEST_PERFORMANCE_VERIFICATION.md`: 検証資料
- `CHATGPT_PRO_VERIFICATION_PROMPT.md`: ChatGPT Pro向けプロンプト

---

## 次のステップ

1. 修正したコードでバックテストを再実行
2. `weight_coverage`を確認し、品質が低いポートフォリオを特定
3. 警告メッセージを確認し、データ品質の問題を特定
4. 必要に応じて、警告をログファイルに出力する機能を追加





