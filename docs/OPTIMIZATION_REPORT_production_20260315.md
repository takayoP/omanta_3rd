# 月次リバランス型 最適化レポート

**実行日**: 2026-03-15  
**共有先**: Claude セッション引き継ぎ・レビュー用  
**リポジトリ**: omanta_3rd  

---

## 1. エグゼクティブサマリー

- **ジョブ**: `python -m omanta_3rd.jobs.optimize_timeseries`（実運用スクリプト: `scripts/run_production_optimization.ps1`）
- **目的**: 月次リバランス型の **StrategyParams + EntryScoreParams** を Optuna で探索し、**Sharpe_excess**（時系列方式・月次超過リターンの年率化シャープ／IR に相当）を最大化。
- **結果**: 200 trial 完了。**最良 trial #120** で目的関数値 **約 2.13**。p95・median も高く、**best だけ突出した「宝くじ型」ではない**分布。
- **推奨次ステップ**: **Holdout（未使用期間）での固定パラメータ検証**、**取引コスト感度**、必要に応じて **WFA / Robust**。詳細は §6。

---

## 2. 実行条件（設定）

| 項目 | 値 |
|------|-----|
| Study 名 | `production_20260315` |
| 評価期間（start–end） | `2021-01-01` ～ `2024-12-31`（スクリプト既定） |
| 試行数 | 200 |
| 取引コスト | **20 bps（片道）**（`--cost 20`） |
| 計算方式 | `timeseries`（月末始値→翌月始値の実運用タイミング） |
| entry_mode | `free` |
| 並列 | `run_production_optimization.ps1` 既定（trial 並列 n-jobs=4, bt-workers=1, BLAS スレッド=1） |

※ 期間がスクリプトと異なる場合は、実際に渡した `--start` / `--end` に読み替えてください。

---

## 3. 最適化結果（数値）

### 3.1 最良試行

| 項目 | 値 |
|------|-----|
| 最良試行番号 | 120 |
| 最良値（目的関数） | **2.1298** |

### 3.2 最良パラメータ（ログ出力・正規化後イメージ）

| パラメータ | 値 |
|------------|-----|
| w_quality | 0.3150 |
| w_value | 0.2018 |
| w_growth | 0.1654 |
| w_record_high | 0.1496 |
| w_size | 0.1730 |
| w_forward_per | 0.5289 |
| roe_min | 0.1167 |
| liquidity_quantile_cut | 0.3456 |
| rsi_base | 29.7366 |
| rsi_max | 47.7687 |
| bb_z_base | -0.7166 |
| bb_z_max | -0.1819 |
| bb_weight | 0.6880 |

### 3.3 JSON 保存値（機械可読・再現用）

- **best_value（高精度）**: `2.129814650076145`
- **best_params / best_params_raw**: 下記ファイル参照（コア重みは JSON 内で正規化済み）。

---

## 4. 分布サマリー（過学習の目安）

| 指標 | 値 | 備考 |
|------|-----|------|
| 完了試行数 | 200 | |
| best（Sharpe_excess） | 2.1298 | |
| p95 | 1.9999 | best の **93.9%** |
| median | 1.6011 | best の **75.2%** |

**解釈（要約）**: p95 が best に非常に近く、median も高いため、「top だけ異常に良い」単発当たりよりは、**探索空間・当該期間では広い領域で似た性能**が出ている可能性がある。ただし **in-sample のみ**のため、外样本検証は必須。

### 上位 5 trial のパラメータレンジ（ログより）

| パラメータ | 最小～最大（レンジ） |
|------------|----------------------|
| bb_weight | 0.6446 ～ 0.6880（range 0.0434） |
| bb_z_base | -1.2644 ～ -0.7166（range 0.5478） |
| bb_z_max | -3.4137 ～ -0.1819（range 3.2318） |
| liquidity_quantile_cut | 0.3245 ～ 0.3500（range 0.0255） |
| rsi_base | 27.52 ～ 35.58（range 8.07） |
| rsi_max | 16.62 ～ 48.49（range 31.88） |
| w_forward_per | 0.5289 ～ 0.5723（range 0.0435） |
| w_growth | 0.1606 ～ 0.1877（range 0.0271） |
| w_quality | 0.2978 ～ 0.3274（range 0.0295） |

**メモ**: `bb_z_max` / `rsi_max` のレンジが広い → 目的関数がそこに**鈍感**な可能性（param_importances 図と併読推奨）。

---

## 5. パラメータの意味（簡易コメント）

- **コア重み**: quality が最大寄与、value / size も一定。growth・record_high もバランス。
- **w_forward_per ≈ 0.53**: バリュー合成で Forward PER 寄与が強め。
- **bb_weight ≈ 0.69**: エントリー側で **BB を RSI より重視**する帯。
- **roe_min ≈ 0.117**: コード上の定義（% か小数か）を `StrategyParams` / サンプリング実装で要確認。
- **liquidity_quantile_cut ≈ 0.35**: 流動性フィルタがやや厳しめ寄り。

---

## 6. 計算時間（Timing サマリー）

| フェーズ | 平均（1 trial） | 備考 |
|----------|-----------------|------|
| data_fetch_time | 約 12648.7 s | **ボトルネック（約 100%）** |
| save_time | 約 0.05 s | |
| timeseries_calc_time | 約 0.44 s | |
| metrics_calc_time | 約 0.00 s | |
| total_time | 約 12649.1 s | |

※ 並列実行時の**壁時計**とは一致しない可能性あり。いずれにせよ **各 trial のデータ取得・ポートフォリオ構築が支配的**。

---

## 7. 生成アーティファクト（パス）

| 種別 | パス（リポジトリルート相対） |
|------|------------------------------|
| 最適化結果 JSON | `optimization_result_optimization_timeseries_production_20260315.json` |
| Optuna DB（既定時） | `optuna_production_20260315.db` |
| 最適化履歴図 | `optimization_history_production_20260315.png` |
| パラメータ重要度図 | `param_importances_production_20260315.png` |
| 実行プラン参照 | `docs/5DAY_PRODUCTION_OPTIMIZATION_PLAN.md` |
| アーキテクチャ・制約 | `CLAUDE.md` |

---

## 8. Claude に依頼したいレビュー観点（チェックリスト）

1. **数値の妥当性**: Sharpe_excess ≈ 2.1 は当該期間・コスト 20bps・実装定義のもとで過大に見えないか（定義確認・サンプル月の手計算）。
2. **Holdout 設計**: Train/Holdout の切り方（例: 2021–2023 / 2024）と、合格ライン（Train 比 50–70% 残存など）の提案。
3. **過学習 vs レジーム**: 分布が上位に密集している解釈と、追加で見るべき統計（分位点・年次分解など）。
4. **運用移行**: `best_params` をレジストリに載せる際のリスク（`roe_min` スケール、entry_mode の固定方針）。
5. **高速化**: data_fetch ボトルネックに対する改善案（キャッシュ戦略・並列・DB）。

---

## 9. 推奨される次のアクション（優先順）

1. **Holdout**: 固定 `best_params` で未使用期間を再評価（`OPTIMIZATION_EXECUTION_EXAMPLES.md` Step 2、`evaluate_candidates_holdout.py` 等）。
2. **コスト感度**: 0 / 10 / 20 / 30 bps で同パラメータを再評価（`TRADING_COST_DOCUMENTATION.md`）。
3. **WFA / Robust**（余力時）: `robust_optimize_timeseries` や walk-forward。
4. **運用**: Holdout 通過後に `params_registry` 反映と、直近月末のポートフォリオ生成・人間による確認。

---

## 10. 免責・注意

本レポートは投資助言ではありません。バックテスト結果は将来を保証しません。データ遅延・流動性・スリッページ・税制等は別途考慮してください。

---

*本ファイルは `optimization_result_optimization_timeseries_production_20260315.json` および実行ログに基づく。数値の最終確定は JSON を正とする。*
