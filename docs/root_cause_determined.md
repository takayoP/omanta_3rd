# ルート差の根本原因（確定版）

## 重要な発見

### 重みの計算方法が異なる

#### compare側: `select_portfolio`（longterm_run.py）

```python
# src/omanta_3rd/jobs/longterm_run.py:1978
n = len(sel)
sel["weight"] = 1.0 / n  # 等ウェイト強制
```

**結果**: 等ウェイト（0.0833 = 1/12）

#### optimize側: `_select_portfolio_with_params`（optimize.py）

```python
# src/omanta_3rd/jobs/optimize.py:307-312
# Weight calculation
total_score = sel_df["core_score"].sum()
if total_score > 0:
    sel_df["weight"] = sel_df["core_score"] / total_score  # スコアベースの重み
else:
    sel_df["weight"] = 1.0 / len(sel_df)
```

**結果**: スコアベースの不均等な重み（0.0879～0.0794）

## 結論

**原因1（等ウェイト強制）と原因2（別の選定ロジック）の両方が確定しました。**

1. **compare側**: `select_portfolio`（等ウェイト）を使用
2. **optimize側**: `_select_portfolio_with_params`（スコアベースの重み）を使用

### 影響

- **selected_codesが異なる**: 重みの計算方法が異なるため、選定ロジックも微妙に異なる可能性
- **total_return_pctが8.50%pt違う**: ポートフォリオ（銘柄と重み）が異なるため

### 次のステップ

1. **実装を統一**
   - compare側も`_select_portfolio_with_params`を使用する
   - または、optimize側も`select_portfolio`を使用する（等ウェイトに統一）

2. **重みの計算方法をパラメータで選択できるようにする**
   - 等ウェイト vs スコアベースの重みを選択可能にする

3. **最適化結果の再評価**
   - 実装を統一した後、最適化を再実行する必要がある




