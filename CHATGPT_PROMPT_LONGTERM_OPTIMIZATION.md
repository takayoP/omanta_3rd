    # ChatGPT検証プロンプト - 長期保有型最適化システム

以下のプロンプトをChatGPTに送信してください。

---

## プロンプト文

```
あなたは金融アルゴリズムの専門家として、長期保有型のパラメータ最適化システムの実装を検証してください。

## 背景

日本株投資アルゴリズムの最適化システムを実装しました。前回の最適化では学習データとテストデータの分割を行わなかったため、過学習のリスクがありました。本実装では、リバランス日基準でランダムに学習/テストデータを分割することで、過学習を抑制する設計にしています。

## 実装の概要

1. **長期保有型の最適化システム** (`src/omanta_3rd/jobs/optimize_longterm.py`)
   - リバランス日をランダムに学習/テストに分割（デフォルト: 80/20）
   - 学習データで最適化、テストデータで評価
   - 評価指標: 年率リターン、累積リターン、平均超過リターン、勝率

2. **月次リバランス型パラメータの再評価機能** (`evaluate_monthly_params_on_longterm.py`)
   - 月次リバランス型で最適化したパラメータを長期保有型で評価

## 検証依頼事項

以下の点について、詳細に検証してください：

### 1. データ分割の妥当性

- `split_rebalance_dates`関数の実装が適切か
- ランダム分割が適切に機能しているか（再現性があるか）
- 学習/テストデータの比率が正しいか
- 分割後がソートされているか

**コード:**
```python
def split_rebalance_dates(
    rebalance_dates: List[str],
    train_ratio: float = 0.8,
    random_seed: Optional[int] = None,
) -> Tuple[List[str], List[str]]:
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

### 2. 過学習抑制の効果

- 学習データでの最適化結果とテストデータでの評価結果の差が妥当か
- テストデータでの評価結果が妥当な範囲内か（例: 年率リターンが-20%〜+30%程度）
- 過学習の兆候がないか（学習データで異常に高い、テストデータで低い）

### 3. 評価指標の計算の正確性

- 年率リターンの計算が正しいか
  ```python
  if years > 0:
      annual_return = (1 + cumulative_return / 100) ** (1 / years) - 1
      annual_return_pct = annual_return * 100
  ```
- 累積リターンの計算が正しいか（全ポートフォリオの平均リターン）
- 平均超過リターンの計算が正しいか
- 勝率の計算が正しいか（超過リターンが正のポートフォリオの割合）

### 4. パフォーマンス計算の正確性

- 各ポートフォリオのパフォーマンス計算が正しいか
- リバランス日から最新日までのリターン計算が正しいか
- 分割・併合の処理が正しいか（`calculate_portfolio_performance`を使用）
- TOPIXとの比較が正しいか

**実装の流れ:**
```python
# 1. ポートフォリオを選定
portfolios = {}
for rebalance_date in rebalance_dates:
    portfolio = _run_single_backtest_portfolio_only(...)
    portfolios[rebalance_date] = portfolio

# 2. 各ポートフォリオのパフォーマンスを計算
performances = []
for rebalance_date in sorted(portfolios.keys()):
    save_portfolio(conn, portfolio_df)  # 一時的にDBに保存
    perf = calculate_portfolio_performance(rebalance_date, latest_date)
    performances.append(perf)
    conn.execute("DELETE FROM portfolio_monthly WHERE rebalance_date = ?", ...)  # クリーンアップ

# 3. 集計指標を計算
total_returns = [p.get("total_return_pct", 0.0) for p in performances]
excess_returns = [p.get("excess_return_pct", 0.0) for p in performances]
years = (end_dt - start_dt).days / 365.25
annual_return = (1 + cumulative_return / 100) ** (1 / years) - 1
```

### 5. コードの品質

- エラーハンドリングが適切か
- コメントが適切か
- 型ヒントが適切か
- 関数の責務が明確か

### 6. 潜在的な問題点

- 改善が必要な点
- バグの可能性がある点
- パフォーマンスの問題がある点

### 7. 設計の妥当性

- 長期保有型に適した設計になっているか
- 月次リバランス型との違いが適切か
- 評価指標の選択が適切か

## 検証方法

以下の観点から検証してください：

1. **論理的な検証**: コードのロジックが正しいか
2. **数値計算の検証**: 計算式が正しいか
3. **設計パターンの検証**: 適切な設計パターンが使われているか
4. **エッジケースの検証**: エッジケース（空のリスト、0除算など）が適切に処理されているか

## 期待される出力

以下の形式で検証結果を出力してください：

1. **各検証項目の結果**
   - 問題がない場合: ✅ 問題なし
   - 問題がある場合: ⚠️ 問題点の説明と改善案

2. **総合評価**
   - 実装の品質評価
   - 推奨される改善点
   - 追加で検証すべき点

3. **具体的な改善案**
   - コードの修正案
   - 設計の改善案

## 参考資料

詳細な実装資料は `CHATGPT_VERIFICATION_LONGTERM_OPTIMIZATION.md` を参照してください。

実装ファイル:
- `src/omanta_3rd/jobs/optimize_longterm.py`
- `evaluate_monthly_params_on_longterm.py`
- `LONGTERM_OPTIMIZATION_GUIDE.md` (使用方法)

以上、よろしくお願いします。
```

---

## 使用方法

1. 上記のプロンプト文をChatGPTに送信
2. 必要に応じて、実装ファイルのコードを添付
3. 検証結果を確認し、改善点があれば実装に反映

## 補足情報

検証時に以下の情報も提供すると良いでしょう：

- 実装の背景（前回の最適化の問題点）
- 期待される動作例
- テストケース（可能であれば）

