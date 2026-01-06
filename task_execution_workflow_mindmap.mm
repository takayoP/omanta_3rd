<map version="1.0.1">
<!-- To view this file, download free mind mapping software FreeMind from http://freemind.sourceforge.net -->
<node CREATED="1700000000000" ID="ID_ROOT" MODIFIED="1700000000000" TEXT="タスク実行ワークフロー">
<node CREATED="1700000000001" ID="ID_1" MODIFIED="1700000000001" POSITION="right" TEXT="【共通】データ準備">
<node CREATED="1700000000002" ID="ID_1_1" MODIFIED="1700000000002" TEXT="1. データベース初期化">
<node CREATED="1700000000003" ID="ID_1_1_1" MODIFIED="1700000000003" TEXT="python -m omanta_3rd.jobs.init_db"/>
</node>
<node CREATED="1700000000004" ID="ID_1_2" MODIFIED="1700000000004" TEXT="2. データ更新">
<node CREATED="1700000000005" ID="ID_1_2_1" MODIFIED="1700000000005" TEXT="銘柄情報: python update_all_data.py --target listed"/>
<node CREATED="1700000000006" ID="ID_1_2_2" MODIFIED="1700000000006" TEXT="価格データ: python update_all_data.py --target prices"/>
<node CREATED="1700000000007" ID="ID_1_2_3" MODIFIED="1700000000007" TEXT="財務データ: python update_all_data.py --target fins"/>
<node CREATED="1700000000008" ID="ID_1_2_4" MODIFIED="1700000000008" TEXT="指数データ: python update_all_data.py --target indices"/>
</node>
</node>
<node CREATED="1700000000009" ID="ID_2" MODIFIED="1700000000009" POSITION="right" TEXT="【長期保有型】運用ワークフロー">
<node CREATED="1700000000010" ID="ID_2_1" MODIFIED="1700000000010" TEXT="A. パラメータ最適化（初回・定期的）">
<node CREATED="1700000000011" ID="ID_2_1_1" MODIFIED="1700000000011" TEXT="基本コマンド">
<node CREATED="1700000000012" ID="ID_2_1_1_1" MODIFIED="1700000000012" TEXT="python -m omanta_3rd.jobs.optimize_longterm --start 2021-01-01 --end 2024-12-31 --study-type C --n-trials 200"/>
</node>
<node CREATED="1700000000013" ID="ID_2_1_2" MODIFIED="1700000000013" TEXT="実行例">
<node CREATED="1700000000014" ID="ID_2_1_2_1" MODIFIED="1700000000014" TEXT="Study A（BB寄り・低ROE）: --study-type A"/>
<node CREATED="1700000000015" ID="ID_2_1_2_2" MODIFIED="1700000000015" TEXT="Study B（Value寄り・ROE高め）: --study-type B"/>
<node CREATED="1700000000016" ID="ID_2_1_2_3" MODIFIED="1700000000016" TEXT="Study C（統合・広範囲）: --study-type C"/>
</node>
<node CREATED="1700000000017" ID="ID_2_1_3" MODIFIED="1700000000017" TEXT="成果物">
<node CREATED="1700000000018" ID="ID_2_1_3_1" MODIFIED="1700000000018" TEXT="最適化結果JSONファイル"/>
<node CREATED="1700000000019" ID="ID_2_1_3_2" MODIFIED="1700000000019" TEXT="best_params（StrategyParams）"/>
</node>
</node>
<node CREATED="1700000000020" ID="ID_2_2" MODIFIED="1700000000020" TEXT="B. Walk-Forward Analysis（検証）">
<node CREATED="1700000000021" ID="ID_2_2_1" MODIFIED="1700000000021" TEXT="基本コマンド">
<node CREATED="1700000000022" ID="ID_2_2_1_1" MODIFIED="1700000000022" TEXT="python walk_forward_longterm.py --start 2020-01-01 --end 2025-12-31 --horizon 12 --fold-type roll --n-trials 30 --study-type C --train-min-years 2.0 --holdout-eval-year 2025"/>
</node>
<node CREATED="1700000000023" ID="ID_2_2_2" MODIFIED="1700000000023" TEXT="実行例（n_trials=100）">
<node CREATED="1700000000024" ID="ID_2_2_2_1" MODIFIED="1700000000024" TEXT="python run_walk_forward_analysis_roll_n100.py"/>
</node>
<node CREATED="1700000000025" ID="ID_2_2_3" MODIFIED="1700000000025" TEXT="実行例（24M/36M同時）">
<node CREATED="1700000000026" ID="ID_2_2_3_1" MODIFIED="1700000000026" TEXT=".\run_walk_forward_analysis_roll_24M_36M.ps1"/>
</node>
<node CREATED="1700000000027" ID="ID_2_2_4" MODIFIED="1700000000027" TEXT="成果物">
<node CREATED="1700000000028" ID="ID_2_2_4_1" MODIFIED="1700000000028" TEXT="walk_forward_longterm_*M_roll_evalYear2025.json"/>
<node CREATED="1700000000029" ID="ID_2_2_4_2" MODIFIED="1700000000029" TEXT="params_by_fold.json"/>
<node CREATED="1700000000030" ID="ID_2_2_4_3" MODIFIED="1700000000030" TEXT="params_operational.json"/>
</node>
</node>
<node CREATED="1700000000031" ID="ID_2_3" MODIFIED="1700000000031" TEXT="C. 月次運用（毎月実行）">
<node CREATED="1700000000032" ID="ID_2_3_1" MODIFIED="1700000000032" TEXT="ステップ1: 特徴量計算とポートフォリオ選定">
<node CREATED="1700000000033" ID="ID_2_3_1_1" MODIFIED="1700000000033" TEXT="python -m omanta_3rd.jobs.monthly_run"/>
<node CREATED="1700000000034" ID="ID_2_3_1_2" MODIFIED="1700000000034" TEXT="特定日付: python -m omanta_3rd.jobs.monthly_run --asof 2025-12-19"/>
</node>
<node CREATED="1700000000035" ID="ID_2_3_2" MODIFIED="1700000000035" TEXT="ステップ2: スクリーニング結果を確認">
<node CREATED="1700000000036" ID="ID_2_3_2_1" MODIFIED="1700000000036" TEXT="portfolio_monthlyテーブルを確認"/>
<node CREATED="1700000000037" ID="ID_2_3_2_2" MODIFIED="1700000000037" TEXT="core_score、entry_scoreを確認"/>
</node>
<node CREATED="1700000000038" ID="ID_2_3_3" MODIFIED="1700000000038" TEXT="ステップ3: 保有銘柄管理">
<node CREATED="1700000000039" ID="ID_2_3_3_1" MODIFIED="1700000000039" TEXT="購入: python -m src.omanta_3rd.jobs.add_holding --purchase-date 2025-01-01 --code 7203 --shares 100 --purchase-price 2500 --broker &quot;SBI&quot;"/>
<node CREATED="1700000000040" ID="ID_2_3_3_2" MODIFIED="1700000000040" TEXT="売却: python -m src.omanta_3rd.jobs.sell_holding --holding-id 1 --sell-date 2025-12-28"/>
<node CREATED="1700000000041" ID="ID_2_3_3_3" MODIFIED="1700000000041" TEXT="更新: python -m src.omanta_3rd.jobs.update_holdings"/>
</node>
<node CREATED="1700000000042" ID="ID_2_3_4" MODIFIED="1700000000042" TEXT="ステップ4: パフォーマンス確認（オプション）">
<node CREATED="1700000000043" ID="ID_2_3_4_1" MODIFIED="1700000000043" TEXT="特定ポートフォリオ: python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19"/>
<node CREATED="1700000000044" ID="ID_2_3_4_2" MODIFIED="1700000000044" TEXT="全ポートフォリオ: python -m omanta_3rd.jobs.backtest"/>
<node CREATED="1700000000045" ID="ID_2_3_4_3" MODIFIED="1700000000045" TEXT="DB保存: python -m omanta_3rd.jobs.backtest --save-to-db"/>
</node>
</node>
<node CREATED="1700000000046" ID="ID_2_4" MODIFIED="1700000000046" TEXT="D. 運用フロー図">
<node CREATED="1700000000047" ID="ID_2_4_1" MODIFIED="1700000000047" TEXT="1. データ更新（毎日・週次）"/>
<node CREATED="1700000000048" ID="ID_2_4_2" MODIFIED="1700000000048" TEXT="2. 月次実行（毎月1回）→ portfolio_monthly"/>
<node CREATED="1700000000049" ID="ID_2_4_3" MODIFIED="1700000000049" TEXT="3. スクリーニング結果確認"/>
<node CREATED="1700000000050" ID="ID_2_4_4" MODIFIED="1700000000050" TEXT="4. 保有銘柄管理（購入・売却）"/>
<node CREATED="1700000000051" ID="ID_2_4_5" MODIFIED="1700000000051" TEXT="5. パフォーマンス確認（随時）"/>
</node>
</node>
<node CREATED="1700000000052" ID="ID_3" MODIFIED="1700000000052" POSITION="left" TEXT="【月次リバランス型】運用ワークフロー">
<node CREATED="1700000000053" ID="ID_3_1" MODIFIED="1700000000053" TEXT="A. パラメータ最適化（初回・定期的）">
<node CREATED="1700000000054" ID="ID_3_1_1" MODIFIED="1700000000054" TEXT="基本コマンド">
<node CREATED="1700000000055" ID="ID_3_1_1_1" MODIFIED="1700000000055" TEXT="$env:OMP_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000056" ID="ID_3_1_1_2" MODIFIED="1700000000056" TEXT="$env:MKL_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000057" ID="ID_3_1_1_3" MODIFIED="1700000000057" TEXT="$env:OPENBLAS_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000058" ID="ID_3_1_1_4" MODIFIED="1700000000058" TEXT="python -m omanta_3rd.jobs.optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 200 --n-jobs 4"/>
</node>
<node CREATED="1700000000059" ID="ID_3_1_2" MODIFIED="1700000000059" TEXT="実行例（信頼性向上型）">
<node CREATED="1700000000060" ID="ID_3_1_2_1" MODIFIED="1700000000060" TEXT="python -m omanta_3rd.jobs.robust_optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 20 --folds 3"/>
</node>
<node CREATED="1700000000061" ID="ID_3_1_3" MODIFIED="1700000000061" TEXT="成果物">
<node CREATED="1700000000062" ID="ID_3_1_3_1" MODIFIED="1700000000062" TEXT="最適化結果JSONファイル"/>
<node CREATED="1700000000063" ID="ID_3_1_3_2" MODIFIED="1700000000063" TEXT="best_params（StrategyParams + EntryScoreParams）"/>
</node>
</node>
<node CREATED="1700000000064" ID="ID_3_2" MODIFIED="1700000000064" TEXT="B. Holdout検証（推奨）">
<node CREATED="1700000000065" ID="ID_3_2_1" MODIFIED="1700000000065" TEXT="基本コマンド">
<node CREATED="1700000000066" ID="ID_3_2_1_1" MODIFIED="1700000000066" TEXT="python -m omanta_3rd.jobs.holdout_eval_timeseries --train-start 2021-01-01 --train-end 2023-12-31 --holdout-start 2024-01-01 --holdout-end 2024-12-31 --n-trials 50"/>
</node>
<node CREATED="1700000000067" ID="ID_3_2_2" MODIFIED="1700000000067" TEXT="成果物">
<node CREATED="1700000000068" ID="ID_3_2_2_1" MODIFIED="1700000000068" TEXT="Holdout評価結果JSON"/>
<node CREATED="1700000000069" ID="ID_3_2_2_2" MODIFIED="1700000000069" TEXT="パフォーマンスメトリクス"/>
</node>
</node>
<node CREATED="1700000000070" ID="ID_3_3" MODIFIED="1700000000070" TEXT="C. Walk-Forward Analysis（オプション）">
<node CREATED="1700000000071" ID="ID_3_3_1" MODIFIED="1700000000071" TEXT="基本コマンド">
<node CREATED="1700000000072" ID="ID_3_3_1_1" MODIFIED="1700000000072" TEXT="python -m omanta_3rd.jobs.walk_forward_timeseries --start 2021-01-01 --end 2024-12-31 --folds 3 --n-trials 50"/>
</node>
<node CREATED="1700000000073" ID="ID_3_3_2" MODIFIED="1700000000073" TEXT="成果物">
<node CREATED="1700000000074" ID="ID_3_3_2_1" MODIFIED="1700000000074" TEXT="WFA評価結果JSON"/>
<node CREATED="1700000000075" ID="ID_3_3_2_2" MODIFIED="1700000000075" TEXT="fold別パフォーマンス"/>
</node>
</node>
<node CREATED="1700000000076" ID="ID_3_4" MODIFIED="1700000000076" TEXT="D. 【月次リバランス用】評価スクリプト">
<node CREATED="1700000000077" ID="ID_3_4_1" MODIFIED="1700000000077" TEXT="候補群のHoldout検証">
<node CREATED="1700000000078" ID="ID_3_4_1_1" MODIFIED="1700000000078" TEXT="python evaluate_candidates_holdout.py --candidates candidates_studyB_20251231_174014.json --holdout-start 2023-01-01 --holdout-end 2024-12-31 --cost-bps 0.0 --output holdout_results_with_holdings.json --use-cache"/>
</node>
<node CREATED="1700000000079" ID="ID_3_4_2" MODIFIED="1700000000079" TEXT="コスト感度分析">
<node CREATED="1700000000080" ID="ID_3_4_2_1" MODIFIED="1700000000080" TEXT="python evaluate_cost_sensitivity.py --candidates candidates_studyB_20251231_174014.json --holdout-start 2023-01-01 --holdout-end 2024-12-31 --cost-levels 0 10 20 30 --output cost_sensitivity_analysis.json"/>
</node>
<node CREATED="1700000000081" ID="ID_3_4_3" MODIFIED="1700000000081" TEXT="月次パラメータの長期評価">
<node CREATED="1700000000082" ID="ID_3_4_3_1" MODIFIED="1700000000082" TEXT="python evaluate_monthly_params_on_longterm.py"/>
</node>
</node>
<node CREATED="1700000000083" ID="ID_3_5" MODIFIED="1700000000083" TEXT="E. 【月次リバランス用】可視化スクリプト">
<node CREATED="1700000000084" ID="ID_3_5_1" MODIFIED="1700000000084" TEXT="保有銘柄詳細">
<node CREATED="1700000000085" ID="ID_3_5_1_1" MODIFIED="1700000000085" TEXT="python visualize_holdings_details.py"/>
</node>
<node CREATED="1700000000086" ID="ID_3_5_2" MODIFIED="1700000000086" TEXT="エクイティカーブと保有銘柄">
<node CREATED="1700000000087" ID="ID_3_5_2_1" MODIFIED="1700000000087" TEXT="python visualize_equity_curve_and_holdings.py"/>
</node>
<node CREATED="1700000000088" ID="ID_3_5_3" MODIFIED="1700000000088" TEXT="保有銘柄の重複">
<node CREATED="1700000000089" ID="ID_3_5_3_1" MODIFIED="1700000000089" TEXT="python visualize_holdings_overlap.py"/>
</node>
<node CREATED="1700000000090" ID="ID_3_5_4" MODIFIED="1700000000090" TEXT="最適化結果">
<node CREATED="1700000000091" ID="ID_3_5_4_1" MODIFIED="1700000000091" TEXT="python visualize_optimization.py"/>
</node>
</node>
<node CREATED="1700000000092" ID="ID_3_6" MODIFIED="1700000000092" TEXT="F. 【月次リバランス用】データベース保存">
<node CREATED="1700000000093" ID="ID_3_6_1" MODIFIED="1700000000093" TEXT="最終候補の保存">
<node CREATED="1700000000094" ID="ID_3_6_1_1" MODIFIED="1700000000094" TEXT="python save_final_candidates_to_db.py"/>
</node>
<node CREATED="1700000000095" ID="ID_3_6_2" MODIFIED="1700000000095" TEXT="時系列パフォーマンスの保存">
<node CREATED="1700000000096" ID="ID_3_6_2_1" MODIFIED="1700000000096" TEXT="python save_performance_time_series_to_db.py"/>
</node>
<node CREATED="1700000000097" ID="ID_3_6_3" MODIFIED="1700000000097" TEXT="バックテスト結果の保存">
<node CREATED="1700000000098" ID="ID_3_6_3_1" MODIFIED="1700000000098" TEXT="python -m omanta_3rd.jobs.backtest --save-to-db"/>
</node>
</node>
<node CREATED="1700000000099" ID="ID_3_7" MODIFIED="1700000000099" TEXT="G. 運用フロー図">
<node CREATED="1700000000100" ID="ID_3_7_1" MODIFIED="1700000000100" TEXT="1. データ更新（毎日・週次）"/>
<node CREATED="1700000000101" ID="ID_3_7_2" MODIFIED="1700000000101" TEXT="2. パラメータ最適化（定期的・必要時）"/>
<node CREATED="1700000000102" ID="ID_3_7_3" MODIFIED="1700000000102" TEXT="3. Holdout検証（推奨）"/>
<node CREATED="1700000000103" ID="ID_3_7_4" MODIFIED="1700000000103" TEXT="4. 候補群の評価（evaluate_candidates_holdout.py）"/>
<node CREATED="1700000000104" ID="ID_3_7_5" MODIFIED="1700000000104" TEXT="5. コスト感度分析（evaluate_cost_sensitivity.py）"/>
<node CREATED="1700000000105" ID="ID_3_7_6" MODIFIED="1700000000105" TEXT="6. 可視化（visualize_*.py）"/>
<node CREATED="1700000000106" ID="ID_3_7_7" MODIFIED="1700000000106" TEXT="7. データベース保存（save_*.py）"/>
</node>
</node>
<node CREATED="1700000000107" ID="ID_4" MODIFIED="1700000000107" POSITION="left" TEXT="【重要】長期保有型と月次リバランス型の違い">
<node CREATED="1700000000108" ID="ID_4_1" MODIFIED="1700000000108" TEXT="長期保有型">
<node CREATED="1700000000109" ID="ID_4_1_1" MODIFIED="1700000000109" TEXT="最適化: optimize_longterm.py"/>
<node CREATED="1700000000110" ID="ID_4_1_2" MODIFIED="1700000000110" TEXT="検証: walk_forward_longterm.py"/>
<node CREATED="1700000000111" ID="ID_4_1_3" MODIFIED="1700000000111" TEXT="運用: monthly_run.py（参考情報のみ）"/>
<node CREATED="1700000000112" ID="ID_4_1_4" MODIFIED="1700000000112" TEXT="保有期間: 長期（数ヶ月～数年）"/>
<node CREATED="1700000000113" ID="ID_4_1_5" MODIFIED="1700000000113" TEXT="リバランス: 不定期（銘柄入れ替えは少ない）"/>
<node CREATED="1700000000114" ID="ID_4_1_6" MODIFIED="1700000000114" TEXT="評価指標: 年率リターン、最大ドローダウン"/>
</node>
<node CREATED="1700000000115" ID="ID_4_2" MODIFIED="1700000000115" TEXT="月次リバランス型">
<node CREATED="1700000000116" ID="ID_4_2_1" MODIFIED="1700000000116" TEXT="最適化: optimize_timeseries.py"/>
<node CREATED="1700000000117" ID="ID_4_2_2" MODIFIED="1700000000117" TEXT="検証: holdout_eval_timeseries.py / walk_forward_timeseries.py"/>
<node CREATED="1700000000118" ID="ID_4_2_3" MODIFIED="1700000000118" TEXT="評価: evaluate_candidates_holdout.py（月次リバランス用）"/>
<node CREATED="1700000000119" ID="ID_4_2_4" MODIFIED="1700000000119" TEXT="可視化: visualize_*.py（月次リバランス用）"/>
<node CREATED="1700000000120" ID="ID_4_2_5" MODIFIED="1700000000120" TEXT="保存: save_*.py（月次リバランス用）"/>
<node CREATED="1700000000121" ID="ID_4_2_6" MODIFIED="1700000000121" TEXT="保有期間: 短期（1ヶ月）"/>
<node CREATED="1700000000122" ID="ID_4_2_7" MODIFIED="1700000000122" TEXT="リバランス: 毎月（定期的）"/>
<node CREATED="1700000000123" ID="ID_4_2_8" MODIFIED="1700000000123" TEXT="評価指標: Sharpe ratio、CAGR、MaxDD、ターンオーバー"/>
</node>
</node>
<node CREATED="1700000000124" ID="ID_5" MODIFIED="1700000000124" POSITION="left" TEXT="【実行例】具体的なシナリオ">
<node CREATED="1700000000125" ID="ID_5_1" MODIFIED="1700000000125" TEXT="シナリオ1: 長期保有型の初回セットアップ">
<node CREATED="1700000000126" ID="ID_5_1_1" MODIFIED="1700000000126" TEXT="1. データ更新: python update_all_data.py"/>
<node CREATED="1700000000127" ID="ID_5_1_2" MODIFIED="1700000000127" TEXT="2. 最適化: python -m omanta_3rd.jobs.optimize_longterm --start 2021-01-01 --end 2024-12-31 --study-type C --n-trials 200"/>
<node CREATED="1700000000128" ID="ID_5_1_3" MODIFIED="1700000000128" TEXT="3. WFA検証: python run_walk_forward_analysis_roll_n100.py"/>
<node CREATED="1700000000129" ID="ID_5_1_4" MODIFIED="1700000000129" TEXT="4. パラメータ確認: params_operational.jsonを確認"/>
<node CREATED="1700000000130" ID="ID_5_1_5" MODIFIED="1700000000130" TEXT="5. 月次実行: python -m omanta_3rd.jobs.monthly_run"/>
</node>
<node CREATED="1700000000131" ID="ID_5_2" MODIFIED="1700000000131" TEXT="シナリオ2: 月次リバランス型の初回セットアップ">
<node CREATED="1700000000132" ID="ID_5_2_1" MODIFIED="1700000000132" TEXT="1. データ更新: python update_all_data.py"/>
<node CREATED="1700000000133" ID="ID_5_2_2" MODIFIED="1700000000133" TEXT="2. 環境変数設定: $env:OMP_NUM_THREADS=&quot;1&quot; ..."/>
<node CREATED="1700000000134" ID="ID_5_2_3" MODIFIED="1700000000134" TEXT="3. 最適化: python -m omanta_3rd.jobs.optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 200"/>
<node CREATED="1700000000135" ID="ID_5_2_4" MODIFIED="1700000000135" TEXT="4. Holdout検証: python -m omanta_3rd.jobs.holdout_eval_timeseries --train-start 2021-01-01 --train-end 2023-12-31 --holdout-start 2024-01-01 --holdout-end 2024-12-31"/>
<node CREATED="1700000000136" ID="ID_5_2_5" MODIFIED="1700000000136" TEXT="5. 候補群評価: python evaluate_candidates_holdout.py --candidates candidates_*.json --holdout-start 2023-01-01 --holdout-end 2024-12-31"/>
<node CREATED="1700000000137" ID="ID_5_2_6" MODIFIED="1700000000137" TEXT="6. 可視化: python visualize_holdings_details.py"/>
<node CREATED="1700000000138" ID="ID_5_2_7" MODIFIED="1700000000138" TEXT="7. DB保存: python save_final_candidates_to_db.py"/>
</node>
<node CREATED="1700000000139" ID="ID_5_3" MODIFIED="1700000000139" TEXT="シナリオ3: 長期保有型の月次運用">
<node CREATED="1700000000140" ID="ID_5_3_1" MODIFIED="1700000000140" TEXT="毎月1回の実行フロー">
<node CREATED="1700000000141" ID="ID_5_3_1_1" MODIFIED="1700000000141" TEXT="1. データ更新（価格・財務）: python update_all_data.py --target prices --target fins"/>
<node CREATED="1700000000142" ID="ID_5_3_1_2" MODIFIED="1700000000142" TEXT="2. 月次実行: python -m omanta_3rd.jobs.monthly_run"/>
<node CREATED="1700000000143" ID="ID_5_3_1_3" MODIFIED="1700000000143" TEXT="3. スクリーニング結果確認（portfolio_monthlyテーブル）"/>
<node CREATED="1700000000144" ID="ID_5_3_1_4" MODIFIED="1700000000144" TEXT="4. 必要に応じて保有銘柄管理（購入・売却）"/>
<node CREATED="1700000000145" ID="ID_5_3_1_5" MODIFIED="1700000000145" TEXT="5. パフォーマンス確認（オプション）: python -m omanta_3rd.jobs.backtest --save-to-db"/>
</node>
</node>
<node CREATED="1700000000146" ID="ID_5_4" MODIFIED="1700000000146" TEXT="シナリオ4: 月次リバランス型の評価・分析">
<node CREATED="1700000000147" ID="ID_5_4_1" MODIFIED="1700000000147" TEXT="評価フロー">
<node CREATED="1700000000148" ID="ID_5_4_1_1" MODIFIED="1700000000148" TEXT="1. 候補群のHoldout検証: python evaluate_candidates_holdout.py ..."/>
<node CREATED="1700000000149" ID="ID_5_4_1_2" MODIFIED="1700000000149" TEXT="2. コスト感度分析: python evaluate_cost_sensitivity.py ..."/>
<node CREATED="1700000000150" ID="ID_5_4_1_3" MODIFIED="1700000000150" TEXT="3. 可視化: python visualize_holdings_details.py"/>
<node CREATED="1700000000151" ID="ID_5_4_1_4" MODIFIED="1700000000151" TEXT="4. 時系列パフォーマンス保存: python save_performance_time_series_to_db.py"/>
</node>
</node>
</node>
</node>
</map>









