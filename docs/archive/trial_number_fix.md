# トライアル数の表示修正

## 問題

`load_if_exists=True`で既存のstudyを読み込む場合、trial番号が累積され、進捗バーの表示と実際のtrial番号が一致しない問題が発生していました。

### 具体例

```
Trial 262 finished with value: 0.7189439543036659
Best trial: 231. Best value: 4.24009:  22%|██████                      | 43/200 [00:58<03:02,  1.16s/it]
```

- Trial 262が完了しているのに、進捗バーでは43/200と表示されている
- これは、既存のstudyに200個のtrialがあり、新しい実行で`n_trials=200`を指定した場合に発生

## 原因

1. **`load_if_exists=True`**: 既存のstudyを読み込むため、以前の実行のtrial番号が続く
2. **進捗バーの表示**: `study.optimize(n_trials=200)`を実行すると、進捗バーは既存のtrialも含めてカウントする
3. **`completed_trials`のカウント**: 既存のtrialも含めて`COMPLETE`状態のtrial数をカウントするため、目標値と実際の値がずれる

## 修正内容

### 1. 既存のtrial数を考慮した目標値の設定

```python
# 既存のtrial数を確認（load_if_exists=Trueの場合）
existing_trials = len(study.trials)
existing_completed = len([t for t in study.trials if t.state == TrialState.COMPLETE])
if existing_trials > 0:
    print(f"既存のstudyを読み込みました（既存trial数: {existing_trials}, 完了: {existing_completed}）")
    print(f"新規に{n_trials}回の正常計算を追加します（合計目標: {existing_completed + n_trials}回の完了trial）")
    print()

# 既存の完了trial数を考慮
initial_completed = existing_completed
target_completed = initial_completed + n_trials
completed_trials = initial_completed
```

### 2. 進捗バーの表示を無効化

```python
# 注意: 進捗バーは既存のtrialも含めてカウントするため、表示がずれる可能性がある
# そのため、進捗バーは表示しない（手動でログを出力する）
show_progress = False  # 進捗バーは表示しない（trial番号がずれるため）
```

### 3. ログ出力の改善

```python
if completed_trials < target_completed:
    new_completed = completed_trials - initial_completed
    print(f"  完了trial数: {completed_trials}/{target_completed}（新規完了: {new_completed}/{n_trials}, 総試行数: {total_trials}, pruned: {pruned_count}, fail: {fail_count}）")
    print(f"  残り{target_completed - completed_trials}回の正常計算を継続します...")
```

## 修正後の動作

### 修正前

```
最適化を開始します（正常に計算が完了したtrial数が200に達するまで実行）...
Trial 262 finished with value: 0.7189439543036659
Best trial: 231. Best value: 4.24009:  22%|██████                      | 43/200 [00:58<03:02,  1.16s/it]
```

### 修正後

```
既存のstudyを読み込みました（既存trial数: 200, 完了: 200）
新規に200回の正常計算を追加します（合計目標: 400回の完了trial）

最適化を開始します（正常に計算が完了したtrial数が400に達するまで実行）...
  既存の完了trial: 200回
  新規に必要な完了trial: 200回

  完了trial数: 243/400（新規完了: 43/200, 総試行数: 262, pruned: 0, fail: 19）
  残り157回の正常計算を継続します...
```

## 効果

1. **明確な目標値**: 既存のtrial数を考慮した目標値が設定される
2. **正確な進捗表示**: 新規完了trial数と総完了trial数を分けて表示
3. **混乱の回避**: 進捗バーの表示を無効化することで、trial番号のずれによる混乱を回避

## 関連ファイル

- `src/omanta_3rd/jobs/optimize_longterm.py`: 修正対象ファイル

