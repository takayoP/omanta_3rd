# ChatGPT再構成案の分析と追質問文

**作成日**: 2025-03-14  
**目的**: ChatGPTの「1つのランキングエンジン＋2ポリシー」案を分析し、必要に応じて追質問で移行マップを具体化するため。

---

## 1. ChatGPT案の要約

- **境界の引き直し**: 長期と月次を「別システム」ではなく、**1つのランキングエンジン**の上に**長期ポリシー**と**月次ポリシー**を載せる。
- **V1で最適化するのは月次だけ**: 長期は最適化対象から外し、「ランキング出力・買い増し候補・ウォッチリスト」の**出力モード**として残す。
- **中核を4つの純粋関数に**: `build_snapshot`, `score_candidates`, `select_portfolio`, `evaluate_portfolio` はDBを書かず・Optuna/CLIを知らず、`jobs/` はこれらを呼ぶだけにする。
- **longterm_run の分解**: `prepare_features`（特徴量生成）と `run_strategy --mode longterm|monthly`（選定実行）に分離。
- **最適化の探索空間を縮小**: V1では raw factor を全部最適化せず、**合成済みスコアの上位レイヤのみ**（例: w_core, w_entry, top_n, sector_cap, liquidity_floor, turnover_penalty など 6〜8 パラメータ）に抑える。
- **WFA**: 別の最適化系にせず、**昇格審査（approval gate）** としてのみ使う。
- **DB**: 運用スタイル別テーブルではなく **run 単位**（`strategy_runs`, `portfolio_snapshots`, `performance_series`, `performance_summary`, `live_holdings`）に寄せ、mode は列で表現。旧テーブルは読み取り専用で温存。

---

## 2. 分析：賛同できる点

| 観点 | 評価 |
|------|------|
| 1つのランキングエンジン＋2ポリシー | 長期/月次の「別コード」を減らし、境界を「policy」に寄せられる。Cursor案の「共通コア＋薄い2レイヤ」より一歩進んだ整理。 |
| 長期を最適化対象から外す | 現状の `optimize_longterm.py`（約2200行・固定ホライズン・study type）の複雑さをV1から外せる。長期の価値を「安定した候補・説明可能なランキング・買い増し材料」に置くのは現状の「手動判断寄り」と整合する。 |
| 中核4関数を純粋関数に | テスト容易性・重複削減・最適化ループの高速化（DB書かない）という効果が期待できる。現状は `longterm_run.build_features` がDB書き込みと密結合しており、ここを「読むだけ/返すだけ」に分離するのは妥当。 |
| longterm_run の分解 | 特徴量計算と選定の責務が混在している現状を解消できる。`prepare_features` と `run_strategy` の分離は、資料で指摘した「実行単位の巨大化」への直接的な対策になる。 |
| WFAを昇格審査に固定 | 「どれが本流か」の曖昧さを減らせる。optimize_timeseries で候補を探し、holdout/WFAで検証する流れが明確になる。 |
| DBを run 単位に | テーブル接頭辞による分裂（portfolio_monthly と monthly_rebalance_*）を解消し、mode 列で長期/月次を表現する設計は、拡張しやすい。旧テーブル温存は現実的。 |

---

## 3. 分析：確認・検討が必要な点

### 3.1 最適化パラメータの「2層」の扱い

**現状**:  
- `features_monthly` には **core_score** と **entry_score** が**1銘柄あたり1値**で格納されている。  
- これらは **longterm_run.build_features()** 内で、**StrategyParams**（w_quality, w_value, w_growth, w_record_high, w_size, w_forward_per, w_pbr, roe_min, liquidity_quantile_cut, sector_cap, pool_size 等）と **EntryScoreParams**（rsi_base, rsi_max, bb_z_base, bb_z_max, bb_weight, rsi_weight 等）を使って**その場で計算**されている。  
- **optimize_timeseries** と **optimize_longterm** は、いずれも **この下位レイヤ（StrategyParams / EntryScoreParams）を Optuna で探索**している。つまり「既に格納された core_score/entry_score に重みをかける」のではなく、「パラメータを変えて core_score/entry_score を再計算し、その結果で選定」している。

**ChatGPT案**:  
- V1 では **合成済みスコアの上位レイヤだけ最適化**（例: w_core, w_entry, top_n, sector_cap, liquidity_floor, turnover_penalty）。  
- 式の例: `total_score = w_core * core_score + w_entry * entry_score - turnover_penalty * turnover_proxy`

**ギャップ**:  
- 現状をそのまま「w_core, w_entry だけ最適化」にするには、**core_score と entry_score を「固定された式」で事前に計算**する必要がある。  
- つまり **(a) StrategyParams / EntryScoreParams をV1では固定（デフォルト or 手動設定）** し、(b) **features_monthly に core_score / entry_score をその固定式で埋める**、(c) **最適化は w_core, w_entry, top_n, sector_cap 等だけ**、という2層構造になる。  
- これは設計として一貫しているが、**現行の「下位パラメータまで全部 Optuna で探索」からは変更**になる。移行時には「V1で固定するパラメータの一覧」と「固定値の決め方（デフォルト / 最後の最適化結果 / 手動）」を決める必要がある。

### 3.2 スコア計算の「単一の真実」の現状

- **strategy/scoring.py**: `calculate_core_score(conn, code, as_of_date)` が存在するが、**config は StrategyConfig（config/strategy.py）** であり、**longterm_run の StrategyParams（w_quality 等）とは別体系**。  
- **longterm_run**: `build_features()` 内で **StrategyParams / EntryScoreParams** に基づき core_score / entry_score を計算し、DataFrame でまとめて features_monthly に保存。  
- つまり **「core_score を決めるロジック」が少なくとも2経路**（strategy/scoring + longterm_run 内）存在する。ChatGPTの「単一の真実」を実現するには、**どちらか一方に寄せるか、あるいは「純粋関数版」を新設して両方から呼ぶ**形にする必要がある。

### 3.3 DB 移行と既存参照

- 現状、**portfolio_monthly** は longterm_run（保存・削除）、backtest/performance（読取）、batch_longterm_run、compare_regime_switching、strategy/select 等で参照されている。  
- **monthly_rebalance_*** 系は月次リバランス用の確定結果・候補パフォーマンス等。  
- 新スキーマ（strategy_runs, portfolio_snapshots, performance_series, performance_summary, live_holdings）を導入する場合、**既存コードが参照しているテーブル・カラム**との対応表と、**段階的移行手順**（まず新 run だけ新テーブルに書き、旧コードは旧テーブル読取のままにする等）があるとよい。

### 3.4 prepare_features と build_snapshot の役割分担

- **prepare_features**: 「特徴量を計算し、features_monthly に保存する」ジョブ（現状の longterm_run の特徴量計算部分に相当）。  
- **build_snapshot(asof) -> DataFrame**: ChatGPT案では「DBを書かない」純粋関数。ここは **「指定日の features_monthly（＋必要なら価格等）を読んで DataFrame で返す」** という意味と解釈できる。  
- 用語の対応: **prepare_features** = features_monthly の**更新**（ETL的）、**build_snapshot** = その**1日分の読出し**（スコア・選定の入力）。この役割分担を追質問で明示してもらうと、実装時のぶれが減る。

### 3.5 legacy 化した場合の依存関係

- **compare_lambda_penalties.py** は **optimize_longterm** の結果（test_dates 等）を利用している。  
- **optimize_longterm** を mainline から外して legacy に移すと、compare_lambda_penalties も legacy に含めるか、あるいは「長期の評価」を別の軽量スクリプト（固定パラメータで train/test 評価だけ）に置き換える必要がある。

---

## 4. 結論：追質問で揃えたいこと

1. **V1の最適化パラメータの具体リスト**  
   - 「w_core, w_entry, top_n, sector_cap, liquidity_floor, turnover_penalty 等 6〜8 個」について、**現行の StrategyParams / EntryScoreParams のどれを固定し、どれをV1で探索するか**を一覧で欲しい。  
   - また、**core_score / entry_score のV1での固定式**を、現行の longterm_run の計算式と対応づけた形で書いてもらえると、実装時に迷わない。

2. **現行ファイル→新ファイルの移行マップ**  
   - 「現行のどのファイル（または関数）が、新構成のどのモジュール/コマンドに移るか」を表形式で欲しい。  
   - 特に: longterm_run.py, optimize_timeseries.py, optimize_longterm.py, backtest/performance, strategy/select.py, strategy/scoring.py の扱い。

3. **DB: 現行テーブル→新テーブルの対応と移行順序**  
   - 現行で実際に使っているテーブル・主なカラムを添えたうえで、**strategy_runs / portfolio_snapshots / performance_series / performance_summary / live_holdings** との対応と、**まずどこから書き始めるか**（例: 新規 run のみ新テーブル、既存は旧テーブル読取のまま）を文章化してほしい。

4. **run_strategy の入出力とバッチ**  
   - `run_strategy --mode monthly --asof 2024-01-31` は「1リバランス日だけ」、`--start / --end` を付けた場合は「期間内の全リバランス日」という理解でよいか。  
   - 最適化（optimize_strategy）は、内部で「複数日について run_strategy 相当を呼び、evaluate_portfolio で指標を集約する」ループになる、という理解でよいか。

5. **長期「出力モード」の具体的アウトプット**  
   - 長期ポリシーで出す「買い増し候補・add候補・watchlist・rank変化・スコア内訳」が、**どの形式で出るか**（DBのどのテーブル／JSON／CSV／レポート）を一文でよいので明確にしてほしい。

---

## 5. ChatGPTへの追質問文（コピー用）

以下をそのまま ChatGPT に貼り、必要なら「読み込んだ資料」として **現状システム構成概要** と **Cursor的な最小構成へのスリム化アイデア** を再度渡してよい。

---

### 添付する前提情報（必要に応じて要約して渡す）

- **現状の最適化パラメータ**:  
  - **StrategyParams**（longterm_run 内）: target_min/max, pool_size, roe_min, liquidity_quantile_cut, sector_cap, w_quality, w_value, w_growth, w_record_high, w_size, w_forward_per, w_pbr, use_entry_score, (EntryScoreParams の各項目).  
  - **EntryScoreParams**（optimize.py 等）: rsi_base, rsi_max, bb_z_base, bb_z_max, bb_weight, rsi_weight.  
  - 現在、optimize_timeseries と optimize_longterm は **これらを Optuna で探索**しており、**features_monthly の core_score/entry_score は「あるパラメータセットで計算した結果」が保存されている**状態。最適化時はパラメータを変えてスコアをその場で再計算している。

- **現状のDB利用**:  
  - **共通**: listed_info, prices_daily, fins_statements, features_monthly（as_of_date, code, core_score, entry_score, sector33, liquidity_60d, market_cap, per, pbr 等）, index_daily.  
  - **長期系**: portfolio_monthly（rebalance_date, code, weight, core_score, entry_score）, holdings, backtest_performance, backtest_stock_performance.  
  - **月次リバランス系**: monthly_rebalance_portfolio, monthly_rebalance_final_selected_candidates, monthly_rebalance_candidate_performance, monthly_rebalance_candidate_monthly_returns, monthly_rebalance_candidate_detailed_metrics.  
  - **書き込み**: portfolio_monthly は longterm_run と optimize_longterm が DELETE/INSERT。monthly_rebalance_* は evaluate/save 系スクリプトが利用。

- **スコア計算の二重性**:  
  - strategy/scoring.py の `calculate_core_score(conn, code, as_of_date)` は StrategyConfig ベース。  
  - longterm_run.build_features() は StrategyParams/EntryScoreParams ベースで core_score/entry_score を計算し DataFrame で features_monthly に保存。  
  - 選定は strategy/select.py（config ベース）と、optimize 系の「パラメータ付き選定」（_select_portfolio_with_params / _select_portfolio_for_rebalance_date）が混在。

---

### 追質問の本文

あなたの「1つのランキングエンジン＋2ポリシー・最適化は月次だけ・長期は出力モード」案を、実装に落とすために以下を教えてください。

1. **V1の最適化パラメータの具体化**  
   - 現状は StrategyParams / EntryScoreParams の**下位レイヤ全体**を Optuna で探索しています。あなたの「V1では合成済みスコアの上位レイヤだけ（w_core, w_entry, top_n 等 6〜8 個）」に抑える案では、**core_score と entry_score は「固定された式」で事前計算**する想定だと思います。  
   - その前提で、**(a) V1で探索するパラメータの一覧（名前・範囲・意味）** と **(b) 固定するパラメータ（core_score/entry_score の式を決めるもの）の一覧と、その固定値の決め方（デフォルト値 / 最後の最適化結果の採用 / 手動）** を表形式で書いてください。  
   - 可能なら、現行の longterm_run の StrategyParams/EntryScoreParams のどれを固定に回すかも対応づけてあると助かります。

2. **現行ファイル→新構成の移行マップ**  
   - 次の現行ファイル（またはその中の主要関数）が、あなたの提案した新構成で**どのモジュール・コマンド・関数に移るか**を、表でまとめてください。  
     - longterm_run.py（build_features, select_portfolio, save_features, save_portfolio, main）  
     - optimize_timeseries.py（objective_timeseries, _select_portfolio_for_rebalance_date 等）  
     - optimize_longterm.py（objective_longterm, calculate_longterm_performance, split_rebalance_dates 等）  
     - backtest/performance.py（calculate_portfolio_performance 等）  
     - strategy/select.py, strategy/scoring.py  
   - 新構成では **prepare_features**, **run_strategy**, **optimize_strategy**, **evaluate_strategy** と、純粋関数 **build_snapshot**, **score_candidates**, **select_portfolio**, **evaluate_portfolio** が出てきます。現行のどのコードがこれらに「移る」「統合される」「廃止される」かを対応づけてください。

3. **DB: 現行テーブルと新テーブルの対応・移行順序**  
   - 上記「添付する前提情報」の現行テーブル一覧を前提に、あなたの提案する **strategy_runs, portfolio_snapshots, performance_series, performance_summary, live_holdings** との対応（どの現行テーブル・カラムがどの新テーブル・カラムに相当するか）を簡潔に表にしてください。  
   - さらに、**移行の段階**（まず新規 run だけ新テーブルに書く／既存ダッシュボードは旧テーブル読取のまま／旧テーブルへの書き込みを止めるタイミング等）を 2〜3 ステップで文章化してください。

4. **run_strategy と optimize_strategy の仕様**  
   - `run_strategy --mode monthly --asof 2024-01-31` は「その1日分のポートフォリオを1回だけ選定して返す（または保存する）」、`--start / --end` を付けた場合は「期間内の各リバランス日について同様に選定する」という理解で正しいか確認してください。  
   - `optimize_strategy --mode monthly` は、内部で「候補パラメータごとに、複数リバランス日について選定→evaluate_portfolio で指標計算→目的関数で比較」というループになる、という理解で正しいか確認してください。

5. **長期「出力モード」のアウトプット形式**  
   - 長期ポリシーで出す「買い増し候補・add候補・watchlist・rank変化・スコア内訳」は、V1では **どの形式で提供するか**（例: DB のどのテーブルに書き込む／JSON ファイル／CSV／レポート Markdown 等）を 1〜2 文で明確にしてください。

---

以上で、ChatGPT から「現行→新構成」の移行マップと、V1 のパラメータ・DB・コマンドの具体案を引き出せます。回答が返ってきたら、その内容を **docs/** に「移行マップ案」として保存し、スリム化の実施順序（Step 1 の legacy 退避から）に反映するのがよいです。
