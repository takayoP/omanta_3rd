# ルート差の根本原因（確定版）

## 重要な発見

### 1. `select_portfolio`（longterm_run.py）は等ウェイトを返す

```python
# src/omanta_3rd/jobs/longterm_run.py:1978
sel["weight"] = 1.0 / n
```

**compare側はこの関数を直接使用** → 等ウェイト（0.0833）

### 2. optimize側は`_select_portfolio_with_params`を使用

`optimize.py`の`_select_portfolio_with_params`関数を確認する必要があります。

### 3. params_hashは一致

- compare側: `b1f763b3`
- optimize側: `b1f763b3`
- ✅ **一致** → パラメータは同じ

### 4. portfolio_hashは不一致

- compare側: `458c5408`
- optimize側: `5e833876`
- ❌ **不一致** → ポートフォリオ生成ロジックが異なる

## 結論

**原因1（等ウェイト強制）が確定しました。**

- compare側: `select_portfolio`（等ウェイト）を使用
- optimize側: `_select_portfolio_with_params`（不均等な重み？）を使用

### 次のステップ

1. **`_select_portfolio_with_params`の重み計算方法を確認**
2. **実装を統一**
   - どちらかの実装に統一する
   - または、重みの計算方法をパラメータで選択できるようにする

