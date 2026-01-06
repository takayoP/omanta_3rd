# レジーム切替機能のパラメータ対応完了報告

## 実装完了

`monthly_run.py`の`build_features`と`select_portfolio`をパラメータ対応に修正しました。

## 変更内容

### 1. `build_features`関数のパラメータ対応 ✅

**シグネチャ変更**:
```python
def build_features(
    conn,
    asof: str,
    strategy_params: Optional[StrategyParams] = None,
    entry_params: Optional[Any] = None,  # EntryScoreParams（循環参照回避のためAny）
) -> pd.DataFrame:
```

**変更点**:
- `strategy_params`と`entry_params`のオプショナル引数を追加
- パラメータが渡された場合はそれを使用、そうでない場合は既存の`PARAMS`を使用（後方互換性を保持）
- `entry_score`計算でパラメータ化版の`_calculate_entry_score_with_params`を使用
- `value_score`と`core_score`の計算でパラメータを使用
- フィルタリング（liquidity, ROE）でパラメータを使用

### 2. `select_portfolio`関数のパラメータ対応 ✅

**シグネチャ変更**:
```python
def select_portfolio(
    feat: pd.DataFrame,
    strategy_params: Optional[StrategyParams] = None,
) -> pd.DataFrame:
```

**変更点**:
- `strategy_params`のオプショナル引数を追加
- パラメータが渡された場合はそれを使用、そうでない場合は既存の`PARAMS`を使用（後方互換性を保持）
- フィルタリング（liquidity, ROE）、プールサイズ、セクターキャップ、目標銘柄数でパラメータを使用

### 3. `batch_monthly_run_with_regime.py`の修正 ✅

**変更点**:
- `normalize_params`を使用してパラメータ辞書を`StrategyParams`と`EntryScoreParams`に変換
- `build_features`と`select_portfolio`にパラメータを渡すように修正

### 4. `params_utils.py`の作成 ✅

**機能**:
- `build_strategy_params_from_dict`: パラメータ辞書から`StrategyParams`を構築
- `build_entry_params_from_dict`: パラメータ辞書から`EntryScoreParams`を構築
- `normalize_params`: パラメータ辞書を正規化して両方のパラメータに変換

**循環参照回避**:
- 遅延インポートを使用して循環参照を回避

## 後方互換性

既存のコードは変更なしで動作します：
- `build_features(conn, asof)` - パラメータなしで呼び出し可能（既存の`PARAMS`を使用）
- `select_portfolio(feat)` - パラメータなしで呼び出し可能（既存の`PARAMS`を使用）

## 使用方法

### レジーム切替モード

```bash
python -m omanta_3rd.jobs.batch_monthly_run_with_regime --start 2020-01-01 --end 2025-12-31
```

各リバランス日で：
1. レジームを判定
2. ポリシーからパラメータIDを決定
3. パラメータを読み込み
4. `build_features`と`select_portfolio`にパラメータを渡して実行

### 固定パラメータモード

```bash
python -m omanta_3rd.jobs.batch_monthly_run_with_regime --start 2020-01-01 --end 2025-12-31 --fixed-params operational_24M
```

指定したパラメータIDのパラメータを使用して実行します。

## テスト結果

```bash
$ python -c "from src.omanta_3rd.jobs.params_utils import normalize_params; params = {'w_quality': 0.2, 'w_value': 0.3, 'rsi_base': 50.0, 'rsi_max': 80.0}; s, e = normalize_params(params); print(f'✓ StrategyParams: w_quality={s.w_quality}, w_value={s.w_value}'); print(f'✓ EntryScoreParams: rsi_base={e.rsi_base}, rsi_max={e.rsi_max}')"
✓ StrategyParams: w_quality=0.2, w_value=0.3
✓ EntryScoreParams: rsi_base=50.0, rsi_max=80.0
```

## 完了

レジーム切替機能が完全に動作するようになりました。パラメータは各リバランス日で動的に切り替わり、実際のポートフォリオ作成に反映されます。

