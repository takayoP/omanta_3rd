# Cursor的な最小構成へのスリム化アイデア

**作成日**: 2025-03-14  
**前提**: [SYSTEM_OVERVIEW_CURRENT.md](./SYSTEM_OVERVIEW_CURRENT.md) の現状を踏まえた整理案。

---

## 1. 「Cursor的な最小構成」の意味

ここでは次のような状態を「Cursor的な最小構成」とする。

| 観点 | 目指す姿 |
|------|----------|
| **入口が少ない** | やることは同じでも、実行経路は「パッケージの数コマンド」に集約。ルート直下のスクリプトは極力減らす。 |
| **責務が1本化** | 最適化は「月次リバランス用」か「長期用」のどちらか1本を主軸にし、旧形式・派生版は廃止またはアーカイブ。 |
| **単一の真実** | ポートフォリオ選定・スコア計算・パラメータ正規化は1箇所にまとめ、他からは参照だけ。 |
| **小さく分割されたコード** | 2000行超の1ファイルは避け、モジュール単位で「読める・変えられる」サイズに分割。 |
| **オプションは明示** | レジーム・WFA・λ比較などは「拡張」として別モジュールまたはサブコマンドにし、本線はシンプルに保つ。 |

---

## 2. スリム化の基本方針

### 2.1 運用スタイルを「まず1本」に絞る

- **案A: 月次リバランス型を主軸にする**  
  - 最適化・評価・テーブルをすべて月次リバランス用に統一。  
  - 長期保有型は「同じ特徴量で手動で見るだけ」にし、`longterm_run` のスクリーニング出力だけ残す（最適化は行わない）。  
- **案B: 長期保有型を主軸にする**  
  - 固定ホライズン評価だけを残し、月次リバランス用の複数最適化（timeseries / robust / clustered）は廃止または別リポの「実験用」に移す。  
- **案C: 両方残すが「共通コア＋薄い2レイヤ」**  
  - 共通: データ・特徴量・**1つのポートフォリオ選定＋1つのバックテスト計算**。  
  - 長期用: `longterm_run`（特徴量＋選定のみ）と `optimize_longterm`（固定ホライズン最適化のみ）。  
  - 月次用: `optimize_timeseries` のみ（robust/clustered は廃止）。  

推奨は **案C（共通コア＋薄い2レイヤ）**。両スタイルを残しつつ、最適化はそれぞれ1本に集約する。

### 2.2 最適化経路を1本に集約する

- **月次リバランス型**  
  - **残す**: `optimize_timeseries.py`（時系列・open-close・Sharpe_excess）。  
  - **廃止 or アーカイブ**: `optimize.py`（旧形式）, `robust_optimize_timeseries.py`, `optimize_timeseries_clustered.py`, `optimize_monthly_rebalance.py`。  
  - Robust の「安定性重視」が必要なら、`optimize_timeseries` の目的関数に「安定性ペナルティ」をオプションで足す形に統合する。  

- **長期保有型**  
  - **残す**: `optimize_longterm.py` のみ（中身は後述の「分割」で整理）。  
  - 比較用の `compare_lambda_penalties.py` は、必要なら「サブコマンド」または `optimize_longterm` の `--compare-lambda` のようなオプションに吸収する。  

- **評価**  
  - **残す**: `holdout_eval_timeseries.py`, `walk_forward_timeseries.py`（月次用）, 長期用は `optimize_longterm` 内の train/test のみ、または単体の小さな評価スクリプト1本）。  
  - レジーム・レンジ比較は「拡張」として別モジュールにし、本線からは外す。  

---

## 3. コードの集約と分割

### 3.1 単一の真実：ポートフォリオ選定・スコア

- **現状**: `optimize.py` の `_select_portfolio_with_params` と `optimize_timeseries` の `_select_portfolio_for_rebalance_date` が別にあり、長期用は時系列側を参照している。  
- **スリム化案**:  
  - **1箇所に集約**: 例）`strategy/select.py` に「パラメータ付きポートフォリオ選定」を1つ実装する（`select_portfolio_with_params(conn, rebalance_date, params, ...)`）。  
  - `optimize.py` / `optimize_timeseries.py` / `optimize_longterm.py` はすべてこの関数を呼ぶだけにする。  
  - スコア・エントリー計算も `strategy/` または `features/` に集約し、`longterm_run` と各 optimize は「同じ関数」を参照する。  

### 3.2 巨大ファイルの分割

- **optimize_longterm.py（約2200行）**  
  - 分割案:  
    - `jobs/optimize_longterm/` のようなサブパッケージにする。  
    - `split.py`（train/test 分割）, `objective.py`（目的関数）, `performance.py`（長期用指標計算）, `cli.py`（argparse と main）に分ける。  
    - または `jobs/longterm_optimize.py`（薄いエントリ）＋ `jobs/longterm_optimize/objectives.py`, `runs.py`, `metrics.py` など。  

- **longterm_run.py（約2000行超）**  
  - 分割案:  
    - `jobs/longterm_run.py` は「orchestration だけ」にし、特徴量計算は `features/` へ、選定は `strategy/select.py` へ、DB 保存は `infra/` または `jobs/db_io.py` へ移す。  
    - または `features/build_monthly.py`, `strategy/select_longterm.py`, `jobs/monthly_run.py`（薄い main）に分ける。  

これにより「どこを読めば何が分かるか」が明確になる。

### 3.3 バックテスト計算の一本化

- 時系列 P/L は **backtest/timeseries.py** を唯一の計算源にする。  
- 長期用の「固定ホライズン・単一リバランス日→評価日」も、可能なら同じ timeseries モジュールの関数を「1リバランス・1期間」で呼ぶ形にし、累積リターン用の別経路は廃止する。  

---

## 4. ルート直下の整理

### 4.1 スクリプトの集約先

- **方針**: 実行は原則 `python -m omanta_3rd.jobs.xxx` に寄せる。ルート直下の `.py` は「ランチャー」か「廃止」のどちらか。  

- **集約例**:  
  - `evaluate_candidates_holdout.py` → `python -m omanta_3rd.jobs.holdout_eval_timeseries` に統合（既に holdout_eval_timeseries があるため、ルート側は「薄いラッパー」にするか削除）。  
  - `save_final_candidates_to_db.py`, `save_performance_time_series_to_db.py` → `jobs/db_export.py` のような1モジュールにまとめ、`python -m omanta_3rd.jobs.db_export --candidates ...` のようにサブコマンド化。  
  - 可視化は `scripts/visualize.py` または `python -m omanta_3rd.reporting.visualize` に1本化し、用途は `--equity`, `--holdings` などで切り替え。  

### 4.2 シェル（.ps1 / .bat）の整理

- **残す**: よく使う1〜2本だけ。例）  
  - `run_update.ps1`（データ更新＋必要なら特徴量まで）  
  - `run_optimize.ps1`（月次用 or 長期用のどちらか、または `--mode monthly | longterm` で切り替え）  
- **その他**: `run_walk_forward_*.ps1`, `run_fixed_horizon_*.ps1` などは、中身を「パッケージの1コマンド」に寄せ、シェルはそのコマンドを呼ぶだけの短いスクリプトに縮小。重複する複数本は1本にまとめる。  

---

## 5. ドキュメントの整理

- **現状維持**: `README.md`, `SYSTEM_SPECIFICATION.md`, `docs/SYSTEM_OVERVIEW_CURRENT.md` は「現状・仕様」として残す。  
- **スリム化後**: `docs/SLIM_DOWN_IDEAS.md`（本資料）を「方針・アイデア」として残し、実施した内容は「実施サマリ」を同じファイルの末尾か `docs/SLIM_DOWN_DONE.md` に追記。  
- **履歴・検証メモ**: `docs/` 内の細かい議事メモは `docs/archive/` に移動し、参照用にだけ残す。新規では「今の設計」を書くファイルを少なく保つ。  

---

## 6. 最小ラン可能セット（スリム化後のイメージ）

「何もないところから動かす」最小の流れを、次のように定義する。

1. **DB 初期化**  
   `python -m omanta_3rd.jobs.init_db`

2. **データ取得**  
   `python -m omanta_3rd.jobs.etl_update --target listed` 等（または `run_update.ps1` で一括）

3. **特徴量計算＋選定（どちらか or 両方）**  
   - 月次リバランス用: 最適化内で特徴量を参照するため、事前に `longterm_run` 相当で features_monthly を埋めておく、または最適化内で計算する。  
   - 長期用: `python -m omanta_3rd.jobs.longterm_run --asof YYYY-MM-DD`  

4. **最適化（1本だけ使う）**  
   - 月次: `python -m omanta_3rd.jobs.optimize_timeseries --start ... --end ... --n-trials N`  
   - 長期: `python -m omanta_3rd.jobs.optimize_longterm --start ... --end ... --study-type B --n-trials N`  

5. **評価**  
   - 月次: `python -m omanta_3rd.jobs.holdout_eval_timeseries ...` または `walk_forward_timeseries`  
   - 長期: optimize_longterm の train/test 結果、または専用の小さな評価スクリプト1本  

6. **バックテスト（必要なら）**  
   `python -m omanta_3rd.jobs.backtest --rebalance-date ... --save-to-db`  

この6ステップを README に「最小クイックスタート」として書き、それ以外は「拡張」として docs にまとめる。

---

## 7. 実施の優先度（案）

| 優先度 | 内容 | 効果 |
|--------|------|------|
| 1 | 運用スタイルと最適化の「1本化」を決める（案C推奨） | 迷いが減る |
| 2 | ポートフォリオ選定・スコアを1箇所に集約 | 重複削減・バグの一貫性 |
| 3 | 廃止する最適化・比較スクリプトをアーカイブ（削除は後でも可） | エントリポイントの削減 |
| 4 | `optimize_longterm.py` の分割（サブパッケージ or 複数ファイル） | 保守性向上 |
| 5 | `longterm_run.py` の分割（orchestration と計算の分離） | 同左 |
| 6 | ルート直下スクリプトのパッケージ移行 or ラッパー化 | 入口の一本化 |
| 7 | .ps1 の統合と「中身はパッケージ1コマンド」化 | 運用の単純化 |
| 8 | docs の archive 化と「最小ラン可能セット」の README 明記 | オンボーディングの容易さ |

---

## 8. まとめ

- **Cursor的な最小構成** = 入口が少ない・責務が1本・単一の真実・ファイルは小さく・オプションは明示。  
- **スリム化の核**: (1) 運用スタイルは「共通コア＋薄い2レイヤ」、(2) 最適化は月次1本・長期1本に集約、(3) ポートフォリオ選定・スコアは1箇所に集約、(4) 巨大ファイルの分割、(5) ルート直下とシェルの整理。  
- まず「どの運用スタイルを主軸にするか」と「残す最適化はどれか」を決め、その上で上記の優先度で段階的に進めると、Cursor 的な最小構成に近づけられる。
