# λ比較の方法と既存結果の活用可能性

## 結論

**現状では、既存の最適化結果から再採点することはできません。**
理由：各trialの`mean_excess`と`p10_excess`がOptunaのstudy DBに保存されていないため。

**確認結果**:
- `optuna_operational_24M_20260109.db`: `mean_excess`と`p10_excess`が保存されていない ❌
- `optuna_12M_momentum_20260109.db`: `mean_excess`と`p10_excess`が保存されていない ❌

**今後の最適化からは可能になります**（修正を実装したため）

ただし、**既に最適化が完了しているstudy DBには適用されません**。

---

## 現状の確認結果

### 現在保存されている情報

Optunaのstudy DB（例：`optuna_operational_24M_20260109.db`）には以下の情報が保存されています：

- **`trial.value`**: 目的関数の値（`objective_value = mean_excess + downside_penalty`）
  - 注意：これはλが適用された後の値なので、元の`mean_excess`と`p10_excess`を分離できない

- **`trial.user_attrs`**: 
  - `rsi_direction`: RSIの方向（順張り/逆張り）
  - `bb_direction`: BBの方向（順張り/逆張り）
  - `rsi_width`: RSIの幅
  - `bb_z_width`: BB Z-scoreの幅

- **`trial.params`**: 最適化パラメータ（rsi_base, rsi_max, bb_z_base, bb_z_max等）

### 保存されていない情報

- **`mean_excess`**: 平均年率超過リターン（%ポイント）
- **`p10_excess`**: P10年率超過リターン（%ポイント）
- **`n_periods`**: P10算出に使ったサンプル数

これらの情報がないため、既存のstudy DBから「λを変えて再採点」することはできません。

---

## λ比較の2つの方法（ChatGPTの説明）

### ① 既存の最適化結果を「採点し直すだけ」（すぐ終わる）

**前提条件**: 各trialの`mean_excess`と`p10_excess`が保存されていること

**方法**:
```python
# 各trialについて、異なるλ値で目的関数を再計算
for trial in study.trials:
    mean_excess = trial.user_attrs.get("mean_excess")
    p10_excess = trial.user_attrs.get("p10_excess")
    
    for lambda_val in [0.00, 0.03, 0.05, 0.08]:
        score = mean_excess + lambda_val * min(0.0, p10_excess)
        # このscoreで並べ替えて、最適なλ値を選ぶ
```

**メリット**: 一瞬で終わる（既存結果の再集計のみ）

**デメリット**:
- 同じtrial群を別のλで並べ替えているだけ
- λを変えたときに**本当に見つかるべき解（下振れが改善する解）**が、そもそもtrial群に含まれていない可能性がある
- λの効果を過小評価しがち

**現状（既存のstudy DB）**: **この方法は使えない**（`mean_excess`と`p10_excess`が保存されていないため）

**今後の最適化から**: **この方法が使えるようになります**（修正を実装したため）

---

### ② λごとに「最適化を回す」（時間がかかる）

**方法**: 各λ値（0.00, 0.05, 0.03, 0.08）で、目的関数を変えて最適化を実行

**メリット**:
- λの真の効果を測定できる
- λを変えたときに、Optunaが「その目的関数で良い内部パラメータ」を探す

**デメリット**: **毎回最適化が走る** = 時間がかかる（4本で約4倍の時間）

**現状**: **この方法を使う必要がある**

---

## 推奨アプローチ（ChatGPT推奨）

### Step 1（すぐ終わる、ただし現状は不可）: 既存結果の再採点

まず①で、手元の結果から：
- λを上げたら上位候補がどう変わるか
- そもそも「下振れがマシなtrial」が過去に存在するか

を確認したいところですが、**現状では`mean_excess`と`p10_excess`が保存されていないため、この方法は使えません**。

### Step 2（本番）: λごとに最適化を実行

`compare_lambda_penalties.py`を使用して、各λ値で最適化を実行します。

```bash
python -m omanta_3rd.jobs.compare_lambda_penalties \
  --params-id operational_24M \
  --start 2020-01-01 \
  --end 2025-12-31 \
  --n-trials 200 \
  --lambda-values 0.00 0.05 0.03 0.08
```

**所要時間**: 各λ値で`n_trials`回の最適化を実行するため、**約4倍の時間がかかります**。
- 例：1つのλ値で200trialが50分なら、4つのλ値で約200分（約3.3時間）

---

## 将来的な改善案：既存結果の再採点を可能にする

### 修正内容（実装済み）

`objective_longterm`関数で、`mean_excess`と`p10_excess`を`trial.set_user_attr`で保存するように修正しました：

```python
# mean_excessとp10_excessをtrialに保存（将来のλ再採点用、ChatGPT推奨）
trial.set_user_attr("mean_excess", mean_excess)
trial.set_user_attr("p10_excess", p10_excess)
trial.set_user_attr("n_periods", n_periods)
trial.set_user_attr("min_excess", min_excess)
trial.set_user_attr("median_excess", perf["median_annual_excess_return_pct"])
trial.set_user_attr("win_rate", perf["win_rate"])
trial.set_user_attr("lambda_penalty", lambda_penalty)  # 使用したλ値も保存
```

**実装場所**: `src/omanta_3rd/jobs/optimize_longterm.py` 行787-793

### この修正のメリット

1. **既存のstudy DBから再採点が可能になる**
   - 既に最適化が完了しているstudy DBでも、異なるλ値で再採点できる
   - 新しい最適化を実行せずに、λ値の影響を確認できる

2. **将来の最適化でも活用可能**
   - 新しい最適化を実行した際に、後から異なるλ値で再評価できる
   - λ値を変えて最適化を再実行する必要がない

3. **比較検証が容易になる**
   - 「λを変えたときの効果」を即座に確認できる
   - 最適化前に、どのλ値が適切かを判断できる

### 注意点

- **既存のstudy DBには適用されない**: 既に最適化が完了しているstudy DB（例：`optuna_operational_24M_20260109.db`、`optuna_12M_momentum_20260109.db`）には、`mean_excess`と`p10_excess`が保存されていないため、この方法は使えません。
- **今後の最適化から有効**: この修正を適用した後の最適化結果から、再採点が可能になります。
- **既存結果を使う場合**: 既存のstudy DBを使う場合は、`compare_lambda_penalties.py`を使用して、各λ値で最適化を再実行する必要があります。

---

## 推奨アクション

### 現時点での推奨

1. **既存の最適化結果**: すでに最適化が完了しているstudy DBには`mean_excess`と`p10_excess`が保存されていないため、**λごとに最適化を再実行する必要があります**。

2. **将来的な改善**: 今後の最適化で`mean_excess`と`p10_excess`を保存するように修正すれば、将来のλ比較で「既存結果の再採点」が可能になります。

### 既存結果の再採点スクリプト（今後の最適化結果用）

今後の最適化結果から再採点する場合は、以下のようなスクリプトを作成できます：

```python
import optuna

def rescore_trials_with_lambda(study_name: str, storage: str, lambda_values: list[float]):
    """既存のstudy DBから、異なるλ値で再採点"""
    study = optuna.load_study(study_name=study_name, storage=storage)
    
    results = []
    for trial in study.trials:
        if trial.state != optuna.trial.TrialState.COMPLETE:
            continue
        
        mean_excess = trial.user_attrs.get("mean_excess")
        p10_excess = trial.user_attrs.get("p10_excess")
        
        if mean_excess is None or p10_excess is None:
            continue  # 古いstudy DBの場合はスキップ
        
        for lambda_val in lambda_values:
            score = mean_excess + lambda_val * min(0.0, p10_excess)
            results.append({
                "trial_number": trial.number,
                "lambda": lambda_val,
                "score": score,
                "mean_excess": mean_excess,
                "p10_excess": p10_excess,
                "params": trial.params,
            })
    
    # lambdaごとに最良trialを選ぶ
    for lambda_val in lambda_values:
        lambda_results = [r for r in results if r["lambda"] == lambda_val]
        if lambda_results:
            best = max(lambda_results, key=lambda x: x["score"])
            print(f"λ={lambda_val}: Best trial {best['trial_number']}, score={best['score']:.4f}")
    
    return results
```

このスクリプトにより、今後の最適化結果から「既存結果の再採点」が可能になります。

---

## まとめ

### 現状（既存のstudy DB）

- **既存の最適化結果から再採点することはできない**
  - 理由: `mean_excess`と`p10_excess`が保存されていない
  - 確認済み: `optuna_operational_24M_20260109.db`、`optuna_12M_momentum_20260109.db`ともに保存されていない ❌

- **今後のλ比較**: `compare_lambda_penalties.py`を使用して、各λ値で最適化を実行する必要がある
  - 所要時間: 各λ値で`n_trials`回の最適化を実行するため、**約4倍の時間がかかります**
  - 例：1つのλ値で200trialが50分なら、4つのλ値で約200分（約3.3時間）

### 今後の改善（実装済み）

- **修正を実装済み**: `trial.set_user_attr`で`mean_excess`と`p10_excess`を保存するように修正しました
  - 今後の最適化結果から「既存結果の再採点」が可能になります
  - ただし、既に最適化が完了しているstudy DBには適用されません

### 推奨アクション

1. **現時点**: 既存のstudy DB（`operational_24M_20260109`、`12M_momentum_20260109`等）を使う場合は、`compare_lambda_penalties.py`で各λ値で最適化を再実行する必要があります

2. **今後の最適化**: 新しい最適化を実行した際には、`mean_excess`と`p10_excess`が保存されるため、後から異なるλ値で再採点が可能になります

3. **最適化前の判断**: 新しい最適化を実行する前に、まず「既存結果の再採点」を試して、どのλ値が適切かを判断することを推奨します（ただし、現状では既存結果がないため、新しい最適化を実行する必要があります）

