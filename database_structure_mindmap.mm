<map version="1.0.1">
<!-- To view this file, download free mind mapping software FreeMind from http://freemind.sourceforge.net -->
<node CREATED="1700000000000" ID="ID_ROOT" MODIFIED="1700000000000" TEXT="投資アルゴリズム データベース構造">
<node CREATED="1700000000001" ID="ID_1" MODIFIED="1700000000001" POSITION="right" TEXT="データベース情報">
<node CREATED="1700000000002" ID="ID_1_1" MODIFIED="1700000000002" TEXT="種類: SQLite"/>
<node CREATED="1700000000003" ID="ID_1_2" MODIFIED="1700000000003" TEXT="パス: .env の DB_PATH（未設定時は data/db/jquants.sqlite 等、環境により異なる）"/>
</node>
<node CREATED="1700000000004" ID="ID_2" MODIFIED="1700000000004" POSITION="right" TEXT="1. 共通テーブル（両方の運用スタイルで使用）">
<node CREATED="1700000000005" ID="ID_2_1" MODIFIED="1700000000005" TEXT="listed_info（銘柄属性）">
<node CREATED="1700000000006" ID="ID_2_1_1" MODIFIED="1700000000006" TEXT="主キー: (date, code)"/>
<node CREATED="1700000000007" ID="ID_2_1_2" MODIFIED="1700000000007" TEXT="主要カラム">
<node CREATED="1700000000008" ID="ID_2_1_2_1" MODIFIED="1700000000008" TEXT="date: 日付（YYYY-MM-DD）"/>
<node CREATED="1700000000009" ID="ID_2_1_2_2" MODIFIED="1700000000009" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000010" ID="ID_2_1_2_3" MODIFIED="1700000000010" TEXT="company_name: 会社名"/>
<node CREATED="1700000000011" ID="ID_2_1_2_4" MODIFIED="1700000000011" TEXT="market_name: 市場名（プライム等）"/>
<node CREATED="1700000000012" ID="ID_2_1_2_5" MODIFIED="1700000000012" TEXT="sector17: 17業種"/>
<node CREATED="1700000000013" ID="ID_2_1_2_6" MODIFIED="1700000000013" TEXT="sector33: 33業種"/>
</node>
</node>
<node CREATED="1700000000014" ID="ID_2_2" MODIFIED="1700000000014" TEXT="prices_daily（日足価格データ）">
<node CREATED="1700000000015" ID="ID_2_2_1" MODIFIED="1700000000015" TEXT="主キー: (date, code)"/>
<node CREATED="1700000000016" ID="ID_2_2_2" MODIFIED="1700000000016" TEXT="主要カラム">
<node CREATED="1700000000017" ID="ID_2_2_2_1" MODIFIED="1700000000017" TEXT="date: 日付（YYYY-MM-DD）"/>
<node CREATED="1700000000018" ID="ID_2_2_2_2" MODIFIED="1700000000018" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000019" ID="ID_2_2_2_3" MODIFIED="1700000000019" TEXT="open: 始値（調整前）"/>
<node CREATED="1700000000020" ID="ID_2_2_2_4" MODIFIED="1700000000020" TEXT="close: 調整前終値"/>
<node CREATED="1700000000021" ID="ID_2_2_2_5" MODIFIED="1700000000021" TEXT="adj_close: 調整済終値"/>
<node CREATED="1700000000022" ID="ID_2_2_2_6" MODIFIED="1700000000022" TEXT="adj_volume: 調整済出来高"/>
<node CREATED="1700000000023" ID="ID_2_2_2_7" MODIFIED="1700000000023" TEXT="turnover_value: 売買代金"/>
<node CREATED="1700000000024" ID="ID_2_2_2_8" MODIFIED="1700000000024" TEXT="adjustment_factor: 調整係数（株式分割等）"/>
</node>
</node>
<node CREATED="1700000000025" ID="ID_2_3" MODIFIED="1700000000025" TEXT="fins_statements（財務データ・開示ベース）">
<node CREATED="1700000000026" ID="ID_2_3_1" MODIFIED="1700000000026" TEXT="主キー: (disclosed_date, code, type_of_current_period, current_period_end)"/>
<node CREATED="1700000000027" ID="ID_2_3_2" MODIFIED="1700000000027" TEXT="主要カラム">
<node CREATED="1700000000028" ID="ID_2_3_2_1" MODIFIED="1700000000028" TEXT="disclosed_date: 開示日（YYYY-MM-DD）"/>
<node CREATED="1700000000029" ID="ID_2_3_2_2" MODIFIED="1700000000029" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000030" ID="ID_2_3_2_3" MODIFIED="1700000000030" TEXT="type_of_current_period: FY/1Q/2Q/3Q"/>
<node CREATED="1700000000031" ID="ID_2_3_2_4" MODIFIED="1700000000031" TEXT="current_period_end: 当期末（YYYY-MM-DD）"/>
<node CREATED="1700000000032" ID="ID_2_3_2_5" MODIFIED="1700000000032" TEXT="実績: operating_profit, profit, equity, eps, bvps"/>
<node CREATED="1700000000033" ID="ID_2_3_2_6" MODIFIED="1700000000033" TEXT="予想: forecast_operating_profit, forecast_profit, forecast_eps"/>
<node CREATED="1700000000034" ID="ID_2_3_2_7" MODIFIED="1700000000034" TEXT="次年度予想: next_year_forecast_*"/>
<node CREATED="1700000000035" ID="ID_2_3_2_8" MODIFIED="1700000000035" TEXT="株数: shares_outstanding, treasury_shares"/>
</node>
</node>
<node CREATED="1700000000036" ID="ID_2_4" MODIFIED="1700000000036" TEXT="features_monthly（月次特徴量・スナップショット）">
<node CREATED="1700000000037" ID="ID_2_4_1" MODIFIED="1700000000037" TEXT="主キー: (as_of_date, code)"/>
<node CREATED="1700000000038" ID="ID_2_4_2" MODIFIED="1700000000038" TEXT="主要カラム">
<node CREATED="1700000000039" ID="ID_2_4_2_1" MODIFIED="1700000000039" TEXT="as_of_date: 評価日（YYYY-MM-DD、月末営業日）"/>
<node CREATED="1700000000040" ID="ID_2_4_2_2" MODIFIED="1700000000040" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000041" ID="ID_2_4_2_3" MODIFIED="1700000000041" TEXT="sector33: 33業種"/>
<node CREATED="1700000000042" ID="ID_2_4_2_4" MODIFIED="1700000000042" TEXT="liquidity_60d: 売買代金60営業日平均"/>
<node CREATED="1700000000043" ID="ID_2_4_2_5" MODIFIED="1700000000043" TEXT="market_cap: 時価総額（推定）"/>
<node CREATED="1700000000044" ID="ID_2_4_2_6" MODIFIED="1700000000044" TEXT="実績: roe, roe_trend"/>
<node CREATED="1700000000045" ID="ID_2_4_2_7" MODIFIED="1700000000045" TEXT="バリュエーション: per, pbr, forward_per"/>
<node CREATED="1700000000046" ID="ID_2_4_2_8" MODIFIED="1700000000046" TEXT="成長率: op_growth, profit_growth"/>
<node CREATED="1700000000047" ID="ID_2_4_2_9" MODIFIED="1700000000047" TEXT="最高益: record_high_flag, record_high_forecast_flag"/>
<node CREATED="1700000000048" ID="ID_2_4_2_10" MODIFIED="1700000000048" TEXT="スコア: core_score, entry_score"/>
<node CREATED="1700000000490" ID="ID_2_4_2_11" MODIFIED="1700000000490" TEXT="ref score用: score_profile, core_score_ref, entry_score_ref"/>
</node>
</node>
<node CREATED="1700000000049" ID="ID_2_5" MODIFIED="1700000000049" TEXT="index_daily（指数データ・TOPIX）">
<node CREATED="1700000000050" ID="ID_2_5_1" MODIFIED="1700000000050" TEXT="主キー: (date, index_code)"/>
<node CREATED="1700000000051" ID="ID_2_5_2" MODIFIED="1700000000051" TEXT="主要カラム">
<node CREATED="1700000000052" ID="ID_2_5_2_1" MODIFIED="1700000000052" TEXT="date: 日付（YYYY-MM-DD）"/>
<node CREATED="1700000000053" ID="ID_2_5_2_2" MODIFIED="1700000000053" TEXT="index_code: 指数コード（0000=TOPIX）"/>
<node CREATED="1700000000054" ID="ID_2_5_2_3" MODIFIED="1700000000054" TEXT="open: 始値"/>
<node CREATED="1700000000055" ID="ID_2_5_2_4" MODIFIED="1700000000055" TEXT="high: 高値"/>
<node CREATED="1700000000056" ID="ID_2_5_2_5" MODIFIED="1700000000056" TEXT="low: 安値"/>
<node CREATED="1700000000057" ID="ID_2_5_2_6" MODIFIED="1700000000057" TEXT="close: 終値"/>
</node>
</node>
<node CREATED="1700000000058" ID="ID_2_6" MODIFIED="1700000000058" TEXT="earnings_calendar（決算発表予定日）">
<node CREATED="1700000000059" ID="ID_2_6_1" MODIFIED="1700000000059" TEXT="主キー: (code, announcement_date, period_type, period_end)"/>
<node CREATED="1700000000060" ID="ID_2_6_2" MODIFIED="1700000000060" TEXT="主要カラム">
<node CREATED="1700000000061" ID="ID_2_6_2_1" MODIFIED="1700000000061" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000062" ID="ID_2_6_2_2" MODIFIED="1700000000062" TEXT="announcement_date: 決算発表予定日（YYYY-MM-DD）"/>
<node CREATED="1700000000063" ID="ID_2_6_2_3" MODIFIED="1700000000063" TEXT="period_type: 期間種別（FY/1Q/2Q/3Q）"/>
<node CREATED="1700000000064" ID="ID_2_6_2_4" MODIFIED="1700000000064" TEXT="period_end: 当期末日（YYYY-MM-DD）"/>
</node>
</node>
<node CREATED="1700000000650" ID="ID_2_7" MODIFIED="1700000000650" TEXT="stock_splits（株式分割情報）">
<node CREATED="1700000000651" ID="ID_2_7_1" MODIFIED="1700000000651" TEXT="主キー: (code, split_date)"/>
<node CREATED="1700000000652" ID="ID_2_7_2" MODIFIED="1700000000652" TEXT="主要カラム: code, split_date, split_ratio, description"/>
</node>
</node>
<node CREATED="1700000000065" ID="ID_3" MODIFIED="1700000000065" POSITION="right" TEXT="2. 長期保有型テーブル">
<node CREATED="1700000000066" ID="ID_3_1" MODIFIED="1700000000066" TEXT="portfolio_monthly（月次ポートフォリオ）">
<node CREATED="1700000000067" ID="ID_3_1_1" MODIFIED="1700000000067" TEXT="主キー: (rebalance_date, code)"/>
<node CREATED="1700000000068" ID="ID_3_1_2" MODIFIED="1700000000068" TEXT="用途">
<node CREATED="1700000000069" ID="ID_3_1_2_1" MODIFIED="1700000000069" TEXT="最適化時の一時保存（最適化後は削除）"/>
<node CREATED="1700000000070" ID="ID_3_1_2_2" MODIFIED="1700000000070" TEXT="longterm_run 実行時の参考情報として保存"/>
</node>
<node CREATED="1700000000071" ID="ID_3_1_3" MODIFIED="1700000000071" TEXT="主要カラム">
<node CREATED="1700000000072" ID="ID_3_1_3_1" MODIFIED="1700000000072" TEXT="rebalance_date: リバランス日（YYYY-MM-DD）"/>
<node CREATED="1700000000073" ID="ID_3_1_3_2" MODIFIED="1700000000073" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000074" ID="ID_3_1_3_3" MODIFIED="1700000000074" TEXT="weight: ウェイト"/>
<node CREATED="1700000000075" ID="ID_3_1_3_4" MODIFIED="1700000000075" TEXT="core_score: ファンダメンタルスコア"/>
<node CREATED="1700000000076" ID="ID_3_1_3_5" MODIFIED="1700000000076" TEXT="entry_score: エントリースコア"/>
<node CREATED="1700000000077" ID="ID_3_1_3_6" MODIFIED="1700000000077" TEXT="reason: 採用理由（JSON文字列）"/>
</node>
</node>
<node CREATED="1700000000078" ID="ID_3_2" MODIFIED="1700000000078" TEXT="holdings（実際の保有銘柄）">
<node CREATED="1700000000079" ID="ID_3_2_1" MODIFIED="1700000000079" TEXT="主キー: id (AUTOINCREMENT)"/>
<node CREATED="1700000000080" ID="ID_3_2_2" MODIFIED="1700000000080" TEXT="用途: 長期保有型の実際の保有状況を管理"/>
<node CREATED="1700000000081" ID="ID_3_2_3" MODIFIED="1700000000081" TEXT="主要カラム">
<node CREATED="1700000000082" ID="ID_3_2_3_1" MODIFIED="1700000000082" TEXT="purchase_date: 購入日（YYYY-MM-DD）"/>
<node CREATED="1700000000083" ID="ID_3_2_3_2" MODIFIED="1700000000083" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000084" ID="ID_3_2_3_3" MODIFIED="1700000000084" TEXT="company_name: 社名"/>
<node CREATED="1700000000085" ID="ID_3_2_3_4" MODIFIED="1700000000085" TEXT="shares: 株数"/>
<node CREATED="1700000000086" ID="ID_3_2_3_5" MODIFIED="1700000000086" TEXT="purchase_price: 購入単価"/>
<node CREATED="1700000000087" ID="ID_3_2_3_6" MODIFIED="1700000000087" TEXT="broker: 証券会社名"/>
<node CREATED="1700000000088" ID="ID_3_2_3_7" MODIFIED="1700000000088" TEXT="current_price: 現在価格（最新の終値）"/>
<node CREATED="1700000000089" ID="ID_3_2_3_8" MODIFIED="1700000000089" TEXT="adjustment_factor: 調整係数（株式分割倍率）"/>
<node CREATED="1700000000090" ID="ID_3_2_3_9" MODIFIED="1700000000090" TEXT="unrealized_pnl: 含み損益"/>
<node CREATED="1700000000091" ID="ID_3_2_3_10" MODIFIED="1700000000091" TEXT="return_pct: リターン（%）"/>
<node CREATED="1700000000092" ID="ID_3_2_3_11" MODIFIED="1700000000092" TEXT="sell_date: 売却日（NULL=保有中）"/>
<node CREATED="1700000000093" ID="ID_3_2_3_12" MODIFIED="1700000000093" TEXT="sell_price: 売却単価（NULL=保有中）"/>
<node CREATED="1700000000094" ID="ID_3_2_3_13" MODIFIED="1700000000094" TEXT="realized_pnl: 実現損益"/>
<node CREATED="1700000000095" ID="ID_3_2_3_14" MODIFIED="1700000000095" TEXT="topix_return_pct: TOPIXリターン（%）"/>
<node CREATED="1700000000096" ID="ID_3_2_3_15" MODIFIED="1700000000096" TEXT="excess_return_pct: 超過リターン（%）"/>
</node>
</node>
<node CREATED="1700000000097" ID="ID_3_3" MODIFIED="1700000000097" TEXT="holdings_summary（保有銘柄全体のパフォーマンスサマリー）">
<node CREATED="1700000000098" ID="ID_3_3_1" MODIFIED="1700000000098" TEXT="主キー: as_of_date"/>
<node CREATED="1700000000099" ID="ID_3_3_2" MODIFIED="1700000000099" TEXT="主要カラム">
<node CREATED="1700000000100" ID="ID_3_3_2_1" MODIFIED="1700000000100" TEXT="as_of_date: 評価日（YYYY-MM-DD）"/>
<node CREATED="1700000000101" ID="ID_3_3_2_2" MODIFIED="1700000000101" TEXT="total_investment: 総投資額"/>
<node CREATED="1700000000102" ID="ID_3_3_2_3" MODIFIED="1700000000102" TEXT="total_unrealized_pnl: 総含み損益"/>
<node CREATED="1700000000103" ID="ID_3_3_2_4" MODIFIED="1700000000103" TEXT="total_realized_pnl: 総実現損益"/>
<node CREATED="1700000000104" ID="ID_3_3_2_5" MODIFIED="1700000000104" TEXT="portfolio_return_pct: ポートフォリオ全体のリターン（%）"/>
<node CREATED="1700000000105" ID="ID_3_3_2_6" MODIFIED="1700000000105" TEXT="topix_return_pct: TOPIXリターン（%）"/>
<node CREATED="1700000000106" ID="ID_3_3_2_7" MODIFIED="1700000000106" TEXT="excess_return_pct: 超過リターン（%）"/>
<node CREATED="1700000000107" ID="ID_3_3_2_8" MODIFIED="1700000000107" TEXT="num_holdings: 保有中銘柄数"/>
<node CREATED="1700000000108" ID="ID_3_3_2_9" MODIFIED="1700000000108" TEXT="num_sold: 売却済み銘柄数"/>
</node>
</node>
<node CREATED="1700000000109" ID="ID_3_4" MODIFIED="1700000000109" TEXT="backtest_performance（バックテストパフォーマンス結果）">
<node CREATED="1700000000110" ID="ID_3_4_1" MODIFIED="1700000000110" TEXT="主キー: (rebalance_date, as_of_date)"/>
<node CREATED="1700000000111" ID="ID_3_4_2" MODIFIED="1700000000111" TEXT="用途: 長期保有型のパフォーマンス評価"/>
<node CREATED="1700000000112" ID="ID_3_4_3" MODIFIED="1700000000112" TEXT="主要カラム">
<node CREATED="1700000000113" ID="ID_3_4_3_1" MODIFIED="1700000000113" TEXT="rebalance_date: リバランス日（YYYY-MM-DD）"/>
<node CREATED="1700000000114" ID="ID_3_4_3_2" MODIFIED="1700000000114" TEXT="as_of_date: 評価日（YYYY-MM-DD）"/>
<node CREATED="1700000000115" ID="ID_3_4_3_3" MODIFIED="1700000000115" TEXT="total_return_pct: ポートフォリオ全体の総リターン（%）"/>
<node CREATED="1700000000116" ID="ID_3_4_3_4" MODIFIED="1700000000116" TEXT="num_stocks: 銘柄数"/>
<node CREATED="1700000000117" ID="ID_3_4_3_5" MODIFIED="1700000000117" TEXT="num_stocks_with_price: 価格データがある銘柄数"/>
<node CREATED="1700000000118" ID="ID_3_4_3_6" MODIFIED="1700000000118" TEXT="avg_return_pct: 平均リターン（%）"/>
<node CREATED="1700000000119" ID="ID_3_4_3_7" MODIFIED="1700000000119" TEXT="min_return_pct: 最小リターン（%）"/>
<node CREATED="1700000000120" ID="ID_3_4_3_8" MODIFIED="1700000000120" TEXT="max_return_pct: 最大リターン（%）"/>
<node CREATED="1700000000121" ID="ID_3_4_3_9" MODIFIED="1700000000121" TEXT="topix_return_pct: TOPIXリターン（%）"/>
<node CREATED="1700000000122" ID="ID_3_4_3_10" MODIFIED="1700000000122" TEXT="excess_return_pct: 超過リターン（%）"/>
</node>
</node>
<node CREATED="1700000000123" ID="ID_3_5" MODIFIED="1700000000123" TEXT="backtest_stock_performance（バックテスト銘柄別パフォーマンス）">
<node CREATED="1700000000124" ID="ID_3_5_1" MODIFIED="1700000000124" TEXT="主キー: (rebalance_date, as_of_date, code)"/>
<node CREATED="1700000000125" ID="ID_3_5_2" MODIFIED="1700000000125" TEXT="用途: 長期保有型の個別銘柄評価"/>
<node CREATED="1700000000126" ID="ID_3_5_3" MODIFIED="1700000000126" TEXT="主要カラム">
<node CREATED="1700000000127" ID="ID_3_5_3_1" MODIFIED="1700000000127" TEXT="rebalance_date: リバランス日（YYYY-MM-DD）"/>
<node CREATED="1700000000128" ID="ID_3_5_3_2" MODIFIED="1700000000128" TEXT="as_of_date: 評価日（YYYY-MM-DD）"/>
<node CREATED="1700000000129" ID="ID_3_5_3_3" MODIFIED="1700000000129" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000130" ID="ID_3_5_3_4" MODIFIED="1700000000130" TEXT="weight: ウェイト"/>
<node CREATED="1700000000131" ID="ID_3_5_3_5" MODIFIED="1700000000131" TEXT="rebalance_price: 購入価格（リバランス日の翌営業日の始値）"/>
<node CREATED="1700000000132" ID="ID_3_5_3_6" MODIFIED="1700000000132" TEXT="current_price: 評価価格（評価日時点の終値）"/>
<node CREATED="1700000000133" ID="ID_3_5_3_7" MODIFIED="1700000000133" TEXT="split_multiplier: 分割倍率"/>
<node CREATED="1700000000134" ID="ID_3_5_3_8" MODIFIED="1700000000134" TEXT="adjusted_current_price: 調整済み評価価格"/>
<node CREATED="1700000000135" ID="ID_3_5_3_9" MODIFIED="1700000000135" TEXT="return_pct: リターン（%）"/>
<node CREATED="1700000000136" ID="ID_3_5_3_10" MODIFIED="1700000000136" TEXT="investment_amount: 投資金額（仮想金額）"/>
<node CREATED="1700000000137" ID="ID_3_5_3_11" MODIFIED="1700000000137" TEXT="topix_return_pct: TOPIXリターン（%）"/>
<node CREATED="1700000000138" ID="ID_3_5_3_12" MODIFIED="1700000000138" TEXT="excess_return_pct: 超過リターン（%）"/>
</node>
</node>
</node>
<node CREATED="1700000000139" ID="ID_3c" MODIFIED="1700000000139" POSITION="right" TEXT="3b. 月次リバランス型テーブル（monthly_rebalance_ 接頭辞）">
<node CREATED="1700000000140" ID="ID_3c_1" MODIFIED="1700000000140" TEXT="monthly_rebalance_final_selected_candidates: 最終選定候補・パラメータ"/>
<node CREATED="1700000000141" ID="ID_3c_2" MODIFIED="1700000000141" TEXT="monthly_rebalance_candidate_performance: パフォーマンス指標"/>
<node CREATED="1700000000142" ID="ID_3c_3" MODIFIED="1700000000142" TEXT="monthly_rebalance_candidate_monthly_returns: 月次超過リターン時系列"/>
<node CREATED="1700000000143" ID="ID_3c_4" MODIFIED="1700000000143" TEXT="monthly_rebalance_candidate_detailed_metrics: 詳細メトリクス"/>
<node CREATED="1700000000144" ID="ID_3c_5" MODIFIED="1700000000144" TEXT="optimize_timeseries の結果保存先（save_to_db 時）"/>
</node>
<node CREATED="1700000002195" ID="ID_4b" MODIFIED="1700000002195" POSITION="left" TEXT="4. 選定・実行テーブル（strategy_runs 系）">
<node CREATED="1700000002200" ID="ID_4b_1" MODIFIED="1700000002200" TEXT="strategy_runs（実行メタデータ）">
<node CREATED="1700000002201" ID="ID_4b_1_1" MODIFIED="1700000002201" TEXT="主キー: run_id"/>
<node CREATED="1700000002202" ID="ID_4b_1_2" MODIFIED="1700000002202" TEXT="主要カラム: mode, run_type, score_profile, params_json, asof, start_date, end_date, objective_name, objective_value, parent_run_id, created_at"/>
</node>
<node CREATED="1700000002203" ID="ID_4b_2" MODIFIED="1700000002203" TEXT="portfolio_snapshots（リバランス日別選定結果）">
<node CREATED="1700000002204" ID="ID_4b_2_1" MODIFIED="1700000002204" TEXT="主キー: (run_id, rebalance_date, code) / FK: run_id → strategy_runs"/>
<node CREATED="1700000002205" ID="ID_4b_2_2" MODIFIED="1700000002205" TEXT="主要カラム: rank, weight, total_score, core_score_ref, entry_score_ref, bucket, action, detail_json"/>
</node>
<node CREATED="1700000002206" ID="ID_4b_3" MODIFIED="1700000002206" TEXT="performance_series（日付別時系列）">
<node CREATED="1700000002207" ID="ID_4b_3_1" MODIFIED="1700000002207" TEXT="主キー: (run_id, date) / FK: run_id → strategy_runs"/>
<node CREATED="1700000002208" ID="ID_4b_3_2" MODIFIED="1700000002208" TEXT="主要カラム: nav, return, benchmark_return, excess_return, drawdown, turnover"/>
</node>
<node CREATED="1700000002209" ID="ID_4b_4" MODIFIED="1700000002209" TEXT="performance_summary（run 単位集計）">
<node CREATED="1700000002210" ID="ID_4b_4_1" MODIFIED="1700000002210" TEXT="主キー: run_id / FK: run_id → strategy_runs"/>
<node CREATED="1700000002211" ID="ID_4b_4_2" MODIFIED="1700000002211" TEXT="主要カラム: cagr, sharpe, maxdd, calmar, avg_turnover, hit_ratio, detail_json"/>
</node>
<node CREATED="1700000002212" ID="ID_4b_5" MODIFIED="1700000002212" TEXT="live_holdings（実保有・optional）">
<node CREATED="1700000002213" ID="ID_4b_5_1" MODIFIED="1700000002213" TEXT="主キー: (asof_date, code)"/>
<node CREATED="1700000002214" ID="ID_4b_5_2" MODIFIED="1700000002214" TEXT="主要カラム: shares, avg_cost, market_value, status"/>
</node>
</node>
<node CREATED="1700000000195" ID="ID_5" MODIFIED="1700000000195" POSITION="left" TEXT="5. テーブル関係性">
<node CREATED="1700000000202" ID="ID_5_2" MODIFIED="1700000000202" TEXT="共通テーブル">
<node CREATED="1700000000203" ID="ID_5_2_1" MODIFIED="1700000000203" TEXT="features_monthly: 特徴量ソース"/>
<node CREATED="1700000000204" ID="ID_5_2_2" MODIFIED="1700000000204" TEXT="prices_daily: 価格データソース"/>
<node CREATED="1700000000205" ID="ID_5_2_3" MODIFIED="1700000000205" TEXT="fins_statements: 財務データソース"/>
<node CREATED="1700000000206" ID="ID_5_2_4" MODIFIED="1700000000206" TEXT="index_daily: TOPIX比較用"/>
</node>
<node CREATED="1700000002220" ID="ID_5_3" MODIFIED="1700000002220" TEXT="strategy_runs を親に">
<node CREATED="1700000002221" ID="ID_5_3_1" MODIFIED="1700000002221" TEXT="portfolio_snapshots (run_id), performance_series (run_id), performance_summary (run_id)"/>
</node>
</node>
<node CREATED="1700000000207" ID="ID_6" MODIFIED="1700000000207" POSITION="left" TEXT="6. インデックス">
<node CREATED="1700000002215" ID="ID_6_4" MODIFIED="1700000002215" TEXT="選定・実行テーブル用">
<node CREATED="1700000002216" ID="ID_6_4_1" MODIFIED="1700000002216" TEXT="ix_portfolio_snapshots_run_rebalance: (run_id, rebalance_date)"/>
<node CREATED="1700000002217" ID="ID_6_4_2" MODIFIED="1700000002217" TEXT="ix_performance_series_run_date: (run_id, date)"/>
</node>
</node>
<node CREATED="1700000000217" ID="ID_7" MODIFIED="1700000000217" POSITION="left" TEXT="7. 命名規則">
<node CREATED="1700000000221" ID="ID_7_2" MODIFIED="1700000000221" TEXT="長期保有型テーブル">
<node CREATED="1700000000222" ID="ID_7_2_1" MODIFIED="1700000000222" TEXT="接頭辞なし（標準的な命名）"/>
<node CREATED="1700000000223" ID="ID_7_2_2" MODIFIED="1700000000223" TEXT="例: portfolio_monthly, holdings, backtest_performance"/>
</node>
<node CREATED="1700000000224" ID="ID_7_3" MODIFIED="1700000000224" TEXT="月次リバランス型テーブル">
<node CREATED="1700000000225" ID="ID_7_3_1" MODIFIED="1700000000225" TEXT="接頭辞: monthly_rebalance_"/>
<node CREATED="1700000000226" ID="ID_7_3_2" MODIFIED="1700000000226" TEXT="例: monthly_rebalance_final_selected_candidates, monthly_rebalance_candidate_performance"/>
</node>
</node>
</node>
</map>















