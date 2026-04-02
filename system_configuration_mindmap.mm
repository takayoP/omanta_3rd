<map version="1.0.1">
<!-- To view this file, use FreeMind http://freemind.sourceforge.net or compatible viewer -->
<node CREATED="1700000000000" ID="ID_ROOT" MODIFIED="1700000000000" TEXT="システム構成">
<node CREATED="1700000000001" ID="ID_1" MODIFIED="1700000000001" POSITION="right" TEXT="1. 目的・概要">
<node CREATED="1700000000002" ID="ID_1_1" MODIFIED="1700000000002" TEXT="目的">
<node CREATED="1700000000003" ID="ID_1_1_1" MODIFIED="1700000000003" TEXT="日本株対象のファンダメンタル中心ランキング"/>
<node CREATED="1700000000004" ID="ID_1_1_2" MODIFIED="1700000000004" TEXT="2つの運用スタイルを併存運用する基盤"/>
<node CREATED="1700000000005" ID="ID_1_1_3" MODIFIED="1700000000005" TEXT="ベンチマーク: TOPIX（J-Quants API経由）"/>
</node>
<node CREATED="1700000000006" ID="ID_1_2" MODIFIED="1700000000006" TEXT="技術スタック">
<node CREATED="1700000000007" ID="ID_1_2_1" MODIFIED="1700000000007" TEXT="データソース: J-Quants API"/>
<node CREATED="1700000000008" ID="ID_1_2_2" MODIFIED="1700000000008" TEXT="DB: SQLite（.env の DB_PATH、未設定時は data/db/jquants.sqlite 等）"/>
<node CREATED="1700000000009" ID="ID_1_2_3" MODIFIED="1700000000009" TEXT="言語: Python 3.9+"/>
<node CREATED="1700000000010" ID="ID_1_2_4" MODIFIED="1700000000010" TEXT="最適化: Optuna"/>
<node CREATED="1700000000011" ID="ID_1_2_5" MODIFIED="1700000000011" TEXT="主依存: pandas, numpy, optuna, requests, python-dotenv"/>
</node>
</node>
<node CREATED="1700000000012" ID="ID_2" MODIFIED="1700000000012" POSITION="right" TEXT="2. 2つの運用スタイル">
<node CREATED="1700000000013" ID="ID_2_1" MODIFIED="1700000000013" TEXT="(A) 長期保有型（NISA想定）">
<node CREATED="1700000000014" ID="ID_2_1_1" MODIFIED="1700000000014" TEXT="目的: 積立・買い増し、低頻度入替"/>
<node CREATED="1700000000015" ID="ID_2_1_2" MODIFIED="1700000000015" TEXT="入替: 月次〜四半期の点検"/>
<node CREATED="1700000000016" ID="ID_2_1_3" MODIFIED="1700000000016" TEXT="意思決定: スクリーニング結果を参考に手動"/>
<node CREATED="1700000000017" ID="ID_2_1_4" MODIFIED="1700000000017" TEXT="主ジョブ: longterm_run, backtest, batch_longterm_run"/>
<node CREATED="1700000000019" ID="ID_2_1_6" MODIFIED="1700000000019" TEXT="テーブル: portfolio_monthly（参考）, holdings"/>
</node>
<node CREATED="1700000000020" ID="ID_2_2" MODIFIED="1700000000020" TEXT="(B) 月次リバランス型">
<node CREATED="1700000000021" ID="ID_2_2_1" MODIFIED="1700000000021" TEXT="目的: 時系列の超過リターン（vs TOPIX）"/>
<node CREATED="1700000000022" ID="ID_2_2_2" MODIFIED="1700000000022" TEXT="入替: 月次で全入れ替え"/>
<node CREATED="1700000000023" ID="ID_2_2_3" MODIFIED="1700000000023" TEXT="意思決定: 最適化パラメータで自動選定"/>
<node CREATED="1700000000024" ID="ID_2_2_4" MODIFIED="1700000000024" TEXT="主ジョブ: optimize_timeseries（月次最適化）, prepare_features, run_strategy"/>
<node CREATED="1700000000025" ID="ID_2_2_5" MODIFIED="1700000000025" TEXT="テーブル: strategy_runs, portfolio_snapshots, monthly_rebalance_*（接頭辞）"/>
<node CREATED="1700000000026" ID="ID_2_2_6" MODIFIED="1700000000026" TEXT="実運用実行: scripts/run_production_optimization.ps1、docs/5DAY_PRODUCTION_OPTIMIZATION_PLAN.md"/>
</node>
</node>
<node CREATED="1700000000026" ID="ID_3" MODIFIED="1700000000026" POSITION="right" TEXT="3. ディレクトリ・モジュール構成">
<node CREATED="1700000000027" ID="ID_3_1" MODIFIED="1700000000027" TEXT="リポジトリルート">
<node CREATED="1700000000028" ID="ID_3_1_1" MODIFIED="1700000000028" TEXT="src/omanta_3rd/ … メインパッケージ（コアロジック）"/>
<node CREATED="1700000000029" ID="ID_3_1_2" MODIFIED="1700000000029" TEXT="sql/ … スキーマ・マイグレーション"/>
<node CREATED="1700000000030" ID="ID_3_1_3" MODIFIED="1700000000030" TEXT="scripts/ … 実行・分析用スクリプト"/>
<node CREATED="1700000000031" ID="ID_3_1_4" MODIFIED="1700000000031" TEXT="docs/ … 設計・検証・議事メモ"/>
<node CREATED="1700000000032" ID="ID_3_1_5" MODIFIED="1700000000032" TEXT="*.py … ルート直下スタンドアロン（検証・可視化・DB保存等）"/>
<node CREATED="1700000000033" ID="ID_3_1_6" MODIFIED="1700000000033" TEXT="*.ps1 / *.bat … 実行用シェル"/>
</node>
<node CREATED="1700000000034" ID="ID_3_2" MODIFIED="1700000000034" TEXT="src/omanta_3rd/ パッケージ（依存は下位→上位の一方向、CLAUDE.md）">
<node CREATED="1700000000035" ID="ID_3_2_1" MODIFIED="1700000000035" TEXT="backtest/ … 時系列P/L, metrics, performance, eval_common, feature_cache（longterm_run は遅延 import）"/>
<node CREATED="1700000000036" ID="ID_3_2_2" MODIFIED="1700000000036" TEXT="config/ … settings, strategy, params_registry, regime_policy, score_profile"/>
<node CREATED="1700000000037" ID="ID_3_2_3" MODIFIED="1700000000037" TEXT="features/ … fundamentals, valuation, technicals, universe"/>
<node CREATED="1700000000038" ID="ID_3_2_4" MODIFIED="1700000000038" TEXT="infra/ … db, jquants, repositories（features_repo, run_repo）"/>
<node CREATED="1700000000039" ID="ID_3_2_5" MODIFIED="1700000000039" TEXT="ingest/ … listed, prices, fins, indices, earnings_calendar"/>
<node CREATED="1700000000040" ID="ID_3_2_6" MODIFIED="1700000000040" TEXT="jobs/ … ジョブ・最適化（多数）"/>
<node CREATED="1700000000041" ID="ID_3_2_7" MODIFIED="1700000000041" TEXT="market/ … regime"/>
<node CREATED="1700000000042" ID="ID_3_2_8" MODIFIED="1700000000042" TEXT="portfolio/ … holdings"/>
<node CREATED="1700000000043" ID="ID_3_2_9" MODIFIED="1700000000043" TEXT="strategy/ … snapshot, scoring_engine, policy, scoring, select"/>
<node CREATED="1700000000044" ID="ID_3_2_10" MODIFIED="1700000000044" TEXT="reporting/ … export"/>
</node>
</node>
<node CREATED="1700000000045" ID="ID_4" MODIFIED="1700000000045" POSITION="left" TEXT="4. ジョブ一覧">
<node CREATED="1700000000046" ID="ID_4_1" MODIFIED="1700000000046" TEXT="メインジョブ（月次リバランス型）">
<node CREATED="1700000000047" ID="ID_4_1_1" MODIFIED="1700000000047" TEXT="prepare_features … 特徴量＋ref score を v1_ref で計算して features_monthly に保存"/>
<node CREATED="1700000000048" ID="ID_4_1_2" MODIFIED="1700000000048" TEXT="run_strategy … 選定のみ（longterm|monthly）、portfolio_snapshots 保存可"/>
<node CREATED="1700000000049" ID="ID_4_1_3" MODIFIED="1700000000049" TEXT="optimize_timeseries … 月次リバランス型最適化（StrategyParams+EntryScoreParams, Sharpe_excess, --cost）"/>
<node CREATED="1700000000050" ID="ID_4_1_4" MODIFIED="1700000000050" TEXT="run_production_optimization.ps1 … 実運用向け 200 trials, cost 20bps"/>
</node>
<node CREATED="1700000000062" ID="ID_4_4" MODIFIED="1700000000062" TEXT="実行・バッチ系">
<node CREATED="1700000000063" ID="ID_4_4_1" MODIFIED="1700000000063" TEXT="etl_update.py … ETL（listed/prices/fins/indices）"/>
<node CREATED="1700000000064" ID="ID_4_4_2" MODIFIED="1700000000064" TEXT="init_db.py … DB 初期化"/>
<node CREATED="1700000000065" ID="ID_4_4_3" MODIFIED="1700000000065" TEXT="longterm_run.py … 長期保有型月次実行（特徴量＋選定）"/>
<node CREATED="1700000000066" ID="ID_4_4_4" MODIFIED="1700000000066" TEXT="batch_longterm_run.py … 長期型期間一括"/>
<node CREATED="1700000000067" ID="ID_4_4_5" MODIFIED="1700000000067" TEXT="backtest.py … バックテスト実行"/>
<node CREATED="1700000000068" ID="ID_4_4_6" MODIFIED="1700000000068" TEXT="calculate_all_performance.py … パフォーマンス一括"/>
</node>
<node CREATED="1700000000069" ID="ID_4_5" MODIFIED="1700000000069" TEXT="ユーティリティ">
<node CREATED="1700000000070" ID="ID_4_5_1" MODIFIED="1700000000070" TEXT="params_utils.py … パラメータ構築・正規化（共通）"/>
<node CREATED="1700000000071" ID="ID_4_5_2" MODIFIED="1700000000071" TEXT="run_migration … SQL マイグレーション実行"/>
</node>
</node>
<node CREATED="1700000000072" ID="ID_5" MODIFIED="1700000000072" POSITION="left" TEXT="5. データベース構成">
<node CREATED="1700000000073" ID="ID_5_1" MODIFIED="1700000000073" TEXT="共通テーブル">
<node CREATED="1700000000074" ID="ID_5_1_1" MODIFIED="1700000000074" TEXT="listed_info … 銘柄属性（日付・コード・市場・セクター）"/>
<node CREATED="1700000000075" ID="ID_5_1_2" MODIFIED="1700000000075" TEXT="prices_daily … 日足（open/close/adj_close/volume 等）"/>
<node CREATED="1700000000076" ID="ID_5_1_3" MODIFIED="1700000000076" TEXT="fins_statements … 財務（開示日・実績・予想）"/>
<node CREATED="1700000000077" ID="ID_5_1_4" MODIFIED="1700000000077" TEXT="features_monthly … 月次特徴量（core/entry_score, core_score_ref, entry_score_ref）"/>
<node CREATED="1700000000078" ID="ID_5_1_5" MODIFIED="1700000000078" TEXT="index_daily … TOPIX 等"/>
<node CREATED="1700000000079" ID="ID_5_1_6" MODIFIED="1700000000079" TEXT="stock_splits … 株式分割"/>
</node>
<node CREATED="1700000000080" ID="ID_5_2" MODIFIED="1700000000080" TEXT="長期保有型関連">
<node CREATED="1700000000081" ID="ID_5_2_1" MODIFIED="1700000000081" TEXT="portfolio_monthly … 月次ポートフォリオ（参考/一時）"/>
<node CREATED="1700000000082" ID="ID_5_2_2" MODIFIED="1700000000082" TEXT="holdings … 実際の保有銘柄"/>
<node CREATED="1700000000083" ID="ID_5_2_3" MODIFIED="1700000000083" TEXT="backtest_performance / backtest_stock_performance"/>
</node>
<node CREATED="1700000000088" ID="ID_5_4" MODIFIED="1700000000088" TEXT="選定・実行テーブル（strategy_runs 系）">
<node CREATED="1700000000089" ID="ID_5_4_1" MODIFIED="1700000000089" TEXT="strategy_runs … 実行メタデータ"/>
<node CREATED="1700000000090" ID="ID_5_4_2" MODIFIED="1700000000090" TEXT="portfolio_snapshots … 日付別ポートフォリオスナップショット"/>
<node CREATED="1700000000091" ID="ID_5_4_3" MODIFIED="1700000000091" TEXT="performance_series / performance_summary / live_holdings"/>
</node>
</node>
<node CREATED="1700000000092" ID="ID_6" MODIFIED="1700000000092" POSITION="left" TEXT="6. 実行エントリポイント">
<node CREATED="1700000000093" ID="ID_6_1" MODIFIED="1700000000093" TEXT="メイン（月次リバランス型）">
<node CREATED="1700000000094" ID="ID_6_1_1" MODIFIED="1700000000094" TEXT="python -m omanta_3rd.jobs.prepare_features --asof 2024-12-31"/>
<node CREATED="1700000000095" ID="ID_6_1_2" MODIFIED="1700000000095" TEXT="python -m omanta_3rd.jobs.run_strategy --mode monthly --asof 2024-12-31"/>
<node CREATED="1700000000096" ID="ID_6_1_3" MODIFIED="1700000000096" TEXT="python -m omanta_3rd.jobs.optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 200 --cost 20 --no-progress-window"/>
<node CREATED="1700000000097" ID="ID_6_1_4" MODIFIED="1700000000097" TEXT=".\scripts\run_production_optimization.ps1（実運用・BLAS環境変数込み）"/>
</node>
<node CREATED="1700000000097" ID="ID_6_2" MODIFIED="1700000000097" TEXT="データ・DB">
<node CREATED="1700000000098" ID="ID_6_2_1" MODIFIED="1700000000098" TEXT="python -m omanta_3rd.jobs.init_db"/>
<node CREATED="1700000000099" ID="ID_6_2_2" MODIFIED="1700000000099" TEXT="python -m omanta_3rd.jobs.etl_update --target listed --date 2025-12-13"/>
</node>
<node CREATED="1700000000100" ID="ID_6_3" MODIFIED="1700000000100" TEXT="長期保有型">
<node CREATED="1700000000101" ID="ID_6_3_1" MODIFIED="1700000000101" TEXT="python -m omanta_3rd.jobs.longterm_run --asof 2025-12-19"/>
<node CREATED="1700000000102" ID="ID_6_3_2" MODIFIED="1700000000102" TEXT="python -m omanta_3rd.jobs.backtest --rebalance-date 2025-12-19 --save-to-db"/>
</node>
<node CREATED="1700000000107" ID="ID_6_5" MODIFIED="1700000000107" TEXT="ルート・シェル">
<node CREATED="1700000000108" ID="ID_6_5_1" MODIFIED="1700000000108" TEXT="update_all_data.py, run_production_optimization.ps1, run_walk_forward_analysis.ps1 等"/>
</node>
</node>
<node CREATED="1700000000109" ID="ID_7" MODIFIED="1700000000109" POSITION="right" TEXT="7. データフロー（簡略）">
<node CREATED="1700000000110" ID="ID_7_1" MODIFIED="1700000000110" TEXT="取り込み">
<node CREATED="1700000000111" ID="ID_7_1_1" MODIFIED="1700000000111" TEXT="J-Quants API → etl_update / update_all_data"/>
<node CREATED="1700000000112" ID="ID_7_1_2" MODIFIED="1700000000112" TEXT="→ listed_info, prices_daily, fins_statements, index_daily"/>
</node>
<node CREATED="1700000000113" ID="ID_7_2" MODIFIED="1700000000113" TEXT="特徴量・選定">
<node CREATED="1700000000114" ID="ID_7_2_1" MODIFIED="1700000000114" TEXT="DB → prepare_features または longterm_run.build_features"/>
<node CREATED="1700000000115" ID="ID_7_2_2" MODIFIED="1700000000115" TEXT="→ features_monthly（core_score_ref, entry_score_ref 含む）"/>
<node CREATED="1700000000116" ID="ID_7_2_3" MODIFIED="1700000000116" TEXT="→ run_strategy / longterm_run → ポートフォリオ"/>
</node>
<node CREATED="1700000000117" ID="ID_7_3" MODIFIED="1700000000117" TEXT="評価">
<node CREATED="1700000000118" ID="ID_7_3_1" MODIFIED="1700000000118" TEXT="ポートフォリオ時系列 → backtest/timeseries, performance, metrics"/>
<node CREATED="1700000000119" ID="ID_7_3_2" MODIFIED="1700000000119" TEXT="→ 時系列/累積リターン → Sharpe/MaxDD/CAGR 等"/>
</node>
</node>
</node>
</map>
