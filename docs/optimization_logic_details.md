# 長期保有型パラメータ最適化システム - ロジック詳細

## 1. システム概要

### 1.1 目的
長期保有型投資戦略のパラメータ最適化を行うシステム。Optunaを使用してハイパーパラメータを最適化し、TOPIXに対する年率超過リターンを最大化する。

### 1.2 基本設計
- **最適化フレームワーク**: Optuna
- **評価方式**: 時系列分割による学習/テストデータ分割
- **投資ホライズン**: 固定ホライズン評価（デフォルト: 24ヶ月）
- **ポートフォリオ選定**: 月次リバランス（ただし長期保有型のため、選択されたポートフォリオは固定ホライズンまで保持）

### 1.3 主要ファイル
- `src/omanta_3rd/jobs/optimize_longterm.py`: 最適化ロジックのメインファイル
- `src/omanta_3rd/jobs/longterm_run.py`: ポートフォリオ選定ロジック
- `src/omanta_3rd/backtest/feature_cache.py`: 特徴量キャッシュシステム
- `src/omanta_3rd/backtest/performance.py`: パフォーマンス計算

## 2. 最適化フロー

### 2.1 全体フロー
```
1. リバランス日の取得（月次）
   ↓
2. 学習/テストデータ分割（時系列分割）
   ↓
3. 特徴量キャッシュの構築/読み込み
   ↓
4. Optuna最適化の実行（複数trial並列実行）
   ↓
   ├─ 4.1 パラメータのサンプリング（Study A/B/C）
   ├─ 4.2 ポートフォリオ選定（学習データで実行）
   ├─ 4.3 パフォーマンス計算（固定ホライズン評価）
   └─ 4.4 目的関数の計算（年率超過リターン）
   ↓
5. ベストパラメータの特定
   ↓
6. テストデータでの評価
   ↓
7. 結果の保存と可視化
```

### 2.2 学習/テストデータ分割
```python
def split_rebalance_dates(
    rebalance_dates: List[str],
    train_ratio: float = 0.8,  # デフォルト: 80%
    train_end_date: Optional[str] = None,  # 明示的な分割日を指定可能
    horizon_months: int = 24,  # 投資ホライズン
    as_of_date: Optional[str] = None,  # 評価の打ち切り日
) -> Tuple[List[str], List[str]]
```

**重要**: 
- デフォルトでは時系列分割（`time_series_split=True`）
- `train_end_date`が指定されている場合は、その日以前が学習データ
- テストデータは`as_of_date - horizon_months`以前に制限される（固定ホライズン評価のため）

### 2.3 特徴量キャッシュシステム

#### キャッシュの目的
- 特徴量計算は時間がかかるため、事前に計算してキャッシュ
- 最適化中の各trialで同じ特徴量を再利用

#### キャッシュされる特徴量
- **含まれる**: quality, value, growth, record_high, sizeスコア、BB Z-score、RSIなどの生特徴量
- **含まれない**: `core_score`、`entry_score`（これらはtrialごとにパラメータに応じて動的に計算）

#### 最近の修正（2026年1月12日）
**問題**: `entry_score`と`core_score`が誤ってキャッシュされ、最適化が正しく動作していなかった

**修正内容**:
1. キャッシュ構築時: `entry_score`と`core_score`列を明示的に削除
2. キャッシュ読み込み時: 既存のキャッシュファイルからも`entry_score`と`core_score`列を削除（防御的プログラミング）
3. ポートフォリオ選定時: `entry_score`は常に再計算されるように修正

## 3. パラメータ探索範囲

### 3.1 Studyタイプ

システムは3つのStudyタイプ（A/B/C）をサポート：

#### Study A: BB寄り・低ROE閾値
```python
w_quality: 0.05 - 0.50
w_growth: 0.01 - 0.30
w_record_high: 0.01 - 0.20
w_size: 0.05 - 0.40
w_value: 0.10 - 0.50
w_forward_per: 0.20 - 0.90  # Forward PERの重み
roe_min: 0.00 - 0.12  # ROE最小閾値（低め）
bb_weight: 0.30 - 0.95  # BB Z-scoreの重み（高い = BB寄り）
```

#### Study B: Value寄り・ROE閾値やや高め
```python
w_quality: 0.05 - 0.50
w_growth: 0.01 - 0.30
w_record_high: 0.01 - 0.20
w_size: 0.05 - 0.40
w_value: 0.20 - 0.60  # Valueの重みが高い
w_forward_per: 0.20 - 0.80
roe_min: 0.00 - 0.20  # ROE閾値がやや高め
bb_weight: 0.20 - 0.80
```

#### Study C: 広範囲探索
```python
w_quality: 0.01 - 0.70  # 拡張範囲
w_growth: 0.01 - 0.50
w_record_high: 0.01 - 0.30
w_size: 0.01 - 0.60
w_value: 0.05 - 0.80
w_forward_per: 0.0 - 1.0  # 完全に自由
roe_min: 0.00 - 0.30
bb_weight: 0.0 - 1.0  # 完全に自由
liquidity_quantile_cut: 0.05 - 0.50  # 流動性フィルタ
```

### 3.2 Entry Scoreパラメータ（共通）

#### RSIパラメータ
```python
rsi_base: 15.0 - 85.0
rsi_max: base ± min_width の範囲外から選択
  - 順張り方向: [base + 10.0, 85.0]
  - 逆張り方向: [15.0, base - 10.0]
rsi_min_width: 10.0  # 最小幅制約
```

#### BB Z-scoreパラメータ
```python
bb_z_base: -3.5 - 3.5
bb_z_max: base ± min_width の範囲外から選択
  - 順張り方向: [base + 0.5, 3.5]
  - 逆張り方向: [-3.5, base - 0.5]
bb_z_min_width: 0.5  # 最小幅制約
```

**注意**: RSI/BBの方向（順張り/逆張り）は、trial番号の偶奇で決定（パラメータ空間を増やさないため）

### 3.3 正規化
- Core Scoreの重み（w_quality, w_value, w_growth, w_record_high, w_size）は合計が1になるように正規化
- Value内訳（w_forward_per, w_pbr）は `w_pbr = 1.0 - w_forward_per` で決定
- Entry Scoreの重み（bb_weight, rsi_weight）は `rsi_weight = 1.0 - bb_weight` で決定

## 4. ポートフォリオ選定ロジック

### 4.1 選定フロー
```
1. 特徴量の取得（キャッシュから読み込み）
   ↓
2. Core Scoreの計算
   core_score = w_quality * quality + w_value * value + w_growth * growth 
                + w_record_high * record_high + w_size * size
   ↓
3. Entry Scoreの計算（常に再計算）
   bb_z_normalized = (bb_z - bb_z_base) / (bb_z_max - bb_z_base)
   rsi_normalized = (rsi - rsi_base) / (rsi_max - rsi_base)
   entry_score = bb_weight * bb_z_normalized + (1 - bb_weight) * rsi_normalized
   ↓
4. フィルタリング
   - ROE >= roe_min
   - 流動性フィルタ（liquidity_quantile_cut）
   - 価格データの存在チェック
   ↓
5. プール選定（上位80銘柄）
   - core_scoreでソート、上位80銘柄を選択
   ↓
6. 最終選定（12銘柄）
   - entry_scoreでソート（降順）
   - core_scoreでタイブレーク（降順）
   - セクターキャップ（最大4銘柄/セクター）
   - 等ウェイト
```

### 4.2 重要な確認事項
- ✅ Core Scoreで80銘柄を選定
- ✅ その80銘柄に対してEntry Scoreで最終12銘柄を選定
- ✅ Entry Scoreは常に再計算される（キャッシュから読み込まない）

## 5. パフォーマンス計算

### 5.1 固定ホライズン評価

各ポートフォリオは、リバランス日から固定ホライズン（例: 24ヶ月）後まで保持され、その時点でのパフォーマンスを評価。

```python
eval_end_date = rebalance_date + relativedelta(months=horizon_months)
```

### 5.2 パフォーマンス指標

各ポートフォリオについて：
1. 累積リターン（%）
2. TOPIXとの比較
   - TOPIX累積リターン（%）
   - 超過リターン（%）= ポートフォリオ累積リターン - TOPIX累積リターン
3. 年率化リターン
   - 年率リターン = (1 + 累積リターン/100)^(1/保有年数) - 1
   - 年率超過リターン = 年率リターン - 年率TOPIXリターン

### 5.3 集計指標

学習データ全体について：
- **目的関数**: 各ポートフォリオの年率超過リターンの平均
  ```python
  mean_annual_excess_return_pct = mean([annual_excess_return_i for i in portfolios])
  ```
- **参考指標**:
  - 年率リターンの平均・中央値
  - 累積リターン
  - 勝率（年率超過リターン > 0 のポートフォリオの割合）
  - 下振れ指標（P10, P25, min）

### 5.4 下振れ罰（λペナルティ）

```python
objective_value = mean_annual_excess_return_pct - lambda_penalty * max(0, -p10_annual_excess_return_pct)
```

- `lambda_penalty > 0`の場合、下位10%のポートフォリオの下振れが大きいほど目的関数の値が低下
- デフォルト: `lambda_penalty = 0.0`（下振れ罰なし）

## 6. 並列化の実装

### 6.1 並列化レベル

#### レベル1: Optuna Trialの並列化
- Optunaが複数のtrialを並列実行
- 並列数: `--n-jobs`で指定（デフォルト: -1 = CPU数に応じて自動調整）

#### レベル2: 各Trial内のバックテスト並列化
- ポートフォリオ選定: 各リバランス日を並列処理
- パフォーマンス計算: 各ポートフォリオの評価を並列処理
- 並列数: `--bt-workers`で指定（デフォルト: -1 = 自動調整）

### 6.2 並列化の実装詳細（最近の改善）

#### ポートフォリオ選定の並列化
```python
# ProcessPoolExecutorを優先使用（CPU集約的なタスク）
# Windowsで失敗した場合はThreadPoolExecutorにフォールバック
with ProcessPoolExecutor(max_workers=n_jobs) as executor:
    futures = {
        executor.submit(_select_portfolio_for_rebalance_date, ...)
        for rebalance_date in rebalance_dates
    }
```

#### パフォーマンス計算の並列化
```python
# 各ポートフォリオのパフォーマンス計算を並列実行
with ProcessPoolExecutor(max_workers=perf_n_jobs) as executor:
    futures = {
        executor.submit(_calculate_performance_single_longterm, ...)
        for rebalance_date, portfolio_df_dict, eval_date in portfolio_tasks
    }
```

**改善点（2026年1月12日）**:
1. パフォーマンス計算部分を並列化可能な関数（`_calculate_performance_single_longterm`）に分離
2. ProcessPoolExecutorを優先使用（CPU集約的なタスクのため）
3. 並列化設定の自動調整を改善（より積極的に並列化）

### 6.3 並列化設定の自動調整

```python
if n_jobs == -1:
    if storage.startswith("sqlite"):
        optuna_n_jobs = min(4, max(2, min(4, cpu_count // 8)))  # SQLiteは並列書き込みに弱い
    else:
        optuna_n_jobs = min(8, max(1, cpu_count // 2))

if bt_workers == -1:
    available_cpus = max(1, cpu_count - optuna_n_jobs)
    # より積極的に並列化（4つ以上のCPUがある場合）
    if len(train_dates) >= 4 and available_cpus >= 4:
        backtest_n_jobs = max(4, min(len(train_dates), min(8, available_cpus)))
```

## 7. 目的関数

### 7.1 基本形
```python
def objective_longterm(...) -> float:
    # パラメータのサンプリング
    strategy_params, entry_params = sample_params(trial, study_type)
    
    # パフォーマンス計算
    perf = calculate_longterm_performance(
        train_dates,
        strategy_params,
        entry_params,
        horizon_months=24,
        as_of_date=train_end_date,
    )
    
    # 目的関数: 年率超過リターン（λペナルティ付き）
    objective_value = (
        perf["mean_annual_excess_return_pct"]
        - lambda_penalty * max(0, -perf["p10_annual_excess_return_pct"])
    )
    
    return objective_value
```

### 7.2 最適化の目標
- **最大化**: 年率超過リターン（TOPIXに対する超過リターン）
- **制約**: 下振れ罰（`lambda_penalty > 0`の場合）

## 8. 重要な注意事項

### 8.1 未来参照リークの防止
1. **as_of_dateの明示的指定**: 評価の打ち切り日を必ず指定
2. **固定ホライズン評価**: 各ポートフォリオは固定期間のみ評価
3. **時系列分割**: 学習データはテストデータより過去に限定

### 8.2 キャッシュの整合性
- `entry_score`と`core_score`はキャッシュに含まれない
- キャッシュ再構築が必要な場合は`--force-rebuild-cache`オプションを使用

### 8.3 並列化の注意点
- Windows環境ではProcessPoolExecutorが失敗する場合がある（その場合はThreadPoolExecutorに自動フォールバック）
- SQLiteストレージを使用する場合、Optunaの並列数は制限される

### 8.4 パフォーマンス計算の注意点
- 累積リターンが-100%未満の場合は年率化をスキップ（複素数が生成されるため）
- ホライズン未達のポートフォリオは除外される（`require_full_horizon=True`の場合）

## 9. 実行コマンド例

### Study Bでの最適化
```powershell
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 `
  --end 2024-12-31 `
  --study-type B `
  --n-trials 200 `
  --train-end-date 2023-12-31 `
  --as-of-date 2024-12-31 `
  --horizon-months 24 `
  --lambda-penalty 0.00 `
  --n-jobs 4 `
  --bt-workers 8 `
  --force-rebuild-cache  # キャッシュ再構築が必要な場合
```

### 主要パラメータ
- `--start`: データの開始日
- `--end`: データの終了日
- `--study-type`: A/B/Cのいずれか
- `--n-trials`: 試行回数
- `--train-end-date`: 学習期間の終了日（明示的に指定を推奨）
- `--as-of-date`: 評価の打ち切り日
- `--horizon-months`: 投資ホライズン（月数）
- `--lambda-penalty`: 下振れ罰の係数
- `--n-jobs`: Optuna試行の並列数
- `--bt-workers`: 各試行内のバックテスト並列数

## 10. 最近の修正履歴

### 2026年1月12日: キャッシュバグ修正
- **問題**: `entry_score`と`core_score`が誤ってキャッシュされ、最適化が正しく動作していなかった
- **修正**: 
  1. キャッシュ構築/読み込み時に`entry_score`と`core_score`列を削除
  2. ポートフォリオ選定時に`entry_score`を常に再計算

### 2026年1月12日: 並列化の改善
- **問題**: 計算が異常に遅い
- **修正**:
  1. パフォーマンス計算部分を並列化
  2. ProcessPoolExecutorを優先使用
  3. 並列化設定の自動調整を改善

## 11. 確認が必要な項目（ChatGPTへの依頼）

1. **目的関数の計算方法**
   - 年率超過リターンの計算が正しいか
   - 各ポートフォリオの保有期間が異なる場合の集計方法が適切か

2. **パラメータ探索範囲**
   - Study A/B/Cの範囲設定が適切か
   - 正規化後の実効的な探索範囲はどうなるか

3. **ポートフォリオ選定ロジック**
   - Core Score → Entry Scoreの2段階選定が正しいか
   - セクターキャップの実装が適切か

4. **並列化の実装**
   - ProcessPoolExecutorとThreadPoolExecutorの使い分けが適切か
   - データベース接続の管理が正しいか（各プロセスで接続を作成）

5. **未来参照リークの防止**
   - 固定ホライズン評価の実装が正しいか
   - as_of_dateの使用が適切か

6. **評価指標**
   - 下振れ罰（λペナルティ）の実装が適切か
   - 勝率やその他の参考指標の計算が正しいか