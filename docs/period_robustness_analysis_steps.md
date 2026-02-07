# 期間ロバスト性分析のステップ

## 概要

2021期間でパフォーマンスが悪化している問題を分析するためのステップです。

## ステップ1: ポートフォリオ特性の比較

2021と2022の期間で、ポートフォリオ特性（選定銘柄数、業種比率、時価総額など）を比較します。

### 実行方法

```powershell
python scripts/analyze_portfolio_characteristics.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260201_132836.json `
  --test-periods "2022,2021"
```

### 出力内容

- 平均選定銘柄数
- 平均Coreスコア
- 平均Entryスコア
- 平均時価総額
- 業種分布（上位5業種）
- PER/PBR/ROEの統計

## ステップ2: アブレーション（Core/Entryの犯人特定）

Coreスコアのみ、Entryスコアのみ、両方を使用した場合のパフォーマンスを比較します。

### 実行方法

```powershell
python scripts/analyze_ablation.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260201_132836.json `
  --test-periods "2022,2021"
```

### 出力内容

- Coreスコアのみ使用した場合のパフォーマンス
- Entryスコアのみ使用した場合のパフォーマンス
- 両方を使用した場合のパフォーマンス（ベースライン）
- 各期間での比較

## ステップ3: 2020期間での検証

2021だけが特異点なのか、それとも2020も同様に悪いのかを判定します。

### 実行方法

```powershell
python scripts/analyze_period_performance.py `
  --params-json optimization_result_optimization_longterm_studyA_local_20260201_132836.json `
  --test-periods "2022,2021,2020" `
  --cost-bps 25.0
```

### 出力内容

- 2020期間でのパフォーマンス
- 2021期間でのパフォーマンス
- 2022期間でのパフォーマンス
- 期間間の比較

## 次のアクション

これらの分析結果に基づいて、以下を検討してください：

1. **ポートフォリオ特性の違いが原因の場合**
   - 業種分布の偏り
   - 時価総額の違い
   - Core/Entryスコアの分布の違い

2. **Core/Entryの犯人特定ができた場合**
   - Coreスコアが原因: Coreスコアの重みや計算ロジックを見直し
   - Entryスコアが原因: Entryスコアの重みや計算ロジックを見直し

3. **2020も同様に悪い場合**
   - 2020-2021期間は市場環境が悪かった可能性
   - 戦略自体が特定の市場環境に適していない可能性

4. **2021だけが特異点の場合**
   - 2021年の市場環境やデータ品質の問題
   - 2021年特有のイベント（例: コロナショック後の反動）
