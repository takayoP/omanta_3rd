# 年別スコアカード自動化（Gate3）の実行例
# 候補JSONを指定して 2020/2021/2022 を採点し CSV を出力する

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

# 例1: 単一候補
# python scripts/build_year_scorecard.py --candidates "path/to/optimization_result_xxx.json" --cost-bps 25 --out scorecard_year.csv

# 例2: 複数候補
# python scripts/build_year_scorecard.py --candidates "result1.json" "result2.json" --cost-bps 25 --out scorecard_year.csv

# 例3: ディレクトリ内の全JSONを候補にする
# python scripts/build_year_scorecard.py --candidates-dir results/raw --cost-bps 25 --out scorecard_year.csv

# デフォルト実行（カレントの optimization_result_*.json を探す場合）
$candidates = Get-ChildItem -Path . -Filter "optimization_result_*.json" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 5 -ExpandProperty FullName
if (-not $candidates) {
    Write-Host "候補JSONが見つかりません。--candidates でパスを指定してください。"
    exit 1
}
python scripts/build_year_scorecard.py --candidates $candidates --cost-bps 25 --bt-workers 4 --out scorecard_year.csv
