<map version="1.0.1">
<!-- To view this file, download free mind mapping software FreeMind from http://freemind.sourceforge.net -->
<node CREATED="1700000000000" ID="ID_ROOT" MODIFIED="1700000000000" TEXT="投資アルゴリズム 実行コマンド体系">
<node CREATED="1700000000001" ID="ID_1" MODIFIED="1700000000001" POSITION="right" TEXT="1. データベース初期化">
<node CREATED="1700000000002" ID="ID_1_1" MODIFIED="1700000000002" TEXT="python -m omanta_3rd.jobs.init_db"/>
<node CREATED="1700000000003" ID="ID_1_2" MODIFIED="1700000000003" TEXT="機能: データベーススキーマとインデックスを作成"/>
</node>
<node CREATED="1700000000004" ID="ID_2" MODIFIED="1700000000004" POSITION="right" TEXT="2. データ更新（ETL）">
<node CREATED="1700000000005" ID="ID_2_1" MODIFIED="1700000000005" TEXT="etl_update.py">
<node CREATED="1700000000006" ID="ID_2_1_1" MODIFIED="1700000000006" TEXT="基本コマンド">
<node CREATED="1700000000007" ID="ID_2_1_1_1" MODIFIED="1700000000007" TEXT="python -m omanta_3rd.jobs.etl_update --target listed"/>
<node CREATED="1700000000008" ID="ID_2_1_1_2" MODIFIED="1700000000008" TEXT="python -m omanta_3rd.jobs.etl_update --target prices --start 2025-09-01 --end 2025-12-13"/>
<node CREATED="1700000000009" ID="ID_2_1_1_3" MODIFIED="1700000000009" TEXT="python -m omanta_3rd.jobs.etl_update --target fins --start 2025-09-01 --end 2025-12-13"/>
</node>
<node CREATED="1700000000010" ID="ID_2_1_2" MODIFIED="1700000000010" TEXT="オプション">
<node CREATED="1700000000011" ID="ID_2_1_2_1" MODIFIED="1700000000011" TEXT="--target: listed/prices/fins/all（デフォルト: all）"/>
<node CREATED="1700000000012" ID="ID_2_1_2_2" MODIFIED="1700000000012" TEXT="--date: 更新日（YYYY-MM-DD、デフォルト: 今日）"/>
<node CREATED="1700000000013" ID="ID_2_1_2_3" MODIFIED="1700000000013" TEXT="--start: 開始日（YYYY-MM-DD、prices/fins用）"/>
<node CREATED="1700000000014" ID="ID_2_1_2_4" MODIFIED="1700000000014" TEXT="--end: 終了日（YYYY-MM-DD、prices/fins用）"/>
</node>
</node>
<node CREATED="1700000000015" ID="ID_2_2" MODIFIED="1700000000015" TEXT="update_all_data.py">
<node CREATED="1700000000016" ID="ID_2_2_1" MODIFIED="1700000000016" TEXT="基本コマンド">
<node CREATED="1700000000017" ID="ID_2_2_1_1" MODIFIED="1700000000017" TEXT="python update_all_data.py"/>
<node CREATED="1700000000018" ID="ID_2_2_1_2" MODIFIED="1700000000018" TEXT="python update_all_data.py --target indices"/>
<node CREATED="1700000000019" ID="ID_2_2_1_3" MODIFIED="1700000000019" TEXT="python update_all_data.py --target prices --start 2024-01-01 --end 2024-12-31"/>
</node>
<node CREATED="1700000000020" ID="ID_2_2_2" MODIFIED="1700000000020" TEXT="オプション">
<node CREATED="1700000000021" ID="ID_2_2_2_1" MODIFIED="1700000000021" TEXT="--target: all/listed/prices/fins/indices（デフォルト: all）"/>
<node CREATED="1700000000022" ID="ID_2_2_2_2" MODIFIED="1700000000022" TEXT="--date: 更新日（YYYY-MM-DD、デフォルト: 今日）"/>
<node CREATED="1700000000023" ID="ID_2_2_2_3" MODIFIED="1700000000023" TEXT="--start: 開始日（YYYY-MM-DD、自動計算可）"/>
<node CREATED="1700000000024" ID="ID_2_2_2_4" MODIFIED="1700000000024" TEXT="--end: 終了日（YYYY-MM-DD、デフォルト: 今日）"/>
<node CREATED="1700000000025" ID="ID_2_2_2_5" MODIFIED="1700000000025" TEXT="--no-auto-calculate: 自動計算を無効化"/>
</node>
</node>
</node>
<node CREATED="1700000000026" ID="ID_3" MODIFIED="1700000000026" POSITION="right" TEXT="3. 長期保有型の運用">
<node CREATED="1700000000027" ID="ID_3_1" MODIFIED="1700000000027" TEXT="monthly_run.py（月次実行）">
<node CREATED="1700000000028" ID="ID_3_1_1" MODIFIED="1700000000028" TEXT="基本コマンド">
<node CREATED="1700000000029" ID="ID_3_1_1_1" MODIFIED="1700000000029" TEXT="python -m omanta_3rd.jobs.monthly_run"/>
<node CREATED="1700000000030" ID="ID_3_1_1_2" MODIFIED="1700000000030" TEXT="python -m omanta_3rd.jobs.monthly_run --asof 2025-12-19"/>
</node>
<node CREATED="1700000000031" ID="ID_3_1_2" MODIFIED="1700000000031" TEXT="オプション">
<node CREATED="1700000000032" ID="ID_3_1_2_1" MODIFIED="1700000000032" TEXT="--asof: 基準日（YYYY-MM-DD、デフォルト: 今日）"/>
</node>
<node CREATED="1700000000033" ID="ID_3_1_3" MODIFIED="1700000000033" TEXT="機能">
<node CREATED="1700000000034" ID="ID_3_1_3_1" MODIFIED="1700000000034" TEXT="特徴量計算"/>
<node CREATED="1700000000035" ID="ID_3_1_3_2" MODIFIED="1700000000035" TEXT="スクリーニング"/>
<node CREATED="1700000000036" ID="ID_3_1_3_3" MODIFIED="1700000000036" TEXT="portfolio_monthlyに保存（参考情報）"/>
</node>
</node>
<node CREATED="1700000000037" ID="ID_3_2" MODIFIED="1700000000037" TEXT="backtest.py（バックテスト）">
<node CREATED="1700000000038" ID="ID_3_2_1" MODIFIED="1700000000038" TEXT="基本コマンド">
<node CREATED="1700000000039" ID="ID_3_2_1_1" MODIFIED="1700000000039" TEXT="python -m omanta_3rd.jobs.backtest"/>
<node CREATED="1700000000040" ID="ID_3_2_1_2" MODIFIED="1700000000040" TEXT="python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19"/>
<node CREATED="1700000000041" ID="ID_3_2_1_3" MODIFIED="1700000000041" TEXT="python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19 --as-of-date 2025-12-20"/>
<node CREATED="1700000000042" ID="ID_3_2_1_4" MODIFIED="1700000000042" TEXT="python -m omanta_3rd.jobs.backtest --save-to-db"/>
</node>
<node CREATED="1700000000043" ID="ID_3_2_2" MODIFIED="1700000000043" TEXT="オプション">
<node CREATED="1700000000044" ID="ID_3_2_2_1" MODIFIED="1700000000044" TEXT="--rebalance-date: リバランス日（YYYY-MM-DD、未指定で全ポートフォリオ）"/>
<node CREATED="1700000000045" ID="ID_3_2_2_2" MODIFIED="1700000000045" TEXT="--as-of-date: 評価日（YYYY-MM-DD、デフォルト: 最新価格データ）"/>
<node CREATED="1700000000046" ID="ID_3_2_2_3" MODIFIED="1700000000046" TEXT="--format: json/csv（デフォルト: json）"/>
<node CREATED="1700000000047" ID="ID_3_2_2_4" MODIFIED="1700000000047" TEXT="--output: 出力パス（未指定で標準出力）"/>
<node CREATED="1700000000048" ID="ID_3_2_2_5" MODIFIED="1700000000048" TEXT="--save-to-db: パフォーマンス結果をDBに保存"/>
</node>
</node>
<node CREATED="1700000000049" ID="ID_3_3" MODIFIED="1700000000049" TEXT="optimize_longterm.py（長期保有型最適化）">
<node CREATED="1700000000049_1" ID="ID_3_3_0_1" MODIFIED="1700000000049_1" TEXT="基本コマンド">
<node CREATED="1700000000049_2" ID="ID_3_3_0_2" MODIFIED="1700000000049_2" TEXT="python -m omanta_3rd.jobs.optimize_longterm --start 2021-01-01 --end 2024-12-31 --study-type A --n-trials 200"/>
</node>
<node CREATED="1700000000049_3" ID="ID_3_3_0_3" MODIFIED="1700000000049_3" TEXT="必須オプション">
<node CREATED="1700000000049_4" ID="ID_3_3_0_4" MODIFIED="1700000000049_4" TEXT="--start: 開始日（YYYY-MM-DD）"/>
<node CREATED="1700000000049_5" ID="ID_3_3_0_5" MODIFIED="1700000000049_5" TEXT="--end: 終了日（YYYY-MM-DD）"/>
<node CREATED="1700000000049_6" ID="ID_3_3_0_6" MODIFIED="1700000000049_6" TEXT="--study-type: A/B/C（A: BB寄り・低ROE、B: Value寄り・ROE高め、C: 統合・広範囲）"/>
</node>
<node CREATED="1700000000049_7" ID="ID_3_3_0_7" MODIFIED="1700000000049_7" TEXT="主要オプション">
<node CREATED="1700000000049_8" ID="ID_3_3_0_8" MODIFIED="1700000000049_8" TEXT="--n-trials: 試行回数（デフォルト: 200）"/>
<node CREATED="1700000000049_9" ID="ID_3_3_0_9" MODIFIED="1700000000049_9" TEXT="--study-name: スタディ名（自動生成可）"/>
<node CREATED="1700000000049_10" ID="ID_3_3_0_10" MODIFIED="1700000000049_10" TEXT="--n-jobs: trial並列数（-1で自動）"/>
<node CREATED="1700000000049_11" ID="ID_3_3_0_11" MODIFIED="1700000000049_11" TEXT="--bt-workers: バックテスト並列数（-1で自動）"/>
<node CREATED="1700000000049_12" ID="ID_3_3_0_12" MODIFIED="1700000000049_12" TEXT="--cost-bps: 取引コスト（bps、デフォルト: 0.0）"/>
<node CREATED="1700000000049_13" ID="ID_3_3_0_13" MODIFIED="1700000000049_13" TEXT="--train-ratio: 学習データ割合（デフォルト: 0.8）"/>
<node CREATED="1700000000049_14" ID="ID_3_3_0_14" MODIFIED="1700000000049_14" TEXT="--random-seed: ランダムシード（デフォルト: 42）"/>
</node>
</node>
<node CREATED="1700000000050" ID="ID_3_4" MODIFIED="1700000000050" TEXT="保有銘柄管理">
<node CREATED="1700000000051" ID="ID_3_4_1" MODIFIED="1700000000051" TEXT="add_holding.py: 保有追加"/>
<node CREATED="1700000000052" ID="ID_3_4_2" MODIFIED="1700000000052" TEXT="sell_holding.py: 売却"/>
<node CREATED="1700000000053" ID="ID_3_4_3" MODIFIED="1700000000053" TEXT="update_holdings.py: 更新"/>
</node>
</node>
<node CREATED="1700000000054" ID="ID_4" MODIFIED="1700000000054" POSITION="right" TEXT="4. 月次リバランス型の運用">
<node CREATED="1700000000055" ID="ID_4_1" MODIFIED="1700000000055" TEXT="optimize_timeseries.py（時系列最適化・推奨）">
<node CREATED="1700000000055" ID="ID_4_1_1" MODIFIED="1700000000055" TEXT="基本コマンド">
<node CREATED="1700000000056" ID="ID_4_1_1_1" MODIFIED="1700000000056" TEXT="python -m omanta_3rd.jobs.optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 200"/>
</node>
<node CREATED="1700000000057" ID="ID_4_1_2" MODIFIED="1700000000057" TEXT="必須オプション">
<node CREATED="1700000000058" ID="ID_4_1_2_1" MODIFIED="1700000000058" TEXT="--start: 開始日（YYYY-MM-DD）"/>
<node CREATED="1700000000059" ID="ID_4_1_2_2" MODIFIED="1700000000059" TEXT="--end: 終了日（YYYY-MM-DD）"/>
</node>
<node CREATED="1700000000060" ID="ID_4_1_3" MODIFIED="1700000000060" TEXT="主要オプション">
<node CREATED="1700000000061" ID="ID_4_1_3_1" MODIFIED="1700000000061" TEXT="--n-trials: 試行回数（デフォルト: 50）"/>
<node CREATED="1700000000062" ID="ID_4_1_3_2" MODIFIED="1700000000062" TEXT="--study-name: スタディ名（自動生成可）"/>
<node CREATED="1700000000063" ID="ID_4_1_3_3" MODIFIED="1700000000063" TEXT="--parallel-mode: trial/backtest/hybrid（デフォルト: trial）"/>
<node CREATED="1700000000064" ID="ID_4_1_3_4" MODIFIED="1700000000064" TEXT="--n-jobs: trial並列数（-1で自動、SQLite環境では2-4推奨）"/>
<node CREATED="1700000000065" ID="ID_4_1_3_5" MODIFIED="1700000000065" TEXT="--bt-workers: バックテスト並列数（-1で自動）"/>
<node CREATED="1700000000066" ID="ID_4_1_3_6" MODIFIED="1700000000066" TEXT="--cost: 取引コスト（bps、デフォルト: 0.0）"/>
</node>
<node CREATED="1700000000067" ID="ID_4_1_4" MODIFIED="1700000000067" TEXT="その他オプション">
<node CREATED="1700000000068" ID="ID_4_1_4_1" MODIFIED="1700000000068" TEXT="--storage: Optunaストレージ（デフォルト: SQLite）"/>
<node CREATED="1700000000069" ID="ID_4_1_4_2" MODIFIED="1700000000069" TEXT="--no-progress-window: 進捗ウィンドウ非表示"/>
<node CREATED="1700000000070" ID="ID_4_1_4_3" MODIFIED="1700000000070" TEXT="--no-db-write: DB書き込み無効"/>
<node CREATED="1700000000071" ID="ID_4_1_4_4" MODIFIED="1700000000071" TEXT="--cache-dir: キャッシュディレクトリ（デフォルト: cache/features）"/>
</node>
<node CREATED="1700000000072" ID="ID_4_1_5" MODIFIED="1700000000072" TEXT="実行例（Windows PowerShell）">
<node CREATED="1700000000073" ID="ID_4_1_5_1" MODIFIED="1700000000073" TEXT="$env:OMP_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000074" ID="ID_4_1_5_2" MODIFIED="1700000000074" TEXT="$env:MKL_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000075" ID="ID_4_1_5_3" MODIFIED="1700000000075" TEXT="$env:OPENBLAS_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000076" ID="ID_4_1_5_4" MODIFIED="1700000000076" TEXT="$env:NUMEXPR_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000077" ID="ID_4_1_5_5" MODIFIED="1700000000077" TEXT="python -m omanta_3rd.jobs.optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 200 --n-jobs 4 --no-progress-window"/>
</node>
</node>
<node CREATED="1700000000093" ID="ID_4_2" MODIFIED="1700000000093" TEXT="robust_optimize_timeseries.py（信頼性向上型）">
<node CREATED="1700000000094" ID="ID_4_3_1" MODIFIED="1700000000094" TEXT="基本コマンド">
<node CREATED="1700000000095" ID="ID_4_3_1_1" MODIFIED="1700000000095" TEXT="python -m omanta_3rd.jobs.robust_optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 20 --folds 3"/>
</node>
<node CREATED="1700000000096" ID="ID_4_3_2" MODIFIED="1700000000096" TEXT="必須オプション">
<node CREATED="1700000000097" ID="ID_4_3_2_1" MODIFIED="1700000000097" TEXT="--start: 開始日（YYYY-MM-DD）"/>
<node CREATED="1700000000098" ID="ID_4_3_2_2" MODIFIED="1700000000098" TEXT="--end: 終了日（YYYY-MM-DD）"/>
</node>
<node CREATED="1700000000099" ID="ID_4_3_3" MODIFIED="1700000000099" TEXT="主要オプション">
<node CREATED="1700000000100" ID="ID_4_3_3_1" MODIFIED="1700000000100" TEXT="--n-trials: 試行回数（推奨: 10-20、デフォルト: 50）"/>
<node CREATED="1700000000101" ID="ID_4_3_3_2" MODIFIED="1700000000101" TEXT="--folds: WFAのfold数（デフォルト: 3）"/>
<node CREATED="1700000000102" ID="ID_4_3_3_3" MODIFIED="1700000000102" TEXT="--train-min-years: 最小Train期間（年、デフォルト: 2.0）"/>
<node CREATED="1700000000103" ID="ID_4_3_3_4" MODIFIED="1700000000103" TEXT="--buy-cost: 購入コスト（bps、デフォルト: 0.0）"/>
<node CREATED="1700000000104" ID="ID_4_3_3_5" MODIFIED="1700000000104" TEXT="--sell-cost: 売却コスト（bps、デフォルト: 0.0）"/>
<node CREATED="1700000000105" ID="ID_4_3_3_6" MODIFIED="1700000000105" TEXT="--stability-weight: 安定性の重み（0.0-1.0、デフォルト: 0.3）"/>
<node CREATED="1700000000106" ID="ID_4_3_3_7" MODIFIED="1700000000106" TEXT="--seed: 乱数シード"/>
</node>
</node>
<node CREATED="1700000000107" ID="ID_4_4" MODIFIED="1700000000107" TEXT="holdout_eval_timeseries.py（Holdout評価）">
<node CREATED="1700000000108" ID="ID_4_4_1" MODIFIED="1700000000108" TEXT="基本コマンド">
<node CREATED="1700000000109" ID="ID_4_4_1_1" MODIFIED="1700000000109" TEXT="python -m omanta_3rd.jobs.holdout_eval_timeseries --train-start 2021-01-01 --train-end 2023-12-31 --holdout-start 2024-01-01 --holdout-end 2024-12-31"/>
</node>
<node CREATED="1700000000110" ID="ID_4_4_2" MODIFIED="1700000000110" TEXT="必須オプション">
<node CREATED="1700000000111" ID="ID_4_4_2_1" MODIFIED="1700000000111" TEXT="--train-start: Train開始日（YYYY-MM-DD）"/>
<node CREATED="1700000000112" ID="ID_4_4_2_2" MODIFIED="1700000000112" TEXT="--train-end: Train終了日（YYYY-MM-DD）"/>
<node CREATED="1700000000113" ID="ID_4_4_2_3" MODIFIED="1700000000113" TEXT="--holdout-start: Holdout開始日（YYYY-MM-DD）"/>
<node CREATED="1700000000114" ID="ID_4_4_2_4" MODIFIED="1700000000114" TEXT="--holdout-end: Holdout終了日（YYYY-MM-DD）"/>
</node>
<node CREATED="1700000000115" ID="ID_4_4_3" MODIFIED="1700000000115" TEXT="主要オプション">
<node CREATED="1700000000116" ID="ID_4_4_3_1" MODIFIED="1700000000116" TEXT="--n-trials: 試行回数（デフォルト: 50）"/>
<node CREATED="1700000000117" ID="ID_4_4_3_2" MODIFIED="1700000000117" TEXT="--buy-cost: 購入コスト（bps、デフォルト: 0.0）"/>
<node CREATED="1700000000118" ID="ID_4_4_3_3" MODIFIED="1700000000118" TEXT="--sell-cost: 売却コスト（bps、デフォルト: 0.0）"/>
<node CREATED="1700000000119" ID="ID_4_4_3_4" MODIFIED="1700000000119" TEXT="--seed: 乱数シード"/>
</node>
</node>
<node CREATED="1700000000120" ID="ID_4_5" MODIFIED="1700000000120" TEXT="walk_forward_timeseries.py（WFA評価）">
<node CREATED="1700000000121" ID="ID_4_5_1" MODIFIED="1700000000121" TEXT="基本コマンド">
<node CREATED="1700000000122" ID="ID_4_5_1_1" MODIFIED="1700000000122" TEXT="python -m omanta_3rd.jobs.walk_forward_timeseries --start 2021-01-01 --end 2024-12-31 --folds 3"/>
</node>
<node CREATED="1700000000123" ID="ID_4_5_2" MODIFIED="1700000000123" TEXT="必須オプション">
<node CREATED="1700000000124" ID="ID_4_5_2_1" MODIFIED="1700000000124" TEXT="--start: 開始日（YYYY-MM-DD）"/>
<node CREATED="1700000000125" ID="ID_4_5_2_2" MODIFIED="1700000000125" TEXT="--end: 終了日（YYYY-MM-DD）"/>
</node>
<node CREATED="1700000000126" ID="ID_4_5_3" MODIFIED="1700000000126" TEXT="主要オプション">
<node CREATED="1700000000127" ID="ID_4_5_3_1" MODIFIED="1700000000127" TEXT="--folds: fold数（デフォルト: 3）"/>
<node CREATED="1700000000128" ID="ID_4_5_3_2" MODIFIED="1700000000128" TEXT="--train-min-years: 最小Train期間（年、デフォルト: 2.0）"/>
<node CREATED="1700000000129" ID="ID_4_5_3_3" MODIFIED="1700000000129" TEXT="--n-trials: 試行回数（デフォルト: 50）"/>
<node CREATED="1700000000130" ID="ID_4_5_3_4" MODIFIED="1700000000130" TEXT="--buy-cost: 購入コスト（bps）"/>
<node CREATED="1700000000131" ID="ID_4_5_3_5" MODIFIED="1700000000131" TEXT="--sell-cost: 売却コスト（bps）"/>
<node CREATED="1700000000132" ID="ID_4_5_3_6" MODIFIED="1700000000132" TEXT="--seed: 乱数シード"/>
</node>
</node>
</node>
<node CREATED="1700000000133" ID="ID_5" MODIFIED="1700000000133" POSITION="left" TEXT="5. 評価・検証スクリプト">
<node CREATED="1700000000134" ID="ID_5_1" MODIFIED="1700000000134" TEXT="evaluate_candidates_holdout.py">
<node CREATED="1700000000135" ID="ID_5_1_1" MODIFIED="1700000000135" TEXT="基本コマンド">
<node CREATED="1700000000136" ID="ID_5_1_1_1" MODIFIED="1700000000136" TEXT="python evaluate_candidates_holdout.py --candidates candidates_studyB_20251231_174014.json --holdout-start 2023-01-01 --holdout-end 2024-12-31 --cost-bps 0.0 --output holdout_results_with_holdings.json --use-cache"/>
</node>
<node CREATED="1700000000137" ID="ID_5_1_2" MODIFIED="1700000000137" TEXT="必須オプション">
<node CREATED="1700000000138" ID="ID_5_1_2_1" MODIFIED="1700000000138" TEXT="--candidates: 候補JSONファイル"/>
<node CREATED="1700000000139" ID="ID_5_1_2_2" MODIFIED="1700000000139" TEXT="--holdout-start: Holdout開始日（YYYY-MM-DD）"/>
<node CREATED="1700000000140" ID="ID_5_1_2_3" MODIFIED="1700000000140" TEXT="--holdout-end: Holdout終了日（YYYY-MM-DD）"/>
</node>
<node CREATED="1700000000141" ID="ID_5_1_3" MODIFIED="1700000000141" TEXT="主要オプション">
<node CREATED="1700000000142" ID="ID_5_1_3_1" MODIFIED="1700000000142" TEXT="--cost-bps: 取引コスト（bps、デフォルト: 0.0）"/>
<node CREATED="1700000000143" ID="ID_5_1_3_2" MODIFIED="1700000000143" TEXT="--output: 出力JSONファイル"/>
<node CREATED="1700000000144" ID="ID_5_1_3_3" MODIFIED="1700000000144" TEXT="--use-cache: キャッシュ使用"/>
</node>
<node CREATED="1700000000145" ID="ID_5_1_4" MODIFIED="1700000000145" TEXT="機能">
<node CREATED="1700000000146" ID="ID_5_1_4_1" MODIFIED="1700000000146" TEXT="候補パラメータでHoldout期間を評価"/>
<node CREATED="1700000000147" ID="ID_5_1_4_2" MODIFIED="1700000000147" TEXT="ポートフォリオ情報と保有銘柄詳細をJSONに保存"/>
<node CREATED="1700000000148" ID="ID_5_1_4_3" MODIFIED="1700000000148" TEXT="詳細メトリクス（年別Sharpe、CAGR、MaxDD、ターンオーバー等）を計算"/>
</node>
</node>
<node CREATED="1700000000149" ID="ID_5_2" MODIFIED="1700000000149" TEXT="evaluate_cost_sensitivity.py">
<node CREATED="1700000000150" ID="ID_5_2_1" MODIFIED="1700000000150" TEXT="基本コマンド">
<node CREATED="1700000000151" ID="ID_5_2_1_1" MODIFIED="1700000000151" TEXT="python evaluate_cost_sensitivity.py --candidates candidates_studyB_20251231_174014.json --holdout-start 2023-01-01 --holdout-end 2024-12-31 --cost-levels 0 10 20 30 --output cost_sensitivity_analysis.json"/>
</node>
<node CREATED="1700000000152" ID="ID_5_2_2" MODIFIED="1700000000152" TEXT="必須オプション">
<node CREATED="1700000000153" ID="ID_5_2_2_1" MODIFIED="1700000000153" TEXT="--candidates: 候補JSONファイル"/>
<node CREATED="1700000000154" ID="ID_5_2_2_2" MODIFIED="1700000000154" TEXT="--holdout-start: Holdout開始日（YYYY-MM-DD）"/>
<node CREATED="1700000000155" ID="ID_5_2_2_3" MODIFIED="1700000000155" TEXT="--holdout-end: Holdout終了日（YYYY-MM-DD）"/>
<node CREATED="1700000000156" ID="ID_5_2_2_4" MODIFIED="1700000000156" TEXT="--cost-levels: コストレベル（bps、複数指定可）"/>
<node CREATED="1700000000157" ID="ID_5_2_2_5" MODIFIED="1700000000157" TEXT="--output: 出力JSONファイル"/>
</node>
<node CREATED="1700000000158" ID="ID_5_2_3" MODIFIED="1700000000158" TEXT="機能">
<node CREATED="1700000000159" ID="ID_5_2_3_1" MODIFIED="1700000000159" TEXT="複数のコストレベルでパフォーマンスを評価"/>
<node CREATED="1700000000160" ID="ID_5_2_3_2" MODIFIED="1700000000160" TEXT="コスト感度分析結果をJSONに保存"/>
</node>
</node>
</node>
<node CREATED="1700000000161" ID="ID_6" MODIFIED="1700000000161" POSITION="left" TEXT="6. 可視化スクリプト">
<node CREATED="1700000000162" ID="ID_6_1" MODIFIED="1700000000162" TEXT="visualize_holdings_details.py">
<node CREATED="1700000000163" ID="ID_6_1_1" MODIFIED="1700000000163" TEXT="機能: 保有銘柄の詳細情報を可視化"/>
<node CREATED="1700000000164" ID="ID_6_1_2" MODIFIED="1700000000164" TEXT="実行: python visualize_holdings_details.py"/>
</node>
<node CREATED="1700000000165" ID="ID_6_2" MODIFIED="1700000000165" TEXT="visualize_equity_curve_and_holdings.py">
<node CREATED="1700000000166" ID="ID_6_2_1" MODIFIED="1700000000166" TEXT="機能: 資産曲線と保有銘柄の推移を可視化"/>
<node CREATED="1700000000167" ID="ID_6_2_2" MODIFIED="1700000000167" TEXT="実行: python visualize_equity_curve_and_holdings.py"/>
</node>
<node CREATED="1700000000168" ID="ID_6_3" MODIFIED="1700000000168" TEXT="visualize_optimization.py">
<node CREATED="1700000000169" ID="ID_6_3_1" MODIFIED="1700000000169" TEXT="機能: 最適化結果を可視化"/>
<node CREATED="1700000000170" ID="ID_6_3_2" MODIFIED="1700000000170" TEXT="実行: python visualize_optimization.py"/>
</node>
</node>
<node CREATED="1700000000171" ID="ID_7" MODIFIED="1700000000171" POSITION="left" TEXT="7. データベース保存スクリプト">
<node CREATED="1700000000172" ID="ID_7_1" MODIFIED="1700000000172" TEXT="save_final_candidates_to_db.py">
<node CREATED="1700000000173" ID="ID_7_1_1" MODIFIED="1700000000173" TEXT="機能: 最終選定候補のパラメータとパフォーマンスをDBに保存"/>
<node CREATED="1700000000174" ID="ID_7_1_2" MODIFIED="1700000000174" TEXT="実行: python save_final_candidates_to_db.py"/>
</node>
<node CREATED="1700000000175" ID="ID_7_2" MODIFIED="1700000000175" TEXT="save_performance_time_series_to_db.py">
<node CREATED="1700000000176" ID="ID_7_2_1" MODIFIED="1700000000176" TEXT="機能: パフォーマンス時系列データをDBに保存"/>
<node CREATED="1700000000177" ID="ID_7_2_2" MODIFIED="1700000000177" TEXT="実行: python save_performance_time_series_to_db.py"/>
</node>
</node>
<node CREATED="1700000000178" ID="ID_8" MODIFIED="1700000000178" POSITION="left" TEXT="8. 環境変数設定（Windows PowerShell）">
<node CREATED="1700000000179" ID="ID_8_1" MODIFIED="1700000000179" TEXT="BLASスレッド設定（並列化制御）">
<node CREATED="1700000000180" ID="ID_8_1_1" MODIFIED="1700000000180" TEXT="$env:OMP_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000181" ID="ID_8_1_2" MODIFIED="1700000000181" TEXT="$env:MKL_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000182" ID="ID_8_1_3" MODIFIED="1700000000182" TEXT="$env:OPENBLAS_NUM_THREADS=&quot;1&quot;"/>
<node CREATED="1700000000183" ID="ID_8_1_4" MODIFIED="1700000000183" TEXT="$env:NUMEXPR_NUM_THREADS=&quot;1&quot;"/>
</node>
<node CREATED="1700000000184" ID="ID_8_2" MODIFIED="1700000000184" TEXT="目的">
<node CREATED="1700000000185" ID="ID_8_2_1" MODIFIED="1700000000185" TEXT="BLASライブラリのスレッドを1に設定"/>
<node CREATED="1700000000186" ID="ID_8_2_2" MODIFIED="1700000000186" TEXT="最適化時の並列化制御"/>
<node CREATED="1700000000187" ID="ID_8_2_3" MODIFIED="1700000000187" TEXT="SQLite環境でのロック待ちを回避"/>
</node>
</node>
<node CREATED="1700000000188" ID="ID_9" MODIFIED="1700000000188" POSITION="left" TEXT="9. ワークフロー例">
<node CREATED="1700000000189" ID="ID_9_1" MODIFIED="1700000000189" TEXT="データ更新ワークフロー">
<node CREATED="1700000000190" ID="ID_9_1_1" MODIFIED="1700000000190" TEXT="1. python update_all_data.py --target listed"/>
<node CREATED="1700000000191" ID="ID_9_1_2" MODIFIED="1700000000191" TEXT="2. python update_all_data.py --target prices"/>
<node CREATED="1700000000192" ID="ID_9_1_3" MODIFIED="1700000000192" TEXT="3. python update_all_data.py --target fins"/>
<node CREATED="1700000000193" ID="ID_9_1_4" MODIFIED="1700000000193" TEXT="4. python update_all_data.py --target indices"/>
</node>
<node CREATED="1700000000194" ID="ID_9_2" MODIFIED="1700000000194" TEXT="月次リバランス型最適化ワークフロー">
<node CREATED="1700000000195" ID="ID_9_2_1" MODIFIED="1700000000195" TEXT="1. 時系列最適化: optimize_timeseries.py"/>
<node CREATED="1700000000196" ID="ID_9_2_2" MODIFIED="1700000000196" TEXT="2. Holdout検証: holdout_eval_timeseries.py"/>
<node CREATED="1700000000197" ID="ID_9_2_3" MODIFIED="1700000000197" TEXT="3. WFA評価: walk_forward_timeseries.py（オプション）"/>
<node CREATED="1700000000198" ID="ID_9_2_4" MODIFIED="1700000000198" TEXT="4. コスト感度分析: evaluate_cost_sensitivity.py"/>
<node CREATED="1700000000199" ID="ID_9_2_5" MODIFIED="1700000000199" TEXT="5. 結果保存: save_final_candidates_to_db.py"/>
</node>
<node CREATED="1700000000200" ID="ID_9_3" MODIFIED="1700000000200" TEXT="長期保有型運用ワークフロー">
<node CREATED="1700000000201" ID="ID_9_3_1" MODIFIED="1700000000201" TEXT="1. 月次実行: monthly_run.py --asof YYYY-MM-DD"/>
<node CREATED="1700000000202" ID="ID_9_3_2" MODIFIED="1700000000202" TEXT="2. スクリーニング結果を確認"/>
<node CREATED="1700000000203" ID="ID_9_3_3" MODIFIED="1700000000203" TEXT="3. 保有銘柄管理: add_holding.py / sell_holding.py"/>
<node CREATED="1700000000204" ID="ID_9_3_4" MODIFIED="1700000000204" TEXT="4. バックテスト: backtest.py --save-to-db"/>
</node>
<node CREATED="1700000000205" ID="ID_9_4" MODIFIED="1700000000205" TEXT="長期保有型最適化ワークフロー">
<node CREATED="1700000000206" ID="ID_9_4_1" MODIFIED="1700000000206" TEXT="1. 最適化: optimize_longterm.py --start YYYY-MM-DD --end YYYY-MM-DD --study-type A/B/C"/>
<node CREATED="1700000000207" ID="ID_9_4_2" MODIFIED="1700000000207" TEXT="2. 最適化結果を確認"/>
<node CREATED="1700000000208" ID="ID_9_4_3" MODIFIED="1700000000208" TEXT="3. monthly_run.pyのパラメータを更新"/>
</node>
</node>
</node>
</map>

