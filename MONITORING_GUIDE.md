# Walk-Forward Analysis 監視ガイド

## 監視スクリプト

Walk-Forward Analysis実行中に、CPU利用率、メモリ使用量、プロセス数を監視するためのスクリプトを用意しています。

## 1. Python版監視スクリプト（推奨）

### 特徴
- より詳細な情報を表示
- クロスプラットフォーム対応
- ディスクI/O情報も表示

### インストール

```bash
pip install psutil
```

### 実行方法

```bash
# 基本実行（5秒ごとに更新）
python monitor_walk_forward.py

# 更新間隔を変更（10秒ごと）
python monitor_walk_forward.py --interval 10

# 最小メモリ表示を変更（2GB以上）
python monitor_walk_forward.py --min-memory-gb 2.0
```

### 表示内容
- Pythonプロセスのメモリ使用量（1GB以上）
- CPU利用率（全体・コア別）
- システム全体のメモリ使用量
- ディスクI/O情報
- 警告（メモリ使用量が高い場合）

## 2. PowerShell版監視スクリプト

### 特徴
- Windows標準のPowerShellで動作
- 追加のインストール不要

### 実行方法

```powershell
.\monitor_walk_forward.ps1
```

### 表示内容
- Pythonプロセスのメモリ使用量（1GB以上）
- CPU利用率
- システム全体のメモリ使用量
- 警告（メモリ使用量が高い場合）

## 監視のポイント

### 必須監視項目

1. **Trial完了ログ**
   - Walk-Forward Analysisの実行ターミナルで確認
   - `[Trial X] ✅ 完了: value=..., 時間=...秒` が定期的に表示される
   - ⚠️ **trial完了ログが10分以上出ない場合は即座に停止**

2. **メモリ使用量**
   - 約37GB付近で安定している
   - ⚠️ **メモリ使用量が増え続ける場合は停止**

3. **CPU利用率**
   - 逐次実行のため3-10%程度（低め）
   - ⚠️ **CPU利用率が0%のまま → ハングの可能性**

### 正常な動作

- **メモリ使用量**: 約37GB付近で安定
- **CPU利用率**: 3-10%程度（逐次実行のため低め）
- **Trial完了**: 約2.5分ごとに新しいtrialが完了

### 異常な動作

- ⚠️ **メモリ使用量が50GBを超える**: リソース不足の可能性
- ⚠️ **メモリ使用量が増え続ける**: メモリリークの可能性
- ⚠️ **CPU利用率が0%のまま**: ハングの可能性
- ⚠️ **trial完了ログが10分以上出ない**: 停止している可能性

## 実行例

### ターミナル1: Walk-Forward Analysis実行

```bash
python run_walk_forward_analysis_roll.py
```

### ターミナル2: 監視スクリプト実行

```bash
# Python版（推奨）
python monitor_walk_forward.py

# または PowerShell版
.\monitor_walk_forward.ps1
```

## トラブルシューティング

### 問題: psutilがインストールされていない

**解決方法**:
```bash
pip install psutil
```

### 問題: PowerShellスクリプトが実行できない

**解決方法**:
```powershell
# 実行ポリシーを確認
Get-ExecutionPolicy

# 必要に応じて変更（現在のセッションのみ）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

### 問題: 監視スクリプトがエラーを出す

**解決方法**:
- Python版とPowerShell版の両方を試す
- エラーメッセージを確認して対処

## 推奨設定

### roll方式の実行時

- **更新間隔**: 5秒（デフォルト）
- **最小メモリ表示**: 1GB（デフォルト）
- **監視頻度**: 最低でも30分ごとに確認

### 長時間実行時

- **更新間隔**: 10秒（負荷を軽減）
- **ログファイルへの出力**: 必要に応じてリダイレクト

```bash
python monitor_walk_forward.py > monitor.log 2>&1
```














