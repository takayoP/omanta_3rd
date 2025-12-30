# Cursor貼り付け用プロンプト：時系列バックテスト（open-close）を実運用仕様で仕上げる

あなたは本リポジトリのAIペアプログラマです。既存ロジック（累積リターン版）は**保持**しつつ、時系列版（open-close方式）を**実運用に耐える**形に仕上げます。

## 0. 現状（前提）
- 既存版：`calculate_performance_metrics.py` / `src/omanta_3rd/backtest/performance.py` / `src/omanta_3rd/jobs/optimize.py` は保持。
- 時系列版：
  - `src/omanta_3rd/backtest/timeseries.py`（月次P/L算出）
  - `src/omanta_3rd/backtest/metrics.py`（標準指標）
  - `calculate_performance_metrics_timeseries.py`（時系列版メトリクス算出）
  - `src/omanta_3rd/jobs/optimize_timeseries.py`（時系列版最適化）
  - `sanity_check_timeseries.py`（サニティチェック）
- 売買仕様（**open-close方式**）：
  - 意思決定：リバランス日 t の引けで新ポートフォリオを確定（t までの情報のみ）
  - 売却：次のリバランス日 t_next の引け成（close）で全決済（現金化）
  - 購入：リバランス日 t の翌営業日 t+1 の寄り成（open）で新規購入
  - 期間リターン：`open(t+1)` → `close(t_next)`
  - TOPIXも同じタイミング（buy=open、sell=close）で取得

## 1. ゴール（今回の作業範囲）
1) **Phase 4（サニティチェック実行）を必ず先に通す**：
   - スクリプトを実行し、結果をMarkdownで保存（例：`reports/sanity_check_timeseries_YYYYMMDD.md`）
   - 異常があれば原因特定→修正→再実行

2) **Phase 2（取引コスト＆指標定義改善）を実装**：
   - ターンオーバー計算を追加
   - コストをターンオーバー連動（買い・売りを分けられる設計）
   - Sortino と Profit Factor を標準定義に修正

3) **Phase 3（目的関数の洗練）を実装**：
   - 目的関数は「超過リターン系列のIR（=Sharpe_excess）」を主軸に
   - 勝率は係数を弱める or 撤去（必要なら）

4) **ドキュメント整合性を修正**：
   - `TIMESERIES_REFINEMENT_PLAN.md` の「close-close」表記を「open-close」に修正
   - 同ファイルのサンプルコードの `purchase_price` の `use_open` 誤り（False→True）を修正
   - `PERFORMANCE_CALCULATION_METHODS.md` に open-close の期間定義を追記（`open(t+1) -> close(t_next)`）

## 2. 実装時の厳守事項（重要）
- **後方互換**：既存版のロジックや出力形式は壊さない。
- **価格取得**：原則 `date = ?` の完全一致。欠損時は「当月取引不可」としてログし、`drop_and_renormalize` でフルインベストを維持。
- **同一タイミング**：ポートフォリオとTOPIXは必ず同じ buy/sell タイミング。
- **ログ**：
  - 欠損銘柄（code, date, open/close）
  - 期間ごとの投資可能銘柄数
  - ターンオーバー（executed / paper）
  - コスト控除額
  をJSON/辞書で保持し、必要に応じてレポートに出す。

## 3. ターンオーバーとコストモデル（提案仕様）
今回の運用は「毎回いったん全売却→翌日寄りで買付」なので、**実売買ベースのターンオーバー**を次のように定義してください。

- `executed_sell_notional = 1.0`（毎回100%売る）
- `executed_buy_notional = 1.0`（毎回100%買う）
- `executed_turnover = executed_sell_notional + executed_buy_notional = 2.0`

コスト（bps）を buy/sell で分け、期間リターンから控除：
- `cost_frac = executed_buy_notional * buy_cost_bps/10000 + executed_sell_notional * sell_cost_bps/10000`
- `r_net = r_gross - cost_frac`

加えて、将来の「現金余力がある」運用に備え、**参考値として paper turnover** も出しておく：
- `paper_turnover = 0.5 * sum(|w_target - w_prev_drift|)`（簡易で良い：等金額なら銘柄入替割合でも可）

## 4. 指標定義（修正仕様）
- Sortino：
  - `downside = np.minimum(0, excess_returns - target)` を全期間に適用
  - `downside_dev = sqrt(mean(downside^2))`
- Profit Factor：
  - `pnl_t = equity_{t-1} * r_t`（通貨建て損益）
  - `PF = sum(pnl_pos) / abs(sum(pnl_neg))`（損失ゼロなら `np.inf` ではなく `None`/`nan` か上限クリップで扱いを統一）

## 5. サニティチェック（合格条件の例）
サニティチェックの実行結果Markdownに、以下を必ず出力：
- TOPIXの期間リターンの summary（count/mean/std/min/p1/median/p99/max）
- 個別銘柄の期間リターンの外れ値件数（例：>+200% or <-80% など）と上位10件
- 欠損銘柄件数（期間別、銘柄別）
- equity curve の min/max、MaxDD
- Sharpe_excess / Sortino_excess が極端値（例：|Sharpe|>10 など）を超えた場合の警告

## 6. 目的関数（optimize_timeseries.py）
まずはシンプルに：
- `objective = sharpe_excess`（年率化済み）
必要なら微調整：
- `objective = sharpe_excess + 0.1*mean_excess - 0.05*turnover_penalty - 0.1*missing_penalty`
※係数はログを見て調整。勝率項は入れる場合でも小さく。

## 7. 期待するアウトプット
- コード変更（timeseries.py / metrics.py / optimize_timeseries.py / sanity_check_timeseries.py など）
- ドキュメント修正（TIMESERIES_REFINEMENT_PLAN.md / PERFORMANCE_CALCULATION_METHODS.md）
- `reports/sanity_check_timeseries_YYYYMMDD.md`（実行結果）
- `pytest`（または既存テストコマンド）と lint を通し、エラー0

## 8. 作業手順（推奨）
1) ドキュメントの表記矛盾を修正（open-closeの統一）
2) `sanity_check_timeseries.py` を実行してレポート出力（現状のまま）
3) Phase 2 を実装 → 再度サニティチェック
4) Phase 3 を実装（目的関数）→ 少数trialで動作確認
5) 既存版との比較（方向感が破綻していないこと）

---

# 補足：ドキュメント修正メモ（差分の要点）
- `TIMESERIES_REFINEMENT_PLAN.md`
  - Phase 1 の「close-close」→「open-close」
  - 3.3 の `purchase_price = _get_price(... use_open=False)` → `use_open=True`
- `PERFORMANCE_CALCULATION_METHODS.md`
  - 時系列版の期間定義を `open(t+1) -> close(t_next)` に更新（TOPIXも同じ）
