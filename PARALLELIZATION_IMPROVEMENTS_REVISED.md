# 並列化・高速化 改善仕様（改訂版）

> 目的：`optimize_timeseries` 実行時の CPU 利用率が低い／試行が遅い問題を、**安全に・再現性を保ちながら**改善する。
>
> 本書は、従来案（「2層並列：trial並列 × trial内バックテスト並列」）の思想を踏まえつつ、**現実にスケールしやすい並列化設計へ修正**した改訂版です。

---

## 0. 背景（現状の整理）

従来案では以下を想定していた：  
- Optunaの試行（trial）は逐次（`n_jobs=1`）
- 各trial内のバックテストは並列化済み
- CPU利用率が低い → trialも並列化してCPUを埋めたい

（従来仕様の要点）  
- 2層並列化（trial並列＋trial内並列）  
- SQLite WAL・timeout 等で競合対策  
- 理論上は「CPU 100%」を期待

---

## 1. CPU利用率が低い主な原因（典型パターン）

**結論：CPUが低い＝並列度不足とは限らない。**  
バックテストは「計算」ではなく「データアクセス（DB/IO）」が支配的になると、CPUは空きます。

よくある原因：
1) **SQLite読み取り/IO待ち**  
   - 価格取得が「銘柄×日付」の多数クエリになっている場合、CPUよりIOがボトルネック
2) **Optuna並列が“スレッド”でGILに阻まれる**（実装依存）  
   - Python処理中心だとスレッド並列は伸びにくい
3) **二重並列によるオーバーサブスクライブ**  
   - trial並列 × trial内並列 × NumPy/BLAS内部スレッド で競合しやすい
4) **Optunaストレージ書き込み競合（SQLite）**  
   - 多数ワーカーで同一SQLiteへ書き込むとロック待ちが発生しやすい

---

## 2. 方針（重要：並列化は「1階層」に寄せる）

### 推奨：まずは **trial並列（プロセス）に一本化**
- Optuna trial を複数ワーカー（プロセス）で回す  
- trial内バックテストは基本 `bt_workers=1`（並列しない）

理由：
- 二重並列は理論ほど伸びず、むしろ遅くなることが多い
- SQLiteやIOが絡むと、trial内並列は逆効果になりやすい

---

## 3. 実装変更（必須：CLIと内部並列制御を明確化）

### 3.1 新設/整理するパラメータ
- `--n-jobs`：trial並列数（Optunaワーカー数）
- `--bt-workers`：trial内バックテストの並列数（デフォルト 1）
- `--parallel-mode`：`trial` / `backtest` / `hybrid`
  - `trial`：**推奨**（trial並列のみ）
  - `backtest`：trial逐次＋trial内並列
  - `hybrid`：条件付き（後述）

> **注意**：従来の実行例では `--n-jobs` がコマンドに入っていないため、  
> 「試行並列化したつもりで逐次のまま」になり得る。  
> コマンド例を必ず更新する。

### 3.2 BLASスレッドの暴走を防ぐ（推奨）
プロセス並列を使う場合は、各プロセス内で NumPy/BLAS が勝手にスレッドを立てて過負荷になりやすい。  
実行前に以下を設定する（少なくともどれか）：

- `OMP_NUM_THREADS=1`
- `MKL_NUM_THREADS=1`
- `OPENBLAS_NUM_THREADS=1`
- `NUMEXPR_NUM_THREADS=1`

---

## 4. Optunaストレージ（SQLite前提の現実的な上限）

### 4.1 SQLiteでの推奨ワーカー数
SQLiteは「多数並列書き込み」に向かないため、**trial並列は控えめにする**のが安全。

- 推奨：`--n-jobs 2〜4`  
- “コア数の半分（最大8）”は **環境次第でロック待ちが増えて遅くなる**可能性が高い

### 4.2 可能なら推奨：OptunaストレージをPostgreSQLへ
もし運用的に許されるなら、OptunaのストレージだけはPostgreSQLにすると並列スケールが改善しやすい。

- 価格データ：SQLite（read-heavy）
- Optuna：PostgreSQL（write-heavy）

※この分離が「CPUが空く/ロック待ち」の大きな改善になることが多い。

---

## 5. trial内バックテスト並列（使うなら条件付き）

### 5.1 trial内並列が効く条件
- 価格データを **事前にまとめてメモリにロード**しており、DBクエリがほぼ無い
- リターン計算がNumPyベクトル化されている（CPUバウンド）

この条件が満たされるなら：
- `parallel-mode=backtest`（trial逐次）で `bt_workers` を増やすと効く可能性がある

### 5.2 hybrid（二重並列）は原則“最後の手段”
hybridを使うなら、以下を明確にする：

- `n_jobs * bt_workers <= physical_cores` を厳守
- SQLite競合が増えるなら即撤退
- BLASスレッドは必ず1に固定

---

## 6. 観測性（最重要：最適化前にボトルネックを見える化）

### 6.1 追加ログ（必須）
trialごとに下記の時間を測ってログ出力：
- データ取得時間（DB/IO）
- シグナル計算時間
- 月次リターン算出時間
- 指標計算時間
- 合計

### 6.2 サマリーレポート（推奨）
最適化終了時に、
- 平均trial時間
- p50/p90 trial時間
- IO比率（データ取得時間/合計）
を出す。

---

## 7. 推奨実行コマンド（更新）

### 7.1 SQLiteストレージ（安全運用：まずはこれ）
```bash
# 例：まずは2〜4並列で様子を見る
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2024-12-31 \
  --n-trials 20 \
  --study-name optimization_timeseries_20251230_phase1 \
  --parallel-mode trial \
  --n-jobs 4 \
  --bt-workers 1 \
  --no-progress-window
```

### 7.2 Postgresストレージ（可能なら：高速化しやすい）
```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
python -m omanta_3rd.jobs.optimize_timeseries \
  --start 2021-01-01 \
  --end 2024-12-31 \
  --n-trials 50 \
  --study-name optimization_timeseries_20251230_phase1 \
  --storage postgresql://... \
  --parallel-mode trial \
  --n-jobs -1 \
  --bt-workers 1 \
  --no-progress-window
```

---

## 8. 進行状況の確認（従来通り）

```bash
python check_optimization_progress.py
```

---

## 9. 期待効果（現実的な表現へ修正）

- 理論上「1/8」などの線形短縮は、**IO/DB競合で崩れる**ことが多い  
- まずは「CPUを100%にする」より、
  - **総処理時間が減るか**
  - **trial/秒が上がるか**
  をKPIにする

目標：
- SQLite環境：`--n-jobs 2〜4` で **体感2〜3倍**を狙う（過大期待しない）
- Postgres＋メモリキャッシュ：より高いスケールが期待可能

---

## 10. 次の改善（CPUが低いままの場合）

CPUが低いままなら「並列度」ではなく「データアクセス」が原因である可能性が高い。  
優先度順に対策：

1) 価格データを期間一括でロード（銘柄×日付）してメモリ参照へ
2) SQLiteクエリ回数を削減（per-ticker per-date を廃止）
3) 可能ならDBを read-only 接続にし、OSキャッシュを効かせる
4) OptunaストレージをPostgresへ

---

