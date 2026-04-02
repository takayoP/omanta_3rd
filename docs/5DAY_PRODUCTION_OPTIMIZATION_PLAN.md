# 5日間・実運用向け 月次リバランス型最適化プラン

## 前提

- **対象**: 月次リバランス型のパラメータ最適化（`optimize_timeseries`）
- **期間**: 5日間で本命の最適化＋Holdout検証＋オプションの信頼性確認まで実施可能
- **参照**: README §7、OPTIMIZATION_EXECUTION_EXAMPLES.md、OPTIMIZATION_SYSTEM_OVERVIEW.md、CLAUDE.md

---

## 時間の目安

| 処理 | 目安 | 備考 |
|------|------|------|
| 本命最適化（200 trials, n-jobs=4） | 約3〜6時間 | 1 trial あたり 1〜5分、SQLite では n-jobs 2〜4 推奨 |
| 特徴量キャッシュ warm | 約30分〜2時間 | 初回のみ。期間内の全リバランス日を計算 |
| Holdout 検証（別スクリプト） | 30〜60分 | 最適化結果 JSON を入力に 2024 で評価 |
| Robust 最適化（オプション） | 5〜15時間 | 30 trials × WFA 複数 fold |

5日あれば本命 200 trials ＋ Holdout ＋ 必要に応じて Robust や追加トライアルが可能。

---

## 推奨スケジュール（案）

### 1日目: 準備と本命最適化の開始

1. **データ確認**  
   - DB に価格・財務・指数データがあることを確認（不足なら `python update_all_data.py` または `python -m omanta_3rd.jobs.etl_update`）
2. **本命最適化の実行**  
   - 下記「本命コマンド」を実行（例: 200 trials）。  
   - ログをファイルに残す:  
     `.\scripts\run_production_optimization.ps1 2>&1 | Tee-Object -FilePath logs\optimization_YYYYMMDD.log`
3. **終了後**  
   - `optimization_result_optimization_timeseries_<study_name>.json` がカレントに出力されていることを確認

### 2日目: 本命が終わっていれば Holdout 検証

- 最適化結果 JSON を使って Holdout 期間（例: 2024）で評価  
- 手順は `OPTIMIZATION_EXECUTION_EXAMPLES.md` の「Step 2: Holdout」を参照  
- 判定目安: Holdout の Sharpe_excess が Train の 50〜70% 残っていれば良好

### 3〜4日目: 追加トライアル or Robust（任意）

- **同一 study に追加**: 同じ `--study-name` で `--n-trials` を足して再実行（`load_if_exists=True` で継続）
- **Robust 最適化**: 時間方向の安定性を見たい場合  
  `python -m omanta_3rd.jobs.robust_optimize_timeseries --start 2021-01-01 --end 2024-12-31 --n-trials 30 --folds 3 ...`

### 5日目: 結果整理と判断

- サマリーレポート・best パラメータ・Holdout 結果を確認
- 運用に使うパラメータを決定し、`config/params_registry_longterm.json` や運用手順に反映

---

## 本命コマンド（実運用想定）

- **期間**: 2021-01-01 ～ 2024-12-31（約4年）
- **トライアル数**: 200（信頼性を重視するなら 100 で一度確認してから 200 も可）
- **取引コスト**: 20 bps（片道）。月次往復で 40 bps を想定（TRADING_COST_DOCUMENTATION.md 参照）
- **並列**: `--n-jobs 4`（SQLite 推奨）、`--bt-workers 1`
- **進捗ウィンドウ**: なし（`--no-progress-window`）でログをファイルに取りやすいようにする

実行は **`scripts/run_production_optimization.ps1`** を使用（BLAS 環境変数と上記オプションを設定済み）。

手動で実行する場合の例:

```powershell
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:OPENBLAS_NUM_THREADS="1"
$env:NUMEXPR_NUM_THREADS="1"
python -m omanta_3rd.jobs.optimize_timeseries `
  --start 2021-01-01 `
  --end 2024-12-31 `
  --n-trials 200 `
  --study-name production_YYYYMMDD `
  --parallel-mode trial `
  --n-jobs 4 `
  --bt-workers 1 `
  --cost 20 `
  --no-progress-window
```

`production_YYYYMMDD` は実行日などに合わせて変更してください。

---

## 出力ファイル

- **最適化結果**: `optimization_result_optimization_timeseries_<study_name>.json`  
  - `best_params`（正規化後）、`best_params_raw`、`best_value`、`entry_mode` などを保持
- **Optuna DB**: `optuna_<study_name>.db`（SQLite の場合、カレントディレクトリ）
- **特徴量キャッシュ**: `cache/features/`（再利用されるため 2 回目以降は warm が短縮）

---

## 注意事項

1. **BLAS スレッド**: 並列実行時は OMP/MKL/OPENBLAS/NUMEXPR を 1 に固定（スクリプトで設定済み）
2. **SQLite**: `--n-jobs` は 2〜4 を推奨。増やしすぎるとロック待ちが増える
3. **取引コスト**: 実運用に近づけるため `--cost 20` を推奨（要約すると月次往復 40 bps）
4. **途中終了**: Ctrl+C で止めても、完了した trial は Optuna DB に残る。同じ `--study-name` で再実行すれば `load_if_exists=True` で継続可能

---

## 関連ドキュメント

- README.md §7（最適化）
- OPTIMIZATION_EXECUTION_EXAMPLES.md（実行例・Holdout）
- OPTIMIZATION_SYSTEM_OVERVIEW.md（計算時間・パラメータ解釈）
- TRADING_COST_DOCUMENTATION.md（コストの定義と感度）
- CLAUDE.md（アーキテクチャ・制約）
