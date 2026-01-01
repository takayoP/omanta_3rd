# 最適化実行ガイド

ChatGPTの提案に基づいた最適化実行の手順と判断基準をまとめます。

## 実行前の確認（必須）

### Go/No-Goチェック

```bash
python check_optimization_readiness.py
```

**必須条件:**
1. ✅ ユニバース診断: 2020-2021が「東証一部」で取得できている
2. ✅ 決定性チェック: 同一条件で2回実行して結果が一致する
3. ✅ Holdout設計: Test期間を複数回使わない設計になっている

## 実行手順（3段階）

### 1. スモーク（各Study 5-10 trial）

```bash
python run_optimization_train_period.py --n-trials 10 --study both
```

**確認事項:**
- エラー/NaN/データ欠損/極端な売買回転になっていないか

### 2. パイロット（各Study 50 trial）

```bash
python run_optimization_train_period.py --n-trials 50 --study both
```

**重要**: 50 trial時点で「本当に勝てる地形があるか」を判定する

#### パイロット結果の評価（必須）

```bash
# 各Studyを個別に評価
python evaluate_pilot_results.py --study-name optimization_timeseries_studyA_YYYYMMDD_HHMMSS
python evaluate_pilot_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS

# Study A/Bを比較
python evaluate_pilot_results.py --study-a optimization_timeseries_studyA_YYYYMMDD_HHMMSS --study-b optimization_timeseries_studyB_YYYYMMDD_HHMMSS
```

#### 判断基準（3つ全てを満たすことが推奨）

1. ✅ **median > -0.05**
   - これ未満だと探索空間がまだ広い/ズレてる疑い

2. ✅ **p95 > 0**
   - 上位がちゃんとプラスに浮くか

3. ✅ **best > 0.15**
   - "伸びしろ"が見える最低ライン

#### 判定結果に応じた対応

| 判定 | 基準通過数 | 対応 |
|------|----------|------|
| **GO** | 3/3 | 200 trialに進む |
| **CAUTION** | 2/3 | 慎重に判断して200 trialに進む |
| **WARNING** | 1/3 | 200 trialに進む前に範囲/目的関数/設計を見直す |
| **NO_GO** | 0/3 | 200 trialに進む前に範囲/目的関数/設計を見直す必要がある |

#### Study A/B比較

- **片方だけ強い場合**: 本番200は片側に集中が合理的（計算時間が重いため）
- **両方そこそこ良い場合**: 両方のStudyを200 trialに進める

### 3. 本番（各Study 200 trial）

```bash
# Study Bに集中（推奨）
python run_optimization_train_period.py --n-trials 200 --study B

# または両方進める場合
python run_optimization_train_period.py --n-trials 200 --study both
```

### 4. 200 trial結果の評価（必須）

```bash
# 成功条件のチェック
python evaluate_200trial_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS

# 候補群の選定（上位＋分散）
python evaluate_200trial_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS --select-candidates --output candidates_studyB.json

# 候補群の可視化（オプション）
python evaluate_200trial_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS --select-candidates --output candidates_studyB.json --visualize --viz-output candidates_studyB_viz.png
```

#### 成功条件（Study B）

1. ✅ **median > 0.10**（理想は0.15以上）
2. ✅ **p95 > 0.25**
3. ✅ **上位10の最小値 > 0.15**
4. ✅ **上位10のbb_weightやroe_minが極端に端に張り付かない**（＝安定）

#### 危険シグナル

- ⚠️ bestだけが異常に高く、p95や上位10が付いてこない
- ⚠️ bestが境界張り付きだらけ（=範囲依存が強い）

#### 候補群の選定方針（重要）

- スコア順だけでなく、「**上位＋分散**」で選定
- bb_weight / roe_min / w_value / w_forward_per の4軸で多様性を確保
- 上位20から10個選ぶなど、分散を考慮した選定
- これによりHoldoutで生き残る確率が上がる

#### 改善された機能

1. **パラメータ範囲チェックの改善**
   - 探索範囲に対する相対的な判定を実装
   - Study A/Bの探索範囲を自動検出して、より正確な判定
   - 相対範囲が20%未満、または探索範囲の端（5%以内）に張り付いている場合に警告

2. **候補群の可視化機能**
   - `--visualize`オプションで候補群のパラメータ分布を可視化
   - ヒストグラムとペアプロットを生成
   - 分散の確認が容易に

3. **エラーハンドリングの改善**
   - ストレージパスの自動推定が失敗した場合、利用可能なDBファイルを検索
   - より詳細なエラーメッセージとヒントを提供

## Holdout検証とWFA

### 実務ステップ（最短ルート）

1. **上位10〜20を"候補群"として保存**（200 trial結果の評価で実施）

2. **Holdout（2023-2024）固定評価**
   - 最初は上位10を丸ごと評価（1つに絞らない）
   - 評価指標:
     - Sharpe_excess > 0.10（最低ライン）
     - 年別（2023/2024）で崩れない

3. **WFA（可能なら）**
   - ここまで来たら「過学習かどうか」がかなり判別できる

### Holdout設計（将来の改善案）

現在の設計:
- Train：2020-2022（最適化）
- Test：2023-2024（固定評価）

将来的には以下の分割を推奨（データがある場合）:
- Train：2020-2022（最適化）
- Validation：2023（方向転換や設計修正に使ってよい）
- Final Test：2024（最後の一発勝負）
- 2025：運用シミュレーション（疑似ライブ）

## 重要な注意事項

### 決定性チェックの結果について

決定性チェックでSharpe=-0.598という結果が出ています：
- ✅ 決定性はOK（同一条件で2回一致）
- ⚠️ そのパラメータでは負けている（普通に負けている）

**意味:**
- 探索が必要なのは確か（最適化の価値はある）
- ただし、もしこの"決定性チェック"が「代表的なパラメータ（例えば前回best）」での評価なら、Train（2020-2022）は相性が悪い可能性がある
- → 2020-2022で勝てない戦略を2023-2024で勝たせるのは難しい

**対応:**
- 50 trial時点で「本当に勝てる地形があるか」を必ず判定する
- 判断基準を満たさない場合は、200 trialに進む前に範囲/目的関数/設計を見直す

### 200 trialの評価ポイント

- bestだけでなく、**median/p95/上位10の安定性**で評価する
- 候補群は「上位＋分散」で選定し、多様性を確保する
- 200後は Holdout→WFA の順で"本物か"を判定する
