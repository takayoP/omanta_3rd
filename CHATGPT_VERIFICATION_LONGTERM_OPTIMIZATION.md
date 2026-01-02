# 長期保有型最適化システム - ChatGPT検証用資料

## 1. 実装の概要

### 1.1 目的

長期保有型のパラメータ最適化システムを実装しました。前回の最適化では学習データとテストデータの分割を行わなかったため、過学習のリスクがありました。本実装では、リバランス日基準でランダムに学習/テストデータを分割することで、過学習を抑制します。

### 1.2 主な機能

1. **学習/テスト分割**: リバランス日をランダムに分割（デフォルト: 80/20）
2. **過学習抑制**: 学習データで最適化、テストデータで評価
3. **評価指標**: 年率リターン、累積リターン、平均超過リターン、勝率
4. **月次リバランス型パラメータの再評価**: 既存の最適化結果を長期保有型で評価可能

### 1.3 実装ファイル

- `src/omanta_3rd/jobs/optimize_longterm.py`: 長期保有型の最適化システム
- `evaluate_monthly_params_on_longterm.py`: 月次リバランス型パラメータの評価
- `LONGTERM_OPTIMIZATION_GUIDE.md`: 使用方法のドキュメント

## 2. 設計思想

### 2.1 データ分割の方法

**問題点（前回の実装）:**
- 全期間のデータで最適化を行っていたため、過学習のリスクがあった
- 学習データとテストデータの分割がなかった

**解決策（本実装）:**
- リバランス日をランダムに学習/テストに分割
- 学習データで最適化、テストデータで評価
- 同じ`random_seed`を使用すると再現可能

**実装（改善後）:**
```python
def split_rebalance_dates(
    rebalance_dates: List[str],
    train_ratio: float = 0.8,
    random_seed: Optional[int] = 42,  # デフォルト42で再現可能
) -> Tuple[List[str], List[str]]:
    """
    リバランス日をランダムに学習/テストに分割
    
    例: 36ヶ月のリバランス日がある場合
    - 学習データ: 29日（80.6%）
    - テストデータ: 7日（19.4%）
    
    改善点:
    - グローバル乱数状態を汚さない（random.Random使用）
    - round()で80/20に近づける
    - バリデーション追加（train_ratio、最小データ数、重複チェック）
    - train/test両方が最低1つになるようにクリップ
    """
    # バリデーション
    if not 0.0 < train_ratio < 1.0:
        raise ValueError(f"train_ratio must be in (0, 1), got {train_ratio}")
    if len(rebalance_dates) < 2:
        raise ValueError(f"rebalance_dates must have at least 2 dates")
    
    # 重複を除去
    unique_dates = list(dict.fromkeys(rebalance_dates))
    
    # 副作用のないローカルRNGを使用
    if random_seed is not None:
        rng = random.Random(random_seed)
    else:
        rng = random.Random()  # OS乱数（非再現）
    rng.shuffle(shuffled)
    
    # round()で80/20に近づける、かつ両側が空にならないようにクリップ
    n_train = int(round(len(shuffled) * train_ratio))
    n_train = max(1, min(len(shuffled) - 1, n_train))
    
    train_dates = sorted(shuffled[:n_train])
    test_dates = sorted(shuffled[n_train:])
    
    return train_dates, test_dates
```

### 2.2 評価指標の選択

**月次リバランス型との違い:**

| 項目 | 月次リバランス型 | 長期保有型 |
|------|----------------|-----------|
| 評価指標 | Sharpe ratio（年率化）、月次勝率 | 年率リターン、累積リターン、勝率 |
| データ分割 | なし（全期間で最適化） | あり（学習/テスト分割） |
| 目的関数 | Sharpe ratio | 年率リターン |

**長期保有型の評価指標:**

1. **年率リターン**: 期間を年換算したリターン
   ```python
   if years > 0:
       annual_return = (1 + cumulative_return / 100) ** (1 / years) - 1
       annual_return_pct = annual_return * 100
   ```

2. **累積リターン**: 全ポートフォリオの平均リターン
   ```python
   cumulative_return = np.mean(total_returns)
   ```

3. **平均超過リターン**: TOPIXに対する平均超過リターン
   ```python
   mean_excess_return = np.mean(excess_returns)
   ```

4. **勝率**: 超過リターンが正のポートフォリオの割合
   ```python
   win_rate = sum(1 for r in excess_returns if r > 0) / len(excess_returns)
   ```

### 2.3 パフォーマンス計算の実装

**実装の流れ:**

1. 各リバランス日でポートフォリオを選定
2. 各ポートフォリオのパフォーマンスを計算（リバランス日から最新日まで）
3. 全ポートフォリオの平均を計算
4. 年率リターンを計算

**コード:**
```python
def calculate_longterm_performance(
    rebalance_dates: List[str],
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    cost_bps: float = 0.0,
    n_jobs: int = -1,
    features_dict: Optional[Dict[str, pd.DataFrame]] = None,
    prices_dict: Optional[Dict[str, Dict[str, List[float]]]] = None,
) -> Dict[str, Any]:
    """
    長期保有型のパフォーマンスを計算
    
    各リバランス日でポートフォリオを選定し、
    リバランス日から最新日までのリターンを計算
    """
    # 1. ポートフォリオを選定（並列実行）
    portfolios = {}
    for rebalance_date in rebalance_dates:
        portfolio = _run_single_backtest_portfolio_only(...)
        portfolios[rebalance_date] = portfolio
    
    # 2. 各ポートフォリオのパフォーマンスを計算
    performances = []
    for rebalance_date in sorted(portfolios.keys()):
        # 一時的にDBに保存（calculate_portfolio_performanceがDBから読み込むため）
        save_portfolio(conn, portfolio_df)
        perf = calculate_portfolio_performance(rebalance_date, latest_date)
        performances.append(perf)
        # クリーンアップ（最適化中は一時的なポートフォリオなので削除）
        conn.execute("DELETE FROM portfolio_monthly WHERE rebalance_date = ?", ...)
    
    # 3. 集計指標を計算
    total_returns = [p.get("total_return_pct", 0.0) for p in performances]
    excess_returns = [p.get("excess_return_pct", 0.0) for p in performances]
    
    # 年率リターンを計算
    years = (end_dt - start_dt).days / 365.25
    annual_return = (1 + cumulative_return / 100) ** (1 / years) - 1
    
    return {
        "annual_return_pct": annual_return_pct,
        "cumulative_return_pct": cumulative_return,
        "mean_excess_return_pct": mean_excess_return,
        "win_rate": win_rate,
        ...
    }
```

## 3. 検証ポイント

### 3.1 データ分割の妥当性

**検証項目:**
1. ランダム分割が適切に機能しているか
2. 学習/テストデータの比率が正しいか（round()で80/20に近づける）
3. 同じ`random_seed`で再現可能か
4. 時系列の順序が保持されているか（分割後はソート）
5. グローバル乱数状態を汚さないか（random.Random使用）
6. バリデーションが適切か（train_ratio、最小データ数、重複チェック）
7. train/test両方が最低1つになるか

**期待される動作:**
- `train_ratio=0.8`の場合、約80%が学習データ、約20%がテストデータ（round()使用）
- 36ヶ月の場合: 学習29日（80.6%）、テスト7日（19.4%）
- 同じ`random_seed`を使用すると同じ分割になる
- 分割後は日付順にソートされる
- グローバル乱数状態を汚さない（副作用なし）

### 3.2 過学習抑制の効果

**検証項目:**
1. 学習データでの最適化結果とテストデータでの評価結果の差
2. テストデータでの評価結果が妥当な範囲内か
3. 過学習の兆候がないか（学習データで異常に高い、テストデータで低い）

**期待される動作:**
- 学習データでの最適化結果とテストデータでの評価結果に大きな差がない
- テストデータでの評価結果が妥当な範囲内（例: 年率リターンが-20%〜+30%程度）

### 3.3 評価指標の計算の正確性

**検証項目:**
1. 年率リターンの計算が正しいか
2. 累積リターンの計算が正しいか
3. 平均超過リターンの計算が正しいか
4. 勝率の計算が正しいか

**期待される動作:**
- 年率リターン: `(1 + cumulative_return / 100) ** (1 / years) - 1`
- 累積リターン: 全ポートフォリオの平均リターン
- 平均超過リターン: TOPIXに対する平均超過リターン
- 勝率: 超過リターンが正のポートフォリオの割合

### 3.4 パフォーマンス計算の正確性

**検証項目:**
1. 各ポートフォリオのパフォーマンス計算が正しいか
2. リバランス日から最新日までのリターン計算が正しいか
3. 分割・併合の処理が正しいか
4. TOPIXとの比較が正しいか

**期待される動作:**
- 各ポートフォリオのリターンが正しく計算される
- 分割・併合が適切に処理される
- TOPIXとの比較が正しい

### 3.5 月次リバランス型パラメータの再評価

**検証項目:**
1. Optunaスタディからパラメータが正しく読み込まれるか
2. パラメータが正しくStrategyParamsとEntryScoreParamsに変換されるか
3. 長期保有型での評価が正しく実行されるか

**期待される動作:**
- Optunaスタディから最良パラメータが正しく読み込まれる
- パラメータが正しく変換される
- 長期保有型での評価が正しく実行される

## 4. テストケース

### 4.1 データ分割のテスト

```python
# テストケース1: 基本的な分割
rebalance_dates = ["2020-01-31", "2020-02-28", ..., "2022-12-30"]  # 36日
train_dates, test_dates = split_rebalance_dates(
    rebalance_dates,
    train_ratio=0.8,
    random_seed=42
)
# 期待: len(train_dates) == 29, len(test_dates) == 7

# テストケース2: 再現性
train_dates1, test_dates1 = split_rebalance_dates(..., random_seed=42)
train_dates2, test_dates2 = split_rebalance_dates(..., random_seed=42)
# 期待: train_dates1 == train_dates2, test_dates1 == test_dates2

# テストケース3: ソート
train_dates, test_dates = split_rebalance_dates(...)
# 期待: train_dates == sorted(train_dates), test_dates == sorted(test_dates)
```

### 4.2 パフォーマンス計算のテスト

```python
# テストケース1: 基本的な計算
rebalance_dates = ["2020-01-31", "2020-02-28"]
perf = calculate_longterm_performance(
    rebalance_dates,
    strategy_params,
    entry_params,
)
# 期待: perf["annual_return_pct"]が計算される
# 期待: perf["cumulative_return_pct"]が計算される
# 期待: perf["win_rate"]が0.0〜1.0の範囲内

# テストケース2: 空のポートフォリオ
# 期待: 適切なエラーメッセージが返される
```

### 4.3 最適化のテスト

```python
# テストケース1: 基本的な最適化
main(
    start_date="2020-01-01",
    end_date="2022-12-31",
    study_type="B",
    n_trials=10,  # スモークテスト
    train_ratio=0.8,
    random_seed=42,
)
# 期待: 最適化が正常に完了する
# 期待: テストデータでの評価結果が表示される

# テストケース2: 異なるrandom_seed
# 期待: 異なる分割が生成される
```

## 5. 潜在的な問題点と改善案

### 5.1 データ分割の方法

**潜在的な問題:**
- ランダム分割により、時系列の順序が失われる可能性がある
- 学習データとテストデータの期間が重複する可能性がある

**改善案:**
- 時系列順に分割する方法も検討（例: 最初の80%を学習、残り20%をテスト）
- ただし、ランダム分割の方が過学習抑制に効果的

### 5.2 評価指標の選択

**潜在的な問題:**
- 年率リターンのみを目的関数にしているため、リスクを考慮していない
- 最大ドローダウンなどのリスク指標を考慮していない

**改善案:**
- リスク調整済みリターン（例: Sharpe ratio）を追加
- 最大ドローダウンを制約条件に追加

### 5.3 パフォーマンス計算の効率

**潜在的な問題:**
- 各ポートフォリオを一時的にDBに保存・削除するため、効率が悪い可能性がある

**改善案:**
- ポートフォリオDataFrameから直接パフォーマンスを計算する関数を追加
- ただし、既存の`calculate_portfolio_performance`がDBから読み込むため、現状の実装は妥当

## 6. コードの主要部分

### 6.1 データ分割関数

```python
def split_rebalance_dates(
    rebalance_dates: List[str],
    train_ratio: float = 0.8,
    random_seed: Optional[int] = None,
) -> Tuple[List[str], List[str]]:
    """
    リバランス日をランダムに学習/テストに分割
    
    検証ポイント:
    - ランダムシードが正しく機能するか
    - 分割比率が正しいか
    - 分割後がソートされているか
    """
    if random_seed is not None:
        random.seed(random_seed)
        np.random.seed(random_seed)
    
    shuffled = rebalance_dates.copy()
    random.shuffle(shuffled)
    
    n_train = int(len(shuffled) * train_ratio)
    train_dates = sorted(shuffled[:n_train])
    test_dates = sorted(shuffled[n_train:])
    
    return train_dates, test_dates
```

### 6.2 パフォーマンス計算関数

```python
def calculate_longterm_performance(
    rebalance_dates: List[str],
    strategy_params: StrategyParams,
    entry_params: EntryScoreParams,
    ...
) -> Dict[str, Any]:
    """
    長期保有型のパフォーマンスを計算
    
    検証ポイント:
    - 各ポートフォリオのパフォーマンス計算が正しいか
    - 年率リターンの計算が正しいか
    - 累積リターンの計算が正しいか
    """
    # 1. ポートフォリオを選定
    portfolios = {}
    ...
    
    # 2. 各ポートフォリオのパフォーマンスを計算
    performances = []
    for rebalance_date in sorted(portfolios.keys()):
        save_portfolio(conn, portfolio_df)
        perf = calculate_portfolio_performance(rebalance_date, latest_date)
        performances.append(perf)
        conn.execute("DELETE FROM portfolio_monthly WHERE rebalance_date = ?", ...)
    
    # 3. 集計指標を計算
    total_returns = [p.get("total_return_pct", 0.0) for p in performances]
    excess_returns = [p.get("excess_return_pct", 0.0) for p in performances]
    
    years = (end_dt - start_dt).days / 365.25
    annual_return = (1 + cumulative_return / 100) ** (1 / years) - 1
    
    return {
        "annual_return_pct": annual_return_pct,
        "cumulative_return_pct": cumulative_return,
        ...
    }
```

### 6.3 目的関数

```python
def objective_longterm(
    trial: optuna.Trial,
    train_dates: List[str],
    study_type: Literal["A", "B"],
    ...
) -> float:
    """
    Optunaの目的関数（長期保有型）
    
    検証ポイント:
    - パラメータの範囲が適切か
    - 目的関数の値が正しく計算されるか
    """
    # パラメータをサンプリング
    w_quality = trial.suggest_float("w_quality", 0.15, 0.35)
    ...
    
    # パフォーマンスを計算
    perf = calculate_longterm_performance(
        train_dates,
        strategy_params,
        entry_params,
        ...
    )
    
    # 目的関数: 年率リターン
    return perf["annual_return_pct"]
```

## 7. 期待される動作例

### 7.1 最適化の実行例

```
長期保有型パラメータ最適化システム（Study B: Value寄り・ROE閾値やや高め）
================================================================================
期間: 2020-01-01 ～ 2022-12-31
試行回数: 200
取引コスト: 0.0 bps
学習/テスト分割: 80.0% / 20.0%
ランダムシード: 42
================================================================================

リバランス日数: 36
最初: 2020-01-31
最後: 2022-12-30

学習データ: 29日
  最初: 2020-02-28
  最後: 2022-11-30
テストデータ: 7日
  最初: 2020-05-29
  最後: 2022-12-30

最適化を開始します...
[Trial 0] objective=12.3456%, cumulative=15.2345%, excess=2.1234%, win_rate=0.6500
...
[Trial 199] objective=18.9012%, cumulative=22.3456%, excess=3.4567%, win_rate=0.7200

【最適化結果 - Study B】
最良試行: 156
最良値（年率リターン）: 18.9012%

テストデータで評価します...
テストデータ評価結果:
  年率リターン: 16.2345%
  累積リターン: 19.5678%
  平均超過リターン: 2.8901%
  勝率: 0.7143
  ポートフォリオ数: 7
```

### 7.2 月次リバランス型パラメータの評価例

```
月次リバランス型パラメータの長期保有型評価
================================================================================
スタディ: optimization_timeseries_studyB_20251231_174014
期間: 2020-01-01 ～ 2024-12-31
取引コスト: 0.0 bps
================================================================================

パラメータを読み込み中...
スタディ: optimization_timeseries_studyB_20251231_174014
最良値: 0.234567
最良試行: 156

パラメータ:
  w_quality: 0.151900
  w_value: 0.390800
  ...

全データで評価: 60日

長期保有型で評価中...
【評価結果】
年率リターン: 15.6789%
累積リターン: 78.9012%
平均超過リターン: 2.3456%
勝率: 0.6833
ポートフォリオ数: 60
期間: 4.95年
```

## 8. 検証依頼事項

以下の点について、ChatGPTに検証をお願いします：

1. **データ分割の妥当性**: ランダム分割が適切に機能しているか、再現性があるか
2. **過学習抑制の効果**: 学習データとテストデータでの評価結果の差が妥当か
3. **評価指標の計算の正確性**: 年率リターン、累積リターンなどの計算が正しいか
4. **パフォーマンス計算の正確性**: 各ポートフォリオのパフォーマンス計算が正しいか
5. **コードの品質**: エラーハンドリング、コメント、型ヒントなどが適切か
6. **潜在的な問題点**: 改善が必要な点、バグの可能性がある点
7. **設計の妥当性**: 長期保有型に適した設計になっているか

