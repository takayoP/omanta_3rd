# ChatGPTフィードバックに基づく改善実装（v2）

## 実装日
2026年1月21日

## 実装した改善（v2）

### 1. ✅ baseのサンプル範囲を制限（空レンジ対策）

**問題点**:
- baseが端に寄ると、maxの探索レンジが空になる
- 例: baseが85付近でmomentumを選ぶと`[base+10, 85]`が空になる

**修正内容**:
```python
# 修正前
rsi_base = trial.suggest_float("rsi_base", RSI_LOW, RSI_HIGH)  # 15.0-85.0

# 修正後
rsi_base = trial.suggest_float("rsi_base", RSI_LOW + rsi_min_width, RSI_HIGH - rsi_min_width)  # 25.0-75.0
bb_z_base = trial.suggest_float("bb_z_base", BB_LOW + bb_z_min_width, BB_HIGH - bb_z_min_width)  # -3.0-3.0
```

**効果**:
- ✅ 両方向（momentum/reversal）が常に可能になる
- ✅ 空レンジエラーが発生しない
- ✅ 探索空間が安定

### 2. ✅ directionを必ず保存・ログ出力

**問題点**:
- directionが結果JSONに含まれていない
- ログに出力されていない

**修正内容**:
```python
# directionをtrialに保存（英語と日本語の両方）
trial.set_user_attr("rsi_direction", rsi_direction)  # "momentum" or "reversal"
trial.set_user_attr("rsi_direction_jp", rsi_direction_str)  # "順張り" or "逆張り"
trial.set_user_attr("bb_direction", bb_direction)
trial.set_user_attr("bb_direction_jp", bb_direction_str)

# ログ出力
print(f"    [objective_longterm] RSI方向: {rsi_direction} ({rsi_direction_str}), BB方向: {bb_direction} ({bb_direction_str})")

# 結果JSONに追加
"normalized_params": {
    ...
    "rsi_direction": best_params.get("rsi_direction", "unknown"),
    "bb_direction": best_params.get("bb_direction", "unknown"),
    ...
}
```

**効果**:
- ✅ 後で「何が効いたか」を説明できる
- ✅ 結果JSONからdirectionを確認できる
- ✅ ログでdirectionを確認できる

### 3. ✅ 目的関数で空評価の場合は強ペナルティ

**問題点**:
- `annual_excess_returns`が空のとき0.0を返すと、「評価不能なのにそこそこ良い点」として扱われる
- 探索が壊れる

**修正内容**:
```python
# 空評価（評価不能）のチェック
if not annual_excess_returns_list or len(annual_excess_returns_list) == 0 or n_periods == 0:
    # 評価不能な場合は強ペナルティを返す
    objective_value = -1e9  # 十分小さい値
    print(f"      [objective_longterm] ⚠️  警告: 評価不能のため、強ペナルティを返します")
    trial.set_user_attr("evaluation_failed", True)
    trial.set_user_attr("evaluation_failed_reason", "empty_annual_excess_returns")
    return objective_value
```

**効果**:
- ✅ 評価不能なtrialが良い点として扱われない
- ✅ 探索が壊れない
- ✅ 評価不能の理由が記録される

### 4. ✅ 方向が1つしかない場合の処理

**修正内容**:
```python
# 方向が1つしかない場合もdirectionを設定
elif can_long:
    rsi_direction = "momentum"  # 自動的にmomentumに設定
    rsi_max = trial.suggest_float("rsi_max", max_low, RSI_HIGH)
elif can_short:
    rsi_direction = "reversal"  # 自動的にreversalに設定
    rsi_max = trial.suggest_float("rsi_max", RSI_LOW, max_high)
```

**効果**:
- ✅ directionが常に設定される（ログ出力とJSON保存が可能）
- ✅ 方向が1つしかない場合でも一貫した処理

## 未実装の改善（今後の検討事項）

### 3. Core重みのDirichlet化

**ChatGPTの推奨**:
- 方針A（最短・安全）: 現状の「個別サンプル→正規化」を維持
- 方針B（Dirichletをやるなら）: "Dirichlet版Study"を別枠（Study D等）として導入

**決定**: 方針Aを採用（現状維持）
- 既存Study A/B/Cの範囲設計と整合性を保つ
- 「正規化後に0.01未満になり得る」は仕様として受け入れる

### 4. 複数年テスト（時系列CV）

**ChatGPTの推奨**:
- walk-forward（ローリング）で実装
- 例: Fold1: train=2018–2019 → test=2020, Fold2: train=2018–2020 → test=2021, ...

**決定**: 後段で実装
- まずは「最適化は従来どおり（train→2022test）で回す」
- best_paramsの健全性チェックとして複数年テストを後段で実行

### 5. 二重並列の調整

**ChatGPTの推奨**:
- デバッグ/検証モード: `optuna_n_jobs=1`、trial内（バックテスト）だけ並列
- 本気探索モード: Optuna並列を上げるなら、trial内並列は抑える

**決定**: 現状維持（必要に応じて手動で調整）
- 既にSQLiteは並列に弱いのでOptuna並列数を制限している
- 必要に応じて手動で`--n-jobs`と`--bt-workers`を調整可能

## 確認チェックリスト

### 必須チェック

- [x] baseのサンプル範囲を制限（空レンジ対策）
- [x] directionを結果JSONとログに保存
- [x] 目的関数で空評価の場合は強ペナルティ
- [ ] 同一seed・単一並列で再現性確認（`optuna_n_jobs=1` & `bt_workers=1`で2回実行）
- [ ] directionが"trial番号依存ではなくパラメータ化"されていること（結果JSONで確認）
- [ ] 空評価が強ペナルティになっていること（ログで確認）
- [ ] 固定ホライズンの厳密確認（チェックA/Bで確認）

### 推奨チェック

- [ ] median目的で結果が改善するか
- [ ] 手数料・コスト感度の確認（`cost_bps=10-50`でテスト）
- [ ] 別splitでの再現（`train_end_date`をずらして別のテスト期間で確認）
- [ ] 安定性（seed）確認（seedを変えても近いbestが出るか）

## 使用方法

### 基本的な使用方法（median目的推奨）

```powershell
python -m omanta_3rd.jobs.optimize_longterm `
  --start 2018-01-31 `
  --end 2024-12-31 `
  --study-type A `
  --n-trials 200 `
  --objective-type median `
  --train-end-date 2023-12-31 `
  --as-of-date 2024-12-31 `
  --horizon-months 24 `
  --lambda-penalty 0.00 `
  --n-jobs 4 `
  --bt-workers 8
```

### 再現性確認用（単一並列）

```powershell
--n-jobs 1 `
--bt-workers 1
```

## 期待される効果

1. **再現性の向上**: baseの範囲制限により、空レンジエラーが発生しない
2. **方向の可視化**: directionが結果JSONとログに保存され、後で説明できる
3. **探索の安定性**: 空評価が強ペナルティになり、探索が壊れない
4. **過学習の低減**: median/trimmed_mean目的により、外れ値に強い

## 次のステップ

1. 修正後のコードで最適化を再実行
2. 同一seedで2回実行して再現性を確認
3. チェックA/Bで固定ホライズン評価を確認
4. median目的とmean目的の結果を比較
5. 必要に応じて、残りの改善（複数年テスト、Dirichlet化）を実装

