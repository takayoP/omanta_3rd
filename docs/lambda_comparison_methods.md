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

**今後の最適化から**: この修正により、今後の最適化結果では再採点が可能になります。ただし、過去に完了したtrial（既存DB）には適用されません。

### Step 2（本番）: λごとに最適化を実行（2段階アプローチ推奨）

計算コストと判断のブレを減らすため、**2段階で進めることを推奨します**。

#### Step 2-A（粗い絞り込み）

**λを2点だけ**で回す：`0.00`と`0.05`

```bash
python -m omanta_3rd.jobs.compare_lambda_penalties \
  --params-id operational_24M \
  --start 2020-01-01 \
  --end 2025-12-31 \
  --n-trials 200 \
  --lambda-values 0.00 0.05
```

**確認事項**:
- 「平均が落ちすぎない」「P10が改善する」傾向があるか確認
- `0.05`が良さそうなら、Step 2-Bへ進む
- `0.00`が明確に勝つなら、λ導入自体を弱める判断も可能

#### Step 2-B（4点で比較）

`0.00, 0.03, 0.05, 0.08`を回す

```bash
python -m omanta_3rd.jobs.compare_lambda_penalties \
  --params-id operational_24M \
  --start 2020-01-01 \
  --end 2025-12-31 \
  --n-trials 200 \
  --lambda-values 0.00 0.05 0.03 0.08
```

**所要時間**: 
- Step 2-A: 2つのλ値で約2倍の時間（例：100分）
- Step 2-B: 4つのλ値で約4倍の時間（例：200分、約3.3時間）
- **推奨**: まずStep 2-Aで傾向を確認してから、Step 2-Bを実行

**判断基準**: 資料の「最小λルール」が実務的で良いです。

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

1. **今後作られるstudy DBから再採点が可能になる**
   - この修正以降に実行される最適化では、各trialの`mean_excess`と`p10_excess`が保存される
   - 新しい最適化を実行した後、異なるλ値で再採点できる
   - **注意**: 過去に完了したtrial（既存DB）の中身は増えないため、既存DBには効かない

2. **将来の最適化でも活用可能**
   - 新しい最適化を実行した際に、後から異なるλ値で再評価できる
   - λ値を変えて最適化を再実行する前に、既存のtrial群から最適なλ値を判断できる

3. **比較検証が容易になる**
   - 「λを変えたときの効果」を即座に確認できる（ただし、探索済みtrialの中での並べ替えのみ）
   - 最適化前に、どのλ値が適切かの当たりをつけられる

### 注意点（再採点の限界）

**再採点は「探索済みtrialの中で並べ替える」だけ**なので、以下の限界があります：

- **λを変えたときに本来見つかる解が探索されていない可能性がある**
- 再採点で良いtrialが見つかっても、そのλで新たに探索するとさらに良い解が見つかる可能性がある

**推奨アプローチ**:
1. まず再採点で当たりをつける（高速）
2. 必要なら、そのλで少しだけ追加trialを回す（補完）

### 注意点

- **既存のstudy DBには適用されない**: 既に最適化が完了しているstudy DB（例：`optuna_operational_24M_20260109.db`、`optuna_12M_momentum_20260109.db`）には、`mean_excess`と`p10_excess`が保存されていないため、この方法は使えません。
- **今後の最適化から有効**: この修正を適用した後の最適化結果から、再採点が可能になります。
- **既存結果を使う場合**: 既存のstudy DBを使う場合は、`compare_lambda_penalties.py`を使用して、各λ値で最適化を再実行する必要があります。

---

## 推奨アクション

### 現時点での推奨（最短ToDo）

1. **Step 2-A（粗い絞り込み）**: `compare_lambda_penalties.py`で**まずλ=0.00と0.05**を実行
   - `mean / P10 / win_rate / n_periods`を比較（資料の基準でOK）
   - 有望ならStep 2-Bへ進む

2. **Step 2-B（4点で比較）**: `0.00, 0.03, 0.05, 0.08`を追加して4点比較
   - 資料の「最小λルール」に沿って判断

3. **採用λを決めたら**: そのλで`reoptimize_all_candidates.py`（本番再最適化）へ
   - **12M用と24M用で同一λにするか／分けるか**も含めて判断

### 将来的な改善（実装済み）

**修正を実装済み**: `objective_longterm`関数で`mean_excess`と`p10_excess`を`trial.set_user_attr`で保存するように修正しました。
- 今後の最適化結果から「既存結果の再採点」が可能になります
- ただし、過去に完了したtrial（既存DB）には適用されません

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

**注意（再採点の限界）**:
- 再採点は「探索済みtrialの中で並べ替える」だけなので、**λを変えたときに本来見つかる解が探索されていない**可能性がある
- 推奨アプローチ: まず再採点で当たりをつける（高速）→ 必要なら、そのλで少しだけ追加trialを回す（補完）

---

## λ比較を「意味ある比較」にするための必須チェック（ChatGPT推奨）

λ比較は「目的関数を変える」ので、比較の信頼性は**固定ホライズン評価の厳密性**と**P10の安定性**に依存します。

### 必須チェック1: `n_periods`が小さすぎるtrialを除外（ChatGPT推奨）

P10はサンプルが少ないと暴れます。最低でも`n_periods`を保存し、例えば：

- `n_periods < 20`は無効（値は目安、データ密度に合わせて調整）
  - 12Mの場合: `n_periods < 20`程度を推奨
  - 24Mの場合: `n_periods < 10`でも良い可能性（サンプル数が少なくなりがち）

のようなガードを入れると、λ比較の結論が安定します。

**実装状況**: 
- `objective_longterm`関数で`n_periods`が少ない場合は警告を出力（12Mなら20、24Mなら10を閾値として使用）
- 現状は警告のみですが、trialを無効（`-inf`を返す）にする修正も検討可能です
- λ比較の際は、`n_periods`が小さすぎるtrialの結果を除外して判断することを推奨します

### 必須チェック2: 固定ホライズン評価の終端が`eval_end`になっていること

これが崩れると、λ以前に比較が壊れます。
（この点は既に丁寧に修正済みです。ログで`rebalance_date/eval_end_date/実際の評価終端`が一致することを確認できれば十分です。）

**確認方法**: 
- 最適化ログで`rebalance_date → eval_end={eval_end_date}`を確認
- `eval_end_date == rebalance_date + horizon_months`が成立していることを確認

---

## まとめ

### 現状（既存のstudy DB）

- **既存の最適化結果から再採点することはできない**
  - 理由: `mean_excess`と`p10_excess`が保存されていない
  - 確認済み: `optuna_operational_24M_20260109.db`、`optuna_12M_momentum_20260109.db`ともに保存されていない ❌

- **今後のλ比較**: `compare_lambda_penalties.py`を使用して、各λ値で最適化を実行する必要がある
  - **推奨アプローチ（2段階）**: まずλ=0.00と0.05で比較（Step 2-A）→ 有望なら4点で比較（Step 2-B）
  - 所要時間: 
    - Step 2-A: 2つのλ値で約2倍の時間（例：100分）
    - Step 2-B: 4つのλ値で約4倍の時間（例：200分、約3.3時間）

### 今後の改善（実装済み）

- **修正を実装済み**: `trial.set_user_attr`で`mean_excess`と`p10_excess`を保存するように修正しました
  - 今後の最適化結果から「既存結果の再採点」が可能になります
  - ただし、**過去に完了したtrial（既存DB）には適用されません**

**注意（再採点の限界）**:
- 再採点は「探索済みtrialの中で並べ替える」だけなので、**λを変えたときに本来見つかる解が探索されていない**可能性がある
- 推奨アプローチ: まず再採点で当たりをつける（高速）→ 必要なら、そのλで少しだけ追加trialを回す（補完）

