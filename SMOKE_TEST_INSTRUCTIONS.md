# スモークテスト実行手順 - 長期保有型最適化システム

## 実行前の確認

以下の致命的な問題は修正済みです：
- ✅ `latest_date`の未定義エラーを修正（`test_perf["last_date"]`を使用）
- ✅ 並列実行時の警告を追加

## スモークテストの実行

### 1. 基本的なスモークテスト（5-10試行）

**Windows PowerShellの場合:**
```powershell
python -m omanta_3rd.jobs.optimize_longterm --start 2020-01-01 --end 2022-12-31 --study-type B --n-trials 10 --n-jobs 1 --bt-workers -1 --train-ratio 0.8 --random-seed 42
```

または、バッククォート（`）で行継続:
```powershell
python -m omanta_3rd.jobs.optimize_longterm `
    --start 2020-01-01 `
    --end 2022-12-31 `
    --study-type B `
    --n-trials 10 `
    --n-jobs 1 `
    --bt-workers -1 `
    --train-ratio 0.8 `
    --random-seed 42
```

**Linux/Macの場合:**
```bash
python -m omanta_3rd.jobs.optimize_longterm \
    --start 2020-01-01 \
    --end 2022-12-31 \
    --study-type B \
    --n-trials 10 \
    --n-jobs 1 \
    --bt-workers -1 \
    --train-ratio 0.8 \
    --random-seed 42
```

**重要:**
- `--n-jobs 1`: Optuna試行の並列を切る（DB書き込み競合を避ける）
- `--bt-workers -1`: バックテスト側の並列はOK（CPU数に合わせて自動設定）

### 2. 確認事項

スモークテストで以下を確認してください：

1. **エラーなく完走するか**
   - `NameError: name 'latest_date' is not defined` が出ないか
   - その他のエラーが出ないか

2. **ログ出力が正しいか**
   - データ分割の詳細（年別分布）が表示されるか
   - 評価窓の重なり分析が表示されるか
   - 最適化結果が表示されるか

3. **出力ファイルが生成されるか**
   - `optimization_history_*.png` が生成されるか
   - `param_importances_*.png` が生成されるか
   - OptunaのDBファイル（`optuna_*.db`）が生成されるか

4. **結果が妥当か**
   - 年率リターンが妥当な範囲内か（例: -50%〜+50%）
   - ポートフォリオ数が期待通りか
   - 平均保有期間が妥当か

### 3. 問題が発生した場合

#### NameError: name 'latest_date' is not defined
- ✅ 修正済み（`test_perf["last_date"]`を使用）

#### DB書き込み競合エラー
- `--n-jobs 1`で実行しているか確認
- 複数の最適化を同時に実行していないか確認

#### その他のエラー
- エラーメッセージを確認
- データベースに価格データが存在するか確認
- リバランス日の範囲が正しいか確認

## スモークテスト後の次のステップ

スモークテストが成功したら：

1. **試行回数を増やす**
   ```powershell
   python -m omanta_3rd.jobs.optimize_longterm --start 2020-01-01 --end 2022-12-31 --study-type B --n-trials 50 --n-jobs 1 --bt-workers -1 --train-ratio 0.8 --random-seed 42
   ```

2. **本番最適化（200試行）**
   ```powershell
   python -m omanta_3rd.jobs.optimize_longterm --start 2020-01-01 --end 2022-12-31 --study-type B --n-trials 200 --n-jobs 1 --bt-workers -1 --train-ratio 0.8 --random-seed 42
   ```

## 並列実行について（将来の改善）

現在は`--n-jobs 1`を推奨していますが、将来的には以下の改善が可能です：

1. **TrialごとのDB分離**
   - 一時テーブルを使用
   - `trial_id`カラムを追加
   - TrialごとにDBを分ける

2. **DataFrame直計算への移行**
   - `calculate_portfolio_performance`をDB非依存にする
   - ポートフォリオDataFrameから直接計算

現時点では、`--n-jobs 1`で実行し、`--bt-workers`でバックテスト側の並列化を活用することを推奨します。

