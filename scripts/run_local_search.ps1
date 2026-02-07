# Study Aのbest近傍で局所探索を実行するPowerShellスクリプト

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
