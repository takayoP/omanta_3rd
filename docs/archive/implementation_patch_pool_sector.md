# 最小パッチ案：pool_size と sector_cap_max を CLI→params→選定ロジックに通す

既存コード構造（`optimize_longterm.py` / `longterm_run.py`）を前提とした、CLI 固定シナリオで `pool_size` と `sector_cap` を渡すための最小パッチ案。

---

## 1. 変更箇所一覧

| ファイル | 変更内容 |
|----------|----------|
| `optimize_longterm.py` | argparse に `--pool-size`, `--sector-cap-max` を追加し、main/run_optimization 経由で渡す |
| `optimize_longterm.py` | objective_longterm / run_optimization で strategy_params 構築時に CLI 値を上書き |
| `optimize_longterm.py` | 最適化結果 JSON に `pool_size`, `sector_cap`, `scenario_id` を保存 |
| `build_year_scorecard.py` | load_normalized_params / create_strategy_params で pool_size, sector_cap を扱う |
| `build_year_scorecard.py` | スコアカード CSV に scenario_id, fail_reason, study_type などを追加 |

---

## 2. optimize_longterm.py のパッチ

### 2.1 argparse に引数を追加

**位置**: `parser.add_argument(...)` ブロック内（`--initial-params-json` の近く）

```python
parser.add_argument("--pool-size", type=int, default=None,
                    help="銘柄プールサイズ（Noneの場合はStrategyParamsのデフォルト80）")
parser.add_argument("--sector-cap-max", type=int, default=None,
                    help="1業種あたりの最大銘柄数（Noneの場合はデフォルト4）")
```

**main 呼び出し**: `main(... pool_size=args.pool_size, sector_cap_max=args.sector_cap_max)`

### 2.2 main のシグネチャ拡張

**関数**: `main(...)`

**追加引数**:
```python
pool_size: Optional[int] = None,
sector_cap_max: Optional[int] = None,
```

**run_optimization_longterm 呼び出し**: 上記を渡す。

### 2.3 run_optimization_longterm のシグネチャ拡張

**関数**: `run_optimization_longterm(...)`

**追加引数**:
```python
pool_size_override: Optional[int] = None,
sector_cap_override: Optional[int] = None,
```

**objective_longterm への渡し方**: `objective_longterm` はクロージャ内で使うため、`run_optimization_longterm` のスコープで `pool_size_override` と `sector_cap_override` をキャプチャして、`objective_longterm` 内で参照する。

### 2.4 objective_longterm 内で strategy_params を上書き

**位置**: `strategy_params = replace(default_params, ...)` の直後（約1236行付近）

```python
# CLI オーバーライド（シナリオ実行時）
if pool_size_override is not None:
    strategy_params = replace(strategy_params, pool_size=pool_size_override)
if sector_cap_override is not None:
    strategy_params = replace(strategy_params, sector_cap=sector_cap_override)
```

**注意**: `longterm_run.py` の `StrategyParams` は `sector_cap` という名前（`sector_cap_max` ではない）。CLI は `--sector-cap-max` で受け、内部では `sector_cap` にマッピングする。

### 2.5 最適化結果 JSON に scenario_id / pool_size / sector_cap を保存

**位置**: `result_data = {...}` の辞書内（約2007行付近）

```python
"pool_size": pool_size_override if pool_size_override is not None else default_params.pool_size,
"sector_cap": sector_cap_override if sector_cap_override is not None else default_params.sector_cap,
"scenario_id": scenario_id_from_cli,  # 例: f"S{pool}_{cap}" → "S120_2"
```

**scenario_id の算出例**:
```python
scenario_id = f"S{pool_size_override or 80}_{sector_cap_override or 4}"
```

### 2.6 initial_params_json 使用時の strategy_params 構築

**位置**: `run_optimization_longterm` 内、`initial_params` から `study.enqueue_trial` する処理の近く。また、**test_perf 評価時の strategy_params**（約1865行付近の `replace(default_params, ...)`）にも同様のオーバーライドを適用する。

```python
# test_perf 用の strategy_params 構築後
if pool_size_override is not None:
    strategy_params = replace(strategy_params, pool_size=pool_size_override)
if sector_cap_override is not None:
    strategy_params = replace(strategy_params, sector_cap=sector_cap_override)
```

---

## 3. longterm_run.py の確認

**変更不要**（既に `StrategyParams` に `pool_size` と `sector_cap` がある）:

```python
# longterm_run.py 34-45行付近
pool_size: int = 80
sector_cap: int = 4
```

`_select_portfolio_for_rebalance_date` に渡される `strategy_params_dict` は `fields(StrategyParams)` から作られるため、`pool_size` と `sector_cap` が含まれていればそのまま選定ロジックに渡る。

---

## 4. build_year_scorecard.py のパッチ

### 4.1 load_normalized_params で pool_size / sector_cap を読み込む

**既存の戻り値に追加**:
```python
return {
    "w_quality": ...,
    # ... 既存フィールド ...
    "pool_size": np_.get("pool_size", data.get("pool_size", 80)),
    "sector_cap": np_.get("sector_cap", data.get("sector_cap", 4)),
}
```

※`normalized_params` に無い場合はトップレベルの `pool_size`/`sector_cap`、それも無ければ 80/4。

### 4.2 create_strategy_params で pool_size / sector_cap を渡す

```python
def create_strategy_params(normalized_params: dict) -> StrategyParams:
    return StrategyParams(
        # ... 既存 ...
        pool_size=normalized_params.get("pool_size", 80),
        sector_cap=normalized_params.get("sector_cap", 4),
    )
```

**注意**: `StrategyParams` のコンストラクタで `pool_size` と `sector_cap` を受け付けるか確認する。`longterm_run.StrategyParams` は dataclass で全フィールドがあるので、上記で問題ないはず。

### 4.3 スコアカード CSV に追加する列（実装チェックリスト）

| 列 | 説明 | 取得元 |
|----|------|--------|
| scenario_id | シナリオ識別（例: S120_2） | JSON の `scenario_id` または `pool_size`+`sector_cap` から算出 |
| study_type | Study 種別（A/B/C/A_local） | JSON の `study_type` |
| seed | 乱数シード | JSON の `random_seed`（あれば） |
| fail_reason | 不合格理由（例: 2020_median<0） | 採点後に算出 |
| final12_overlap_rate | 候補間の final12 Jaccard 重複率 | 複数候補比較時に計算（将来） |
| sector_HHI | 業種 HHI | `calculate_longterm_performance` の戻り値に追加するか、別計算 |

**fail_reason の算出例**:
```python
reasons = []
if rec.get("median_annual_excess_return_pct") is not None and rec["median_annual_excess_return_pct"] < 0:
    reasons.append(f"{rec['year']}_median<0")
if rec.get("win_rate") is not None and rec["win_rate"] < 0.3:
    reasons.append(f"{rec['year']}_win_rate<0.3")
rec["fail_reason"] = ";".join(reasons) if reasons else ""
```

---

## 5. 実行例（シナリオ S4: pool=120, sector_cap=2）

```powershell
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 --end 2024-12-31 `
  --study-type C `
  --n-trials 50 `
  --pool-size 120 `
  --sector-cap-max 2 `
  --train-end-date 2021-12-30 --as-of-date 2024-12-31 `
  --horizon-months 24 `
  --random-seed 11 `
  --n-jobs 1 --bt-workers 8
```

出力 JSON に `scenario_id: "S120_2"`, `pool_size: 120`, `sector_cap: 2` が含まれる想定。

---

## 6. ログキー一覧（Phase A/B 用）

| キー | 説明 | 出力先 |
|------|------|--------|
| study_type | A/B/C/A_local | optimization_result_*.json |
| random_seed | 乱数シード | optimization_result_*.json |
| n_trials | 試行回数 | optimization_result_*.json |
| best_trial_number | 最良 trial 番号 | optimization_result_*.json |
| best_value | 最良値 | optimization_result_*.json |
| best_params | 最良パラメータ | optimization_result_*.json |
| params_hash | 候補ID | 算出（sha256 等） |
| scenario_id | シナリオ識別 | optimization_result_*.json |
| pool_size | プールサイズ | optimization_result_*.json |
| sector_cap | 業種キャップ | optimization_result_*.json |

---

## 7. 実装優先順位

1. **optimize_longterm.py**: `--pool-size`, `--sector-cap-max` の追加と strategy_params への反映
2. **optimize_longterm.py**: 結果 JSON への `pool_size`, `sector_cap`, `scenario_id` 保存
3. **build_year_scorecard.py**: `load_normalized_params` / `create_strategy_params` で pool_size, sector_cap を扱う
4. **build_year_scorecard.py**: CSV に `scenario_id`, `study_type`, `fail_reason` を追加
5. （将来）`calculate_longterm_performance` の戻り値に `sector_HHI`, `final12_overlap_rate` を追加
