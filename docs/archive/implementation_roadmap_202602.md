# 実装ロードマップ（2026-02版）

ChatGPTフィードバックに基づく、原因切り分け・検証手順・目的関数改善・ゲート設計の統合ドキュメント。

---

## 結論：次にやる順番 TOP5（年別スコアカード反映版）

1. ~~**コストが本当に効いているか**~~ ✅ 完了
2. ~~**2021の負けを寄与分解**~~ ✅ 完了（恒常型確定）
3. ~~**Gate3（年別スコアカード）を機械化**~~ ✅ 完了（`build_year_scorecard.py`）
4. **A_local 近傍では Gate3 を通らない**と割り切り、**Study C（広範囲）を最優先で回す**（multi-start、5 seed × 50 trials の軽いバッチ）
5. **「銘柄集合が変わるレバー」を先に増やす**：`pool_size` と `sector_cap_max`（＋できれば `min_sectors` or HHI ペナルティ）。まずは **CLI 固定シナリオ**で回す
6. **最初は Optuna 外のスコアカードで maximin 選抜**（最短・安全）→ 効果が見えたら目的関数に内製
7. **採用ゲートを二段階化**：Gate3-pre（探索用・緩い）→ Gate3（本採用・厳格）
8. **Gate4（optimize/compare/prod 一致）を hash で固定化** → 最後に **2025ホールドアウトを1回だけ**

> 前提：年別スコアカードで両候補とも 2020/2021 がマイナス（win_rate 0〜0.42）で Gate3 不合格が確定。2022だけ強い。

### 結論：次にやる順番 TOP5（Study C 不発を踏まえた版）

1. **その Study C 結果 JSON を年別スコアカード（2020/21/22）に必ず通す**（悪い谷の「どの年が死んでるか」を確定）
2. **Phase A を継続**：seed×trial を増やして候補集合を作る（まず 5 seed × 50 trials）。1本の負けは気にしない
3. **シナリオを切る**：**S120_4 → S120_2 → S160_2** の順で Study C を回す（銘柄集合を意図的に変える）
4. **採用は maximin（worst_year_median）で選抜**：Optuna 目的関数に入れるのは後（外部スコアカードで絞ってから）
5. **地雷谷検知の早期打ち切り（prune/early-stop）**を入れて計算を節約（2022単年ですら median&lt;-5% なら終了など）※将来実装

### 結論：次にやる順番 TOP5（Study C “地雷谷”確定後）

1. **“地雷谷早期検知（2022だけの coarse gate）”を入れて Phase A を回す**  
   - 2022の1年だけで **median &lt; -5% or win_rate &lt; 0.2 or p10 &lt; -10%** なら即打ち切り（trial/seed 単位で捨てる）
2. **シナリオ優先順位を固定**：**S120_4 → S120_2 → S160_2** の順で Study C を multi-start
3. **候補採用は maximin（worst_year_median）**で scorecard 上から選ぶ（Optuna 内製はまだ）
4. **“銘柄集合が変わっているか”を毎回ログで監視**（overlap / HHI / pool→final 入替率）
5. **500〜1000 trial 回しても Gate3-pre がゼロなら**、仕様変更（特徴量・フィルタ・長短分離など）に踏み込む

**Coarse gate（2022単年・地雷除去）**
- `median_2022 < -5%` → 即死
- `win_rate_2022 < 0.20` → 即死
- `p10_2022 < -10%` → 即死（下振れ地雷）

→ 3年スコアカードへ進めるのは、**この coarse gate を通過した候補だけ**（無駄計算を減らす）。

**Phase A-mini（分布推定バッチ・最小構成）**
- seeds = [11, 22, 33, 44, 55]、trials = 50、scenarios = [S120_4, S120_2]、study = C
- 粗評価は **2022だけ**（coarse gate）。通過した上位だけ `build_year_scorecard.py` で 2020/21/22 採点
- 成果物イメージ: `candidate_pool.csv`（scenario_id, seed, best_value_train, median_2022, win_rate_2022, p10_2022, params_hash, result_json_path）

**必須ログ項目（比較に必要）**
- [ ] scenario_id / seed / study_type
- [ ] params_hash
- [ ] 2022のみ: median, p10, win_rate
- [ ] 銘柄集合メタ: sector_HHI, sector_cap_hit_rate, pool→final入替率, final12_overlap（前候補比）

**目的関数 multi-year を Optuna 内に入れるタイミング**
- **いまは外部スコアカード選抜が正解**。内製のメリットが出るのは、coarse gate を通る候補が「ある程度」出て、Gate3-pre 近傍の候補が複数見つかった段階。地雷谷が普通に出る現状で内製すると「全滅確認が3倍」になりやすい。

**2022だけ評価する軽量モード**
- Phase A で「3年スコアカードは通過候補だけに絞る」ため、**`build_year_scorecard.py --years 2022`** で 2022 のみ採点するモードを用意すると効く（実装済み）。**`--years 2021`** で 2021 単年も可能（Stage1 用）。

### 結論：次にやる順番 TOP5（S120_4 追記後）

1. **coarse gate を2段階化**し、S120_4型（2022だけマシだが 2020/21 崩壊）を早めに弾く  
   - **Stage0**：2022のみ（地雷除去）  
   - **Stage1**：2021のみ（「深掘りする価値」判定）
2. **Study C は「best だけ」ではなく「上位 K 候補」を回収**してスコアカードに送る（best-of-run 偏重をやめる）
3. **シナリオ探索は cap=3 を最優先**（S120_2 は 2022 が死ぬ、S120_4 は 2020/21 が死ぬ → 中間が必要）
4. **候補の「銘柄集合が変わっているか」を監視**（overlap / HHI / pool→final 入替率）。変わらない探索は打ち切り
5. **停止条件（仕様変更判断）を明文化**：一定 trial 回して Gate3-pre 合格が 0 なら、探索ではなく戦略仕様（特徴量/制約/リスク制御）を増やす

**現状スコアカードの整理（パターン比較）**

| 候補 | scenario | 2020 median/win | 2021 median/win | 2022 median/win | 最悪年 | パターン | コメント |
|------|----------|----------------|-----------------|-----------------|--------|----------|----------|
| A_local 132836 | (固定) | -2.88/0.00 | -2.16/0.25 | +6.40/1.00 | -2.88 | 2022だけ勝つ谷 | 良い谷だがロバスト性不足 |
| A_local 194538 | (固定) | -2.54/0.00 | -1.08/0.42 | +6.92/1.00 | -2.54 | 2022だけ勝つ谷 | 2021が軽いがGate3は無理 |
| Study C 115413 | S120_2 | -2.58/0.33 | -3.25/0.33 | **-11.96/0.08** | -11.96 | 2022激負の地雷谷 | 2022で即死させたいタイプ |
| Study C 131248 | S120_4 | **-6.93/0.33** | **-6.04/0.08** | -2.27/0.42 | -6.93 | 2022はマシだが20/21崩壊 | 3年採点に回す価値は低い |

**含意**: cap=2（S120_2）だと 2020/21 はそこそこだが 2022 が死ぬ。cap=4（S120_4）だと 2022 はマシだが 2020/21 が深く死ぬ。→ **cap=3（中間）を早急に試す**（S120_3, S160_3）。

**採用判定ルール（2段階 coarse gate 更新案）**

| 段階 | 条件 | 目的 |
|------|------|------|
| **Stage0**（2022のみ） | median_2022 ≥ -5%, win_rate_2022 ≥ 0.20 | 地雷除去 |
| **Stage1**（2021のみ） | median_2021 ≥ -2%, win_rate_2021 ≥ 0.25 | S120_4型を3年採点前に弾く |
| **Gate3-pre** | median_2020≥-1%, median_2021≥-0.5%, win_rate_2020≥0.30, win_rate_2021≥0.40 | 探索用 |
| **Gate3** | worst_year_median≥0%, each_year_win_rate≥0.55 | 本採用 |

**シナリオ優先順位（この順で試す）**
1. **S120_3**（pool120, cap3）
2. **S160_3**（pool160, cap3）
3. **S160_2**
4. **S120_2**（地雷が出やすいので Stage0 で即死させる前提）
5. **S120_4**（20/21 崩壊が出たため優先度は下げ）

**Phase A-mini（最小バッチ）**: study=C, seeds=[11,22,33,44,55], trials=50, scenarios=**[S120_3, S160_3]**。Stage0 通過 → Stage1（2021のみ採点）通過 → 生き残りだけ 3年スコアカード。

**最短の論点**: **「cap=3×pool拡張」で「2022も死なず、2020/21も深掘り負けしない谷」が探索空間内に存在するか？** 出る → その周辺を増やして Gate3-pre→Gate3 へ。出ない → 戦略仕様の追加（レジーム耐性の特徴量/制約）に進む。

**解釈（良い谷 vs 悪い谷）**
- Study C は探索範囲が大きいため、**良い谷にも悪い谷にも行く**。A_local の best は 2022 で +6% 前後（＝2022レジーム寄りの谷）。今回の Study C 1本は 2022 で -11%（＝別の悪い谷）。→ **探索空間には「2022だけ強い谷」と「2022も弱い谷」が両方ある**。問いは「Study C で 2020/21 を殺さない谷に到達できる頻度」。
- ログ（2022 median -11.19%、勝率 1/12）は**地雷谷の存在が観測できた**ことで、Phase A（multi-start）継続の正当性が増した。

**目的関数 multi-year を内製するタイミング**
- 外部スコアカードで **Gate3-pre を通る候補が「ある程度」出てから**（例：500 trials で 5〜10個）。その段階で内製すると探索効率が上がる。逆に Gate3-pre がほぼゼロなら、内製は「全滅を3倍速で確認する」だけになりやすい。

---

## 確定している「原因の形」と残る論点

### 確定（前提として次工程に進んでOK）

- **コストは効いている**（0/25/50bpsで単調悪化、gross-net差分の観測）
- **2021は事故型ではなく恒常型**（前半に負が集中、業種寄与も広く負）
- **Core/Entry重みの微調整は効いていない**（アブレーションでほぼ同一）→ 主戦場は **プール形成/制約/レジーム耐性**

### 残る論点（次に潰すべき）

- **「2021で負ける」を避けるのに、いまの探索空間は十分な自由度があるか？**
- 目的関数を変えても **銘柄集合が変わらない**なら改善しない → **銘柄集合を変えるレバー**を増やすのが最短

### 年別スコアカードで示された事実（2026-02）

- 132836：2020 median **-2.88%** / 2021 median **-2.16%** / 2022 median +6.40%
- 194538：2020 median **-2.54%** / 2021 median **-1.08%** / 2022 median +6.92%
- **2020 win_rate が両方 0.00（0/12）** → 「たまたま」より「構造」寄りの強いシグナル
- **解釈**：いまの A_local 周辺の解は、2022レジーム（バリュー・景気敏感寄り）に強いが、2020/2021レジームに弱い「スタイル賭け」になっている可能性が高い

---

## 業種制約 vs 銘柄除外 vs 目的関数複数年化（優先順位）

| 施策 | 優先 | なぜ効く/効かない | 実装のコツ | 過適合リスク |
|------|------|-------------------|------------|-------------|
| **目的関数の複数年化**（worst-year/下振れ罰） | ★★★ | 「2022だけ強い」を最適化段階で排除 | まずはOptuna外のスコアカードで選抜→勝てたら目的関数に内製 | 低 |
| **業種制約（一般形）**：sector_cap_max/min_sectors/HHIペナルティ | ★★☆ | 2021の負けが業種偏りなら効く。「業種名の直指定」は危険 | **業種名を固定で罰しない**。分散の一般形で入れる | 中 |
| **銘柄除外（ブラックリスト）** | ★☆☆ | 再現性は出るが2021特化しがち。検証の自由度を奪う | 本番のリスク管理としては有効、探索には入れない | 高 |

> サービス業・小売業に「名指し制約」を入れるのは最終手段に寄せる。

---

## 原因候補 → 確認ログ → 判断基準（切り分け表）

| 原因候補 | 何が起きるとそう見える？ | 取るべき確認ログ | 判断基準（YES/NO） |
|----------|--------------------------|------------------|---------------------|
| **A. コストが未適用/単位バグ** | 0bpsと25bpsが完全一致 | gross_return, net_return, cost_total_pct, turnover | 差分が非ゼロならOK。差分が機械的に0なら要修正 |
| **B. turnover定義がゼロ** | costを掛けてるが turnover=0 で cost=0 | turnover_pct の定義・値（各rebalance） | turnoverが常に0なら、コストモデルを「エントリー固定コスト」へ変更 |
| **C. ベンチマーク整合ミス** | 年によってズレ | bench_price_start/end, bench_return, portfolio_return | 日付と指数種別が一致し、excess = port - bench が成立 |
| **D. 価格データ調整/欠損** | 年によってサンプルが落ちる | dropped_portfolios_count, drop_reason, dropped_codes | drop率が年で偏るなら欠損の扱いを再検討 |
| **E. 2021は「数本の大事故」** | 少数銘柄の寄与が極端に負 | contribution_by_code, Top/Bottom寄与 | 下位3銘柄で-80%寄与なら事故型 |
| **F. 2021は「広く恒常的に弱い」** | 多くのrebalanceで負、時期に集中 | rebalance_date別 annual_excess | **既に前半で負が連続**（8/11負、2〜7月全負）→レジーム型濃厚 |
| **G. Core/Entryは原因ではない** | アブレーション一致 | variant=core_only/entry_only/baseline | 既に差分ほぼゼロ → プール/制約/レジームが主戦場 |
| **H. セクターキャップが劣後銘柄を入れる** | capが頻繁にhit | sector_cap_hit_count, replaced_candidates_log | cap hit率が2021で高いなら再設計 |
| **I. フィルタでプールが歪む** | 2021だけ適格数が減る | n_universe → after_roe → after_liq → pool_size | pool_size<80 が2021で増えるならフィルタが原因 |
| **J. 探索が2022に都合よい山に寄る** | 2022強・2021負 | multi-yearスコアカード＋複数seed比較 | 現状、両候補が不合格 |

### 次フェーズ用（robust化で詰まる箇所）※A/Bは✅済み

| 原因候補 | 何が起きる？ | 追加で出すべきログ | 判断基準 |
|----------|--------------|-------------------|----------|
| **K. 探索空間が実質「同じ銘柄集合」しか出さない** | seed/目的関数を変えても選定銘柄がほぼ同じ | holding_overlap_rate, top80_overlap_rate, final12_overlap_rate | final12重複率>70%なら自由度不足 |
| **L. セクターキャップ(4)が緩すぎて集中が残る** | 12銘柄で1業種最大4=33%は大きい | sector_counts_final, HHI = Σ(count/12)^2 | HHIが高い年で悪化→capの探索が必要 |
| **M. pool_size=80 が小さくEntryで入れ替わらない** | top80が似すぎて最終12も似る | pool_size可変で pool→final 入替率をログ | 入替率が常に低いならpool拡張が必要 |
| **N. ROE/流動性フィルタが2021だけ歪む** | 2021だけ適格数や業種分布が変 | after_roe/after_liq/pool_size を年別集計 | 2021だけ急変するならフィルタが原因 |
| **O. 24M固定の評価がレジーム変化に弱い** | 2021H1だけ悪くH2で回復など | rebalance_date別annual_excess＋半期別集計 | 半年単位で符号が変わるならレジーム耐性が課題 |

### 次の探索フェーズ用（候補が出る空間を作るための判定ログ）

| 失敗モード | 何が起きている？ | 必須ログ（1候補あたり） | 判断基準 |
|------------|------------------|-------------------------|----------|
| 銘柄集合が変わらない | 目的関数/seedを変えても同じ銘柄 | final12_overlap_rate, pool_overlap_rate | overlap>70%ならレバー不足 |
| セクター集中が残る | 2022は海運で勝つが他年で負 | sector_counts_final, HHI, sector_cap_hit_count | HHI高＆負の年→sector_cap_maxを下げる |
| フィルタが歪む | 2020/2021だけ適格が偏る | n_universe→after_roe→after_liq→pool_size_actual | 2020/21でpool不足→フィルタ見直し |
| 探索が局所に閉じる | A_localで似た候補しか出ない | study_type別候補分布、params_hash重複率 | A_local重複率高→Study Cへ |
| 年別で勝てない | 2020/21 win_rateが極端に低い | median/p10/win_rate 年別 | 2020 win_rate=0 が続くなら仕様変更が必要 |

---

## 最短の実行手順

### 0) コスト効き確認（最優先）

```powershell
# cost 0 / 25 / 50 で同一paramsを評価
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 --end 2024-12-31 --study-type A_local `
  --n-trials 1 --train-end-date 2021-12-30 --as-of-date 2024-12-31 `
  --horizon-months 24 --objective-type mean --n-jobs 1 --bt-workers 1 `
  --cost-bps 0 --initial-params-json optimization_result_optimization_longterm_studyA_local_20260201_132836.json

# cost-bps を 25, 50 に変えて同様に実行
```

**必須ログ項目**
- [ ] cost_bps（入力値）
- [ ] turnover_pct
- [ ] gross_cumulative_return_pct / net_cumulative_return_pct
- [ ] gross_annual_return_pct / net_annual_return_pct
- [ ] net - gross の差分（bps換算）

**判定**: costを上げると net が単調悪化。0→50bpsで差分が非ゼロ。

---

### 1) 2021寄与分解

```powershell
# 寄与分解スクリプト（銘柄別・業種別）
python scripts/analyze_2021_contribution.py --params-json optimization_result_optimization_longterm_studyA_local_20260201_132836.json --cost-bps 25

# または
.\scripts\run_2021_contribution.ps1
```

**出力**: リバランス日別年率超過、負け月の銘柄別寄与Bottom5/Top5、業種別合計寄与、事故型 vs 恒常型の判定

```powershell
# （参考）2021評価（optimize_longterm経由）
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 --end 2023-12-31 --study-type A_local `
  --n-trials 1 --train-end-date 2020-12-30 --as-of-date 2023-12-31 `
  --horizon-months 24 --objective-type mean --n-jobs 1 --bt-workers 4 `
  --cost-bps 25 --initial-params-json optimization_result_optimization_longterm_studyA_local_20260201_132836.json
```

**必須ログ項目**
- (i) リバランス日別: rebalance_date, pool_size, sector_cap_hit_count, annual_excess, top/bottom_contrib_codes
- (ii) 銘柄別寄与: code, weight, stock_return_24m, bench_return_24m, excess_component, sector
- (iii) 集計: 2021H1/H2 の median, win_rate、セクター別合算寄与

**判定**: 恒常型＝負が多数＋寄与が広く分散 / 事故型＝少数銘柄が支配

**✅ 2021寄与分解 実施済み（2025-02）**

| 項目 | 結果 |
|------|------|
| 判定 | **恒常型**（下位3銘柄の寄与割合 74.5% < 80%） |
| 負け月 | 8/11（73%） |
| 主な負の業種 | サービス業 -65.75%、小売業 -30.60%、情報･通信業 -13.83%、医薬品 -10.25% |
| 主な正の業種 | 海運業 +86.46%、電気機器 +11.14% |
| 繰り返し負の銘柄 | 2371/2412（サービス業）、3092（小売業）、4519（医薬品） |

**次の打ち手**: 業種制約（一般形）、目的関数の複数年化、銘柄除外は最後（安全弁）

---

### 2) Gate3：年別スコアカードの機械化（最優先）

**目的**: 候補paramsを年別に横並び採点し、「どのレバーが効くか」を定量化する。Optunaの目的関数に手を入れる前に実施。

#### Step 1) 2020/2021/2022 を同一paramsで年別評価（n_trials=1）

各年YのOOS評価は **train_end=Y-1年末**, **as_of=Y+2年末**（24M確保）。

**2020 test**（train=〜2019、test=2020）:
```powershell
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 --end 2022-12-30 --study-type A_local `
  --n-trials 1 --train-end-date 2019-12-30 --as-of-date 2022-12-30 `
  --horizon-months 24 --objective-type mean --n-jobs 1 --bt-workers 4 `
  --cost-bps 25 --initial-params-json <candidate.json>
```

**2021 test**（train=〜2020、test=2021）:
```powershell
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 --end 2023-12-31 --study-type A_local `
  --n-trials 1 --train-end-date 2020-12-30 --as-of-date 2023-12-31 `
  --horizon-months 24 --objective-type mean --n-jobs 1 --bt-workers 4 `
  --cost-bps 25 --initial-params-json <candidate.json>
```

**2022 test**（train=〜2021、test=2022）:
```powershell
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 --end 2024-12-31 --study-type A_local `
  --n-trials 1 --train-end-date 2021-12-30 --as-of-date 2024-12-31 `
  --horizon-months 24 --objective-type mean --n-jobs 1 --bt-workers 4 `
  --cost-bps 25 --initial-params-json <candidate.json>
```

#### Step 2) スコアカードCSVの列定義

| 列 | 説明 |
|----|------|
| candidate_id（params_hash） | 候補の一意識別 |
| year | 2020 / 2021 / 2022 |
| median_annual_excess_return_pct | 必須 |
| trimmed_mean_annual_excess_return_pct | 可能なら |
| p10_annual_excess_return_pct | 必須 |
| win_rate | 必須 |
| sector_HHI | 可能なら |
| sector_cap_hit_rate | 可能なら |
| final12_overlap_vs_prev_month | 回転の代理 |
| turnover_pct / cost_drag_pct | 既出ならそのまま |

→ **年別スコアカードの自動化**（候補JSON群を走査→3年評価をキック→集計CSV吐き）が「次の1週間で最もリターンが大きい実装」。  
**スクリプト**: `scripts/build_year_scorecard.py`（`--candidates` または `--candidates-dir` で候補を指定し、`--out scorecard_year.csv` で出力）。

---

### 3) 目的関数を multi-year 化

**最短で効く順（実装コストと過適合耐性のバランス）**

1. **まずは Optuna 外の採用ルールで maximin 選抜**（コード改修ほぼゼロ）
   - `score(candidate) = min_{y∈{2020,2021,2022}} median_y`
   - tie-break: `median_all` や `p10_all`
2. **次に Optuna 目的関数へ内製**
   - 既存の `lambda_penalty * max(0, -p10)` に加え、`lambda_worst * max(0, -worst_year_median)` を足す
3. **さらに安定化：分散制約（一般形）**
   - 例: `penalty_sector = λhhi * max(0, HHI - HHI_target)` または `sector_cap_max` を探索変数（2〜4）

**従来の式（参考）**
- Penalty: `score = median_all - λ1*max(0, -worst_year_median) - λ2*max(0, -p10_all)`
- Maximin: `score = min_y median_y + 0.1*median_all`
- Prune: `worst_year_median < 0` なら prune

---

### 4) robust候補探索設計（Phase A→B→C）

**フェーズA：候補生成（多様性が最重要）**
- **Study を混ぜる**: A_local だけでなく **B と C** も混ぜて「違う山」を確保
- **multi-start**: seed を 5〜10
- **budget 固定**: 各 (seed, study) で n_trials=30〜50（まず候補数を作る）
- **成果物**: `results/raw/<study>/<seed>/optimization_result_*.json` を保存。候補抽出は test(2022) 上位 K ＋ params_hash で重複排除

**フェーズB：精密採点（年別スコアカード）**
- フェーズAの上位候補（例: 20〜50個）だけに、2020/2021/2022 の n_trials=1 評価を実施
- ここで初めて **multi-year 採用ルール** を適用

**フェーズC：局所改善**
- スコアカード上位3候補だけ、A_local で局所探索（seed 複数）
- **Gate3 合格を崩す方向なら棄却**（「2022だけ上がる」を禁止）

（従来の coarse→fine: リバランス隔月/四半期、formation年固定などは必要に応じて併用）

#### Phase A：Study C（＋B）で候補生成（multi-start、小さく）

まずは「軽いバッチ」で分布を見る。

```powershell
$seeds   = @(11, 22, 33, 44, 55)
$studies = @("C", "B")   # まずはC優先、余力でB
$trials  = 50

foreach ($study in $studies) {
  foreach ($seed in $seeds) {
    python -m omanta_3rd.jobs.optimize_longterm `
      --start 2018-01-31 --end 2024-12-31 `
      --study-type $study `
      --n-trials $trials `
      --train-end-date 2021-12-30 --as-of-date 2024-12-31 `
      --horizon-months 24 `
      --objective-type median `
      --lambda-penalty 0.50 `
      --random-seed $seed `
      --n-jobs 1 --bt-workers 8
  }
}
```

#### Phase C：銘柄集合レバーを CLI 固定シナリオで回す

いきなり Optuna 探索に入れず、**CLI 固定（シナリオ）**で回す。

| scenario_id | pool_size | sector_cap_max |
|-------------|-----------|----------------|
| S1 | 80 | 4 |
| S2 | 120 | 4 |
| S3 | 120 | 3 |
| S4 | 120 | 2 |
| S5 | 160 | 3 |
| S6 | 160 | 2 |

**ログ必須**：`scenario_id` をすべての出力に刻む（`--pool-size`, `--sector-cap-max` を CLI で渡す前提で、JSON に scenario_id を記録）。

**実装パッチ案**: `docs/implementation_patch_pool_sector.md`（関数名・引数・ログキーまで記載）

#### 銘柄集合レバーの推奨レンジ（最初の試行）

| レバー | 推奨レンジ | 理由 | 過適合を抑える工夫 |
|--------|-----------|------|-------------------|
| sector_cap_max | {2, 3, 4} | 12銘柄で cap=4 は最大33%/業種。cap=2 にすると強制分散が効く | 連続値にせず **3値だけ** |
| pool_size | {60, 80, 120, 160} | pool80固定だと「入替が起きない」ことがある。pool を増やすと Entry が効きやすい | まずは **4値**。後で絞る |
| roe_min | 0.00〜0.20（Study C/B 側） | 2021で負の業種が多いなら、質で切れる可能性 | 目的関数を multi-year にして暴れを抑制 |
| liquidity_quantile_cut | 0.05〜0.30（まず） | 流動性を厳しくしすぎるとプールが歪む | 年別で pool_size 不足が起きないかログ監視 |

**シナリオ優先順位（S120_4 追記後・cap=3 最優先）**: **S120_3** → **S160_3** → S160_2 → S120_2（Stage0 で即死前提）→ S120_4（優先度下げ）。上記「結論 TOP5（S120_4 追記後）」の表を参照。

**原因候補 → 確認ログ → 判断基準（S120_4型を早期に弾く設計）**

| 失敗タイプ | 兆候（観測） | 追加ログ | 早期に弾く判断基準 |
|------------|--------------|----------|---------------------|
| 地雷谷 | 2022 median -11.96 / win 0.08 | 2022のみ: median/p10/win | 2022 median < -5 または win < 0.20 → 即死 |
| S120_4型（2022だけマシ） | 2022は -2.27/win0.42 でも 2020/21 が -6% | 2021のみ: median/win | 2021 median < -2 または win < 0.25 → 3年採点に回さない |
| 銘柄集合が変わらない | A_local 近傍で同じ | overlap, HHI, pool→final入替率 | overlap 高止まりならレバー追加優先 |

**2段階 coarse gate の実行フロー**
- **Step 2（Stage0）**: 2022のみで median≥-5%, win_rate≥0.20 を確認 → 地雷を捨てる
- **Step 3（Stage1）**: Stage0 通過候補だけ `build_year_scorecard.py --years 2021` で 2021 単年採点。median_2021≥-2%, win_rate_2021≥0.25 で S120_4型を弾く
- **Step 4**: Stage0+Stage1 通過候補だけ 3年スコアカード（2020/2021/2022）で本採点。maximin（worst_year_median）で採用候補を選ぶ

**必要ログ項目（optimize_longterm trial ごと）**: scenario_id, seed, trial_id, params_hash, median_2022, p10_2022, win_rate_2022, selected_codes_digest, sector_HHI, sector_cap_hit_rate, pool_size_actual

**実装済み**: `optimize_longterm` 実行時に **`trials_log_{study_name}.jsonl`** を出力（各 trial 完了ごとに scenario_id, seed, trial_id, params_hash, median_2022, p10_2022, win_rate_2022, pool_size_actual を追記）。結果 JSON の `test_performance.by_year` に 2020/2021/2022 の median・win_rate を保存。**Phase A-mini 一括実行**: `python scripts/run_phase_a_mini.py`（S120_3 / S160_3 × 5 seed × 50 trials、`--trials` / `--seeds` で変更可）。

---

### 次に何を試すか（A→B→C：最短順）

**A. まず：今回の Study C 結果 JSON → 年別スコアカード**
- **目的**: この候補が「2022だけ死んでる」のか「2020/21も壊滅」なのかを確定
- **実行**: `python scripts/build_year_scorecard.py --candidates <studyC_result.json> --cost-bps 25 --out scorecard_studyC.csv`
- **必須ログ（scorecard）**: `median/p10/win_rate`（2020/21/22）、`fail_reason`、`scenario_id`、`study_type`
- **判定**: 2022だけ激負 → Entry/フィルタの方向性が逆寄り。全滅 → ROE/流動性/重みが極端でプール自体がダメ寄り

**B. 次：シナリオを変えて再実行（S120_4 → S120_2 → S160_2）**
- 80/4 が地雷でも 120/2 が救うことはあり得る。まず S120_4、次に S120_2、余力で S160_2
- 各シナリオで Gate3-pre の4条件と `worst_year_median` の改善度を確認

**C. Phase A 継続：seed×trial で候補集合を作る**
- **最短バッチ**: seeds=[11,22,33,44,55]、trials=50、study=C、scenarios=[S120_4, S120_2] → 合計 5×50×2=500 trials
- **ログ必須**: best_value（train）、test_2022_median、params_hash、scenario_id、seed
- スコアカード上で **maximin（worst_year_median）ランキング**を作り、上位5候補だけ Gate3（厳格）に進める

---

### 実行チェックリスト（漏れなく次に進む用）

**すぐやる（今回の Study C 1本に対して）**
- [ ] `build_year_scorecard.py <this_studyC_result.json>` 実行
- [ ] 2020/21/22 の `median/p10/win_rate` を記録
- [ ] `fail_reason` を確認（scorecard に自動出力済み）

**次のバッチ（cap=3 最優先）**
- [ ] Scenario **S120_3** で Study C：seed 22 / trials 50
- [ ] Scenario **S160_3** で Study C：seed 22 / trials 50
- [ ] Stage0（2022のみ）→ Stage1（`--years 2021`）→ 通過候補だけ 3年スコアカード

```powershell
# S120_3
python -m omanta_3rd.jobs.optimize_longterm --start 2018-01-31 --end 2024-12-31 --study-type C --n-trials 50 --pool-size 120 --sector-cap-max 3 --train-end-date 2021-12-30 --as-of-date 2024-12-31 --horizon-months 24 --cost-bps 25 --random-seed 22 --n-jobs 1 --bt-workers 8

# S160_3
python -m omanta_3rd.jobs.optimize_longterm --start 2018-01-31 --end 2024-12-31 --study-type C --n-trials 50 --pool-size 160 --sector-cap-max 3 --train-end-date 2021-12-30 --as-of-date 2024-12-31 --horizon-months 24 --cost-bps 25 --random-seed 22 --n-jobs 1 --bt-workers 8
```

**Phase A-mini（分布を見る）**
- [ ] seeds=[11,22,33,44,55] × trials=50 × scenarios=**[S120_3, S160_3]**
- [ ] Stage0 通過 → Stage1（`build_year_scorecard.py --years 2021`）通過 → 生き残りだけ 3年スコアカード
- [ ] scorecard 上で **maximin（worst_year_median）ランキング**を作り、上位5候補を Gate3（厳格）へ

---

## 本番ゲート設計

| Gate | 内容 | 状態 |
|------|------|------|
| **Gate0** | 決定性（seed固定、n_jobs=1、Train/Test/params完全一致） | ✅ PASS |
| **Gate1** | 到達ブレ（複数seedで候補集合→再評価で採用） | ⚠️ |
| **Gate2** | コスト感度（0/10/25/50bpsで net 単調悪化） | ✅ 検証済み（2025-02: 0/25/50bpsで単調悪化、gross-net一致、0→25で-0.26pt、0→50で-0.51pt） |
| **Gate3** | 別期間検証（2020/2021/2022）。cost=25bps の年別 median/p10/win_rate を必須採用条件に。「2021のような負け年」が出たら即落ち（maximin思想） | 要確認 |
| **Gate4** | 各 rebalance_date で selected_codes / weights をファイル出力（CSV/JSON）。portfolio_hash = sha256(rebalance_date + sorted(code,weight))。optimize と compare と prod で **hash 一致**（差が出たら即調査） | 要確認 |
| **Final** | 候補が Gate3/4 を通った**後**にだけ実行。実行時は git_sha / data_hash / params_hash / portfolio_hash を固定し保存。**2025ホールドアウトは1回だけ**、以降パラメータ変更禁止 | 温存 |

---

## 採用判定ルール（二段階化：探索を回すため）

いきなり `worst_year_median>=0` に固執すると探索が全部死ぬので、**pre-gate**を置く。

### Gate3-pre（探索用：まず候補を生かす）

- `median_2020 >= -1.0%`
- `median_2021 >= -0.5%`
- `win_rate_2020 >= 0.30`
- `win_rate_2021 >= 0.40`

### Gate3（本採用候補）

- `worst_year_median_excess >= 0.0%`
- `each_year_win_rate >= 0.55`
- `worst_year_p10_excess >= -2.0%`（推奨）

※今回の候補は Gate3 はもちろん、Gate3-pre も落ちる（2020 win_rate=0）。銘柄集合レバー追加＋Study C が必須。

---

## 採用判定ルール（強め版・最終）

目標: **「2021を二度と踏まない」** を最上位に置く（長期・等ウェイト・集中回避の思想に整合）。

### Pre-2025（2020/2021/2022、cost=25bps）

**必須（合否）**
- `worst_year_median_excess >= 0.0%`
- `each_year_win_rate >= 0.55`

**推奨（品質）**
- `overall_trimmed_mean_excess >= +2.0%`（期待水準に応じて調整）
- `worst_year_p10_excess >= -2.0%`
- `sector_HHI <= 0.18`（目安: 12銘柄で2銘柄/業種くらいの分散感）

### Gate4（整合）
- `portfolio_hash` 一致が必須（ズレたら採用不可）

### 2025ホールドアウト（最終）
- `median_excess >= 0.0%` かつ `win_rate >= 0.55`
- ここで OK でも **以降パラメータ変更禁止**

### コスト感度（Gate2）
- cost 増で net が悪化、0→50bps の差分が観測できる

### 実装整合
- git_sha, data_hash, cache_hash を固定

---

## 当たり仮説（優先度順）

1. **スコア（Core/Entry）の微調整は主因ではない**（アブレーション同一）
2. 主戦場は **プール形成（フィルタ・制約・セクター偏り）とレジーム耐性**
3. seed42/123の最良paramsは quality/size 寄りで、2021に沈むならレジーム不適合の可能性が高い

**寄与分解後の検討順**（2025-02 実施済み→恒常型確定）
- **業種制約**: サービス業・小売業のウェイト上限または上限強化
- **銘柄除外**: 2371, 2412, 3092 など継続負の銘柄の検討
- フィルタ（ROE/流動性）
- セクターキャップの発動頻度
- プール80→100等の緩和
- スタイル偏りの上限制約（soft penalty）
