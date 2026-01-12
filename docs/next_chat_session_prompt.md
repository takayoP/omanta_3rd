# 次のチャットセッション用プロンプト

## プロジェクト概要

日本株の長期保有型投資戦略のパラメータ最適化システムです。Optunaを使用したハイパーパラメータ最適化により、最適なポートフォリオ選定パラメータを探索します。

**対象**: 長期保有型アルゴリズム（24Mホライズン）

---

## 現在のシステム状態

### 1. スコア計算ロジック

#### Core Score（基本評価スコア）
```python
core_score = 
    w_quality × quality_score +      # 品質（ROE）
    w_value × value_score +          # バリュエーション（PER/PBR）
    w_growth × growth_score +        # 成長性
    w_record_high × record_high_score +  # 最高益フラグ
    w_size × size_score              # サイズ（時価総額）
```

- **quality_score**: ROEのパーセンタイルランク
- **value_score**: 業種内でのPER/PBRのパーセンタイルランク（低いほど高スコア）
- **growth_score**: 営業利益成長率、利益成長率、営業利益トレンド（3年スロープ）のパーセンタイルランク
- **record_high_score**: 予想最高益フラグ（0 or 1）
- **size_score**: 時価総額（対数）のパーセンタイルランク（小さいほど高スコア）

#### Entry Score（エントリータイミングスコア）
```python
entry_score = bb_weight × bb_score + rsi_weight × rsi_score
```

**計算方法（以前の実装に戻した）**:
1. 3つの期間（20日、60日、200日）でBB Z-scoreとRSIを計算
2. **BB値の最大値、RSI値の最大値を採用**
3. その後、スコアを計算して重み付き合計

**注意**: 以前は平均を取っていたが、現在は最大値を採用する実装に修正済み

### 2. ポートフォリオ選択ロジック

**選定フロー**:
1. フィルタリング（流動性、ROE）
2. Pool selection（core_score上位80銘柄）
3. Final selection（entry_score + core_scoreでソート）
4. Sector cap適用（セクターあたり最大4銘柄）
5. **重み付け: 等ウェイト**（選定ロジックはスコア比例）

**重要なポイント**:
- **選定ロジック**: スコア比例（`core_score`と`entry_score`に基づいて選定）
- **重み付け**: **等ウェイト**（選定された銘柄に均等に重みを付ける）
- 以前のスコア比例ウェイト戦略の選定ロジックを使用し、重みは等ウェイトに変更

### 3. 最適化ロジック

**目的関数**: `mean_annual_excess_return_pct`（年率超過リターンの平均）- λ × 下振れペナルティ

**Study Cの探索範囲（最近拡張）**:
- `w_quality`: 0.01-0.70（拡張）
- `w_value`: 0.05-0.80（拡張）
- `w_growth`: 0.01-0.50（拡張）
- `w_record_high`: 0.01-0.30（拡張）
- `w_size`: 0.01-0.60（拡張）
- `w_forward_per`: 0.0-1.0（完全に自由）
- `roe_min`: 0.00-0.30（拡張）
- `bb_weight`: 0.0-1.0（完全に自由）
- `liquidity_quantile_cut`: 0.05-0.50（拡張）

### 4. データフロー

- `build_features`: 特徴量計算、`core_score`と`entry_score`を計算
- `_select_portfolio_with_params`: ポートフォリオ選択（スコア比例選定 + 等ウェイト）
- `objective_longterm`: Optunaの目的関数
- `calculate_longterm_performance`: 長期保有パフォーマンス計算

---

## 最近の修正内容（2026年1月12日）

### 1. Study Cの探索範囲拡張
- 意味のある範囲で自由に探索できるように拡張
- 詳細は上記「Study Cの探索範囲」を参照

### 2. BBとRSIの計算方法修正
- **期間**: 90日 → 200日に変更（以前の実装に戻した）
- **計算方法**: 各期間で個別にスコアを計算 → **BB値とRSI値の最大値を先に採用してからスコアを計算**（以前の実装に戻した）

### 3. 営業利益スロープの期間修正
- 5年 → 3年に変更（仕様書も修正済み）

### 4. 未使用インポートの削除
- `compare_lambda_penalties.py`から`run_monthly_portfolio_with_regime`のインポートを削除（レジーム切替は使用していない）

### 5. **重要**: entry_score/core_scoreキャッシュ問題の修正
- **問題**: `FeatureCache`でキャッシュされた`entry_score`が最適化で使用され、trialごとに異なる`entry_params`を試してもスコアが変わらない問題
- **修正内容**:
  - `FeatureCache._build_features_single`: `entry_score`と`core_score`をキャッシュから削除
  - `_select_portfolio_with_params`: スキップロジックを削除し、常に`entry_params`に基づいて再計算
- **影響**: 最適化で正しくパラメータ探索が行われるようになる
- **注意**: 既存のキャッシュを再構築することを推奨（`--force-rebuild`またはキャッシュディレクトリの削除）
- **詳細**: `docs/cache_score_bug_fix.md`を参照

---

## 現在の最適化結果（参考）

**as_of_date=2024-12-31、test期間=2022年（24期間）**:
- λ=0.00: 平均超過 -1.34%, P10(超過) -10.58%, 勝率 37.5%, train超過 4.54%, test超過 -1.06%

**以前の結果（as_of_date=2023-12-31、test期間=2021年（12期間））**:
- λ=0.00: 平均超過 -5.00%, P10(超過) -11.00%, 勝率 25.0%, train超過 4.20%, test超過 -4.41%

**改善点**:
- 平均超過: -5.00% → -1.34%（+3.66%pt改善）
- 勝率: 25.0% → 37.5%（+12.5%pt改善）
- test超過: -4.41% → -1.06%（+3.35%pt改善）

---

## 確認済み事項

1. **レジーム切替**: 現在の実装はレジーム切替を使用していない（以前の実装と同じ）
2. **ポートフォリオ選択**: optimize/compare/本番で統一済み（`_select_portfolio_with_params`を使用、重みは等ウェイト）
3. **スコア計算**: 
   - **最適化時**: `_select_portfolio_with_params`で常に`entry_params`と`strategy_params`に基づいて再計算（キャッシュされたスコアは使用しない）
   - **本番運用時**: `build_features`で計算したスコアを`select_portfolio`で使用（`PARAMS`を使用）
   - **統一性**: 最適化と本番で選定ロジックは統一（`_select_portfolio_with_params`のコアロジックを使用）
4. **キャッシュ問題**: entry_score/core_scoreのキャッシュ問題を修正済み
   - `FeatureCache._build_features_single`: 新規構築時にスコア列を削除
   - `FeatureCache._load_cache`: 既存キャッシュ読み込み時にもスコア列を削除（`--force-rebuild`忘れ対策）
   - `_select_portfolio_with_params`: スキップロジックを削除し、常に再計算
   - `_select_portfolio_with_params`: `df = feat.copy()`でfeatを保護（trial間汚染防止）

---

## 次のステップ

1. **最適化の再実行**
   - Study Cの拡張された探索範囲で最適化を実行
   - BB/RSIの計算方法修正（最大値採用）を反映

2. **λ比較の再実行**
   - 最適化完了後、λ=0.00とλ=0.05を比較

3. **本番再最適化**
   - 採用λが決まった後、`reoptimize_all_candidates.py`を実行

---

## 重要なファイル

- `src/omanta_3rd/jobs/longterm_run.py`: 特徴量計算、ポートフォリオ選択（本番用）
- `src/omanta_3rd/jobs/optimize.py`: 最適化用のポートフォリオ選択（`_select_portfolio_with_params`）
- `src/omanta_3rd/jobs/optimize_longterm.py`: 長期保有型の最適化（`objective_longterm`）
- `src/omanta_3rd/jobs/compare_lambda_penalties.py`: λ比較スクリプト
- `src/omanta_3rd/backtest/feature_cache.py`: 特徴量キャッシュ（entry_score/core_scoreを削除）
- `docs/system_specification_for_chatgpt_analysis.md`: システム仕様書（ChatGPT分析用）
- `docs/cache_score_bug_fix.md`: entry_score/core_scoreキャッシュ問題の修正ドキュメント

---

## 注意事項

1. **train期間とtest期間の乖離**: train期間（+4.54%）とtest期間（-1.06%）で乖離がある（-5.60%pt）。過学習の可能性や市場環境の違いが考えられる。

2. **不完全なcore_scoreの割合**: フィルタ後で10.1%、プールで18.8%が不完全なcore_score。欠損値処理により中立的な値が設定されているため、大きな問題にはならないが、選定の質に影響する可能性がある。

3. **24Mホライズンの制約**: 24Mホライズンでは`require_full_horizon=True`を維持するため、test期間が制約される。現在は`as_of_date=2024-12-31`でtest期間を2022年に設定している。

---

## 次のチャットセッションで確認すべきこと

1. **entry_score/core_scoreキャッシュ問題の修正の確認**
   - 修正後の最適化で正しくパラメータ探索が行われているか
   - キャッシュの再構築が必要か（既存キャッシュの削除または`--force-rebuild`）
2. 最適化の実行状況と結果
3. Study Cの拡張された探索範囲での最適化結果
4. BB/RSIの計算方法修正（最大値採用）の影響
5. train期間とtest期間の乖離の改善状況

---

**以上**

