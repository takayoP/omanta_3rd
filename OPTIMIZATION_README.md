# パラメータ最適化システム

`entry_score`と`core_score`のパラメータを最適化するシステムです。Optunaを使用したベイズ最適化を実装しています。

## 主な機能

- **並列計算対応**: バックテストの並列実行により計算時間を大幅に短縮
- **順張り戦略対応**: RSIとボリンジャーバンドが高いときにエントリーする順張り戦略を最適化
- **効率的な最適化**: 各試行内でバックテストを並列実行し、全体の計算時間を削減

## 機能

- **entry_scoreパラメータの最適化**
  - RSI基準値・上限
  - BB Z-score基準値・上限
  - BBとRSIの重み

- **core_scoreパラメータの最適化**
  - 各サブスコアの重み（quality, value, growth, record_high, size）
  - value_score内の重み（forward_per, pbr）
  - フィルタ条件（roe_min, liquidity_quantile_cut）

## 使用方法

### 基本的な使用方法

```bash
python -m omanta_3rd.jobs.optimize --start 2022-01-01 --end 2025-12-28 --n-trials 50
```

### パラメータ

- `--start`: 開始日（YYYY-MM-DD、必須）
- `--end`: 終了日（YYYY-MM-DD、必須）
- `--n-trials`: 試行回数（デフォルト: 50）
- `--as-of-date`: 評価日（YYYY-MM-DD、省略時は最新の価格データを使用）
- `--study-name`: スタディ名（省略時は自動生成）

### 例

```bash
# 2022年から2025年までのデータで50回試行（並列計算自動）
python -m omanta_3rd.jobs.optimize --start 2022-01-01 --end 2025-12-28 --n-trials 50

# 評価日を指定
python -m omanta_3rd.jobs.optimize --start 2022-01-01 --end 2025-12-28 --as-of-date 2025-12-26 --n-trials 100

# スタディ名を指定（再開可能）
python -m omanta_3rd.jobs.optimize --start 2022-01-01 --end 2025-12-28 --study-name my_study --n-trials 100

# 並列実行数を指定（デフォルトはCPU数-1）
python -m omanta_3rd.jobs.optimize --start 2022-01-01 --end 2025-12-28 --n-trials 50 --n-jobs 4

# 逐次実行（並列化しない）
python -m omanta_3rd.jobs.optimize --start 2022-01-01 --end 2025-12-28 --n-trials 50 --n-jobs 1
```

## 最適化対象

最適化システムは以下の目的関数を最大化します：

```
objective = mean_excess_return * 0.7 + win_rate * 10 * 0.2 + sharpe_ratio * 0.1
```

- `mean_excess_return`: 平均超過リターン（ポートフォリオ - TOPIX）
- `win_rate`: TOPIXを上回った割合
- `sharpe_ratio`: 簡易シャープレシオ（超過リターンの平均/標準偏差）

## 出力

最適化実行後、以下のファイルが生成されます：

1. **`optimization_result_{study_name}.json`**: 最良パラメータのJSONファイル
2. **`optimization_history_{study_name}.png`**: 最適化履歴の可視化
3. **`param_importances_{study_name}.png`**: パラメータ重要度の可視化
4. **`optuna_{study_name}.db`**: Optunaのデータベース（再開可能）

## 最適化パラメータの範囲

### StrategyParams

- `w_quality`: 0.2 ~ 0.5
- `w_value`: 0.15 ~ 0.35
- `w_growth`: 0.1 ~ 0.25
- `w_record_high`: 0.05 ~ 0.25
- `w_size`: 0.05 ~ 0.2
- `w_forward_per`: 0.3 ~ 0.7
- `roe_min`: 0.05 ~ 0.15
- `liquidity_quantile_cut`: 0.1 ~ 0.3

### EntryScoreParams（順張り戦略向け）

- `rsi_base`: 30.0 ~ 70.0（基準値、RSIがこの値以上で高スコア）
- `rsi_max`: 70.0 ~ 90.0（上限、RSIがこの値で最大スコア）
- `bb_z_base`: -2.0 ~ 2.0（基準値、BB Z-scoreがこの値以上で高スコア）
- `bb_z_max`: 2.0 ~ 4.0（上限、BB Z-scoreがこの値で最大スコア）
- `bb_weight`: 0.2 ~ 0.8（BBとRSIの重み、BB側）

**注意**: 
- 順張り戦略のため、RSIとBB Z-scoreが高いほど高スコアになります。
- BB Z-scoreはボリンジャーバンドのシグマ（標準偏差の倍数）を表します。
  - Z-score = 0: 移動平均
  - Z-score = ±1: ±1シグマ（通常のボリンジャーバンドの上下限）
  - Z-score = ±2: ±2シグマ（ボリンジャーバンドの外側）

## 並列計算について

- **デフォルト動作**: CPU数-1の並列実行（安全のため）
- **並列化レベル**: 各試行内でバックテストを並列実行（複数のリバランス日を同時に処理）
- **効率**: 並列実行により、計算時間を大幅に短縮（CPU数に応じて最大数倍高速化）
- **制御**: `--n-jobs`オプションで並列実行数を指定可能（1で逐次実行）

## 注意事項

1. **実行時間**: 最適化は時間がかかりますが、並列計算により大幅に短縮されます
2. **データベース**: 最適化中は`portfolio_monthly`テーブルが上書きされます
3. **メモリ**: 並列実行時はメモリ使用量が増加します（CPU数に応じて）
4. **Windows**: Windows環境では`multiprocessing`の制限により、一部機能が制限される場合があります

## 最適化結果の適用

最適化結果のJSONファイルから最良パラメータを取得し、以下のファイルに適用してください：

### 1. StrategyParamsの適用

`src/omanta_3rd/jobs/monthly_run.py`の`StrategyParams`クラス（31-59行目）を更新：

```python
@dataclass(frozen=True)
class StrategyParams:
    # 最適化結果から取得した値を設定
    w_quality: float = 0.35  # 最適化結果の値
    w_value: float = 0.25    # 最適化結果の値
    w_growth: float = 0.15   # 最適化結果の値
    w_record_high: float = 0.15  # 最適化結果の値
    w_size: float = 0.10     # 最適化結果の値
    # ... その他のパラメータ
```

### 2. entry_scoreの適用

`src/omanta_3rd/jobs/monthly_run.py`の`_entry_score`関数（136-165行目）を更新：

現在の実装は既に順張り（RSI高い、BB高い）になっていますが、最適化結果に基づいてパラメータを調整できます：

```python
def _entry_score(close: pd.Series) -> float:
    scores = []
    for n in (20, 60, 90):
        z = _bb_zscore(close, n)
        rsi = _rsi_from_series(close, n)

        bb_score = np.nan
        rsi_score = np.nan

        if not pd.isna(z):
            # 最適化結果のbb_z_base, bb_z_maxを使用
            bb_z_base = 0.0  # 最適化結果の値
            bb_z_max = 3.0  # 最適化結果の値
            if bb_z_max != bb_z_base:
                bb_score = (z - bb_z_base) / (bb_z_max - bb_z_base)
            else:
                bb_score = 0.0
                
        if not pd.isna(rsi):
            # 最適化結果のrsi_base, rsi_maxを使用
            rsi_base = 50.0  # 最適化結果の値
            rsi_max = 80.0   # 最適化結果の値
            if rsi_max != rsi_base:
                rsi_score = (rsi - rsi_base) / (rsi_max - rsi_base)
            else:
                rsi_score = 0.0

        # 最適化結果の重みを使用
        bb_weight = 0.5  # 最適化結果の値
        rsi_weight = 0.5  # 最適化結果の値
        total_weight = bb_weight + rsi_weight
        
        if total_weight > 0:
            if not pd.isna(bb_score) and not pd.isna(rsi_score):
                scores.append(
                    (bb_weight * bb_score + rsi_weight * rsi_score) / total_weight
                )
            elif not pd.isna(bb_score):
                scores.append(bb_score)
            elif not pd.isna(rsi_score):
                scores.append(rsi_score)

    if not scores:
        return np.nan
    return float(np.nanmax(scores))
```

### 3. 最適化結果の確認

最適化結果のJSONファイル（`optimization_result_{study_name}.json`）を確認：

```json
{
  "best_value": 2.345,
  "best_params": {
    "w_quality": 0.35,
    "w_value": 0.25,
    "w_growth": 0.15,
    "w_record_high": 0.15,
    "w_size": 0.10,
    "rsi_base": 50.0,
    "rsi_max": 80.0,
    "bb_z_base": 0.0,
    "bb_z_max": 3.0,
    "bb_weight": 0.5,
    ...
  },
  "n_trials": 50
}
```

## トラブルシューティング

### エラー: "ポートフォリオが見つかりません"

- リバランス日の価格データが不足している可能性があります
- データベースの価格データを更新してください

### エラー: "特徴量が空です"

- 財務データが不足している可能性があります
- データベースの財務データを更新してください

