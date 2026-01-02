# 投資アルゴリズム / スクリーニング & バックテスト基盤（日本株・TOPIX比較）

本リポジトリは、日本株を対象に **ファンダメンタル指標を中心とした銘柄序列化（ランキング）**を行い、  
その結果を使って **(A) 中長期（NISA想定）の積立・買い増し** と **(B) 月次リバランス運用** の両方を検証・運用できるようにするための基盤です。

> ⚠️ 注意：本リポジトリは投資助言ではありません。最終判断は自己責任でお願いします。  
> バックテストは将来の成果を保証しません（特にコスト・データ遅延・流動性・企業イベントの影響に注意）。

---

## 1. 投資方針（共通：変わらない軸）

### 1.1 銘柄選定の考え方（スクリーニング）
以下のような **業績・資本効率（Quality）** と **割安性（Value）** を中心に、銘柄をスコアリングして序列化します。

- **Quality / 収益力・持続性**
  - ROE（水準・安定性）
  - 利益成長の一貫性
  - 過去最高益（更新フラグ 等）
- **Value / バリュー指標**
  - PER（予想PER・実績PERなど、利用可能な指標に応じて）
  - PBR

※テクニカル指標（例：BB・RSI）は **補助（エントリー/タイミング調整）** として扱います。  
※将来予測値（予想PERなど）は **参考情報**として扱い、データ更新タイミング（ラグ）に注意します。

### 1.2 ベンチマーク
バックテストの評価は **TOPIX** をベンチマークとして比較します。  
TOPIXデータは J-Quants API を通じて取得し、`index_daily` テーブルに保存されます。  
（注：J-Quants APIでは日経平均指数が提供されないため、TOPIXを使用）

---

## 2. 運用スタイル（2つのモードを併存運用）

本プロジェクトでは、**長期保有型（NISA想定）**と**月次リバランス型**の2つの運用スタイルを併存して運用します。  
両者は異なる目的と評価方法を持ち、データベース上でも明確に区別されます。

### 2.1 長期保有型（NISA想定）積立・買い増し
- **目的**：**永続的競争優位性（ワイドモート）**が期待できる企業を、割安な局面で購入し、積立・長期保有を目指す
- **入替頻度**：低頻度（月次〜四半期の定期点検）
- **使い方**：
  - `monthly_run.py` でスクリーニング結果を取得
  - スクリーニング結果を「買い増し候補」「監視リスト」として活用
  - `holdings` テーブルで実際の保有銘柄を管理
  - `backtest.py` でパフォーマンス評価
- **データ保存先**：
  - `holdings`: 実際の保有銘柄
  - `backtest_performance`: パフォーマンス結果
  - `backtest_stock_performance`: 銘柄別パフォーマンス

### 2.2 月次リバランス型
- **目的**：スクリーニング上位銘柄を定期的に入替し、**時系列の超過リターン（vs TOPIX）**を狙う
- **入替頻度**：高頻度（月次で全入れ替え）
- **特徴**：検証のために、実運用の制約（現金余力）を反映した **open-close 方式**の売買定義を採用
- **データ保存先**：
  - `portfolio_monthly`: 月次ポートフォリオ（確定結果）
  - `monthly_rebalance_*`: 月次リバランス型専用テーブル（接頭辞付き）

#### データベーステーブルの命名規則

月次リバランス型のテーブルには `monthly_rebalance_` という接頭辞を付けます。  
これにより、長期保有型と月次リバランス型のデータを明確に区別できます。

**月次リバランス型専用テーブル**：
- `monthly_rebalance_final_selected_candidates`: 最終選定候補（基本情報とパラメータ）
- `monthly_rebalance_candidate_performance`: パフォーマンス指標
- `monthly_rebalance_candidate_monthly_returns`: 月次超過リターン時系列
- `monthly_rebalance_candidate_detailed_metrics`: 詳細パフォーマンス指標

**共通テーブル**（両方で使用）：
- `listed_info`: 銘柄属性
- `prices_daily`: 日足価格データ
- `fins_statements`: 財務データ
- `features_monthly`: 月次特徴量
- `index_daily`: 指数データ（TOPIX）

#### open-close方式（時系列バックテストの標準仕様）
- **意思決定**：リバランス日 `t` の時点で新ポートフォリオ（上位N銘柄）を確定
- **購入**：翌営業日 `t+1` の寄り（open）で新規購入（寄り成）
- **売却**：次リバランス日 `t_next` の引け（close）で全決済（引け成）
- **期間リターン**：`open(t+1) → close(t_next)`  
- **TOPIXも同じタイミング**（open / close）で統一

> 補足：現金余力が無い前提のため、毎月「全売却→全買付」になる実装（保守的なコスト仮定）です。  
> 将来的に「同一銘柄は持ち越す」運用に拡張する余地もあります。

> **詳細なシステム構成については `SYSTEM_SPECIFICATION.md` を参照してください。**

---

## 3. システム構成（概要）

- **データ**：J-Quants API  
- **DB**：SQLite（`C:\Users\takay\AppData\Local\omanta_3rd\db\jquants.sqlite`）
  - 長期保有型と月次リバランス型のデータを同じデータベースで管理
  - 月次リバランス型のテーブルには `monthly_rebalance_` 接頭辞を付与
- **思想**：
  - 過学習を避け、解釈可能性を重視
  - 「最適化結果（in-sample）＝性能」ではなく、OOS検証（holdout / WFA）で信頼性を評価

> **詳細なシステム構成、データフロー、実行コマンドについては `SYSTEM_SPECIFICATION.md` を参照してください。**

---

## 4. クイックスタート（例）

> 実行方法は環境・ファイル構成によって異なる場合があります。  
> まずは各スクリプトの `--help` を確認してください。

### 4.1 TOPIXデータ更新（例）
```bash
python update_all_data.py --target indices
```

---

## 5. バックテスト / 評価

本リポジトリには、互換性のための **旧方式（累積リターン系）** と、推奨の **時系列方式（open-close）** が共存します。

- 旧方式：特定リバランス日時点から「最終日まで」の累積を見る用途（標準的なSharpe/MaxDDの評価には不向き）
- 時系列方式（推奨）：月次の時系列リターン系列から、標準的指標を計算（Sharpe / Sortino / MaxDD 等）

---

## 6. 最適化（Optuna）

### 6.1 時系列版（推奨：open-close方式）
Optunaでハイパーパラメータ最適化を行います。  
目的関数は、まずは **Sharpe_excess（=IR）** を主軸にしています（勝率項などは状況に応じて調整）。

#### 基本的な実行例

**Step 1: 追加トライアル（10〜20）を回す（同一期間）**
```bash
# Windows PowerShell
$env:OMP_NUM_THREADS="1"
$env:MKL_NUM_THREADS="1"
$env:OPENBLAS_NUM_THREADS="1"
$env:NUMEXPR_NUM_THREADS="1"
python -m omanta_3rd.jobs.optimize_timeseries `
  --start 2021-01-01 `
  --end 2024-12-31 `
  --n-trials 20 `
  --study-name optimization_timeseries_20251230_phase1 `
  --parallel-mode trial `
  --n-jobs 4 `
  --bt-workers 1 `
  --no-progress-window
```

```bash
# Linux/Mac
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
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

#### 主なパラメータ

- `--parallel-mode`: 並列化モード（`trial`/`backtest`/`hybrid`、デフォルト: `trial`）
  - `trial`: Optuna trialを並列化（推奨）
  - `backtest`: trial内バックテストを並列化
  - `hybrid`: 二重並列（条件付き）
- `--n-jobs`: trial並列数（-1で自動、SQLite環境では2〜4を推奨）
- `--bt-workers`: trial内バックテストの並列数（デフォルト: 1）
- `--storage`: Optunaストレージ（Noneの場合はSQLite、例: `postgresql://...`）

#### 出力される情報

- **各trialのログ**: データ取得時間、保存時間、時系列計算時間、指標計算時間
- **サマリーレポート**: best/p95/medianのSharpe_excess分布、上位5 trialのパラメータ分布

> ⚠️ **注意事項**:
> - SQLite環境では `--n-jobs 2〜4` を推奨（多数並列書き込みはロック待ちが増える）
> - BLASスレッドは自動で1に設定されますが、手動で環境変数を設定することも可能
> - 詳細な実行例は `OPTIMIZATION_EXECUTION_EXAMPLES.md` を参照してください

---

## 7. 信頼性検証（過学習対策）

最適化は「当たりを引く」ことがあり得るため、以下の検証で **再現性** を確認します。

### 検証ステップ

**Step 1: 追加トライアル（10〜20）を回す（同一期間）**
- 目的: bestが再現するかを確認
- 見るべき指標:
  - best / p95 / median の Sharpe_excess
  - 上位5 trial のパラメータ分布（極端にブレるか）
  - missing_count が上位に偏ってないか（欠損が都合よく効いていないか）
- 合格ライン（目安）:
  - bestが0.44付近でも、p95が0.30前後、medianが0.10〜0.20なら「普通にあり得る上振れ」
  - bestだけ0.44で、他が0近辺なら「当たりの可能性が高い」

**Step 2: Holdout（1年）で"崩れ方"を見る**
- 推奨分割: Train: 2021-2023, Holdout: 2024
- 判定の勘所:
  - Holdout Sharpe_excess が Train の **50〜70%**残るならかなり良い
  - 0付近〜マイナスなら、過学習か、相場局面依存が強い

**Step 3: WFA / Robust（fold=3）へ**
- 最後にWFA/Robustで「時間方向の安定性」を確認

### 検証手法

- **Holdout**：訓練期間で最適化 → 別期間で固定パラメータ評価
- **Walk-Forward Analysis（WFA）**：複数foldで時系列安定性を評価
- **Robust Optimization**：fold平均＋安定性（分散）を考慮して最適化

詳細は `OPTIMIZATION_RESULT_INTERPRETATION.md` と `OPTIMIZATION_EXECUTION_EXAMPLES.md` を参照してください。

---

## 8. 注意事項（実運用で効く論点）

- データ遅延（決算反映、予想値更新）と情報利用可能性（ルックアヘッド）を常に意識する
- 流動性・スリッページ・売買コスト（特に小型株）を過小評価しない
- 企業イベント（分割、併合、上場廃止、TOB）対応は重要
- 税制（NISA/特定口座）・売買頻度の影響も運用選択（中長期 vs 月次）に影響する

---

## 9. 今後のロードマップ（例）

- 中長期積立（NISA想定）と月次リバランスの **比較検証**（同一スコアリングで運用ルールのみ変更）
- Holdout / WFA の自動レポート化
- データアクセスの高速化（メモリキャッシュ・DB最適化）
- ポジション引継ぎ（部分入替）版のバックテスト追加（必要なら）

---

## 付録：関連ドキュメント

### システム全体
- `SYSTEM_SPECIFICATION.md`：**システム仕様書**（構成、データフロー、実行コマンド、データベーススキーマ）

### 最適化・評価
- `OPTIMIZATION_SYSTEM_OVERVIEW.md`：最適化システム全体像
- `OPTIMIZATION_RESULT_INTERPRETATION.md`：最適化結果の解釈と次のステップ
- `OPTIMIZATION_EXECUTION_EXAMPLES.md`：最適化実行例（並列化・高速化対応版）
- `PERFORMANCE_CALCULATION_METHODS.md`：パフォーマンス計算方法の比較（旧方式 / 時系列方式）
- `TIMESERIES_REFINEMENT_PLAN.md`：時系列バックテストの設計・改善履歴
- `TRADING_COST_DOCUMENTATION.md`：取引コストの扱い

### 結果・分析
- `FINAL_SELECTED_CANDIDATES.md`：最終選定候補の情報

