<map version="1.0.1">
<!-- To view this file, download free mind mapping software FreeMind from http://freemind.sourceforge.net -->
<node CREATED="1700000000000" ID="ID_ROOT" MODIFIED="1700000000000" TEXT="投資アルゴリズム データベース構造">
<node CREATED="1700000000001" ID="ID_1" MODIFIED="1700000000001" POSITION="right" TEXT="データベース情報">
<node CREATED="1700000000002" ID="ID_1_1" MODIFIED="1700000000002" TEXT="種類: SQLite"/>
<node CREATED="1700000000003" ID="ID_1_2" MODIFIED="1700000000003" TEXT="パス: C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite"/>
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
</node>
<node CREATED="1700000000065" ID="ID_3" MODIFIED="1700000000065" POSITION="right" TEXT="2. 長期保有型テーブル">
<node CREATED="1700000000066" ID="ID_3_1" MODIFIED="1700000000066" TEXT="portfolio_monthly（月次ポートフォリオ）">
<node CREATED="1700000000067" ID="ID_3_1_1" MODIFIED="1700000000067" TEXT="主キー: (rebalance_date, code)"/>
<node CREATED="1700000000068" ID="ID_3_1_2" MODIFIED="1700000000068" TEXT="用途">
<node CREATED="1700000000069" ID="ID_3_1_2_1" MODIFIED="1700000000069" TEXT="最適化時の一時保存（最適化後は削除）"/>
<node CREATED="1700000000070" ID="ID_3_1_2_2" MODIFIED="1700000000070" TEXT="monthly_run.py実行時の参考情報として保存"/>
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
<node CREATED="1700000000139" ID="ID_4" MODIFIED="1700000000139" POSITION="left" TEXT="3. 月次リバランス型テーブル（monthly_rebalance_接頭辞）">
<node CREATED="1700000000140" ID="ID_4_1" MODIFIED="1700000000140" TEXT="monthly_rebalance_portfolio（月次リバランス型専用ポートフォリオ）">
<node CREATED="1700000000141" ID="ID_4_1_1" MODIFIED="1700000000141" TEXT="主キー: (rebalance_date, code)"/>
<node CREATED="1700000000142" ID="ID_4_1_2" MODIFIED="1700000000142" TEXT="用途: 月次リバランス型の確定結果として保存"/>
<node CREATED="1700000000143" ID="ID_4_1_3" MODIFIED="1700000000143" TEXT="主要カラム">
<node CREATED="1700000000144" ID="ID_4_1_3_1" MODIFIED="1700000000144" TEXT="rebalance_date: リバランス日（YYYY-MM-DD）"/>
<node CREATED="1700000000145" ID="ID_4_1_3_2" MODIFIED="1700000000145" TEXT="code: 銘柄コード"/>
<node CREATED="1700000000146" ID="ID_4_1_3_3" MODIFIED="1700000000146" TEXT="weight: ウェイト"/>
<node CREATED="1700000000147" ID="ID_4_1_3_4" MODIFIED="1700000000147" TEXT="core_score: ファンダメンタルスコア"/>
<node CREATED="1700000000148" ID="ID_4_1_3_5" MODIFIED="1700000000148" TEXT="entry_score: エントリースコア"/>
<node CREATED="1700000000149" ID="ID_4_1_3_6" MODIFIED="1700000000149" TEXT="reason: 採用理由（JSON文字列）"/>
</node>
</node>
<node CREATED="1700000000150" ID="ID_4_2" MODIFIED="1700000000150" TEXT="monthly_rebalance_final_selected_candidates（最終選定候補・基本情報とパラメータ）">
<node CREATED="1700000000151" ID="ID_4_2_1" MODIFIED="1700000000151" TEXT="主キー: trial_number"/>
<node CREATED="1700000000152" ID="ID_4_2_2" MODIFIED="1700000000152" TEXT="用途: 月次リバランス型の最適化結果"/>
<node CREATED="1700000000153" ID="ID_4_2_3" MODIFIED="1700000000153" TEXT="主要カラム">
<node CREATED="1700000000154" ID="ID_4_2_3_1" MODIFIED="1700000000154" TEXT="trial_number: トライアル番号"/>
<node CREATED="1700000000155" ID="ID_4_2_3_2" MODIFIED="1700000000155" TEXT="cluster: クラスタ番号"/>
<node CREATED="1700000000156" ID="ID_4_2_3_3" MODIFIED="1700000000156" TEXT="train_sharpe: Train期間のSharpe比"/>
<node CREATED="1700000000157" ID="ID_4_2_3_4" MODIFIED="1700000000157" TEXT="ranking: ランキング"/>
<node CREATED="1700000000158" ID="ID_4_2_3_5" MODIFIED="1700000000158" TEXT="recommendation_text: 推奨テキスト"/>
<node CREATED="1700000000159" ID="ID_4_2_3_6" MODIFIED="1700000000159" TEXT="パラメータ: w_quality, w_growth, w_record_high, w_size, w_value, w_forward_per, roe_min, bb_weight, liquidity_quantile_cut, rsi_base, rsi_max, bb_z_base, bb_z_max"/>
</node>
</node>
<node CREATED="1700000000160" ID="ID_4_3" MODIFIED="1700000000160" TEXT="monthly_rebalance_candidate_performance（最終選定候補のパフォーマンス指標）">
<node CREATED="1700000000161" ID="ID_4_3_1" MODIFIED="1700000000161" TEXT="主キー: id (AUTOINCREMENT)"/>
<node CREATED="1700000000162" ID="ID_4_3_2" MODIFIED="1700000000162" TEXT="外部キー: trial_number → monthly_rebalance_final_selected_candidates"/>
<node CREATED="1700000000163" ID="ID_4_3_3" MODIFIED="1700000000163" TEXT="用途: 月次リバランス型のパフォーマンス集計"/>
<node CREATED="1700000000164" ID="ID_4_3_4" MODIFIED="1700000000164" TEXT="主要カラム">
<node CREATED="1700000000165" ID="ID_4_3_4_1" MODIFIED="1700000000165" TEXT="trial_number: トライアル番号"/>
<node CREATED="1700000000166" ID="ID_4_3_4_2" MODIFIED="1700000000166" TEXT="evaluation_type: 評価タイプ（2023-2024 Holdout期間等）"/>
<node CREATED="1700000000167" ID="ID_4_3_4_3" MODIFIED="1700000000167" TEXT="sharpe_excess_0bps/10bps/20bps/30bps: コスト別Sharpe超過"/>
<node CREATED="1700000000168" ID="ID_4_3_4_4" MODIFIED="1700000000168" TEXT="sharpe_excess_2023/2024: 年別Sharpe超過"/>
<node CREATED="1700000000169" ID="ID_4_3_4_5" MODIFIED="1700000000169" TEXT="cagr_excess_2023/2024: 年別CAGR超過"/>
<node CREATED="1700000000170" ID="ID_4_3_4_6" MODIFIED="1700000000170" TEXT="max_drawdown: 最大ドローダウン"/>
<node CREATED="1700000000171" ID="ID_4_3_4_7" MODIFIED="1700000000171" TEXT="turnover_annual: 年間ターンオーバー"/>
<node CREATED="1700000000172" ID="ID_4_3_4_8" MODIFIED="1700000000172" TEXT="2025疑似ライブ指標: sharpe_excess_2025_10bps, cagr_excess_2025_10bps, max_drawdown_2025"/>
</node>
</node>
<node CREATED="1700000000173" ID="ID_4_4" MODIFIED="1700000000173" TEXT="monthly_rebalance_candidate_monthly_returns（月次超過リターン時系列）">
<node CREATED="1700000000174" ID="ID_4_4_1" MODIFIED="1700000000174" TEXT="主キー: id (AUTOINCREMENT)"/>
<node CREATED="1700000000175" ID="ID_4_4_2" MODIFIED="1700000000175" TEXT="外部キー: trial_number → monthly_rebalance_final_selected_candidates"/>
<node CREATED="1700000000176" ID="ID_4_4_3" MODIFIED="1700000000176" TEXT="ユニーク制約: (trial_number, evaluation_period, period_date)"/>
<node CREATED="1700000000177" ID="ID_4_4_4" MODIFIED="1700000000177" TEXT="用途: 月次リバランス型の時系列データ"/>
<node CREATED="1700000000178" ID="ID_4_4_5" MODIFIED="1700000000178" TEXT="主要カラム">
<node CREATED="1700000000179" ID="ID_4_4_5_1" MODIFIED="1700000000179" TEXT="trial_number: トライアル番号"/>
<node CREATED="1700000000180" ID="ID_4_4_5_2" MODIFIED="1700000000180" TEXT="evaluation_period: 評価期間（holdout_2023_2024/holdout_2025等）"/>
<node CREATED="1700000000181" ID="ID_4_4_5_3" MODIFIED="1700000000181" TEXT="period_date: 期間日（YYYY-MM-DD、月末日）"/>
<node CREATED="1700000000182" ID="ID_4_4_5_4" MODIFIED="1700000000182" TEXT="excess_return: 月次超過リターン（小数、例: 0.05 = 5%）"/>
</node>
</node>
<node CREATED="1700000000183" ID="ID_4_5" MODIFIED="1700000000183" TEXT="monthly_rebalance_candidate_detailed_metrics（詳細パフォーマンス指標）">
<node CREATED="1700000000184" ID="ID_4_5_1" MODIFIED="1700000000184" TEXT="主キー: id (AUTOINCREMENT)"/>
<node CREATED="1700000000185" ID="ID_4_5_2" MODIFIED="1700000000185" TEXT="外部キー: trial_number → monthly_rebalance_final_selected_candidates"/>
<node CREATED="1700000000186" ID="ID_4_5_3" MODIFIED="1700000000186" TEXT="ユニーク制約: (trial_number, evaluation_period, cost_bps)"/>
<node CREATED="1700000000187" ID="ID_4_5_4" MODIFIED="1700000000187" TEXT="用途: 月次リバランス型の詳細メトリクス"/>
<node CREATED="1700000000188" ID="ID_4_5_5" MODIFIED="1700000000188" TEXT="主要カラム">
<node CREATED="1700000000189" ID="ID_4_5_5_1" MODIFIED="1700000000189" TEXT="trial_number: トライアル番号"/>
<node CREATED="1700000000190" ID="ID_4_5_5_2" MODIFIED="1700000000190" TEXT="evaluation_period: 評価期間（holdout_2023_2024/holdout_2025等）"/>
<node CREATED="1700000000191" ID="ID_4_5_5_3" MODIFIED="1700000000191" TEXT="cost_bps: 取引コスト（bps、0.0/10.0/20.0等）"/>
<node CREATED="1700000000192" ID="ID_4_5_5_4" MODIFIED="1700000000192" TEXT="基本指標: cagr, mean_return, mean_excess_return, total_return, volatility, sharpe_ratio, sortino_ratio, win_rate, profit_factor"/>
<node CREATED="1700000000193" ID="ID_4_5_5_5" MODIFIED="1700000000193" TEXT="詳細指標: num_periods, num_missing_stocks, mean_excess_return_monthly/annual, vol_excess_monthly/annual, max_drawdown_topix, turnover_monthly/annual"/>
<node CREATED="1700000000194" ID="ID_4_5_5_6" MODIFIED="1700000000194" TEXT="コスト関連: sharpe_excess_after_cost, mean_excess_return_after_cost_monthly/annual, vol_excess_after_cost_monthly/annual, annual_cost_bps/pct"/>
</node>
</node>
</node>
<node CREATED="1700000000195" ID="ID_5" MODIFIED="1700000000195" POSITION="left" TEXT="4. テーブル関係性">
<node CREATED="1700000000196" ID="ID_5_1" MODIFIED="1700000000196" TEXT="月次リバランス型の外部キー関係">
<node CREATED="1700000000197" ID="ID_5_1_1" MODIFIED="1700000000197" TEXT="monthly_rebalance_final_selected_candidates (trial_number)"/>
<node CREATED="1700000000198" ID="ID_5_1_2" MODIFIED="1700000000198" TEXT="↓"/>
<node CREATED="1700000000199" ID="ID_5_1_3" MODIFIED="1700000000199" TEXT="monthly_rebalance_candidate_performance (trial_number)"/>
<node CREATED="1700000000200" ID="ID_5_1_4" MODIFIED="1700000000200" TEXT="monthly_rebalance_candidate_monthly_returns (trial_number)"/>
<node CREATED="1700000000201" ID="ID_5_1_5" MODIFIED="1700000000201" TEXT="monthly_rebalance_candidate_detailed_metrics (trial_number)"/>
</node>
<node CREATED="1700000000202" ID="ID_5_2" MODIFIED="1700000000202" TEXT="共通テーブルとの関係">
<node CREATED="1700000000203" ID="ID_5_2_1" MODIFIED="1700000000203" TEXT="features_monthly: 全テーブルの特徴量ソース"/>
<node CREATED="1700000000204" ID="ID_5_2_2" MODIFIED="1700000000204" TEXT="prices_daily: 価格データソース"/>
<node CREATED="1700000000205" ID="ID_5_2_3" MODIFIED="1700000000205" TEXT="fins_statements: 財務データソース"/>
<node CREATED="1700000000206" ID="ID_5_2_4" MODIFIED="1700000000206" TEXT="index_daily: TOPIX比較用"/>
</node>
</node>
<node CREATED="1700000000207" ID="ID_6" MODIFIED="1700000000207" POSITION="left" TEXT="5. インデックス">
<node CREATED="1700000000208" ID="ID_6_1" MODIFIED="1700000000208" TEXT="idx_monthly_rebalance_performance_trial">
<node CREATED="1700000000209" ID="ID_6_1_1" MODIFIED="1700000000209" TEXT="テーブル: monthly_rebalance_candidate_performance"/>
<node CREATED="1700000000210" ID="ID_6_1_2" MODIFIED="1700000000210" TEXT="カラム: trial_number"/>
</node>
<node CREATED="1700000000211" ID="ID_6_2" MODIFIED="1700000000211" TEXT="idx_monthly_rebalance_returns_trial_period">
<node CREATED="1700000000212" ID="ID_6_2_1" MODIFIED="1700000000212" TEXT="テーブル: monthly_rebalance_candidate_monthly_returns"/>
<node CREATED="1700000000213" ID="ID_6_2_2" MODIFIED="1700000000213" TEXT="カラム: (trial_number, evaluation_period)"/>
</node>
<node CREATED="1700000000214" ID="ID_6_3" MODIFIED="1700000000214" TEXT="idx_monthly_rebalance_detailed_metrics_trial_period">
<node CREATED="1700000000215" ID="ID_6_3_1" MODIFIED="1700000000215" TEXT="テーブル: monthly_rebalance_candidate_detailed_metrics"/>
<node CREATED="1700000000216" ID="ID_6_3_2" MODIFIED="1700000000216" TEXT="カラム: (trial_number, evaluation_period)"/>
</node>
</node>
<node CREATED="1700000000217" ID="ID_7" MODIFIED="1700000000217" POSITION="left" TEXT="6. 命名規則">
<node CREATED="1700000000218" ID="ID_7_1" MODIFIED="1700000000218" TEXT="月次リバランス型テーブル">
<node CREATED="1700000000219" ID="ID_7_1_1" MODIFIED="1700000000219" TEXT="接頭辞: monthly_rebalance_"/>
<node CREATED="1700000000220" ID="ID_7_1_2" MODIFIED="1700000000220" TEXT="目的: 長期保有型と明確に区別"/>
</node>
<node CREATED="1700000000221" ID="ID_7_2" MODIFIED="1700000000221" TEXT="長期保有型テーブル">
<node CREATED="1700000000222" ID="ID_7_2_1" MODIFIED="1700000000222" TEXT="接頭辞なし（標準的な命名）"/>
<node CREATED="1700000000223" ID="ID_7_2_2" MODIFIED="1700000000223" TEXT="例: portfolio_monthly, holdings, backtest_performance"/>
</node>
</node>
</node>
</map>

