# uv セットアップ完了

## 現在の状況

✅ `uv`は `C:\Users\takay\.local\bin\uv.exe` にインストールされています
✅ ユーザー環境変数のPATHに `C:\Users\takay\.local\bin` が追加されています

## 新しいPowerShellセッションで使う方法

新しいPowerShellセッションで`uv`コマンドが認識されない場合は、以下のいずれかを試してください：

### 方法1: 環境変数を再読み込み（推奨）

新しいPowerShellセッションで以下を実行：

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
uv --version
```

### 方法2: 直接パスを指定

```powershell
& "$env:USERPROFILE\.local\bin\uv.exe" --version
```

### 方法3: エイリアスを作成

PowerShellプロファイルに以下を追加：

```powershell
# PowerShellプロファイルを開く
notepad $PROFILE

# 以下を追加
$env:Path += ";$env:USERPROFILE\.local\bin"
```

### 方法4: システム環境変数に追加（管理者権限が必要）

システム全体で使いたい場合：

```powershell
# 管理者権限でPowerShellを開いて実行
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "Machine") + ";$env:USERPROFILE\.local\bin", "Machine")
```

## 確認方法

```powershell
# PATHの確認
[Environment]::GetEnvironmentVariable("Path", "User")

# uvのバージョン確認
& "$env:USERPROFILE\.local\bin\uv.exe" --version

# インストール済みツールの確認
& "$env:USERPROFILE\.local\bin\uv.exe" tool list
```














