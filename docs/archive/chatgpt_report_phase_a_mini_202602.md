# ChatGPT報告用：Phase A-mini 実行結果と2段階 coarse gate（2026-02）

以下の内容を ChatGPT に貼り付けて報告し、アドバイスを求めてください。

---

## 実施したこと（前回報告からの継続）

### 1. 2段階 coarse gate の設計と実装

- **Stage0（2022のみ）**: median_2022 ≥ -5%, win_rate_2022 ≥ 0.20 → 地雷谷を捨てる
- **Stage1（2021のみ）**: median_2021 ≥ -2%, win_rate_2021 ≥ 0.25 → S120_4型（2022だけマシだが2020/21崩壊）を3年採点前に弾く
- **build_year_scorecard.py**: `--years 2022` / `--years 2021` で単年採点可能。2021採点時に **stage1_discard** 列を出力（median_2021<-2 または win_rate_2021<0.25 なら "yes"）

### 2. Phase A-mini の実行

- **内容**: Study C、**S120_3**（pool=120, cap=3）と **S160_3**（pool=160, cap=3）を **5 seed（11, 22, 33, 44, 55）× 50 trials** で実行。計 **10 run**。
- **目的**: ロードマップの「cap=3 を最優先で試す」に沿い、2022 で死なない谷（Stage0 通過）がどれだけ出るかを確認。
- **実行方法**: `python scripts/run_phase_a_mini.py --n-jobs 1 --bt-workers 8`（ターミナルでフォアグラウンド実行）

### 3. 一括サマリ・Stage1 用スクリプト

- **summarize_phase_a_mini_stage0.py**: 複数の `optimization_result_*studyC*.json` を読み、Stage0 通過本数と通過 run（scenario_id, seed, median_2022, win_rate_2022）を一覧出力。
- **run_stage1_and_scorecard.ps1**: Stage0 通過 9 本の JSON に対して `build_year_scorecard.py --years 2021` を実行し、Stage1 用 CSV を出力する PowerShell スクリプト（要 DB）。

### 4. optimize_longterm のログ拡張

- 結果 JSON の **test_performance** に **by_year**（2020/2021/2022 の median, p10, win_rate）を保存。
- **trials_log_{study_name}.jsonl**: 各 trial 完了時に scenario_id, seed, trial_id, params_hash, median_2022, p10_2022, win_rate_2022, pool_size_actual を追記。
  - **既知の制約**: 現在、by_year は **学習期間（train_dates）のみ**から計算しているため、train_end=2021-12-30 のとき **2022 年は train に含まれず、trials_log の median_2022 / win_rate_2022 は常に null**。Stage0 の trial 別分布は、現状は best  trial の test_perf のみで確認可能。

---

## Phase A-mini 実行結果（Stage0 サマリ）

対象はプロジェクト内の **全 Study C 結果 JSON 35 件**（Phase A-mini の 10 本を含む）。同一条件で summarize_phase_a_mini_stage0.py を実行した結果です。

### 集計

| 項目 | 値 |
|------|-----|
| 対象 JSON 数 | 35 |
| **Stage0 通過本数** | **9** |
| Stage0 不合格 | 26 |
| 基準 | median_2022 ≥ -5.0%, win_rate_2022 ≥ 0.20 |

### Stage0 通過 run 一覧（9 本）

| scenario_id | seed | median_2022 | win_rate_2022 | 備考 |
|-------------|------|------------|---------------|------|
| - | 42 | 4.53% | 0.92 | 旧 Study C（pool/cap 未記録） |
| - | 42 | 0.11% | 0.50 | 旧 Study C |
| **S120_4** | 22 | -2.27% | 0.42 | S120_4型（2020/21 崩壊のため Stage1 で弾く想定） |
| **S120_3** | 22 | -0.87% | 0.50 | Phase A-mini |
| **S160_3** | 22 | -3.64% | 0.33 | Phase A-mini |
| S120_3 | 22 | -0.87% | 0.50 | Phase A-mini（別 run） |
| S160_3 | 22 | -3.64% | 0.33 | Phase A-mini（別 run） |
| S120_3 | 22 | -0.87% | 0.50 | Phase A-mini（別 run） |
| S160_3 | 22 | -3.64% | 0.33 | Phase A-mini（別 run） |

### Phase A-mini 10 本だけに絞った整理

| scenario | seed=11 | seed=22 | seed=33 | seed=44 | seed=55 |
|----------|---------|---------|---------|---------|---------|
| **S120_3** | 不合格（-12.65%, 0.08） | **通過**（-0.87%, 0.50） | 不合格（-12.08%, 0.08） | 不合格（-12.85%, 0.25） | 不合格（-12.47%, 0.17） |
| **S160_3** | 不合格（-8.13%, 0.17） | **通過**（-3.64%, 0.33） | 不合格（-11.29%, 0.00） | 不合格（-12.85%, 0.25） | 不合格（-7.39%, 0.08） |

- **通過しているのは seed=22 のみ**。S120_3 と S160_3 のいずれも seed=22 のときだけ 2022 テストが Stage0 基準を満たしている。
- seed=11, 33, 44, 55 は、cap=3 でも 2022 で大きく負けており、「地雷に近い谷」になっている。

### 所見

1. **cap=3（S120_3, S160_3）でも seed 依存が強い**。同じ 50 trials でも seed=22 のときだけ best が Stage0 を通り、他 4 seed では通過しない。
2. **S120_3 seed=22** が 2022 で最もマシ（median -0.87%, win 0.50）。S160_3 seed=22 は -3.64% / 0.33 で通過しているが、S120_3 よりは劣る。
3. **S120_4 seed=22**（131248）は Stage0 通過だが、既に 3 年スコアカードで **2020/2021 が -6% 前後・win_rate 0.08〜0.33** と分かっており、Stage1 で「3年採点に回さない」候補とする設計。
4. **最適化時の train と test（2022）のギャップ**: best value（train）が +9% 前後でも、test（2022）では -7% 程度になる run が多く、過学習または 2022 レジームとの不整合が顕著。

---

## 次の実施予定・フロー

1. **Stage1**: Stage0 通過 9 本の JSON を `build_year_scorecard.py --years 2021` で採点し、**stage1_discard** を確認。`yes` の候補は 3 年採点に回さない。
2. **3年スコアカード**: Stage0＋Stage1 通過候補だけを 2020/2021/2022 で採点し、maximin（worst_year_median）でランク付け。
3. **ロードマップ方針**: 一定 trial 回して Gate3-pre 合格が 0 なら、探索だけでなく **戦略仕様の見直し**（特徴量・制約・リジーム耐性）に進む。

---

## 判定基準の整理（ロードマップ準拠）

| ゲート | 条件 |
|--------|------|
| **Stage0** | median_2022 ≥ -5%, win_rate_2022 ≥ 0.20 |
| **Stage1** | median_2021 ≥ -2%, win_rate_2021 ≥ 0.25 |
| **Gate3-pre** | median_2020≥-1%, median_2021≥-0.5%, win_rate_2020≥0.30, win_rate_2021≥0.40 |
| **Gate3** | worst_year_median≥0%, each_year_win_rate≥0.55 |

---

## 質問（ChatGPTへ）

1. **Phase A-mini では seed=22 のときだけ Stage0 通過**（S120_3 / S160_3 とも）で、他 4 seed は 2022 で -7%〜-12% でした。**「cap=3 で 2022 がマシな谷」は seed に強く依存している**と見てよいでしょうか。次の一手として、**seed を増やして 22 以外でも通過が出るか確認する**のと、**まず seed=22 の通過候補を Stage1→3年スコアカードで掘り下げる**のと、どちらを優先すべきでしょうか。

2. **Stage1 で S120_4 型を弾いたあと**、残る候補（例: S120_3 seed=22, S160_3 seed=22）だけ 3 年採点すると、現状の傾向から **Gate3-pre や Gate3 にはまだ届かない**可能性が高いです。**「cap=3 × 複数 seed で Stage0 通過は出るが、Gate3-pre 合格はまだ 0」** という段階で、**探索をさらに続ける**（trials 増・シナリオ追加）のと、**戦略仕様の変更**（特徴量・業種制約・リジーム耐性）に早めに舵を切るのと、どのように判断するのがよいでしょうか。

3. **trials_log の median_2022 が null** なのは、by_year を train 期間だけで計算しているためです。**trial ごとに Stage0 を判定する**には、各 trial 完了後に test_dates で 2022 のみ評価する計算が 1 回ずつ追加になります。**計算コストを増やしてまで trial 別 Stage0 をログに持つ**価値はありますか。それとも、**run 単位で best の test_perf だけ Stage0 判定に使う**現状の運用で十分でしょうか。

4. **S120_3 seed=22**（median_2022 -0.87%, win 0.50）を、Stage1 通過後に 3 年スコアカードで見たとき、**2020/2021 がどの程度なら「Gate3-pre に届く可能性がある」**と解釈すべきか、目安（例: median_2020/2021 が -1% 以内、win_rate 0.3 以上など）の考え方を教えてください。

---

## 参考：現在の設定

- **投資ホライズン**: 24 ヶ月
- **コスト**: 25 bps
- **train_end_date**: 2021-12-30、**as_of_date**: 2024-12-31
- **テスト期間**: 2022 年のリバランス日 12 回 → 2024 年末まで評価
- **探索**: Study C。CLI で `--pool-size`, `--sector-cap-max` を指定（シナリオ: S120_3=120/3, S160_3=160/3 など）
- **目的関数**: mean または median（年率超過リターン、学習期間のみ）
