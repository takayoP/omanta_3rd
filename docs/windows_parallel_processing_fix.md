# Windowsでの並列処理エラー修正

## 問題

Windowsで`ProcessPoolExecutor`を使用した並列処理で、以下のエラーが発生していました：

```
エラー (2020-02-28): A process in the process pool was terminated abruptly while the future was running or pending.
RuntimeError: No portfolios were generated
```

## 原因

Windowsでの`ProcessPoolExecutor`の問題：
1. Windowsでは`multiprocessing`が`spawn`方式を使用するため、プロセス間でオブジェクトをpickle化する必要がある
2. 複雑なオブジェクト（DataFrame、データベース接続など）のpickle化が失敗することがある
3. プロセスが異常終了し、`No portfolios were generated`エラーが発生

## 解決策

`ProcessPoolExecutor`を`ThreadPoolExecutor`に変更しました。

### 変更内容

1. **`calculate_longterm_performance`関数**:
   - `ProcessPoolExecutor` → `ThreadPoolExecutor`に変更
   - Windowsでのプロセスプールの問題を回避

2. **メリット**:
   - Windowsでの並列処理エラーを回避
   - I/Oバウンドな処理（データベースアクセス、ファイル読み込み）には有効
   - メモリ共有が容易（GILの制約はあるが、I/O待機中は解放される）

3. **デメリット**:
   - CPUバウンドな処理には効果が限定的（GILの制約）
   - ただし、ポートフォリオ選定は主にI/Oバウンドなので、実用上問題なし

## 変更ファイル

- `src/omanta_3rd/jobs/optimize_longterm.py`:
  - `ProcessPoolExecutor` → `ThreadPoolExecutor`に変更
  - インポート文を修正

## 注意事項

- `ThreadPoolExecutor`はGILの制約があるため、CPUバウンドな処理には効果が限定的
- ただし、ポートフォリオ選定は主にI/Oバウンド（データベースアクセス、特徴量計算）なので、実用上問題なし
- 最適化の実行時間は、`ProcessPoolExecutor`と同等または若干遅くなる可能性があるが、エラーを回避できる

