# PowerShellでのコマンド実行方法

## 問題

PowerShellでは、バックスラッシュ（`\`）による行継続が正しく動作しません。

## 解決方法

### 方法1: バッククォート（`` ` ``）を使用

PowerShellでは、バッククォート（`` ` ``）を使用して行を継続できます。

```powershell
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 `
  --end 2024-12-31 `
  --study-type A_local `
  --n-trials 100 `
  --train-end-date 2023-12-31 `
  --as-of-date 2024-12-31 `
  --horizon-months 24 `
  --lambda-penalty 0.00 `
  --objective-type mean `
  --n-jobs 1 `
  --bt-workers 4 `
  --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

### 方法2: 1行で記述

すべてを1行で記述することもできます。

```powershell
python -m omanta_3rd.jobs.optimize_longterm --start 2018-01-31 --end 2024-12-31 --study-type A_local --n-trials 100 --train-end-date 2023-12-31 --as-of-date 2024-12-31 --horizon-months 24 --lambda-penalty 0.00 --objective-type mean --n-jobs 1 --bt-workers 4 --initial-params-json optimization_result_optimization_longterm_studyA_20260121_204615.json
```

### 方法3: PowerShellスクリプトを使用

`scripts/run_local_search.ps1`を実行します。

```powershell
.\scripts\run_local_search.ps1
```

## 注意事項

- PowerShellでは、バックスラッシュ（`\`）ではなく、バッククォート（`` ` ``）を使用します
- バッククォートは行末に配置し、その後に改行を入れます
- バッククォートの前にはスペースを入れないでください（行末に直接配置）
