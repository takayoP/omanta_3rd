# ChatGPTフィードバック分析と対応方針

## 日付
2026-02-03

## ChatGPTからの主要な指摘

### 1. 確定事項

- ✅ **Gate 0がPASS**: 実装の非決定性は潰せた
- ❌ **期間ロバスト性不足**: 候補パラメータが「2022に寄りすぎ」で、2021では機能しない
- ⚠️ **本番反映は危険**: 2021期間でマイナスになるため、本番運用ではリスクが高い

### 2. 原因候補の優先順位

1. **過適合（=単一年に寄った最適化）** ← 最有力
2. **市場環境（レジーム）依存** ← 次点（Aとほぼセット）
3. **データ問題** ← 低め（ただし最短で潰す価値は高い）

### 3. 重要な指摘

- **コストが本当に効いているか**: 0bpsと25bpsが同じは不自然
- **2021で負ける理由を突き止める**: Core/Entryの犯人特定が必要
- **目的関数をmulti-year対応に**: worst-yearを重視した目的関数が必要

---

## 対応方針

### 最優先（即座に実施）

1. **コスト検証スクリプト**: コストが本当に効いているか確認
2. **2021詳細分析スクリプト**: Core/Entryの犯人特定
3. **2020期間での検証**: 2021だけ特異点なのか判定

### 次に実施

4. **Multi-year目的関数の実装**: worst-yearを重視した目的関数
5. **Multi-start候補収集**: 5〜10 seedで実行し、worst-yearで判定

### 長期的

6. **探索範囲の調整**: multi-year目的関数実装後に実施

---

## 実装予定

### 1. コスト検証スクリプト
- `scripts/verify_cost_application.py`
- turnover、cost_deduction、gross_return/net_returnの差分を確認

### 2. 2021詳細分析スクリプト
- `scripts/analyze_period_performance.py`
- ポートフォリオ特性比較（2021 vs 2022）
- アブレーション（Core/Entryの犯人特定）

### 3. Multi-year目的関数
- `src/omanta_3rd/jobs/optimize_longterm.py`に追加
- Maximin型、平均＋下振れ罰、中央値重視の3タイプ

---

## 参考

- ChatGPTフィードバック: 2026-02-03
- Gate検証結果: `docs/gate_validation_results_report.md`
