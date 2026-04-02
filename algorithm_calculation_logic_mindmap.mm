<map version="1.0.1">
<!-- To view this file, use FreeMind http://freemind.sourceforge.net or compatible viewer -->
<node CREATED="1700000000000" ID="ID_ROOT" MODIFIED="1700000000000" TEXT="アルゴリズム全体の計算ロジック">
<node CREATED="1700000000001" ID="ID_1" MODIFIED="1700000000001" POSITION="right" TEXT="1. データフロー全体">
<node CREATED="1700000000002" ID="ID_1_1" MODIFIED="1700000000002" TEXT="入力">
<node CREATED="1700000000003" ID="ID_1_1_1" MODIFIED="1700000000003" TEXT="J-Quants API"/>
<node CREATED="1700000000004" ID="ID_1_1_2" MODIFIED="1700000000004" TEXT="etl_update（python -m omanta_3rd.jobs.etl_update）/ update_all_data"/>
<node CREATED="1700000000005" ID="ID_1_1_3" MODIFIED="1700000000005" TEXT="listed_info, prices_daily, fins_statements, index_daily"/>
</node>
<node CREATED="1700000000006" ID="ID_1_2" MODIFIED="1700000000006" TEXT="特徴量・スコア計算">
<node CREATED="1700000000007" ID="ID_1_2_1" MODIFIED="1700000000007" TEXT="prepare_features または longterm_run.build_features"/>
<node CREATED="1700000000008" ID="ID_1_2_2" MODIFIED="1700000000008" TEXT="→ features_monthly（core_score, entry_score, core_score_ref, entry_score_ref）"/>
</node>
<node CREATED="1700000000009" ID="ID_1_3" MODIFIED="1700000000009" TEXT="選定">
<node CREATED="1700000000010" ID="ID_1_3_1" MODIFIED="1700000000010" TEXT="build_snapshot → score_candidates → select_portfolio"/>
<node CREATED="1700000000012" ID="ID_1_3_3" MODIFIED="1700000000012" TEXT="→ portfolio_snapshots（月次）/ portfolio_monthly（長期保有型参考）"/>
</node>
<node CREATED="1700000000013" ID="ID_1_4" MODIFIED="1700000000013" TEXT="評価">
<node CREATED="1700000000014" ID="ID_1_4_1" MODIFIED="1700000000014" TEXT="evaluate_portfolio または calculate_portfolio_performance"/>
<node CREATED="1700000000015" ID="ID_1_4_2" MODIFIED="1700000000015" TEXT="→ 時系列リターン → Sharpe_excess, MaxDD, CAGR, objective"/>
</node>
</node>
<node CREATED="1700000000016" ID="ID_2" MODIFIED="1700000000016" POSITION="right" TEXT="2. 単一ランキングエンジン">
<node CREATED="1700000000017" ID="ID_2_1" MODIFIED="1700000000017" TEXT="パラメータの2層">
<node CREATED="1700000000018" ID="ID_2_1_1" MODIFIED="1700000000018" TEXT="ScoreProfile（凍結）">
<node CREATED="1700000000019" ID="ID_2_1_1_1" MODIFIED="1700000000019" TEXT="core_weights: w_quality, w_value, w_growth, w_record_high, w_size, w_forward_per, w_pbr"/>
<node CREATED="1700000000020" ID="ID_2_1_1_2" MODIFIED="1700000000020" TEXT="entry_params: rsi_base, rsi_max, bb_z_base, bb_z_max, bb_weight, rsi_weight"/>
<node CREATED="1700000000021" ID="ID_2_1_1_3" MODIFIED="1700000000021" TEXT="pool_size, roe_min, liquidity_quantile_cut"/>
<node CREATED="1700000000022" ID="ID_2_1_1_4" MODIFIED="1700000000022" TEXT="v1_ref で固定、core_score_ref / entry_score_ref の式を決定"/>
</node>
<node CREATED="1700000000023" ID="ID_2_1_2" MODIFIED="1700000000023" TEXT="PolicyParams（探索）">
<node CREATED="1700000000024" ID="ID_2_1_2_1" MODIFIED="1700000000024" TEXT="entry_share (0〜0.35): total_score における entry の比率"/>
<node CREATED="1700000000025" ID="ID_2_1_2_2" MODIFIED="1700000000025" TEXT="top_n: 8,10,12,14,16"/>
<node CREATED="1700000000026" ID="ID_2_1_2_3" MODIFIED="1700000000026" TEXT="sector_cap (2〜4), liquidity_floor_q (0.3〜0.6)"/>
<node CREATED="1700000000027" ID="ID_2_1_2_4" MODIFIED="1700000000027" TEXT="rebalance_buffer (0〜3), lambda_turnover (0〜0.2)"/>
</node>
</node>
<node CREATED="1700000000028" ID="ID_2_2" MODIFIED="1700000000028" TEXT="純粋関数4本">
<node CREATED="1700000000029" ID="ID_2_2_1" MODIFIED="1700000000029" TEXT="build_snapshot(conn, asof)">
<node CREATED="1700000000030" ID="ID_2_2_1_1" MODIFIED="1700000000030" TEXT="指定日の features_monthly を読むだけ（DBを書かない）"/>
</node>
<node CREATED="1700000000031" ID="ID_2_2_2" MODIFIED="1700000000031" TEXT="score_candidates(snapshot, score_profile, policy_params)">
<node CREATED="1700000000032" ID="ID_2_2_2_1" MODIFIED="1700000000032" TEXT="core_ref_pct = クロスセクション percentile(core_score_ref)"/>
<node CREATED="1700000000033" ID="ID_2_2_2_2" MODIFIED="1700000000033" TEXT="entry_ref_pct = クロスセクション percentile(entry_score_ref)"/>
<node CREATED="1700000000034" ID="ID_2_2_2_3" MODIFIED="1700000000034" TEXT="total_score = (1-entry_share)×core_ref_pct + entry_share×entry_ref_pct"/>
</node>
<node CREATED="1700000000035" ID="ID_2_2_3" MODIFIED="1700000000035" TEXT="select_portfolio(scored_df, policy_params, rebalance_date, prev)">
<node CREATED="1700000000036" ID="ID_2_2_3_1" MODIFIED="1700000000036" TEXT="流動性フィルタ → total_score ソート → セクター上限 → rebalance_buffer で前回優先 → top_n"/>
</node>
<node CREATED="1700000000037" ID="ID_2_2_4" MODIFIED="1700000000037" TEXT="evaluate_portfolio(portfolios, start, end, cost_bps, lambda_turnover)">
<node CREATED="1700000000038" ID="ID_2_2_4_1" MODIFIED="1700000000038" TEXT="時系列リターン計算 → sharpe_excess, cagr, maxdd, avg_turnover"/>
<node CREATED="1700000000039" ID="ID_2_2_4_2" MODIFIED="1700000000039" TEXT="objective = sharpe_excess - lambda_turnover × avg_turnover"/>
</node>
</node>
</node>
<node CREATED="1700000000040" ID="ID_3" MODIFIED="1700000000040" POSITION="left" TEXT="3. 特徴量計算（build_features 系）">
<node CREATED="1700000000041" ID="ID_3_1" MODIFIED="1700000000041" TEXT="財務指標">
<node CREATED="1700000000042" ID="ID_3_1_1" MODIFIED="1700000000042" TEXT="ROE = profit / equity"/>
<node CREATED="1700000000043" ID="ID_3_1_2" MODIFIED="1700000000043" TEXT="ROEトレンド: 現在ROE - 過去4期平均ROE"/>
<node CREATED="1700000000044" ID="ID_3_1_3" MODIFIED="1700000000044" TEXT="PER/PBR/Forward PER: 未調整終値と補正後株数で再計算"/>
<node CREATED="1700000000045" ID="ID_3_1_4" MODIFIED="1700000000045" TEXT="op_growth, profit_growth: 予想/実績の比 - 1"/>
<node CREATED="1700000000046" ID="ID_3_1_5" MODIFIED="1700000000046" TEXT="record_high_forecast_flag: 予想営業利益 ≥ 過去最高"/>
</node>
<node CREATED="1700000000047" ID="ID_3_2" MODIFIED="1700000000047" TEXT="テクニカル（Entry Score用）">
<node CREATED="1700000000048" ID="ID_3_2_1" MODIFIED="1700000000048" TEXT="RSI: 20/60/90日、max を採用"/>
<node CREATED="1700000000049" ID="ID_3_2_2" MODIFIED="1700000000049" TEXT="BB Z-score: (price-mean)/std、20/60/90日"/>
<node CREATED="1700000000050" ID="ID_3_2_3" MODIFIED="1700000000050" TEXT="entry_score = bb_weight×bb_score + rsi_weight×rsi_score（線形変換後 clip 0-1）"/>
</node>
<node CREATED="1700000000051" ID="ID_3_3" MODIFIED="1700000000051" TEXT="その他">
<node CREATED="1700000000052" ID="ID_3_3_1" MODIFIED="1700000000052" TEXT="流動性: 60営業日平均売買代金"/>
<node CREATED="1700000000053" ID="ID_3_3_2" MODIFIED="1700000000053" TEXT="時価総額: price × 補正後株数"/>
</node>
</node>
<node CREATED="1700000000054" ID="ID_4" MODIFIED="1700000000054" POSITION="left" TEXT="4. スコア合成（下位＝凍結）">
<node CREATED="1700000000055" ID="ID_4_1" MODIFIED="1700000000055" TEXT="サブスコア（業種内 or 全体パーセンタイル）">
<node CREATED="1700000000056" ID="ID_4_1_1" MODIFIED="1700000000056" TEXT="quality_score = rank(roe)"/>
<node CREATED="1700000000057" ID="ID_4_1_2" MODIFIED="1700000000057" TEXT="value_score = w_forward_per×(1-forward_per_pct) + w_pbr×(1-pbr_pct)"/>
<node CREATED="1700000000058" ID="ID_4_1_3" MODIFIED="1700000000058" TEXT="growth_score = 0.4×op_growth_score + 0.4×profit_growth + 0.2×op_trend"/>
<node CREATED="1700000000059" ID="ID_4_1_4" MODIFIED="1700000000059" TEXT="record_high_score = record_high_forecast_flag"/>
<node CREATED="1700000000060" ID="ID_4_1_5" MODIFIED="1700000000060" TEXT="size_score = rank(log(market_cap))"/>
</node>
<node CREATED="1700000000061" ID="ID_4_2" MODIFIED="1700000000061" TEXT="core_score（ScoreProfile の重みで固定）">
<node CREATED="1700000000062" ID="ID_4_2_1" MODIFIED="1700000000062" TEXT="core_score = w_quality×quality + w_value×value + w_growth×growth + w_record_high×record_high + w_size×size"/>
<node CREATED="1700000000063" ID="ID_4_2_2" MODIFIED="1700000000063" TEXT="欠損は 0.5 または 0.0 で fill"/>
</node>
<node CREATED="1700000000064" ID="ID_4_3" MODIFIED="1700000000064" TEXT="total_score（PolicyParams で合成）">
<node CREATED="1700000000065" ID="ID_4_3_1" MODIFIED="1700000000065" TEXT="core_ref_pct, entry_ref_pct = クロスセクション percentile"/>
<node CREATED="1700000000066" ID="ID_4_3_2" MODIFIED="1700000000066" TEXT="total_score = (1-entry_share)×core_ref_pct + entry_share×entry_ref_pct"/>
</node>
</node>
<node CREATED="1700000000067" ID="ID_5" MODIFIED="1700000000067" POSITION="left" TEXT="5. ポートフォリオ選定プロセス">
<node CREATED="1700000000068" ID="ID_5_1" MODIFIED="1700000000068" TEXT="フィルタ">
<node CREATED="1700000000069" ID="ID_5_1_1" MODIFIED="1700000000069" TEXT="流動性: liquidity_60d ≥ quantile(liquidity_floor_q)"/>
<node CREATED="1700000000070" ID="ID_5_1_2" MODIFIED="1700000000070" TEXT="ROE: roe ≥ roe_min（ScoreProfile で固定）"/>
</node>
<node CREATED="1700000000071" ID="ID_5_2" MODIFIED="1700000000071" TEXT="ソート">
<node CREATED="1700000000072" ID="ID_5_2_1" MODIFIED="1700000000072" TEXT="total_score の降順"/>
</node>
<node CREATED="1700000000074" ID="ID_5_3" MODIFIED="1700000000074" TEXT="セクター上限">
<node CREATED="1700000000075" ID="ID_5_3_1" MODIFIED="1700000000075" TEXT="sector33 ごとに最大 sector_cap 銘柄"/>
</node>
<node CREATED="1700000000076" ID="ID_5_4" MODIFIED="1700000000076" TEXT="最終選定">
<node CREATED="1700000000077" ID="ID_5_4_1" MODIFIED="1700000000077" TEXT="top_n 銘柄、等加重 weight = 1/top_n"/>
<node CREATED="1700000000078" ID="ID_5_4_2" MODIFIED="1700000000078" TEXT="rebalance_buffer で前回保有を優先して残す"/>
</node>
</node>
<node CREATED="1700000000079" ID="ID_6" MODIFIED="1700000000079" POSITION="left" TEXT="6. バックテスト・評価計算">
<node CREATED="1700000000078" ID="ID_6_0" MODIFIED="1700000000078" TEXT="先読み防止: disclosed_date&lt;=rebalance_date, as_of_date 必須（CLAUDE.md）"/>
<node CREATED="1700000000080" ID="ID_6_1" MODIFIED="1700000000080" TEXT="売買タイミング（実運用方式）">
<node CREATED="1700000000081" ID="ID_6_1_1" MODIFIED="1700000000081" TEXT="売却: リバランス日（月末）の始値"/>
<node CREATED="1700000000082" ID="ID_6_1_2" MODIFIED="1700000000082" TEXT="購入: 翌リバランス日（月初）の始値"/>
<node CREATED="1700000000083" ID="ID_6_1_3" MODIFIED="1700000000083" TEXT="期間リターン: open(t) → open(t_next)"/>
</node>
<node CREATED="1700000000084" ID="ID_6_2" MODIFIED="1700000000084" TEXT="リターン計算">
<node CREATED="1700000000085" ID="ID_6_2_1" MODIFIED="1700000000085" TEXT="銘柄別: 分割倍率で購入価格を補正してから return = sell/adj_buy - 1"/>
<node CREATED="1700000000086" ID="ID_6_2_2" MODIFIED="1700000000086" TEXT="ポートフォリオ: 重み付き平均、欠損銘柄は除外して再正規化"/>
<node CREATED="1700000000087" ID="ID_6_2_3" MODIFIED="1700000000087" TEXT="TOPIX: 同タイミングでリターン、超過 = ポートフォリオ - TOPIX"/>
</node>
<node CREATED="1700000000088" ID="ID_6_3" MODIFIED="1700000000088" TEXT="指標">
<node CREATED="1700000000089" ID="ID_6_3_1" MODIFIED="1700000000089" TEXT="Sharpe_excess: 月次超過リターンの年率化 Sharpe（= IR）"/>
<node CREATED="1700000000090" ID="ID_6_3_2" MODIFIED="1700000000090" TEXT="CAGR, MaxDD, Calmar, avg_turnover（paper_turnover の平均）"/>
<node CREATED="1700000000091" ID="ID_6_3_3" MODIFIED="1700000000091" TEXT="objective = sharpe_excess - lambda_turnover × avg_turnover"/>
</node>
</node>
<node CREATED="1700000000092" ID="ID_7" MODIFIED="1700000000092" POSITION="right" TEXT="7. 最適化">
<node CREATED="1700000000093" ID="ID_7_1" MODIFIED="1700000000093" TEXT="月次リバランス型: optimize_timeseries（StrategyParams+EntryScoreParams を Optuna 探索）"/>
<node CREATED="1700000000095" ID="ID_7_2" MODIFIED="1700000000095" TEXT="FeatureCache.warm で特徴量を事前計算、trial 内はキャッシュ利用（build_features は遅延インポートで循環回避）"/>
<node CREATED="1700000000096" ID="ID_7_3" MODIFIED="1700000000096" TEXT="目的関数: Sharpe_excess（=IR）、取引コスト --cost（bps）で期間リターンから控除"/>
<node CREATED="1700000000101" ID="ID_7_4" MODIFIED="1700000000101" TEXT="時系列リターン（月末始値→翌月始値）、実運用方式"/>
<node CREATED="1700000000102" ID="ID_7_5" MODIFIED="1700000000102" TEXT="長期保有型: optimize_longterm（別ジョブ）"/>
</node>
<node CREATED="1700000000103" ID="ID_8" MODIFIED="1700000000103" POSITION="right" TEXT="8. 実行ジョブ">
<node CREATED="1700000000104" ID="ID_8_1" MODIFIED="1700000000104" TEXT="prepare_features">
<node CREATED="1700000000105" ID="ID_8_1_1" MODIFIED="1700000000105" TEXT="v1_ref で特徴量＋core_score_ref/entry_score_ref を計算して features_monthly に保存"/>
</node>
<node CREATED="1700000000106" ID="ID_8_2" MODIFIED="1700000000106" TEXT="run_strategy">
<node CREATED="1700000000107" ID="ID_8_2_1" MODIFIED="1700000000107" TEXT="--mode longterm | monthly、--asof または --start/--end"/>
<node CREATED="1700000000108" ID="ID_8_2_2" MODIFIED="1700000000108" TEXT="build_snapshot → score_candidates → select_portfolio、結果を portfolio_snapshots に保存可"/>
</node>
<node CREATED="1700000000109" ID="ID_8_3" MODIFIED="1700000000109" TEXT="月次リバランス型最適化">
<node CREATED="1700000000110" ID="ID_8_3_1" MODIFIED="1700000000110" TEXT="optimize_timeseries: --start/--end, --n-trials, --cost, --study-name"/>
<node CREATED="1700000000111" ID="ID_8_3_2" MODIFIED="1700000000111" TEXT="実運用: scripts/run_production_optimization.ps1（200 trials, cost 20bps）"/>
<node CREATED="1700000000112" ID="ID_8_3_3" MODIFIED="1700000000112" TEXT="プラン: docs/5DAY_PRODUCTION_OPTIMIZATION_PLAN.md"/>
</node>
</node>
</node>
</map>
