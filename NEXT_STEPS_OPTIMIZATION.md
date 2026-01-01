# 次のステップ：最適化の改善計画

ChatGPTの分析に基づいて、次のステップを実施します。

## 1. 実施済み

✅ **Study A/B分割版の最適化スクリプト作成**
- `src/omanta_3rd/jobs/optimize_timeseries_clustered.py`: Study A/B分割対応の最適化スクリプト
- `run_optimization_train_period.py`: Train期間（2020-2022）での再最適化実行スクリプト

## 2. パラメータ範囲の調整

ChatGPTの提案に基づいて、パラメータ範囲を調整しました。

### Study A（BB寄り・低ROE閾値）
- `bb_weight`: 0.55〜0.90（拡大）
- `roe_min`: 0.00〜0.08（下限を0に拡大）
- `w_value`: 0.20〜0.35
- `w_forward_per`: 0.40〜0.80
- `w_record_high`: 0.035〜0.065（固定級）

### Study B（Value寄り・ROE閾値やや高め）
- `bb_weight`: 0.40〜0.65
- `roe_min`: 0.08〜0.15
- `w_value`: 0.33〜0.50
- `w_forward_per`: 0.30〜0.55
- `w_record_high`: 0.035〜0.065（固定級）

### 共通パラメータ
- `rsi_base`: 40.0〜58.0（上位10 trialの範囲に収束）
- `rsi_max`: 76.5〜79.0（安定範囲）
- `bb_z_base`: -2.0〜-0.8（上位10 trialの範囲に収束）
- `bb_z_max`: 2.0〜3.6（上位10 trialの範囲に収束）
- `liquidity_quantile_cut`: 0.16〜0.25（安定範囲）

## 3. Go/No-Goチェック（実行前の必須確認）

ChatGPTの提案に基づいて、最適化実行前に以下のチェックを実施してください。

```bash
# Go/No-Goチェックを実行
python check_optimization_readiness.py
```

**チェック項目:**
1. **チェックA：ユニバース診断（最重要）**
   - 2020-2021に"プライム限定"っぽい挙動になっていないか
   - 銘柄数が不自然に少ない/多いか
   - listed_infoテーブルに過去の日付が適切に保存されているか

2. **チェックB：決定性チェック**
   - 同一条件で2回実行して結果が一致するか（非決定性の有無）

3. **チェックC：Holdout設計**
   - Test期間を複数回使わない設計になっているか

**判断基準:**
- ❌ NO-GO: 重大な問題が見つかった場合、最適化実行前に修正が必要
- ⚠️ WARNING: 警告がある場合、確認してから実行
- ✅ GO: 全てのチェックをパスした場合、実行可能

## 4. 次の実行手順

### ステップ1: Train期間（2020-2022）での再最適化

**推奨実行手順（無駄撃ちを避ける）:**

1. **スモーク（各Study 5〜10 trial）**
   ```bash
   python run_optimization_train_period.py --n-trials 10 --study both
   ```
   - エラー/NaN/データ欠損/極端な売買回転になってないかを確認

2. **パイロット（各Study 50 trial）**
   ```bash
   python run_optimization_train_period.py --n-trials 50 --study both
   ```
   - 目的：分布の形を見る
   - **重要**: 50 trial時点で「本当に勝てる地形があるか」を判定する

3. **パイロット結果の評価（必須）**
   ```bash
   # 各Studyを個別に評価
   python evaluate_pilot_results.py --study-name optimization_timeseries_studyA_YYYYMMDD_HHMMSS
   python evaluate_pilot_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS
   
   # Study A/Bを比較
   python evaluate_pilot_results.py --study-a optimization_timeseries_studyA_YYYYMMDD_HHMMSS --study-b optimization_timeseries_studyB_YYYYMMDD_HHMMSS
   ```
   
   **判断基準（3つ全てを満たすことが推奨）:**
   - ✅ median > -0.05（これ未満だと探索空間がまだ広い/ズレてる疑い）
   - ✅ p95 > 0（上位がちゃんとプラスに浮くか）
   - ✅ best > 0.15（"伸びしろ"が見える最低ライン）
   
   **判定結果に応じた対応:**
   - **GO（3/3）**: 200 trialに進む
   - **CAUTION（2/3）**: 慎重に判断して200 trialに進む
   - **WARNING（1/3）**: 200 trialに進む前に範囲/目的関数/設計を見直す
   - **NO_GO（0/3）**: 200 trialに進む前に範囲/目的関数/設計を見直す必要がある
   
   **Study A/B比較:**
   - 片方だけ強い場合: 本番200は片側に集中が合理的（計算時間が重いため）
   - 両方そこそこ良い場合: 両方のStudyを200 trialに進める

4. **本番（各Study 200 trial）**
   ```bash
   # Study Bに集中（推奨）
   python run_optimization_train_period.py --n-trials 200 --study B
   
   # または両方進める場合
   python run_optimization_train_period.py --n-trials 200 --study both
   ```

5. **200 trial結果の評価（必須）**
   ```bash
   # 成功条件のチェック
   python evaluate_200trial_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS
   
   # 候補群の選定（上位＋分散）
   python evaluate_200trial_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS --select-candidates --output candidates_studyB.json
   
   # 候補群の可視化（オプション）
   python evaluate_200trial_results.py --study-name optimization_timeseries_studyB_YYYYMMDD_HHMMSS --select-candidates --output candidates_studyB.json --visualize --viz-output candidates_studyB_viz.png
   ```
   
   **成功条件（Study B）:**
   - ✅ median > 0.10（理想は0.15以上）
   - ✅ p95 > 0.25
   - ✅ 上位10の最小値 > 0.15
   - ✅ 上位10のbb_weightやroe_minが極端に端に張り付かない（＝安定）
   
   **危険シグナル:**
   - ⚠️ bestだけが異常に高く、p95や上位10が付いてこない
   - ⚠️ bestが境界張り付きだらけ（=範囲依存が強い）
   
   **候補群の選定方針（重要）:**
   - スコア順だけでなく、「上位＋分散」で選定
   - bb_weight / roe_min / w_value / w_forward_per の4軸で多様性を確保
   - 上位20から10個選ぶなど、分散を考慮した選定
   - これによりHoldoutで生き残る確率が上がる

**⚠️ 重要な注意:**
- 決定性チェックでSharpe=-0.598という結果が出ています（決定性はOKだが、そのパラメータでは負けている）
- これは「探索が必要なのは確か」だが、「Train（2020-2022）は相性が悪い可能性」も示唆しています
- 50 trial時点で「本当に勝てる地形があるか」を必ず判定してください

**期待される結果:**
- Study A: BB寄り・低ROE閾値の領域を深掘り
- Study B: Value寄り・ROE閾値やや高めの領域を深掘り
- 各Studyで上位5〜10 trialを候補群として保持

### ステップ2: Holdout検証（Test期間2023-2024）

**実務ステップ（最短ルート）:**

1. **上位10〜20を"候補群"として保存**（200 trial結果の評価で実施）

2. **Holdout（2023-2024）固定評価**
   - 最初は上位10を丸ごと評価（1つに絞らない）
   - 評価指標:
     - Sharpe_excess > 0.10（最低ライン）
     - 年別（2023/2024）で崩れない
   
3. **WFA（可能なら）**
   - ここまで来たら「過学習かどうか」がかなり判別できる

**注意: 将来的には以下の分割を推奨（現在の設計では Test 2023-2024）**
- Train：2020-2022（最適化に使う）
- Validation：2023（方針修正・再最適化の意思決定に使ってよい）
- Final Test：2024（最後の一発勝負。ここは触らない）
- 2025：運用シミュレーション（疑似ライブ）

**2025年のデータについて:**
- 現在は2025/12/31なので、2025年のデータは未使用で残っています
- 今後、より長期間の評価や追加の検証に使用可能です
- Final Testとして2025年を確保しておくのも選択肢です

Train期間で最適化した結果を、Test期間（2023-2024）で固定評価します。

#### 2.1 最適化結果から上位5〜10 trialを抽出

最適化結果のJSONファイルから、上位trialのパラメータを抽出します。

```python
import json
import optuna

# 最適化結果のDBを読み込み
study = optuna.load_study(
    study_name="optimization_timeseries_studyA_YYYYMMDD_HHMMSS",
    storage="sqlite:///optuna_optimization_timeseries_studyA_YYYYMMDD_HHMMSS.db"
)

# 上位10 trialを取得
top_trials = sorted(
    [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE],
    key=lambda t: t.value if t.value is not None else float('-inf'),
    reverse=True
)[:10]

# パラメータを保存
top_params = [trial.params for trial in top_trials]
```

#### 2.2 Test期間で固定評価

既存の`holdout_eval_timeseries.py`を使用するか、カスタムスクリプトを作成して評価します。

**評価基準（ChatGPTの提案）:**
- Test Sharpe_excess: > 0.10 を最低ライン、> 0.20 ならかなり良い
- Test MaxDD: 許容レンジ内（運用要件次第）
- 月次勝率（excessがプラスの月割合）: > 55% を目安
- 年別で崩れていないこと（2023年と2024年で安定）

### ステップ3: WFA（Walk-Forward Analysis）検証

Holdout検証で良好な結果が得られた場合、WFAを実施します。

**推奨WFA（expanding window / 年次更新）:**
- Fold1: Train 2020-2021 → Test 2022
- Fold2: Train 2020-2022 → Test 2023
- Fold3: Train 2020-2023 → Test 2024

各foldで「Train内最適化 → そのパラメータをTestに適用」を行います。

**合格のイメージ:**
- 3fold中、2fold以上がプラス、かつ平均が>0.1
- 1foldがマイナスでも「下げが浅い（例：-0.05程度）」なら許容
- 1foldで大きく崩れる（例：-0.3）なら、相場レジーム依存が強い可能性

既存の`walk_forward_timeseries.py`を使用できます。

## 4. data_fetch_timeの改善（将来の課題）

現状、data_fetch_timeが681秒/trialと長いため、将来的に改善が必要です。

**改善案:**
1. 詳細計測の追加（load_time, feature_calc_time, cache_read_time, universe_filter_timeに分解）
2. params非依存のデータ生成をobjective外へ追い出す（特徴量事前計算・使い回し）
3. 並列実行時のpickle化オーバーヘッド削減

ただし、現在の実装では`FeatureCache`を使用して事前計算しているため、既に改善されています。
今後、さらに詳細な計測を追加してボトルネックを特定する価値があります。

## 5. 評価の判断基準

### 過学習リスク評価

**現時点での評価: 中〜高**
- パラメータ13個に対し、評価点は月次60点。自由度が高い
- 100 trialのbest-of選抜で、多重比較バイアスが強い
- medianがほぼゼロ＝「当たりを引くゲーム」要素が残る

**過学習を抑える現実的な手:**
- ✅ 重要度が低いものを固定して次元削減（特にentry閾値の一部）→ 実施済み
- Holdout/WFAを必須ゲートにする → 次のステップ
- 目的関数をSharpe単独から「Sharpe − λ * turnover」のように罰則付きにする（将来の改善）

### 実務的な判断基準

**Train期間での最適化結果:**
- best Sharpe_excess > 0.30 を目安
- median > -0.05 を目安（探索空間の改善）

**Holdout期間での評価:**
- Test Sharpe_excess > 0.10 を最低ライン、> 0.20 ならかなり良い
- 月次勝率 > 55%
- 年別で安定（片年だけで稼いでいない）

**WFAでの評価:**
- 3fold中、2fold以上がプラス、かつ平均が>0.1
- 1foldで大きく崩れない（-0.05程度以内なら許容）

## 6. 注意事項

### ユニバース定義の注意

東証プライムは2022年開始のため、2020〜2021を含む場合、「当時の構成銘柄」をどう扱っているかでバイアスが出ます。
もし"現在のプライム採用銘柄"を過去に遡って使っていると、サバイバーシップ・バイアスが強烈に乗ります。
→ これはSharpe 0.33を簡単に"見かけ上"作ってしまう典型なので、念のため最優先で確認推奨。

## 7. 重要な注意事項（ChatGPTからの指摘）

### ユニバース定義について（最重要）

東証プライムは2022年開始のため、2020-2021を含む場合、「当時の構成銘柄」をどう扱っているかでバイアスが出ます。

**現在の実装:**
- `_load_universe`関数は「プライム|Prime」と「東証一部」の両方をフィルタしている
- これにより、2020-2021年は「東証一部」、2022年以降は「プライム」が取得できる
- ✅ OKの例に該当：2020-2021は（当時の）東証一部相当の構成を日付で復元している

**ただし、`listed_info`テーブルに2020-2021年の「東証一部」データが実際に入っているかは確認が必要です。**
→ `check_optimization_readiness.py`でチェック可能

### 情報リーケージ対策

現在の実装では、以下の対策が実施されています：

- ✅ 財務指標：`disclosed_date <= asof`の条件で取得（発表遅延を考慮）
- ✅ forward PER：予想値の"その時点"のスナップショットを使用
- ✅ テクニカル：当日引けで計算→翌営業日以降に売買（時系列バックテストで実装済み）

### 2025年のデータについて

- 現在は2025/12/31なので、2025年のデータは未使用で残っています
- 今後、より長期間の評価や追加の検証に使用可能です
- Final Testとして2025年を確保しておくのも選択肢です

## 8. 参考資料

- `OPTIMIZATION_RESULT_REPORT_20251231.md`: 100 trialの最適化結果レポート
- `top_10_trials_optimization_timeseries_20251231_081028.json`: 上位10 trialの詳細データ
- ChatGPTの分析レポート（ユーザー提供）: 詳細な分析と提案

