# アルゴリズム ステップバイステップ学習ガイド

現状のアルゴリズムを「データの流れ」に沿って、ステップごとに理解するための資料です。  
各ステップは短く区切っているので、順に読んでいけば全体像が掴めます。

**参照**：アーキテクチャ・レイヤー・制約は **CLAUDE.md**、実運用最適化は **docs/5DAY_PRODUCTION_OPTIMIZATION_PLAN.md** と **scripts/run_production_optimization.ps1** を参照。

---

## Step 0：全体像（1枚で把握）

アルゴリズムは **4つのブロック** でつながっています。

```
[1] データ取り込み     →  [2] 特徴量・スコア計算  →  [3] 選定  →  [4] 評価・最適化
     J-Quants API            prepare_features          run_strategy    evaluate_portfolio
     ↓                        ↓                         ↓               optimize_strategy
     listed_info,              features_monthly          portfolio_      指標・目的関数
     prices_daily,             (core_score_ref,           snapshots
     fins_statements            entry_score_ref)
```

- **固定しているもの**：銘柄の「良さ」の**下位スコア**（core_score_ref, entry_score_ref）の計算式（ScoreProfile）。
- **探索しているもの**：そのスコアを**どう混ぜて・何本選ぶか**（PolicyParams：entry_share, top_n, sector_cap など）。月次リバランス型の本命最適化（**optimize_timeseries**）では StrategyParams と EntryScoreParams も Optuna で探索する。

まずは「データ → 特徴量 → スコア → 選定 → 評価」の順で進む、とだけ押さえておけば十分です。**先読み防止**：全クエリで `disclosed_date <= rebalance_date` または `date <= as_of_date` を付け、`as_of_date` は必須で渡す（CLAUDE.md）。

---

## Step 1：データの入口（何を読んでいるか）

### 1.1 元データはどこから来るか

- **銘柄情報・日足・財務・指数** は **J-Quants API** から取得し、SQLite に保存します。
- 保存先テーブル：`listed_info`（銘柄属性）, `prices_daily`（日足）, `fins_statements`（財務）, `index_daily`（TOPIX 等）。

### 1.2 アルゴリズムが「読む」テーブル

選定やバックテストのとき、主に次のデータを使います。

| テーブル | 中身（イメージ） |
|----------|------------------|
| listed_info | 銘柄コード・市場・セクター（33業種） |
| prices_daily | 日ごとの始値・終値・出来高・売買代金・調整係数 |
| fins_statements | 開示日・実績（利益・純資産等）・予想（営業利益・利益等）・株数 |
| index_daily | TOPIX の日次（超過リターン計算用） |
| features_monthly | **月末時点の「特徴量」と「スコア」**（後述） |

### 1.3 まとめ

- アルゴリズムの**入力**は、API で取り込んだ上記テーブルと、その上に載る **features_monthly**（特徴量＋スコア）です。
- **prepare_features** が、raw データから features_monthly を**作って書き込む**役割です。

---

## Step 2：特徴量とは何か（数字の意味）

「特徴量」は、**銘柄ごと・月末時点で計算した指標**です。  
選定やスコア計算の「材料」になります。

### 2.1 財務まわり

| 指標 | 意味（イメージ） |
|------|------------------|
| ROE | 当期純利益 ÷ 純資産（収益性） |
| roe_trend | 現在の ROE と過去の平均 ROE の差（改善/悪化） |
| PER / PBR / Forward PER | 株価 ÷ 1株あたり利益 or 純資産 or 予想利益（割安さ） |
| op_growth / profit_growth | 予想÷実績 − 1（成長率のイメージ） |
| record_high_forecast_flag | 予想営業利益が過去最高かどうか（0/1） |

これらは **fins_statements** と **prices_daily** などから計算されます。

### 2.2 テクニカル（エントリー用）

- **RSI**：20/60/90日など、複数期間を計算し「一番強いもの」を採用。
- **BB Z-score**：(価格 − 移動平均) ÷ 標準偏差。20/60/90日など。
- これらを **bb_weight / rsi_weight** で混ぜて **entry_score** の元になるスコアを作ります（0〜1に clip）。

### 2.3 その他

- **liquidity_60d**：直近 60 営業日の平均売買代金（流動性）。
- **market_cap**：価格 × 補正後株数（時価総額の推定）。

### 2.4 まとめ

- 特徴量 = **財務・テクニカル・流動性・時価** などの「銘柄の属性を表す数字」。
- これらを **ScoreProfile の重み** で組み合わせて、**core_score** と **entry_score** が計算されます（Step 3 で扱います）。

---

## Step 3：スコアの2層（何を固定し、何をいじるか）

スコアは **2段階** で決まります。

### 3.1 下位スコア（固定：ScoreProfile）

**ScoreProfile** は「式を決めるパラメータ」で、**いじらない（凍結）** とします。

- **core_score（core_score_ref）**  
  次のような**サブスコア**を、決まった重みで足し算したもの：
  - quality（ROE のランク）
  - value（Forward PER / PBR の「割安さ」のランク）
  - growth（成長率のランク）
  - record_high（過去最高予想フラグ）
  - size（時価のランク）  
  重みは `w_quality`, `w_value`, `w_growth`, `w_record_high`, `w_size`, `w_forward_per`, `w_pbr` など（ScoreProfile で固定）。

- **entry_score（entry_score_ref）**  
  RSI と BB Z-score を、決まった **bb_weight / rsi_weight** で混ぜて 0〜1 にしたもの。  
  パラメータは `rsi_base`, `rsi_max`, `bb_z_base`, `bb_z_max`, `bb_weight`, `rsi_weight`（ScoreProfile で固定）。

実際の計算は **longterm_run.build_features** 系で行われ、**prepare_features** がその結果を `features_monthly` に **core_score_ref / entry_score_ref** として保存します。

### 3.2 上位スコア（探索：PolicyParams）

**PolicyParams** は「選定ルール」用のパラメータで、**最適化（Optuna）が探索**します。

- **core_ref_pct**：その日の銘柄全体で、core_score_ref の**パーセンタイル（0〜1）**。
- **entry_ref_pct**：同様に、entry_score_ref の**パーセンタイル（0〜1）**。
- **total_score** の式：
  ```text
  total_score = (1 − entry_share) × core_ref_pct + entry_share × entry_ref_pct
  ```
  - **entry_share**：0〜0.35 程度。「ファンダ」と「エントリー（テクニカル）」をどう混ぜるかを決めます。

この計算は **score_candidates**（`strategy/scoring_engine.py`）で行われ、DB は書きません（純粋関数）。

### 3.3 まとめ

- **ScoreProfile**：core / entry の**中身の式**を固定。
- **PolicyParams**：core と entry を **entry_share** で混ぜて **total_score** にし、さらに **top_n / sector_cap / liquidity_floor_q / rebalance_buffer** などで「何本・どう選ぶか」を決める。

---

## Step 4：選定の流れ（どの順で絞り込むか）

**select_portfolio**（`strategy/policy.py`）が、**total_score の付いた DataFrame** から「今月のポートフォリオ」を決めます。

### 4.1 手順（順番が大事）

1. **流動性フィルタ**  
   `liquidity_60d` が、全銘柄の **liquidity_floor_q 分位** 以上だけ残す。
2. **ROE フィルタ**  
   特徴量計算側（prepare_features / build_features）で、**roe_min** 以上だけにしている想定。選定関数側では必要なら roe 列があれば roe_min で切る（現状は主に liquidity と total_score を使用）。
3. **total_score でソート**  
   降順（スコアが高いほど上）。
4. **セクター上限**  
   33業種ごとに、**最大 sector_cap 銘柄**まで。これを超える業種はそれ以上は採用しない。
5. **rebalance_buffer**  
   前回保有していた銘柄を、**ランクで最大 rebalance_buffer 個まで優先**して残す（入れ替えを穏やかにする）。
6. **top_n**  
   上から **top_n 本** を採用。  
   重みは **等加重**（各 1/top_n）。

### 4.2 入力・出力のイメージ

- **入力**：`score_candidates` の戻り値（`total_score`, `sector33`, `liquidity_60d`, `code` などを持つ DataFrame）と、**PolicyParams**・**rebalance_date**・**前回ポートフォリオ（あれば）**。
- **出力**：`rebalance_date`, `code`, `weight`, `rank`, `total_score`, `action` などを持つ「今月のポートフォリオ」の DataFrame。

### 4.3 まとめ

選定は **「流動性で切る → total_score で並べる → セクター上限と buffer をかけながら上から top_n 本取る」** という流れです。

---

## Step 5：バックテスト・評価の考え方

**evaluate_portfolio**（`backtest/evaluator.py`）が、**リバランス日ごとのポートフォリオ**を受け取り、時系列リターンと指標を計算します。

### 5.1 売買のタイミング（実運用に合わせる）

- **売却**：リバランス日（月末）の**始値**で売る。
- **購入**：**翌月の初回営業日の始値**で買う。
- 1期間のリターンは **「前回の購入始値 → 今回の売却始値」** で計算します（月次 open → open）。

### 5.2 リターン計算の要点

- 銘柄ごと：**分割倍率で購入価格を補正**したうえで、`return = 売却価格/補正購入価格 − 1`。
- ポートフォリオ：各銘柄のリターンを **weight** で加重平均。欠損銘柄は除外して重みを再正規化。
- **TOPIX**：同じタイミングでリターンを計算し、**超過リターン = ポートフォリオ − TOPIX** とします。

### 5.3 主な指標

| 指標 | 意味 |
|------|------|
| sharpe_excess | 月次超過リターンの年率化シャープ（情報率に相当） |
| cagr | ポートフォリオの複利年率リターン |
| maxdd | 最大ドローダウン |
| calmar | CAGR ÷ MaxDD |
| avg_turnover | 期間ごとの「紙上の」ターンオーバー率の平均 |

### 5.4 目的関数（最適化で使う）

```text
objective = sharpe_excess − lambda_turnover × avg_turnover
```

- **lambda_turnover**：ターンオーバーをどれだけ嫌うか（PolicyParams の一つ）。  
  大きいほど「回転を抑えたポートフォリオ」が有利になります。

---

## Step 6：最適化で何を探しているか

**月次リバランス型**の本命は **optimize_timeseries** です。StrategyParams（core 重み・roe_min 等）と EntryScoreParams（RSI/BB 等）を Optuna で探索し、目的関数は **Sharpe_excess**（= 情報率）。取引コストは `--cost`（bps）で指定し、期間リターンから控除する。実運用向けの実行は **scripts/run_production_optimization.ps1**（200 trials, cost 20 bps）と **docs/5DAY_PRODUCTION_OPTIMIZATION_PLAN.md** を参照。

**optimize_strategy** は、**PolicyParams の 6 個**を Optuna で探索する別ルートです。

### 6.1 探索するパラメータ（PolicyParams）

| パラメータ | 意味・範囲の例 |
|------------|----------------|
| entry_share | core と entry の混ぜ具合（0〜0.35） |
| top_n | 採用銘柄数（8, 10, 12, 14, 16 など） |
| sector_cap | 1業種あたりの最大銘柄数（2〜4） |
| liquidity_floor_q | 流動性の下側何分位で切るか（0.3〜0.6） |
| rebalance_buffer | 前回保有を何ランクまで優先して残すか（0〜3） |
| lambda_turnover | 目的関数でのターンオーバーペナルティ（0〜0.2） |

### 6.2 やっていることの流れ

1. **prepare_features** で、評価期間の **features_monthly**（core_score_ref, entry_score_ref 含む）を用意。
2. 各リバランス日で **build_snapshot → score_candidates → select_portfolio** を呼び、**月ごとのポートフォリオ**を得る。
3. **evaluate_portfolio** で時系列リターン・sharpe_excess・avg_turnover などを計算し、**objective** を求める。
4. Optuna が **objective を最大化する PolicyParams** を探す。

ScoreProfile（core/entry の式）は**いじらない**ので、「同じランキングの上で、選び方だけ最適化する」形になっています。

---

## Step 7：実行の流れ（何をいつ動かすか）

### 7.1 初回 or スキーマ変更時

1. **init_db**：DB 作成・スキーマ適用。
2. **run_migration**：`migration_add_ref_scores_to_features.sql` と `migration_add_strategy_runs_tables.sql` を実行し、`features_monthly` に ref 列を追加、`strategy_runs` / `portfolio_snapshots` などを作成。

### 7.2 日常の流れ（月次リバランス型）

1. **データ更新**  
   `etl_update` または `update_all_data` で API から取得 → DB に保存。
2. **特徴量・スコアの準備**  
   `prepare_features --asof 月末日` または `--start / --end` で期間一括。  
   → **features_monthly** に **core_score_ref / entry_score_ref** が入る。
3. **選定**  
   `run_strategy --mode monthly --asof 月末日`（または `--start / --end`）。  
   → **build_snapshot → score_candidates → select_portfolio** が実行され、結果は **portfolio_snapshots** などに保存可能。
4. **最適化（パラメータを探したいとき）**  
   - **月次リバランス型（推奨）**：`optimize_timeseries --start 開始日 --end 終了日 --n-trials 数 --cost 20`。または **.\scripts\run_production_optimization.ps1**（実運用・5日間プランは docs/5DAY_PRODUCTION_OPTIMIZATION_PLAN.md）。  
   - **PolicyParams のみ**：`optimize_strategy --start 開始日 --end 終了日 --n-trials 数`。

### 7.3 コード上の対応関係

| 処理 | 主なコード |
|------|------------|
| スナップショット取得 | `strategy/snapshot.py` の `build_snapshot` |
| total_score 計算 | `strategy/scoring_engine.py` の `score_candidates` |
| 選定 | `strategy/policy.py` の `select_portfolio` |
| 評価 | `backtest/evaluator.py` の `evaluate_portfolio` |
| 特徴量・ref 計算 | `jobs/prepare_features.py`（内部で longterm_run.build_features を使用） |
| パラメータ定義 | `config/score_profile.py`（ScoreProfile, PolicyParams, get_v1_ref_score_profile, get_default_policy_params） |

---

## 次の一歩（自分で確かめる）

1. **1日分だけ動かす**  
   `prepare_features --asof 2024-12-31` のあと、DB の `features_monthly` で `core_score_ref` / `entry_score_ref` を眺める。
2. **選定だけ試す**  
   `run_strategy --mode monthly --asof 2024-12-31 --no-save-new` で、標準出力の `run_id` と選定結果を確認する。
3. **短い期間で最適化**  
   `optimize_timeseries --start 2023-01-01 --end 2023-12-31 --n-trials 5 --no-progress-window` で、Sharpe_excess がどう変わるかを見る。本格運用は **run_production_optimization.ps1** と **5DAY_PRODUCTION_OPTIMIZATION_PLAN.md** を参照。

### アーキテクチャ・テスト（CLAUDE.md と一致）

- **レイヤー**：依存は下位→上位の一方向（config → infra → ingest → features, market → strategy → backtest, portfolio, reporting → jobs）。逆方向の import は禁止。例外として `backtest/feature_cache.py` が `jobs/longterm_run` を**遅延 import** して循環を避けている。
- **DB**：接続は `connect_db()` のコンテキストマネージャのみ。パスは .env の `DB_PATH`（未設定時は data/db/jquants.sqlite 等）。
- **テスト**：88 件（tests/）。`backtest/performance.py` と `timeseries.py` は実 DB 依存が深くテストは未整備。

不明な用語や「この Step をもう少し詳しく」があれば、`algorithm_calculation_logic_mindmap.mm`、`system_configuration_mindmap.mm`、`CLAUDE.md` や `docs/V1_SLIM_IMPLEMENTATION_SUMMARY.md` とあわせて参照すると整理しやすいです。
