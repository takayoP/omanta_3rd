# ChatGPT検証結果サマリー

ChatGPTによる計算式検証の結果と、それに基づく改善内容をまとめます。

---

## 検証結果の要約

### 全体評価

**結論**: 大枠は標準的で正しいです。ただし、**2点だけ"改善強く推奨"**があり、これらを修正しました。

---

## 1. Sharpe Ratio（Sharpe_excess）の検証結果

### ✅ 正しい点

- **定義と実装の整合**: 数式と実装コードは一致している
- **年率化（√12）**: 標準的で正しい（i.i.d.近似、月次を前提）
- **不偏標準偏差（ddof=1）**: 適切
- **std==0の処理**: Noneを返すのは妥当

### ⚠️ 改善実施済み

**問題点**: 「超過リターン」を渡している場合、RFを引くと二重控除になり得る

- `monthly_excess_returns`を使う場合、通常それは既にベンチマーク（TOPIX）控除済み
- ここでさらに`risk_free_rate/12`を引くと、「ベンチマーク超過」と「無リスク超過」が混線

**改善内容**:
- `monthly_excess_returns`が指定された場合、RFは引かない（TOPIX超過Sharpe = 情報比率IR相当）
- `monthly_returns`のみ使用時のみRFを引く

**実装変更**:
```python
# 改善前
sharpe = (mean_return - risk_free_rate / 12.0) / std_return

# 改善後
if monthly_excess_returns is not None:
    # ベンチマーク超過リターンの場合、RFは引かない
    sharpe = mean_return / std_return
else:
    # 通常リターンの場合はRFを引く
    sharpe = (mean_return - risk_free_rate / 12.0) / std_return
```

### 注意点

- **年別Sharpe（12点）**: 推定誤差が大きいので、参考値として扱うのが無難（統計の限界）

---

## 2. CAGR（全期間・年別）の検証結果

### ✅ 正しい点

- **全期間CAGR**: `(1+total_return)^(12/num_months)-1` は正しい（等間隔月次を前提）
- **年別CAGR_excess**: 複利の扱いは正しい
- **複利計算**: `np.prod([1.0 + r for r in year_excess])` で正しく計算

### 注意点（軽微）

- 年別CAGRは「その年に存在する月数」が12未満でも年率化されるので、途中から開始/終了するサンプルでは解釈注意
- 月次リバランス戦略では現方式でOK

---

## 3. 平均超過リターン・ボラティリティの年率換算

### ✅ 正しい点

- **平均の年率換算**: `mean_monthly * 12` は正しい
- **標準偏差の年率換算**: `std_monthly * √12` は正しい
- **Sharpeとの整合**: Sharpe年率化（√12）とも整合している

---

## 4. MaxDD（最大ドローダウン）

### ✅ 正しい点

- **定義**: `(equity - peak) / peak` は正しい
- **実装**: `np.maximum.accumulate(values)` でピークを計算するのは正しい
- **TOPIXのMaxDD**: 同様に計算するのは正しい

---

## 5. ターンオーバー（売買回転率）

### ✅ 正しい点（前提条件付き）

- **実装**: 「毎回100%売って100%買う前提」で `executed_turnover = 2.0` は算術的に正しい
- **年間換算**: 月次平均に12を掛けるのは正しい

### ⚠️ 注意点

- **一般的な「ターンオーバー」との違い**: 
  - 一般的: `turnover = Σ|w_t - w_{t-1}| / 2`（重みベース）
  - 本実装: 常に2.0固定（毎回全売買）
- **将来の設計変更**: 「ホールド部分を残す」設計にする場合、重み差分方式に更新推奨
- **現状**: 月次で全部入れ替える設計なら問題なし

---

## 6. コスト考慮後Sharpe（最大の改善点）

### ⚠️ 改善実施済み

**問題点**: 「平均だけからコストを引く」簡易法は、評価が歪みやすい

**旧実装（簡易版）**:
```python
# 年間コスト = ターンオーバー * コスト
annual_cost = avg_turnover_annual * cost_bps / 10000.0
# コスト調整後の平均超過リターン（簡易計算）
mean_excess_after_cost = mean_excess_monthly - (annual_cost / 12.0)
# コスト調整後のSharpe（簡易計算、ボラティリティは変更なしと仮定）
sharpe_after_cost = (mean_excess_after_cost * 12.0) / (vol_excess_monthly * np.sqrt(12.0))
```

**問題**: ボラティリティが反映されない

**新実装（推奨方法）**:
```python
# 月次超過リターンから月次コストを控除
monthly_excess_after_cost = [
    r - c for r, c in zip(monthly_excess_returns, monthly_costs)
]

# コスト控除後の統計を再計算
mean_excess_after_cost_monthly = np.mean(monthly_excess_after_cost)
vol_excess_after_cost_monthly = np.std(monthly_excess_after_cost, ddof=1)

# コスト控除後のSharpe Ratioを計算
sharpe_after_cost = (
    (mean_excess_after_cost_monthly * 12.0) / (vol_excess_after_cost_monthly * np.sqrt(12.0))
)
```

**改善効果**:
- ボラティリティも正しく反映される
- 「コストがある月だけ下がる」効果も入る
- より正確な評価が可能

---

## 7. 年別分解（年別Sharpe/CAGR）

### ✅ 正しい点

- **年別Sharpe**: 年ごとの月次系列に同じSharpe関数（√12年率化）を適用するのは数学的にOK
- **年別CAGR**: 複利計算は正しい

### 注意点

- **12点Sharpeは誤差大**: 年別Sharpeは「符号・崩れ方」の確認用として扱うのが無難

---

## 8. 追加推奨事項（将来の改善）

### 検証用チェック項目

1. **Sharpe_excess = mean_excess_annual / vol_excess_annual の一致テスト**
   - 年率化は整合しているので、コードで常に一致するはず（数値誤差は除く）
   - これは実装検証として強力

2. **CAGRと平均リターンの乖離の監視**
   - 複利効果で乖離するが、異常に乖離する候補は分布が歪んでいる可能性がある（大損→大勝等）

3. **欠損月の扱いがSharpe/CAGRに影響しないか**
   - 欠損月を「月ごとスキップ」するとSharpeが盛れる
   - 推奨: 欠損銘柄だけ除外し、月自体は残す

### 関数の分離（将来の改善）

- **TOPIX超過Sharpe（IR相当）を計算する関数**: RFを引かない
- **無リスク超過Sharpeを計算する関数**: RFを引く
- 現状は`monthly_excess_returns`の有無で自動判定（実用上は問題なし）

---

## 検証結果一覧表

| 計算式 | 検証結果 | 改善状況 |
|--------|----------|----------|
| Sharpe_excess（年率化） | ✅ 標準的で正しい | ✅ 改善済み（RF扱い） |
| CAGR / 年別CAGR | ✅ 正しい（複利・指数もOK） | - |
| MaxDD | ✅ 正しい | - |
| 平均・ボラ年率換算 | ✅ 正しい（Sharpeと整合） | - |
| ターンオーバー | ✅ 前提（毎回全売買）なら正しい | ⚠️ 将来設計変更時は重み差分方式推奨 |
| コスト考慮後Sharpe | ⚠️ 簡易版から改善 | ✅ 改善済み（月次系列から控除） |

---

## 改善実施内容

### 1. Sharpe RatioのRF扱いの改善

**ファイル**: `src/omanta_3rd/backtest/metrics.py`

**変更内容**:
- `monthly_excess_returns`が指定された場合（ベンチマーク超過リターン）、RFを引かない
- これにより、TOPIX超過Sharpe（情報比率IR相当）を正しく計算

### 2. コスト考慮後Sharpe計算の改善

**ファイル**: `evaluate_candidates_holdout.py`

**変更内容**:
- 簡易版（平均からコストを引く）から、月次系列からコストを控除して再計算する方法に変更
- これにより、ボラティリティも正しく反映され、より正確な評価が可能

---

## 結論

ChatGPTによる検証の結果、計算式は大枠標準的で正しいことが確認されました。
2点の改善を実施し、より正確な評価が可能になりました。

- ✅ Sharpe RatioのRF扱い: 超過リターン使用時はRFを引かないように修正
- ✅ コスト考慮後Sharpe: 月次系列から控除して再計算する方法に改善

これらの改善により、Holdout検証の結果はより信頼性が高くなりました。

