# ChatGPTフィードバックに基づく改善案

## 問題点と改善案

### 1. 【最重要】RSI/BBの順張り/逆張りをtrial番号の偶奇で決める問題

**現状の問題**:
- `trial.number % 2`で方向を決定（1002行目、1038行目）
- 並列数や途中再開でtrial番号の割り当てが変わり、再現性が壊れる
- Optunaが方向を学習できない

**改善案**: categoricalパラメータとしてOptunaに渡す

```python
# 修正前
if trial.number % 2 == 0:
    rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)  # 順張り
else:
    rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)  # 逆張り

# 修正後
rsi_direction = trial.suggest_categorical("rsi_direction", ["momentum", "reversal"])
if rsi_direction == "momentum":
    rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)  # 順張り
else:
    rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)  # 逆張り
```

### 2. コア重みの正規化後の実効値が仕様とズレる

**現状の問題**:
- 個々のサンプル下限を0.01にしていても、正規化後は0.01未満になり得る
- 実際、bestでは`w_growth`が正規化後0.0075まで落ちている

**改善案**: Dirichlet分布を使用するか、正規化後に最小比率を保証

```python
# 改善案1: Dirichlet分布を使用（推奨）
from scipy.stats import dirichlet
alpha = [1.0] * 5  # 5つの重み
weights = dirichlet.rvs(alpha)[0]
w_quality, w_value, w_growth, w_record_high, w_size = weights

# 改善案2: 正規化後に最小比率を保証
MIN_WEIGHT = 0.01
total = w_quality + w_value + w_growth + w_record_high + w_size
w_quality = max(MIN_WEIGHT, w_quality / total)
# ... 他の重みも同様
# 再度正規化
```

### 3. 目的関数（mean）が過学習しやすい

**現状の問題**:
- meanは外れ値に弱く、trainだけ「数本の大当たり」で上がる
- p10はポートフォリオ数が少ないと不安定（12本だと下から2番目相当）

**改善案**: median目的やtrimmed meanを使用

```python
# 改善案1: median目的（推奨）
objective_value = np.median(annual_excess_returns) if annual_excess_returns else 0.0

# 改善案2: trimmed mean（上下10%をカット）
from scipy.stats import trim_mean
objective_value = trim_mean(annual_excess_returns, 0.1) if annual_excess_returns else 0.0

# 改善案3: λ>0を本運用に（下振れ耐性を重視）
objective_value = (
    np.mean(annual_excess_returns)
    - lambda_penalty * max(0, -np.percentile(annual_excess_returns, 10))
)
```

### 4. 評価設計：固定ホライズンの月次12本は分散が大きい

**現状の問題**:
- テストが「ある1年の12本（2022年など）」でサンプル数が少ない
- 評価がブレやすい

**改善案**: 複数年を順にtestして平均する（時系列CV）

```python
# 改善案: 複数年を順にtest
# 2020/2021/2022のように複数年を順にtestして平均
test_years = [2020, 2021, 2022]
test_results = []
for year in test_years:
    test_dates = [d for d in rebalance_dates if d.startswith(str(year))]
    perf = calculate_longterm_performance(...)
    test_results.append(perf["mean_annual_excess_return_pct"])
final_result = np.mean(test_results)
```

### 5. 二重並列化が再現性と安定性の敵

**現状の問題**:
- Optuna trial並列 + trial内バックテスト並列の二重並列
- CPU過剰割当で遅くなる/不安定になる
- trial番号の順序が変わりやすくなる

**改善案**: どちらか片側だけ並列にする

```python
# 改善案: Optunaは並列、trial内はシングル
# または、Optunaはシングル、trial内は並列
# デフォルト設定を変更
if n_jobs == -1:
    optuna_n_jobs = 1  # Optunaはシングル
    backtest_n_jobs = cpu_count - 1  # trial内は並列
```

## 実装優先度

1. **【最優先】RSI/BBの方向をcategoricalパラメータ化**（再現性の問題）
2. **目的関数をmedian/trimmed meanに変更**（過学習対策）
3. **コア重みの正規化を改善**（意図の明確化）
4. **評価設計の改善**（分散削減）
5. **並列化設定の調整**（再現性向上）

## 確認チェックリスト

- [ ] 同一seedで2回回して`best_params`/`best_value`が一致するか
- [ ] `direction`をcategorical化して1回回し、結果が安定するか
- [ ] 正規化後の`entry_score`が極端値になっていないか
- [ ] median目的で結果が改善するか

