# ルート差の根本原因分析

## 重要な発見

### `select_portfolio`の実装

`src/omanta_3rd/jobs/longterm_run.py`の1978行目：

```python
sel["weight"] = 1.0 / n
```

**`select_portfolio`関数自体が等ウェイトを返すように実装されています。**

### 問題の核心

1. **compare側**: `select_portfolio`を直接呼び出し → **等ウェイト（1/12 = 0.0833）**
2. **optimize側**: 別の方法で重みを計算している可能性 → **不均等な重み（0.0879～0.0794）**

### 次のステップ

1. **optimize側でどのようにポートフォリオを生成しているか確認**
   - `_run_single_backtest_portfolio_only`の実装を確認
   - `_select_portfolio_with_params`の実装を確認

2. **重みの計算方法の違いを特定**
   - optimize側がスコアベースの重みを計算している可能性
   - compare側は等ウェイトを強制している

3. **実装を統一**
   - どちらかの実装に統一する必要がある
   - または、重みの計算方法をパラメータで選択できるようにする




