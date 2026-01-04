# Walk-Forward Analysis 診断レポート

## 実行日時
2026-01-03 19:07-19:35

## 問題の概要
- **症状**: 30分経過しても1 trialも完了しない
- **CPU利用率**: 約3%（異常に低い）
- **メモリ使用量**: 約37GB
- **ディスク**: アクティブ時間ほぼ0（ページング地獄ではない）

## 診断アプローチ

### 1. 進捗可視化の追加
`timed_objective`ラッパーを追加し、各trialの実行時間を計測できるようにしました。

### 2. 詳細ログの追加
以下の箇所にログを追加して、停止箇所を特定できるようにしました：
- `study.optimize`呼び出し直前
- `timed_objective`呼び出し開始
- `objective_longterm`関数開始
- `calculate_longterm_performance`関数開始
- 各リバランス日の処理状況
- `_run_single_backtest_portfolio_only`内の各処理ステップ

## 診断結果

### ✅ Aパターン（1 trialが重い）と確定

**1 trialの実行時間**: 148.4秒（約2.5分）

**処理内容**:
- 36日分のリバランス日を逐次処理
- 各リバランス日でポートフォリオ選定を実行
- パフォーマンス計算を実行

**50 trialsの見積もり**: 約2時間（現実的な時間）

### 発見された問題

#### 1. `entry_score`の重複計算
- **問題**: `_run_single_backtest_portfolio_only`で`entry_score`を計算済みなのに、`_select_portfolio_with_params`内で再度DBから価格データを取得して再計算していた
- **影響**: 各リバランス日ごとに不要なDBアクセスが発生

#### 2. 致命的バグ（並列化時）
- **問題**: `_process_single_fold_wrapper`で`n_jobs_optuna`が未定義
- **影響**: fold並列化時に`NameError`が発生する可能性

#### 3. 並列化戦略の問題
- **問題**: fold並列とOptuna並列を同時に使用していた
- **影響**: オーバーサブスクライブによる性能低下

## 実施した修正

### 1. `entry_score`の重複計算を回避
**ファイル**: `src/omanta_3rd/jobs/optimize.py`

```python
# entry_scoreが既に計算済みの場合はスキップ
if "entry_score" not in feat.columns or feat["entry_score"].isna().all():
    # 再計算が必要な場合のみDBから取得
    ...
else:
    # 既に計算済みの場合はスキップ
    print(f"        [_select_portfolio] entry_scoreは既に計算済み（スキップ）")
```

**効果**: DBアクセスの削減

### 2. 並列化バグの修正
**ファイル**: `walk_forward_longterm.py`

- `_process_single_fold_wrapper`の引数に`n_jobs_optuna`を追加
- `executor.submit`で`n_jobs_optuna`を渡すように修正

### 3. 並列化戦略の見直し
**ファイル**: `walk_forward_longterm.py`

- fold並列が有効な場合、Optuna並列を無効化
- fold並列が無効な場合、Optuna並列を有効化
- 二重並列を防止

### 4. BLASスレッドの制御
**ファイル**: `walk_forward_longterm.py`

```python
# BLASスレッドの制御（並列化時のオーバーサブスクライブを防ぐ）
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
```

### 5. 進捗可視化の追加
**ファイル**: `walk_forward_longterm.py`, `src/omanta_3rd/jobs/optimize_longterm.py`

- `timed_objective`で各trialの実行時間を計測
- 詳細ログで処理状況を可視化

## パフォーマンス改善の確認

### 修正前
- 30分経過しても1 trialも完了しない
- 停止箇所が不明

### 修正後
- **1 trial完了**: 148.4秒（約2.5分）
- **処理内容**: 36日分のリバランス日を正常に処理
- **重複計算回避**: `entry_scoreは既に計算済み（スキップ）`が表示されることを確認

## 実行結果サマリー

### 最適化結果（1 trial）
- **Best value**: -9.9349%（年率超過リターン）
- **実行時間**: 148.4秒
- **処理日数**: 36日分

### Test期間の評価結果
- **年率超過リターン（平均）**: 0.4784%
- **年率超過リターン（中央値）**: 2.6288%
- **勝率**: 58.33%
- **ポートフォリオ数**: 12

## 今後の改善案

### 1. Prunerの追加（最優先・効果大）
**目的**: 見込みの低いtrialを早期打ち切り

**実装方針**:
- train_datesの先頭数回（例：8回）だけで暫定スコアを計算
- `trial.report()` → `trial.should_prune()` で打ち切り判定
- 体感10倍以上の短縮が期待できる

**期待効果**: 50 trials → 約20分（10倍短縮）

### 2. 特徴量の列削減
**目的**: メモリ使用量の削減（現在37GB）

**実装方針**:
- 必要な列のみを読み込む（quality/value/growth/record_high/size/forward_per/liquidity/rsi/bb系など）
- 不要な列を削除

**期待効果**: メモリ使用量の削減、キャッシュミスの減少

### 3. float32化
**目的**: メモリ使用量とキャッシュミスの削減

**実装方針**:
- float64 → float32に変換
- 精度への影響を確認

**期待効果**: メモリ使用量の約半分、処理速度の向上

### 4. DataFrame操作の最適化
**目的**: `_pct_rank`などの処理を高速化

**実装方針**:
- pandas処理を「numpy配列＋内積」に寄せる
- スコアが線形重みなら、`score = X @ w`だけでランキング

**期待効果**: DataFrame操作の削減、処理速度の向上

### 5. 並列化の最適化
**目的**: CPU利用率の向上

**現状**:
- fold=1（simple方式）のため、fold並列は無効
- Optuna並列は`n_jobs=1`で実行（メモリ使用量を考慮）

**改善案**:
- `n_jobs_optuna=2`に設定してOptuna並列を有効化
- メモリ使用量を監視しながら調整

## 推奨される次のステップ

### ✅ 即座に実行可能（現状で2時間半で回す判断は妥当）

**結論**: 現状の改善状態で50 trials（約2時間半）を実行して問題ありません。

#### 実行前の確認事項
1. ✅ **`n_jobs_optuna=1`のまま**: まず安定優先
2. ✅ **`timed_objective`のログ**: trialごとに完了時刻が出続ける（止まっていない）
3. ✅ **メモリ使用量**: 37GB付近で頭打ちになっている（増え続けない）

#### 実行中の監視ポイント
- **trial完了ログが10分以上出ない**: その時点で停止して原因切り分け
- **メモリ使用量が増え続ける**: メモリリークの可能性
- **CPU利用率が異常に低い**: ハングの可能性

### 小さな保険（推奨）

#### 1. 途中経過の保存（落ちても再開できるように）
- OptunaをRDB（SQLite等）にして`study_name`を固定
- 途中停止→再開できる形にする
- **注意**: 現在は「メモリストレージ」を使用しているため、再開不可

#### 2. ログ頻度の調整
- 「trial完了ログ」だけは残す（進捗監視に必須）
- 詳細ログは必要に応じて削減可能

### 次回の改善（今すぐじゃなくて次）

#### Prunerの追加（最優先・効果大）
- **目的**: 見込みの低いtrialを早期打ち切り
- **期待効果**: 体感10倍以上の短縮（50 trials → 約20分）
- **実装**: train_datesの先頭数回（例：8回）だけで暫定スコアを計算
- **タイミング**: 次回の作業でOK（いまはまず通しで結果を取りに行くのが正解）

### 中期（パフォーマンス改善）
1. **特徴量の列削減**: メモリ使用量の削減
2. **float32化**: メモリとキャッシュミスの削減

### 長期（最適化）
1. **DataFrame操作の最適化**: numpy配列化
2. **キャッシュ戦略の見直し**: 重複warmの削減

## 結論

### 問題の原因
1. **Aパターン（1 trialが重い）**: 36日分のリバランス日を逐次処理するため、1 trialあたり約2.5分かかる
2. **重複計算**: `entry_score`の重複計算により、不要なDBアクセスが発生

### 修正の効果
- ✅ 重複計算を回避し、DBアクセスを削減
- ✅ 進捗可視化により、処理状況を把握可能
- ✅ 並列化バグを修正し、安定性を向上

### 現状の評価
- **50 trials**: 約2時間（現実的な時間）
- **改善余地**: Pruner追加により、約20分まで短縮可能

### 推奨事項
1. ✅ **現状で50 trials（約2時間半）を実行**: 妥当な判断
2. **実行前の確認**: `n_jobs_optuna=1`、ログ出力、メモリ使用量
3. **実行中の監視**: trial完了ログが10分以上出ない場合は停止
4. **小さな保険**: 途中経過の保存（RDB使用）、ログ頻度の調整
5. **次回の改善**: Prunerの追加（今すぐじゃなくて次でOK）

---

## 参考情報

### 実行環境
- OS: Windows 10
- Python: ml-env環境
- CPU: 複数コア（詳細未確認）
- メモリ: 約37GB使用

### 実行コマンド
```bash
python run_walk_forward_analysis_diagnostic.py
```

### 設定パラメータ
- 期間: 2020-01-01 ～ 2025-12-31
- ホライズン: 12ヶ月
- Fold数: 1（simple方式）
- 最適化試行回数: 1（診断用）
- Optuna並列数: 1（診断用）

### 関連ファイル
- `walk_forward_longterm.py`: メインスクリプト
- `src/omanta_3rd/jobs/optimize_longterm.py`: 最適化ロジック
- `src/omanta_3rd/jobs/optimize.py`: ポートフォリオ選択
- `src/omanta_3rd/jobs/optimize_timeseries.py`: 時系列最適化
- `run_walk_forward_analysis_diagnostic.py`: 診断用スクリプト

