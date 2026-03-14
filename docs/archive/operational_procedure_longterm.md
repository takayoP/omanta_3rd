# 長期保有型：運用準備手順書

## 概要

長期保有型（Part A）の運用フローとして、半年/1年ごとに候補パラメータを更新する手順を文書化します。

## 更新頻度

- **推奨頻度**: 6ヶ月 or 1年ごと
- **初回更新**: 運用開始から6ヶ月後
- **以降**: 前回更新から6ヶ月 or 1年後

## 更新手順

### ステップ1: パラメータの再最適化

以下の3つのパラメータセットを再最適化します：

1. **12M_momentum**（12ヶ月順張り候補）
2. **12M_reversal**（12ヶ月逆張り候補）
3. **operational_24M**（24ヶ月安定型）

#### 最適化コマンド例

```bash
# 12M_momentumの最適化
python -m omanta_3rd.jobs.optimize_longterm \
    --horizon-months 12 \
    --mode momentum \
    --output params_12M_momentum.json

# 12M_reversalの最適化
python -m omanta_3rd.jobs.optimize_longterm \
    --horizon-months 12 \
    --mode reversal \
    --output params_12M_reversal.json

# operational_24Mの最適化
python -m omanta_3rd.jobs.optimize_longterm \
    --horizon-months 24 \
    --mode momentum \
    --output params_operational_24M.json
```

### ステップ2: 横持ち評価

最適化したパラメータを別年へ適用して、安定性を評価します。

#### 評価コマンド例

```bash
# 横持ち評価を実行
python -m omanta_3rd.jobs.evaluate_monthly_params_on_longterm \
    --params-file params_12M_momentum.json \
    --eval-year 2025

python -m omanta_3rd.jobs.evaluate_monthly_params_on_longterm \
    --params-file params_12M_reversal.json \
    --eval-year 2025

python -m omanta_3rd.jobs.evaluate_monthly_params_on_longterm \
    --params-file params_operational_24M.json \
    --eval-year 2025
```

#### 評価基準

- **安定型**: 複数年にわたって安定したパフォーマンス
- **特化型**: 特定の年で高いパフォーマンスを示すが、他の年では低い

### ステップ3: 運用候補の選定

横持ち評価の結果に基づいて、運用候補を選定します。

- **operational_24M**: 安定型を優先
- **12M_momentum**: 順張りが効く年で高いパフォーマンスを示すもの
- **12M_reversal**: 逆張りが効く年で高いパフォーマンスを示すもの

### ステップ4: パラメータ台帳の更新

選定したパラメータを`config/params_registry_longterm.json`に登録します。

#### 更新例

```json
{
  "operational_24M": {
    "horizon_months": 24,
    "role": "operational",
    "mode": "momentum",
    "source": "fold1_2022",
    "params_file_path": "params_operational_24M.json",
    "notes": "24M安定型。2022/2023で横持ちプラス。",
    "version": "v2.0",
    "updated_date": "2025-06-01"
  },
  "12M_momentum": {
    "horizon_months": 12,
    "role": "research",
    "mode": "momentum",
    "source": "fold1_2022",
    "params_file_path": "params_12M_momentum.json",
    "notes": "12M順張り候補。レジーム切替前提。",
    "version": "v2.0",
    "updated_date": "2025-06-01"
  },
  "12M_reversal": {
    "horizon_months": 12,
    "role": "research",
    "mode": "reversal",
    "source": "fold2_2023",
    "params_file_path": "params_12M_reversal.json",
    "notes": "12M逆張り候補。レジーム切替前提。",
    "version": "v2.0",
    "updated_date": "2025-06-01"
  }
}
```

#### バージョン管理

- **version**: パラメータのバージョン番号（例: "v1.0", "v2.0"）
- **updated_date**: 更新日（YYYY-MM-DD形式）

### ステップ5: レジームポリシーの確認

`config/regime_policy_longterm.json`が正しく設定されているか確認します。

```json
{
  "up": "12M_momentum",
  "down": "12M_reversal",
  "range": "operational_24M"
}
```

### ステップ6: 整合性チェック

更新後のパラメータで整合性チェックを実行します。

```bash
# 整合性チェック
python -m omanta_3rd.jobs.check_regime_consistency \
    --start 2020-01-01 \
    --end 2025-12-31 \
    --output outputs/consistency_check.json
```

### ステップ7: バックテスト実行

更新後のパラメータでバックテストを実行し、パフォーマンスを確認します。

```bash
# レジーム切替モードでバックテスト
python -m omanta_3rd.jobs.batch_longterm_run_with_regime \
    --start 2020-01-01 \
    --end 2025-12-31

# 切替あり vs なしの比較
python -m omanta_3rd.jobs.compare_regime_switching \
    --start 2020-01-01 \
    --end 2025-12-31 \
    --output outputs/regime_comparison.json
```

## 運用中の注意事項

### 運用中は最適化しない

- 運用中はパラメータを最適化しない
- レジーム切替のみを使用
- パラメータ更新は半年/1年ごとの定期更新時のみ

### ログの確認

- 整合性チェックの結果を確認
- レジーム分布を確認
- パフォーマンス指標を確認

## トラブルシューティング

### パラメータファイルが見つからない

- `config/params_registry_longterm.json`の`params_file_path`を確認
- パラメータファイルが正しい場所にあるか確認

### レジーム判定が正しく動作しない

- `config/regime_policy_longterm.json`を確認
- 整合性チェックを実行してエラーを確認

### パフォーマンスが期待通りでない

- 横持ち評価の結果を確認
- レジーム分布を確認
- 切替あり vs なしの比較結果を確認

## 関連ファイル

- `config/params_registry_longterm.json`: パラメータ台帳
- `config/regime_policy_longterm.json`: レジームポリシー
- `params_operational_24M.json`: 24M安定型パラメータ
- `params_12M_momentum.json`: 12M順張りパラメータ
- `params_12M_reversal.json`: 12M逆張りパラメータ

