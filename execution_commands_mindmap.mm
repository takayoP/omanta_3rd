<map version="1.0.1">
<!-- To view this file, download free mind mapping software FreeMind from http://freemind.sourceforge.net -->
<node CREATED="1700000000000" ID="ID_ROOT" MODIFIED="1700000000000" TEXT="投資アルゴリズム 実行コマンド体系">
<node CREATED="1700000000001" ID="ID_1" MODIFIED="1700000000001" POSITION="right" TEXT="1. データベース・マイグレーション">
<node CREATED="1700000000002" ID="ID_1_1" MODIFIED="1700000000002" TEXT="init_db">
<node CREATED="1700000000003" ID="ID_1_1_1" MODIFIED="1700000000003" TEXT="python -m omanta_3rd.jobs.init_db"/>
<node CREATED="1700000000299" ID="ID_1_1_2" MODIFIED="1700000000299" TEXT="機能: スキーマとインデックス作成"/>
</node>
<node CREATED="1700000000300" ID="ID_1_2" MODIFIED="1700000000300" TEXT="run_migration（マイグレーション実行）">
<node CREATED="1700000000301" ID="ID_1_2_1" MODIFIED="1700000000301" TEXT="python -m omanta_3rd.jobs.run_migration sql/migration_add_ref_scores_to_features.sql"/>
<node CREATED="1700000000302" ID="ID_1_2_2" MODIFIED="1700000000302" TEXT="python -m omanta_3rd.jobs.run_migration sql/migration_add_strategy_runs_tables.sql"/>
<node CREATED="1700000000303" ID="ID_1_2_3" MODIFIED="1700000000303" TEXT="引数: マイグレーションSQLファイルパス（省略時はデフォルト）"/>
</node>
</node>
<node CREATED="1700000000310" ID="ID_1v1" MODIFIED="1700000000310" POSITION="right" TEXT="2. メインコマンド（特徴量・選定・最適化）">
<node CREATED="1700000000311" ID="ID_1v1_1" MODIFIED="1700000000311" TEXT="prepare_features（特徴量・ref score 計算）">
<node CREATED="1700000000312" ID="ID_1v1_1_1" MODIFIED="1700000000312" TEXT="python -m omanta_3rd.jobs.prepare_features --asof 2024-12-31"/>
<node CREATED="1700000000313" ID="ID_1v1_1_2" MODIFIED="1700000000313" TEXT="python -m omanta_3rd.jobs.prepare_features --start 2021-01-01 --end 2024-12-31"/>
<node CREATED="1700000000314" ID="ID_1v1_1_3" MODIFIED="1700000000314" TEXT="オプション: --asof（単日）または --start/--end（一括）, --score-profile（デフォルト: v1_ref）"/>
</node>
<node CREATED="1700000000315" ID="ID_1v1_2" MODIFIED="1700000000315" TEXT="run_strategy（選定のみ）">
<node CREATED="1700000000316" ID="ID_1v1_2_1" MODIFIED="1700000000316" TEXT="python -m omanta_3rd.jobs.run_strategy --mode monthly --asof 2024-12-31"/>
<node CREATED="1700000000317" ID="ID_1v1_2_2" MODIFIED="1700000000317" TEXT="python -m omanta_3rd.jobs.run_strategy --mode monthly --start 2021-01-01 --end 2024-12-31"/>
<node CREATED="1700000000318" ID="ID_1v1_2_3" MODIFIED="1700000000318" TEXT="オプション: --mode longterm|monthly, --asof または --start/--end, --no-save-new"/>
</node>
<node CREATED="1700000000319" ID="ID_1v1_3" MODIFIED="1700000000319" TEXT="optimize_strategy（月次最適化・PolicyParams 6 個）">
<node CREATED="1700000000320" ID="ID_1v1_3_1" MODIFIED="1700000000320" TEXT="python -m omanta_3rd.jobs.optimize_strategy --start 2021-01-01 --end 2024-12-31 --n-trials 20 --study-name v1_study"/>
<node CREATED="1700000000321" ID="ID_1v1_3_2" MODIFIED="1700000000321" TEXT="オプション: --start/--end 必須, --n-trials, --study-name, --cost-bps, --n-jobs"/>
</node>
</node>
<node CREATED="1700000000004" ID="ID_2" MODIFIED="1700000000004" POSITION="right" TEXT="3. データ更新（ETL）">
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
<node CREATED="1700000000026" ID="ID_3" MODIFIED="1700000000026" POSITION="right" TEXT="4. 長期保有型の運用">
<node CREATED="1700000000027" ID="ID_3_1" MODIFIED="1700000000027" TEXT="longterm_run.py（月次実行）">
<node CREATED="1700000000028" ID="ID_3_1_1" MODIFIED="1700000000028" TEXT="基本コマンド">
<node CREATED="1700000000029" ID="ID_3_1_1_1" MODIFIED="1700000000029" TEXT="python -m omanta_3rd.jobs.longterm_run --asof 2025-12-19"/>
</node>
<node CREATED="1700000000031" ID="ID_3_1_2" MODIFIED="1700000000031" TEXT="オプション: --asof（基準日 YYYY-MM-DD）"/>
<node CREATED="1700000000033" ID="ID_3_1_3" MODIFIED="1700000000033" TEXT="機能: 特徴量計算・スクリーニング・portfolio_monthly 保存（参考）"/>
</node>
<node CREATED="1700000000330" ID="ID_3_1b" MODIFIED="1700000000330" TEXT="batch_longterm_run.py（期間一括）">
<node CREATED="1700000000331" ID="ID_3_1b_1" MODIFIED="1700000000331" TEXT="python -m omanta_3rd.jobs.batch_longterm_run --start 2016-01-01 --end 2025-12-28"/>
<node CREATED="1700000000332" ID="ID_3_1b_2" MODIFIED="1700000000332" TEXT="オプション: --no-performance, --as-of-date, --no-skip-existing"/>
</node>
<node CREATED="1700000000037" ID="ID_3_2" MODIFIED="1700000000037" TEXT="backtest.py（バックテスト・月次リバランス用）">
<node CREATED="1700000000038" ID="ID_3_2_1" MODIFIED="1700000000038" TEXT="基本コマンド（月次リバランス用）">
<node CREATED="1700000000039" ID="ID_3_2_1_1" MODIFIED="1700000000039" TEXT="python -m omanta_3rd.jobs.backtest"/>
<node CREATED="1700000000040" ID="ID_3_2_1_2" MODIFIED="1700000000040" TEXT="python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19"/>
<node CREATED="1700000000041" ID="ID_3_2_1_3" MODIFIED="1700000000041" TEXT="python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19 --as-of-date 2025-12-20"/>
<node CREATED="1700000000042" ID="ID_3_2_1_4" MODIFIED="1700000000042" TEXT="python -m omanta_3rd.jobs.backtest --save-to-db"/>
<node CREATED="1700000003042" ID="ID_3_2_1_5" MODIFIED="1700000003042" TEXT="python -m omanta_3rd.jobs.backtest --format csv --output backtest_results.csv"/>
</node>
<node CREATED="1700000000043" ID="ID_3_2_2" MODIFIED="1700000000043" TEXT="オプション">
<node CREATED="1700000000044" ID="ID_3_2_2_1" MODIFIED="1700000000044" TEXT="--rebalance-date: リバランス日（YYYY-MM-DD、未指定で全ポートフォリオ）"/>
<node CREATED="1700000000045" ID="ID_3_2_2_2" MODIFIED="1700000000045" TEXT="--as-of-date: 評価日（YYYY-MM-DD、デフォルト: 最新価格データ）"/>
<node CREATED="1700000000046" ID="ID_3_2_2_3" MODIFIED="1700000000046" TEXT="--format: json/csv（デフォルト: json）"/>
<node CREATED="1700000000047" ID="ID_3_2_2_4" MODIFIED="1700000000047" TEXT="--output: 出力パス（未指定で標準出力）"/>
<node CREATED="1700000000048" ID="ID_3_2_2_5" MODIFIED="1700000000048" TEXT="--save-to-db: パフォーマンス結果をDBに保存"/>
</node>
</node>
<node CREATED="1700000003053" ID="ID_3_3b" MODIFIED="1700000003053" TEXT="calculate_all_performance.py（パフォーマンス一括）">
<node CREATED="1700000003054" ID="ID_3_3b_1" MODIFIED="1700000003054" TEXT="python -m omanta_3rd.jobs.calculate_all_performance"/>
<node CREATED="1700000003055" ID="ID_3_3b_2" MODIFIED="1700000003055" TEXT="python -m omanta_3rd.jobs.calculate_all_performance --as-of-date 2025-12-28"/>
<node CREATED="1700000003056" ID="ID_3_3b_3" MODIFIED="1700000003056" TEXT="オプション: --as-of-date, --start/--end"/>
</node>
<node CREATED="1700000000050" ID="ID_3_4" MODIFIED="1700000000050" TEXT="保有銘柄管理">
<node CREATED="1700000000051" ID="ID_3_4_1" MODIFIED="1700000000051" TEXT="add_holding.py: 保有追加"/>
<node CREATED="1700000000052" ID="ID_3_4_2" MODIFIED="1700000000052" TEXT="sell_holding.py: 売却"/>
<node CREATED="1700000000053" ID="ID_3_4_3" MODIFIED="1700000000053" TEXT="update_holdings.py: 更新"/>
</node>
</node>
<node CREATED="1700000000133" ID="ID_5" MODIFIED="1700000000133" POSITION="left" TEXT="5. 可視化・補助スクリプト">
<node CREATED="1700000000162" ID="ID_5_1" MODIFIED="1700000000162" TEXT="visualize_holdings_details.py … python visualize_holdings_details.py"/>
<node CREATED="1700000000165" ID="ID_5_2" MODIFIED="1700000000165" TEXT="visualize_equity_curve_and_holdings.py … 資産曲線・保有銘柄推移"/>
<node CREATED="1700000000168" ID="ID_5_3" MODIFIED="1700000000168" TEXT="visualize_optimization.py … 最適化結果の可視化"/>
<node CREATED="1700000001680" ID="ID_5_4" MODIFIED="1700000001680" TEXT="visualize_holdings_overlap.py … 保有銘柄の重複可視化"/>
</node>
<node CREATED="1700000001690" ID="ID_6b" MODIFIED="1700000001690" POSITION="left" TEXT="6. シェル・バッチ（.ps1 / .bat）">
<node CREATED="1700000001691" ID="ID_6b_1" MODIFIED="1700000001691" TEXT="run_optimization_with_cache_rebuild.ps1: 最適化＋キャッシュ再構築"/>
<node CREATED="1700000001694" ID="ID_6b_4" MODIFIED="1700000001694" TEXT="run_2025_live_evaluation.ps1 / .bat: 疑似ライブ評価"/>
</node>
<node CREATED="1700000000171" ID="ID_7" MODIFIED="1700000000171" POSITION="left" TEXT="7. データベース保存スクリプト">
<node CREATED="1700000000172" ID="ID_7_1" MODIFIED="1700000000172" TEXT="save_final_candidates_to_db.py … 選定候補・パフォーマンスをDB保存"/>
<node CREATED="1700000000175" ID="ID_7_2" MODIFIED="1700000000175" TEXT="save_performance_time_series_to_db.py … 時系列データをDB保存"/>
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
<node CREATED="1700000001880" ID="ID_9_0" MODIFIED="1700000001880" TEXT="メインワークフロー（月次リバランス型）">
<node CREATED="1700000001881" ID="ID_9_0_1" MODIFIED="1700000001881" TEXT="1. マイグレーション: run_migration（ref_scores, strategy_runs テーブル）"/>
<node CREATED="1700000001882" ID="ID_9_0_2" MODIFIED="1700000001882" TEXT="2. 特徴量: prepare_features --asof または --start/--end"/>
<node CREATED="1700000001883" ID="ID_9_0_3" MODIFIED="1700000001883" TEXT="3. 選定: run_strategy --mode monthly --asof または --start/--end"/>
<node CREATED="1700000001884" ID="ID_9_0_4" MODIFIED="1700000001884" TEXT="4. 最適化: optimize_strategy --start/--end --n-trials"/>
</node>
<node CREATED="1700000000189" ID="ID_9_1" MODIFIED="1700000000189" TEXT="データ更新ワークフロー">
<node CREATED="1700000000190" ID="ID_9_1_1" MODIFIED="1700000000190" TEXT="1. python update_all_data.py --target listed"/>
<node CREATED="1700000000191" ID="ID_9_1_2" MODIFIED="1700000000191" TEXT="2. python update_all_data.py --target prices"/>
<node CREATED="1700000000192" ID="ID_9_1_3" MODIFIED="1700000000192" TEXT="3. python update_all_data.py --target fins"/>
<node CREATED="1700000000193" ID="ID_9_1_4" MODIFIED="1700000000193" TEXT="4. python update_all_data.py --target indices"/>
</node>
<node CREATED="1700000000200" ID="ID_9_3" MODIFIED="1700000000200" TEXT="長期保有型運用ワークフロー">
<node CREATED="1700000000201" ID="ID_9_3_1" MODIFIED="1700000000201" TEXT="1. 月次実行: longterm_run --asof YYYY-MM-DD"/>
<node CREATED="1700000000202" ID="ID_9_3_2" MODIFIED="1700000000202" TEXT="2. スクリーニング結果を確認"/>
<node CREATED="1700000000203" ID="ID_9_3_3" MODIFIED="1700000000203" TEXT="3. 保有銘柄管理: add_holding.py / sell_holding.py"/>
<node CREATED="1700000000204" ID="ID_9_3_4" MODIFIED="1700000000204" TEXT="4. バックテスト: backtest.py --save-to-db"/>
</node>
</node>
</node>
</map>

