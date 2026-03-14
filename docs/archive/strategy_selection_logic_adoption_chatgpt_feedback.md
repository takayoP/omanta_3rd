# ポートフォリオ選定ロジックの変更：ChatGPTフィードバックと対応方針

## ChatGPTからのフィードバック要約

### 良い点（変更の方向性は妥当）

1. **「重みは等ウェイトを維持」しつつ、旧ロジックの選定部分を使う方針は一貫している**
2. **`_select_portfolio_with_params` の weight 計算を等ウェイトに変えたのは筋が良い**
3. **optimize側の呼び出しを `_select_portfolio_with_params` に寄せている**

### 重要な注意点

#### 注意点A：因果関係の説明が弱い

- 「13.49%→等ウェイトにすると-2.54%なので、選定ロジックが優れていた」という説明は論理的に弱い
- -2.54%になったのは「旧best paramsが比例ウェイト向けに最適化されていた」ことの証拠にはなるが、「選定ロジックが優れている」とは言えない（重みの付け方の効果の可能性も大きい）
- **修正**: 「優れている前提」ではなく「優れているか検証するため」という書き方に変更

#### 注意点B：本番運用との不一致リスク（最重要）

**現状**:
- 本番運用：`select_portfolio（longterm_run.py）` を引き続き使用
- 最適化ルート：`_select_portfolio_with_params（等ウェイト版）` を使用

**問題**: 最適化している戦略と、実際に運用する戦略が違う状態。この状態で再最適化しても、最終的に本番に載せた瞬間に「思ったのと違う」が再発する。

**解決策（どちらかは必須）**:
1. **本番も同じロジック（等ウェイト版 `_select_portfolio_with_params` 相当）に統一する**（推奨）
2. **最適化/比較を本番ロジック（`select_portfolio`）に戻す**（＝今回の採用をやめる）

#### 注意点C：compare側のロジック確認が必要

- 資料の末尾で「比較ルートも同じ選定ロジックを使う」とあるが、変更ファイル一覧に `compare_lambda_penalties.py` 等が含まれていない
- **確認必要**: コード上で本当に compare 側が `_select_portfolio_with_params` を通っているかをログで確認

#### 注意点D：スコア再計算の二重定義リスク

- `_select_portfolio_with_params` は `value_score/size_score/quality_score/growth_score/...` と `core_score` を内部で作る
- `build_features` でも `core_score` / `entry_score` を作っている
- **問題**: 「どっちのcore_scoreが真なのか」「同じ名前の列を上書きしていないか」が混乱ポイント

**解決策**:
- `_select_portfolio_with_params` で計算するなら **列名を変える（例：`core_score_v2`）**か、
- **共通の `compute_scores()` を1箇所に切り出して、build_featuresもselect側もそれを使う**

## まずやるべき確認

### 確認1：optimize と compare で同一日付のポートが一致するか

- paramsファイル固定
- rebalance_date固定（例：2021-01-29でも2023-01-31でもOK）
- `selected_codes / weights / portfolio_hash` が optimize と compare で完全一致

**これが一致しないなら**: 「compare側が別ロジック」または「呼び出し経路が違う」が残っている

### 確認2：本番（batch_longterm_run 等）とも一致するか

- 本番実行の同一条件で `portfolio_hash` を出す
- optimize/compare と一致する

**一致しないなら**: 再び "最適化した戦略を運用していない" になる

## ChatGPTの提案（採用を成功させる一番安全な形）

最終形として推奨される設計：

* `select_portfolio()` を **1個に統合**（本番も最適化も比較も同じ関数）
* その中で
  * `score_engine="v1|v2"`（旧/新の選定ロジック）
  * `weight_method="equal|score"`（ただし運用はequal固定）
  を選べるようにする

**メリット**:
- v2（旧ロジック由来）が本当に良いかA/B比較できる
- 本番・比較・最適化の不一致が起きない

## 現在の実装状況の確認

### compare_lambda_penalties.py の確認

**確認必要**: `compare_lambda_penalties.py` が `_select_portfolio_with_params` を使用しているか、それとも `select_portfolio`（`longterm_run.py`）を使用しているか

### batch_longterm_run.py の確認

**確認必要**: 本番運用（`batch_longterm_run.py`）が `select_portfolio`（`longterm_run.py`）を使用しているか、それとも `_select_portfolio_with_params` を使用しているか

## 次のステップ

1. **確認スクリプトの作成**: optimize/compare/本番で同一条件の `portfolio_hash` を比較するスクリプトを作成
2. **実装状況の確認**: `compare_lambda_penalties.py` と `batch_longterm_run.py` の実装を確認
3. **統一方針の決定**: 
   - 本番も `_select_portfolio_with_params`（等ウェイト版）に統一するか
   - または、最適化/比較を本番ロジック（`select_portfolio`）に戻すか
4. **スコア計算の統一**: `core_score` の二重定義を解消（共通関数化または列名変更）

## 確認スクリプトの要件

以下の情報を出力するスクリプトが必要：

1. **optimize の結果**:
   - `selected_codes`
   - `weights`
   - `portfolio_hash`
   - 使用した関数名（`_select_portfolio_with_params` または `select_portfolio`）

2. **compare の結果**:
   - `selected_codes`
   - `weights`
   - `portfolio_hash`
   - 使用した関数名（`_select_portfolio_with_params` または `select_portfolio`）

3. **本番（batch_longterm_run）の結果**:
   - `selected_codes`
   - `weights`
   - `portfolio_hash`
   - 使用した関数名（`_select_portfolio_with_params` または `select_portfolio`）

4. **比較結果**:
   - optimize vs compare: 一致/不一致
   - optimize vs 本番: 一致/不一致
   - compare vs 本番: 一致/不一致

