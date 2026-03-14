# Legacy / 研究用コード

V1 スリム化後、本番の「最適化・選定」の mainline は以下です。

- **最適化**: `python -m omanta_3rd.jobs.optimize_strategy --start ... --end ...`
- **選定実行**: `python -m omanta_3rd.jobs.run_strategy --mode monthly|longterm --asof ...` または `--start / --end`
- **特徴量準備**: `python -m omanta_3rd.jobs.prepare_features --asof ...`

以下は **legacy** です。新機能では使わず、既存の検証・研究用スクリプトからのみ参照してください。

| 対象 | 場所 | 備考 |
|------|------|------|
| 長期保有型の Optuna 最適化 | `src/omanta_3rd/jobs/optimize_longterm.py` | V1 mainline からは外す。固定ホライズン・study type 等は研究用。 |
| λ ペナルティ比較 | `src/omanta_3rd/jobs/compare_lambda_penalties.py` | optimize_longterm に依存。研究用。 |

上記ファイルは **移動していません**。既存の `from omanta_3rd.jobs.optimize_longterm import ...` 等はそのまま動作します。将来、これらを別パッケージや `legacy/` 配下に移す場合は、参照しているスクリプトの import を一括で書き換えてください。
