# Walk-Forward Analysis 実行ガイド

## 概要

逆張り許可設計でのWalk-Forward Analysis実行用スクリプトとガイドです。

## 実行スクリプト一覧

### 1. n_trials=100のテスト（12M）

**ファイル**: `run_walk_forward_analysis_roll_n100.py`

**実行方法**:
```bash
python run_walk_forward_analysis_roll_n100.py
```

**説明**:
- 12Mホライズンでn_trials=100のrollテストを実行
- 再現性確認のため試行回数を増加
- 実行時間: 約3-4時間（推定）

**期待される成果物**:
- `walk_forward_longterm_12M_roll_evalYear2025.json`
- `params_by_fold.json`
- `params_operational.json`

---

### 2. 24M/36M同時実行（n_trials=30）

**ファイル**: `run_walk_forward_analysis_roll_24M_36M.ps1`

**実行方法**:
```powershell
.\run_walk_forward_analysis_roll_24M_36M.ps1
```

**説明**:
- 24Mと36Mのrollテストを同時に実行
- n_trials=30（初期設定）
- 実行時間: 約4-6時間（推定、並列実行により短縮）

**期待される成果物**:
- `walk_forward_longterm_24M_roll_evalYear2025.json`
- `walk_forward_longterm_36M_roll_evalYear2025.json`
- `params_by_fold_24M.json` / `params_by_fold_36M.json`
- `params_operational_24M.json` / `params_operational_36M.json`

**ログファイル**:
- `walk_forward_24M_YYYYMMDD_HHMMSS.log`
- `walk_forward_36M_YYYYMMDD_HHMMSS.log`

---

### 3. 24M/36M同時実行（n_trials=100）

**ファイル**: `run_walk_forward_analysis_roll_n100_24M_36M.ps1`

**実行方法**:
```powershell
.\run_walk_forward_analysis_roll_n100_24M_36M.ps1
```

**説明**:
- 24Mと36Mのrollテストを同時に実行
- n_trials=100（再現性確認のため増加）
- 実行時間: 約8-12時間（推定、並列実行により短縮）

**期待される成果物**:
- 上記（24M/36M同時実行）と同じ

**ログファイル**:
- `walk_forward_24M_n100_YYYYMMDD_HHMMSS.log`
- `walk_forward_36M_n100_YYYYMMDD_HHMMSS.log`

---

## 実行順序の推奨

### 今日（即座に実行可能）

1. **n_trials=100の12Mテスト**
   ```bash
   python run_walk_forward_analysis_roll_n100.py
   ```
   - 実行時間: 約3-4時間
   - 再現性確認のため優先実行

### 明日（仕事中に実行）

2. **24M/36M同時実行（n_trials=30）**
   ```powershell
   .\run_walk_forward_analysis_roll_24M_36M.ps1
   ```
   - 実行時間: 約4-6時間（並列実行）
   - 時間があればn_trials=100版も実行可能

---

## 実行中の監視

### PowerShellスクリプトの場合

スクリプトが自動的に進行状況を監視し、30秒ごとに以下を表示します：
- 経過時間
- 各ジョブの状態（Running/Completed/Failed）
- ログファイルの最後の行（進行状況確認）

### 手動監視

ログファイルを直接確認:
```powershell
Get-Content walk_forward_24M_*.log -Tail 20
Get-Content walk_forward_36M_*.log -Tail 20
```

ジョブの状態確認:
```powershell
Get-Job
```

---

## 実行後の確認事項

### 1. 結果ファイルの確認

各テストの結果JSONファイルを確認:
```bash
python -c "import json; data = json.load(open('walk_forward_longterm_12M_roll_evalYear2025.json', 'r', encoding='utf-8')); print('平均超過リターン:', data['summary']['mean_mean_excess_return_pct'], '%'); print('P10:', data['summary']['test_ann_excess_mean']['p10'], '%')"
```

### 2. パラメータの確認

各foldのbest_paramsを確認:
```bash
python -c "import json; data = json.load(open('params_by_fold.json', 'r', encoding='utf-8')); [print(f\"fold{k}: {v}\") for k, v in data.items()]"
```

### 3. 逆張り戦略の確認

逆張り戦略が選択されているか確認:
```bash
python -c "import json; data = json.load(open('walk_forward_longterm_12M_roll_evalYear2025.json', 'r', encoding='utf-8')); [print(f\"fold{r['fold']}: rsi_base={r['optimization']['best_params']['rsi_base']:.2f}, rsi_max={r['optimization']['best_params']['rsi_max']:.2f}\") for r in data['fold_results']]"
```

---

## トラブルシューティング

### ジョブが完了しない場合

1. ログファイルを確認してエラーを特定
2. ジョブの状態を確認:
   ```powershell
   Get-Job
   ```
3. 必要に応じてジョブを停止:
   ```powershell
   Stop-Job -Job <JobId>
   Remove-Job -Job <JobId>
   ```

### メモリ不足の場合

- `N_JOBS_FOLD`と`N_JOBS_OPTUNA`を1に設定（既に設定済み）
- 同時実行数を減らす（24M/36Mを別々に実行）

### 実行時間が長すぎる場合

- n_trialsを減らす（30 → 20など）
- 並列実行を無効化（既に無効化済み）

---

## 注意事項

1. **実行時間**: n_trials=100の場合、各foldで約1-2時間かかる可能性があります
2. **リソース**: 同時実行時はCPU/メモリ使用量が増加します
3. **ログファイル**: ログファイルは自動的に作成されますが、ディスク容量に注意してください
4. **中断**: Ctrl+Cで中断できますが、バックグラウンドジョブは継続します

---

## 次のステップ

実行完了後:
1. 結果を分析（`ROLL_TEST_RESULTS_ANALYSIS.md`を更新）
2. 固定パラメータ運用の候補を作成
3. 横持ち評価を実施（各foldのbest_paramsを他foldに適用）









